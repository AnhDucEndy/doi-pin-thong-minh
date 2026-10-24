"""F2 management and read-only BR02 availability; no telemetry ingestion or swaps."""
from datetime import timedelta
import base64
import hashlib
import hmac
import os
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from app.application.identity import DomainError, audit, utcnow
from app.config import ConfigNotReady
from app.infrastructure.db import advisory_lock

CLOSED_SWAPS = ['COMPLETED', 'CANCELLED', 'CLOSED_COMPENSATED']


def public_device(row):
    return {key: value for key, value in row.items() if key != 'key_hash'}


def get_row(session, db, name, identity, lock=False):
    table = db.table(name)
    query = select(table).where(table.c.id == identity)
    row = session.execute(query.with_for_update() if lock else query).mappings().first()
    if not row:
        raise DomainError(404, 'RESOURCE_NOT_FOUND')
    return row


def version(row, expected):
    if row['version'] != expected:
        raise DomainError(409, 'VERSION_CONFLICT')


def scope(session, db, user, station_id):
    if user['role'] == 'ADMIN':
        return
    assignments = db.table('user_station_assignments')
    if user['role'] != 'TECHNICIAN' or not session.execute(select(assignments.c.user_id).where(
            assignments.c.user_id == user['id'], assignments.c.station_id == station_id)).first():
        raise DomainError(403, 'STATION_FORBIDDEN')


def active_swaps(session, db, station_id, compartment_id=None):
    table = db.table('swap_transactions')
    query = select(table).where(table.c.station_id == station_id, table.c.state.not_in(CLOSED_SWAPS))
    if compartment_id:
        query = query.where(or_(table.c.return_compartment_id == compartment_id, table.c.supply_compartment_id == compartment_id))
    return session.execute(query).mappings().all()


def held(session, db, compartment_id=None, battery_id=None):
    table = db.table('resource_reservations')
    match = []
    if compartment_id:
        match.append(table.c.compartment_id == compartment_id)
    if battery_id:
        match.append(table.c.battery_id == battery_id)
    return bool(session.execute(select(table.c.id).where(table.c.released_at.is_(None), or_(*match))).first())


def station_lock(session, db, station_id):
    advisory_lock(session, 'assets:station:' + str(station_id))
    return get_row(session, db, 'stations', station_id, lock=True)


def available_device(session, db, station_id):
    table = db.table('devices')
    return session.execute(select(table).where(table.c.station_id == station_id)).mappings().first()


def fresh(value, now, policy):
    return value is not None and now - timedelta(seconds=policy['telemetry_stale_seconds']) <= value <= now


def snapshot(session, db, device, now, evidence_id=None):
    if not device or not device['boot_id']:
        return None
    events = db.table('device_events')
    query = select(events).where(events.c.device_id == device['id'], events.c.boot_id == device['boot_id'],
        events.c.kind == 'SNAPSHOT', events.c.accepted.is_(True), events.c.processed_at.is_not(None), events.c.received_at <= now)
    if evidence_id:
        query = query.where(events.c.id == evidence_id)
    return session.execute(query.order_by(events.c.received_at.desc(), events.c.seq.desc()).limit(1)).mappings().first()


def online(session, db, device, now, policy):
    return bool(device and device['enabled'] and fresh(device['last_received_at'], now, policy)
                and snapshot(session, db, device, now))


def has_alert(session, db, station_id, compartment_id, battery_id=None):
    alerts = db.table('alerts')
    relevant = [alerts.c.compartment_id == compartment_id,
                and_(alerts.c.compartment_id.is_(None), alerts.c.battery_id.is_(None))]
    if battery_id:
        relevant.append(alerts.c.battery_id == battery_id)
    return bool(session.execute(select(alerts.c.id).where(alerts.c.station_id == station_id,
                alerts.c.state != 'RESOLVED', or_(*relevant))).first())


def pin_at(session, db, slot):
    pins = db.table('batteries')
    return session.execute(select(pins).where(pins.c.compartment_id == slot['id'])).mappings().first()


def quality(session, db, pin, device, now, policy, issue=True):
    if not pin or pin['lifecycle'] != 'IN_SERVICE' or pin['family'] != policy['battery_family']:
        return False
    readings, events = db.table('battery_telemetry'), db.table('device_events')
    # Select newest first, then validate: never fall back to an older good sample.
    reading = session.execute(select(readings).where(readings.c.battery_id == pin['id'])
                              .order_by(readings.c.received_at.desc(), readings.c.id.desc()).limit(1)).mappings().first()
    if not reading or not reading['quality_ok'] or reading['fault_codes'] or any(reading[k] is None for k in ('soc', 'soh', 'temperature_c')):
        return False
    if any(not reading[k].is_finite() for k in ('soc', 'soh', 'temperature_c')):
        return False
    event = session.execute(select(events).where(events.c.id == reading['event_id'])).mappings().first()
    if not (event and event['accepted'] and event['processed_at'] and event['kind'] == 'TELEMETRY'
            and event['device_id'] == device['id'] and event['boot_id'] == device['boot_id']
            and event['compartment_id'] == pin['compartment_id']
            and fresh(reading['received_at'], now, policy) and fresh(reading['measured_at'], now, policy)):
        return False
    if reading['temperature_c'] > policy['temperature_max_c']:
        return False
    return not issue or (reading['soc'] >= policy['soc_min_pct'] and reading['soh'] >= policy['soh_min_pct'])


