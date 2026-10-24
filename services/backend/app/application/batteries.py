"""F3 profile/lifecycle management. Device ingestion belongs to the next phase."""
from uuid import uuid4

from sqlalchemy import and_, insert, or_, select, update
from app.application import assets
from app.application.identity import DomainError, utcnow


def station_for(session, db, pin):
    if pin['compartment_id']:
        return assets.get_row(session, db, 'compartments', pin['compartment_id'])['station_id']
    return None


def scope(session, db, actor, pin):
    if actor['role'] == 'ADMIN':
        return
    station_id = station_for(session, db, pin)
    if station_id is None:
        raise DomainError(403, 'STATION_FORBIDDEN')
    assets.scope(session, db, actor, station_id)


def active(session, db, pin):
    swaps = db.table('swap_transactions')
    return session.execute(select(swaps.c.id).where(swaps.c.state.not_in(assets.CLOSED_SWAPS),
        or_(swaps.c.old_battery_id == pin['id'], swaps.c.new_battery_id == pin['id'],
            and_(swaps.c.customer_id == pin['holder_user_id'], pin['holder_user_id'] is not None)))).first() is not None


def create(session, db, actor, body, policy):
    if body.family != policy['battery_family']:
        raise DomainError(422, 'BATTERY_FAMILY_INVALID')
    valid = ((body.location_kind == 'COMPARTMENT' and body.compartment_id is not None and body.holder_user_id is None)
        or (body.location_kind == 'CUSTOMER' and body.holder_user_id is not None and body.compartment_id is None)
        or (body.location_kind == 'UNKNOWN' and body.compartment_id is None and body.holder_user_id is None))
    if not valid:
        raise DomainError(422, 'BATTERY_LOCATION_INVALID')
    pins = db.table('batteries')
    if body.holder_user_id:
        user = assets.get_row(session, db, 'users', body.holder_user_id, lock=True)
        if user['role'] != 'CUSTOMER':
            raise DomainError(422, 'BATTERY_HOLDER_INVALID')
        if session.execute(select(pins.c.id).where(pins.c.holder_user_id == body.holder_user_id)).first():
            raise DomainError(409, 'RESOURCE_CONFLICT')
    if body.compartment_id:
        slot = assets.get_row(session, db, 'compartments', body.compartment_id)
        assets.station_lock(session, db, slot['station_id'])
        slot = assets.get_row(session, db, 'compartments', slot['id'], lock=True)
        if (slot['service_state'] == 'RETIRED' or slot['observed_present'] is True or slot['observed_serial'] is not None
            or assets.pin_at(session, db, slot)):
            raise DomainError(409, 'COMPARTMENT_NOT_EMPTY')
        if assets.held(session, db, slot['id']) or assets.active_swaps(session, db, slot['station_id'], slot['id']):
            raise DomainError(409, 'ACTIVE_TRANSACTION')
    result = session.execute(insert(pins).values(id=uuid4(), **body.model_dump()).returning(pins)).mappings().one()
    assets.asset_audit(session, db, actor, 'battery', 'CREATE_BATTERY', result['id'], after=dict(result))
    return dict(result)