def availability(session, db, station, policy, now):
    state = station['state']
    device = available_device(session, db, station['id'])
    operating = state if state != 'ACTIVE' else ('ONLINE' if online(session, db, device, now, policy) else 'OFFLINE')
    count = 0
    if operating == 'ONLINE':
        slots = db.table('compartments')
        rows = session.execute(select(slots).where(slots.c.station_id == station['id'],
            slots.c.service_state == 'ACTIVE', slots.c.door_state == 'CLOSED', slots.c.observed_present.is_(True))).mappings().all()
        active = active_swaps(session, db, station['id'])
        for slot in rows:
            pin = pin_at(session, db, slot)
            if (not pin or pin['location_kind'] != 'COMPARTMENT' or pin['holder_user_id'] is not None
                or pin['serial'] != slot['observed_serial'] or not fresh(slot['observed_at'], now, policy)
                or held(session, db, slot['id'], pin['id'])
                or any(s['new_battery_id'] == pin['id'] or slot['id'] in (s['return_compartment_id'], s['supply_compartment_id']) for s in active)
                or has_alert(session, db, station['id'], slot['id'], pin['id'])
                or not quality(session, db, pin, device, now, policy)):
                continue
            count += 1
    return {'station_id': station['id'], 'name': station['name'], 'address': station['address'],
            'operational_state': operating, 'available_count': count, 'as_of': now}


def asset_audit(session, db, actor, kind, action, identity, before=None, after=None):
    audit(session, db, actor['id'], action, identity, before, after, aggregate_type=kind)


def update_station(session, db, actor, identity, body):
    row = station_lock(session, db, identity)
    version(row, body.expected_version)
    changes = body.model_dump(exclude={'expected_version'}, exclude_unset=True)
    if not changes or any(v is None for v in changes.values()):
        raise DomainError(422, 'INVALID_ACTION')
    slots = db.table('compartments')
    # Lock every slot in UUID order before checking reservations; future reserve must recheck under these same locks.
    ids = list(session.scalars(select(slots.c.id).where(slots.c.station_id == identity).order_by(slots.c.id).with_for_update()))
    pins = db.table('batteries')
    pin_ids = list(session.scalars(select(pins.c.id).where(pins.c.compartment_id.in_(ids))))
    if changes.get('state', row['state']) != 'ACTIVE' and (active_swaps(session, db, identity)
            or any(held(session, db, slot) for slot in ids)
            or any(held(session, db, battery_id=pin) for pin in pin_ids)):
        raise DomainError(409, 'ACTIVE_TRANSACTION')
    table = db.table('stations')
    result = session.execute(update(table).where(table.c.id == identity).values(**changes, version=row['version'] + 1).returning(table)).mappings().one()
    asset_audit(session, db, actor, 'station', 'UPDATE_STATION', identity, dict(row), dict(result))
    return dict(result)