def change(session, db, actor, identity, body, policy):
    initial = assets.get_row(session, db, 'batteries', identity)
    scope(session, db, actor, initial)
    if (actor['role'] == 'ADMIN') != (body.action == 'RETIRE'):
        raise DomainError(403, 'FORBIDDEN')
    if body.resolve_alert_ids and body.action != 'RESTORE':
        raise DomainError(422, 'INVALID_ACTION')
    if len(body.resolve_alert_ids) != len(set(body.resolve_alert_ids)):
        raise DomainError(422, 'INVALID_ALERTS')
    station_id = station_for(session, db, initial)
    slot = None
    if station_id:
        station = assets.station_lock(session, db, station_id)
        slot = assets.get_row(session, db, 'compartments', initial['compartment_id'], lock=True)
    pin = assets.get_row(session, db, 'batteries', identity, lock=True)
    assets.version(pin, body.expected_version)
    if pin['compartment_id'] != initial['compartment_id'] or pin['holder_user_id'] != initial['holder_user_id']:
        raise DomainError(409, 'VERSION_CONFLICT')
    transitions = {'ACTIVATE': {'REGISTERED'}, 'QUARANTINE': {'REGISTERED', 'IN_SERVICE'},
                  'RESTORE': {'QUARANTINED'}, 'RETIRE': {'REGISTERED', 'IN_SERVICE', 'QUARANTINED'}}
    if pin['lifecycle'] not in transitions[body.action]:
        raise DomainError(409, 'STATE_CONFLICT')
    # No action may release or bypass a resource held by a running/uncertain transaction.
    if active(session, db, pin) or assets.held(session, db, battery_id=identity) or (slot and assets.held(session, db, slot['id'])):
        raise DomainError(409, 'ACTIVE_TRANSACTION')
    if body.action == 'RETIRE' and pin['holder_user_id']:
        raise DomainError(409, 'BATTERY_CUSTOMER_HELD')
    now = utcnow()
    if body.action in ('ACTIVATE', 'RESTORE'):
        if not slot or station['state'] != 'ACTIVE' or slot['service_state'] == 'RETIRED':
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        device = assets.available_device(session, db, station_id)
        evidence = assets.snapshot(session, db, device, now, body.evidence_event_id) if body.evidence_event_id else None
        commands = db.table('device_commands')
        pending = session.execute(select(commands.c.id).where(commands.c.compartment_id == slot['id'],
            commands.c.state.in_(['QUEUED', 'DISPATCHED', 'ACKNOWLEDGED', 'UNKNOWN']))).first()
        if (not evidence or not assets.online(session, db, device, now, policy) or pending
            or not assets.fresh(evidence['received_at'], now, policy) or not assets.fresh(slot['observed_at'], now, policy)
            or evidence['received_at'] < slot['observed_at'] or slot['door_state'] != 'CLOSED'
            or slot['observed_present'] is not True or slot['observed_serial'] != pin['serial']
            or not assets.quality(session, db, pin, device, now, policy, issue=False, require_service=False)):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        snapshots = [s for s in evidence['payload'].get('slots', []) if s.get('compartment_id') == str(slot['id'])]
        if len(snapshots) != 1 or any(snapshots[0].get(k) != v for k, v in
            [('door_state', 'CLOSED'), ('present', True), ('observed_serial', pin['serial'])]):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        alerts = db.table('alerts')
        # Lock every relevant alert; ACK remains blocking. RESTORE can resolve this set atomically.
        relevant = session.execute(select(alerts).where(alerts.c.station_id == station_id,
            or_(alerts.c.battery_id == identity, alerts.c.compartment_id == slot['id'],
                and_(alerts.c.battery_id.is_(None), alerts.c.compartment_id.is_(None))))
            .order_by(alerts.c.id).with_for_update()).mappings().all()
        requested = set(body.resolve_alert_ids)
        # Only pin-specific alerts can be resolved by a pin restoration. Station/slot-wide faults stay blocking.
        resolvable = {a['id'] for a in relevant if a['battery_id'] == identity and a['compartment_id'] in (None, slot['id']) and a['state'] != 'RESOLVED'}
        if not requested.issubset(resolvable):
            raise DomainError(422, 'INVALID_ALERTS')
        if any(a['state'] != 'RESOLVED' and a['id'] not in requested for a in relevant):
            raise DomainError(422, 'UNRESOLVED_ALERTS')
        for alert in relevant:
            if alert['id'] in requested:
                after = session.execute(update(alerts).where(alerts.c.id == alert['id']).values(state='RESOLVED',
                    resolved_by=actor['id'], resolution_note=body.reason, last_event_id=evidence['id'],
                    version=alert['version'] + 1).returning(alerts)).mappings().one()
                assets.asset_audit(session, db, actor, 'alert', 'BATTERY_RESTORE_RESOLVE', alert['id'], dict(alert), dict(after))
    state = {'ACTIVATE': 'IN_SERVICE', 'QUARANTINE': 'QUARANTINED', 'RESTORE': 'IN_SERVICE', 'RETIRE': 'RETIRED'}[body.action]
    pins = db.table('batteries')
    result = session.execute(update(pins).where(pins.c.id == identity).values(lifecycle=state,
        version=pin['version'] + 1).returning(pins)).mappings().one()
    assets.asset_audit(session, db, actor, 'battery', body.action, identity, dict(pin),
        {**dict(result), 'reason': body.reason, 'evidence_event_id': str(body.evidence_event_id) if body.evidence_event_id else None})
    return dict(result)