def device_key(actor_id, idempotency_key):
    secret = os.getenv('DEVICE_KEY_DERIVATION_SECRET', '')
    if len(secret) < 32 or secret.startswith('REPLACE_'):
        raise ConfigNotReady('CONFIG_NOT_READY')
    # Deterministic secret delivery on retry, without storing plaintext in response cache/audit.
    key = hmac.new(secret.encode(), f'createDevice:{actor_id}:{idempotency_key}'.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(key).decode().rstrip('=')


def disable_device(session, db, actor, identity, body):
    initial = get_row(session, db, 'devices', identity)
    station_lock(session, db, initial['station_id'])
    active = active_swaps(session, db, initial['station_id']) if not body.enabled else []
    users, swaps = db.table('users'), db.table('swap_transactions')
    for user in sorted({s['customer_id'] for s in active}):
        session.execute(select(users.c.id).where(users.c.id == user).with_for_update())
    locked = []
    for swap in sorted(active, key=lambda s: s['id']):
        current = session.execute(select(swaps).where(swaps.c.id == swap['id']).with_for_update()).mappings().one()
        if current['state'] not in CLOSED_SWAPS:
            if any(current[k] is None for k in ('old_battery_id', 'new_battery_id', 'return_compartment_id', 'supply_compartment_id', 'amount_minor')):
                raise DomainError(409, 'ACTIVE_TRANSACTION', 'An unreserved verification must be settled before disabling this device')
            locked.append(current)
    row = get_row(session, db, 'devices', identity, lock=True)
    version(row, body.expected_version)
    for swap in locked:
        # Guard the forward transition; COMPENSATING already awaits settlement and must not regress.
        if swap['state'] != 'COMPENSATING':
            session.execute(update(swaps).where(swaps.c.id == swap['id']).values(
                state='REVIEW_REQUIRED', review_reason='DEVICE_DISABLED', version=swap['version'] + 1))
    table = db.table('devices')
    result = session.execute(update(table).where(table.c.id == identity).values(enabled=body.enabled,
                                version=row['version'] + 1).returning(table)).mappings().one()
    asset_audit(session, db, actor, 'device', 'UPDATE_DEVICE', identity, public_device(row), public_device(result))
    for swap in locked:
        asset_audit(session, db, actor, 'swap', 'DEVICE_DISABLED_REVIEW', swap['id'],
                    {'state': swap['state']}, {'state': 'COMPENSATING' if swap['state'] == 'COMPENSATING' else 'REVIEW_REQUIRED'})
    return public_device(result)


def change_compartment(session, db, actor, identity, body, policy):
    initial = get_row(session, db, 'compartments', identity)
    scope(session, db, actor, initial['station_id'])
    if body.action == 'RETIRE' and actor['role'] != 'ADMIN':
        raise DomainError(403, 'FORBIDDEN')
    station = station_lock(session, db, initial['station_id'])
    slot = get_row(session, db, 'compartments', identity, lock=True)
    version(slot, body.expected_version)
    if active_swaps(session, db, slot['station_id'], identity) or held(session, db, identity):
        raise DomainError(409, 'ACTIVE_TRANSACTION')
    allowed = {'SET_MAINTENANCE': {'ACTIVE', 'BLOCKED'}, 'RESTORE': {'BLOCKED', 'MAINTENANCE'}, 'RETIRE': {'MAINTENANCE'}}
    if slot['service_state'] not in allowed[body.action]:
        raise DomainError(409, 'STATE_CONFLICT')
    now = utcnow()
    pin = pin_at(session, db, slot)
    if pin and held(session, db, battery_id=pin['id']):
        raise DomainError(409, 'ACTIVE_TRANSACTION')
    if body.action == 'RETIRE':
        if pin or slot['observed_present'] is not False or slot['observed_serial'] is not None or not fresh(slot['observed_at'], now, policy):
            raise DomainError(422, 'COMPARTMENT_NOT_EMPTY')
    if body.action == 'RESTORE':
        device = available_device(session, db, slot['station_id'])
        evidence = snapshot(session, db, device, now, body.evidence_event_id) if body.evidence_event_id else None
        commands = db.table('device_commands')
        pending = session.execute(select(commands.c.id).where(commands.c.compartment_id == identity,
                    commands.c.state.in_(['QUEUED', 'DISPATCHED', 'ACKNOWLEDGED', 'UNKNOWN']))).first()
        if (station['state'] != 'ACTIVE' or not online(session, db, device, now, policy) or not evidence
            or not fresh(evidence['received_at'], now, policy) or not fresh(slot['observed_at'], now, policy)
            or evidence['received_at'] < slot['observed_at'] or slot['door_state'] != 'CLOSED'
            or slot['observed_present'] is None or pending or has_alert(session, db, slot['station_id'], identity, pin['id'] if pin else None)):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        observed = [s for s in evidence['payload'].get('slots', []) if s.get('compartment_id') == str(identity)]
        if len(observed) != 1 or any(observed[0].get(k) != slot[v] for k, v in (
            ('door_state', 'door_state'), ('present', 'observed_present'), ('observed_serial', 'observed_serial'))):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        if slot['observed_present']:
            if (not pin or pin['serial'] != slot['observed_serial'] or pin['location_kind'] != 'COMPARTMENT'
                or not quality(session, db, pin, device, now, policy, issue=False)):
                raise DomainError(422, 'PIN_NOT_VERIFIED')
        elif pin or slot['observed_serial'] is not None:
            raise DomainError(422, 'PIN_NOT_VERIFIED')
    state = {'SET_MAINTENANCE': 'MAINTENANCE', 'RESTORE': 'ACTIVE', 'RETIRE': 'RETIRED'}[body.action]
    table = db.table('compartments')
    result = session.execute(update(table).where(table.c.id == identity).values(service_state=state,
                                version=slot['version'] + 1).returning(table)).mappings().one()
    asset_audit(session, db, actor, 'compartment', body.action, identity, dict(slot),
                {**dict(result), 'reason': body.reason, 'evidence_event_id': str(body.evidence_event_id) if body.evidence_event_id else None})
    return dict(result)
