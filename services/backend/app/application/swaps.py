"""AD-02b: durable orchestration from accepted evidence, never from ACK.

The device worker calls this under the same station/user/resource locks as
telemetry, reservation and settlement. No external I/O occurs in this module.
"""
from datetime import timedelta
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.application import assets, device, payments
from app.application.identity import DomainError, utcnow


def transition(session, db, swap, state, **values):
    table = db.table('swap_transactions')
    result = session.execute(update(table).where(table.c.id == swap['id']).values(
        state=state, version=swap['version'] + 1, **values).returning(table)).mappings().one()
    session.execute(insert(db.table('audit_events')).values(id=uuid4(), actor_type='SYSTEM',
        actor_id='device-worker', aggregate_type='swap', aggregate_id=swap['id'],
        action='SWAP_' + state, before_data={'state': swap['state']},
        after_data=jsonable_encoder(dict(result)), correlation_id=swap['id']))
    return result


def review(session, db, swap, reason):
    cases = db.table('recovery_cases')
    session.execute(pg_insert(cases).values(id=uuid4(), swap_id=swap['id'])
        .on_conflict_do_nothing(index_elements=[cases.c.swap_id]))
    transition(session, db, swap, 'REVIEW_REQUIRED', review_reason=reason)


def resources(session, db, swap):
    """Validate all three holds, identities and paid amount before custody writes."""
    ids = [swap['return_compartment_id'], swap['supply_compartment_id']]
    pins = [swap['old_battery_id'], swap['new_battery_id']]
    if None in ids + pins or len(set(ids)) != 2 or len(set(pins)) != 2:
        return None
    slots = {i: assets.get_row(session, db, 'compartments', i, lock=True) for i in sorted(ids)}
    batteries = {i: assets.get_row(session, db, 'batteries', i, lock=True) for i in sorted(pins)}
    holds = db.table('resource_reservations')
    rows = session.execute(select(holds).where(holds.c.swap_id == swap['id'],
        holds.c.released_at.is_(None))).mappings().all()
    if (len(rows) != 3 or {r['compartment_id'] for r in rows if r['compartment_id']} != set(ids)
            or {r['battery_id'] for r in rows if r['battery_id']} != {pins[1]}):
        return None
    payment = payments.get(session, db, swap['id'])
    if (payment['state'] != 'SUCCEEDED' or not payment['verified_at'] or not swap['consented_at']
            or payment['amount_minor'] != swap['amount_minor'] or payment['currency'] != swap['currency']):
        return None
    return slots[ids[0]], slots[ids[1]], batteries[pins[0]], batteries[pins[1]]


def physical_context(session, db, swap, items, receiving, supplying, command=None, issuing=False):
    ret, supply, old, new = items
    policy = swap['policy_snapshot']
    station = assets.get_row(session, db, 'stations', swap['station_id'])
    dev = assets.available_device(session, db, station['id'])
    if station['state'] != 'ACTIVE' or not dev or not dev['enabled']:
        return False
    timestamps = [dev['last_received_at']]
    for slot, expected in ((ret, receiving), (supply, supplying)):
        if (slot['station_id'] != station['id'] or slot['service_state'] != 'ACTIVE'
                or slot['door_state'] != 'CLOSED' or slot['observed_present'] != (expected is not None)
                or slot['observed_serial'] != expected or not assets.current_observation(session, db, dev, slot)
                or assets.has_alert(session, db, station['id'], slot['id'])):
            return False
        evidence = assets.latest_observation(session, db, dev['id'], slot['id'])
        timestamps.extend([slot['observed_at'], evidence['observed_at']])
    if command:
        event = assets.get_row(session, db, 'device_events', command['evidence_event_id'])
        timestamps.extend([event['observed_at'], event['received_at']])
    if issuing:
        readings = db.table('battery_telemetry')
        reading = session.execute(select(readings).where(readings.c.battery_id == new['id'])
            .order_by(readings.c.received_at.desc(), readings.c.id.desc()).limit(1)).mappings().first()
        if not reading: return False
        timestamps.extend([reading['received_at'], reading['measured_at']])
    # Final custody decision under station/resource locks, after all reads.
    # Fresh evidence does not extend the command's physical window; receipt,
    # ACK, retry and restart never move its origin. Equality is expired.
    now = utcnow()
    if command and now >= command['created_at'] + timedelta(seconds=policy['physical_step_timeout_seconds']):
        return False
    return all(assets.fresh(t, now, policy) for t in timestamps)


def proof(session, db, swap, command):
    if not command or command['state'] != 'OBSERVED' or not command['evidence_event_id']:
        return False
    event = assets.get_row(session, db, 'device_events', command['evidence_event_id'])
    dev = assets.get_row(session, db, 'devices', command['device_id'])
    now = utcnow()
    return bool(event['accepted'] and event['processed_at'] and event['kind'] == 'DOOR'
        and event['command_id'] == command['id'] and event['swap_id'] == swap['id']
        and event['compartment_id'] == command['compartment_id'] and event['device_id'] == dev['id']
        and event['boot_id'] == dev['boot_id'] and event['payload']['door_state'] == 'CLOSED'
        and all(assets.fresh(t, now, swap['policy_snapshot']) for t in (event['observed_at'], event['received_at'])))


def supply_ready(session, db, swap, items):
    ret, supply, old, new = items
    dev = assets.available_device(session, db, swap['station_id'])
    if (old['location_kind'] != 'COMPARTMENT' or old['compartment_id'] != ret['id']
            or old['holder_user_id'] is not None or new['location_kind'] != 'COMPARTMENT'
            or new['compartment_id'] != supply['id'] or new['holder_user_id'] is not None
            or assets.has_alert(session, db, swap['station_id'], supply['id'], new['id'])
            or not dev or not assets.quality(session, db, new, dev, utcnow(), swap['policy_snapshot'])):
        return False
    readings = db.table('battery_telemetry')
    reading = session.execute(select(readings).where(readings.c.battery_id == new['id'])
        .order_by(readings.c.received_at.desc(), readings.c.id.desc()).limit(1)).mappings().first()
    now = utcnow()
    return bool(reading and all(assets.fresh(t, now, swap['policy_snapshot'])
        for t in (reading['received_at'], reading['measured_at'])))


def advance(session, db, identity):
    """Resume a durable step once; callers hold station_locks, including both pins."""
    swap = assets.get_row(session, db, 'swap_transactions', identity, lock=True)
    if swap['state'] not in ('AWAITING_RETURN', 'RETURN_ACCEPTED', 'AWAITING_PICKUP'):
        return
    items = resources(session, db, swap)
    if not items:
        review(session, db, swap, 'SWAP_RESOURCE_CONFLICT')
        return
    ret, supply, old, new = items
    commands = db.table('device_commands')
    kind = 'OPEN_RETURN' if swap['state'] == 'AWAITING_RETURN' else 'OPEN_SUPPLY'
    command = session.execute(select(commands).where(commands.c.swap_id == identity,
        commands.c.kind == kind)).mappings().first()
    if command and command['state'] in ('UNKNOWN', 'REJECTED', 'EXPIRED'):
        review(session, db, swap, 'SWAP_COMMAND_' + command['state'])
        return
    if swap['state'] == 'AWAITING_RETURN':
        if not command:
            if not payments.resources_valid(session, db, swap, utcnow()):
                review(session, db, swap, 'SWAP_RETURN_INTERLOCK')
                return
            device.enqueue_command(session, db, identity, ret['id'], kind, swap['policy_snapshot'])
            return
        if command['state'] != 'OBSERVED':
            return
        event = (assets.get_row(session, db, 'device_events', command['evidence_event_id'])
                 if command['evidence_event_id'] else None)
        if (not proof(session, db, swap, command) or old['location_kind'] != 'CUSTOMER'
                or old['holder_user_id'] != swap['customer_id'] or old['family'] != swap['policy_snapshot']['battery_family']
                or assets.pin_at(session, db, ret)
                or not physical_context(session, db, swap, items, old['serial'], new['serial'], command)):
            review(session, db, swap, 'SWAP_RETURN_EVIDENCE')
            return
        pins = db.table('batteries')
        session.execute(update(pins).where(pins.c.id == old['id']).values(location_kind='COMPARTMENT',
            compartment_id=ret['id'], holder_user_id=None, version=old['version'] + 1))
        transition(session, db, swap, 'RETURN_ACCEPTED', return_observed_at=event['observed_at'])
        return  # Custody is durable now; a restart resumes the following step.
    if swap['state'] == 'RETURN_ACCEPTED':
        if (not supply_ready(session, db, swap, items)
                or not physical_context(session, db, swap, items, old['serial'], new['serial'], issuing=True)):
            review(session, db, swap, 'SWAP_SUPPLY_INTERLOCK')
            return
        device.enqueue_command(session, db, identity, supply['id'], 'OPEN_SUPPLY', swap['policy_snapshot'])
        transition(session, db, swap, 'AWAITING_PICKUP')
        return
    if not command or command['state'] != 'OBSERVED':
        return
    event = (assets.get_row(session, db, 'device_events', command['evidence_event_id'])
             if command['evidence_event_id'] else None)
    if (not proof(session, db, swap, command) or not supply_ready(session, db, swap, items)
            or not physical_context(session, db, swap, items, old['serial'], None, command, issuing=True)):
        review(session, db, swap, 'SWAP_PICKUP_EVIDENCE')
        return
    pins = db.table('batteries')
    session.execute(update(pins).where(pins.c.id == new['id']).values(location_kind='CUSTOMER',
        compartment_id=None, holder_user_id=swap['customer_id'], version=new['version'] + 1))
    now = utcnow()
    transition(session, db, swap, 'COMPLETED', pickup_observed_at=event['observed_at'], closed_at=now)
    holds = db.table('resource_reservations')
    session.execute(update(holds).where(holds.c.swap_id == identity, holds.c.released_at.is_(None))
        .values(released_at=now))


def tick(db):
    from app.workers.device import station_locks
    table = db.table('swap_transactions')
    with db.sessions() as session:
        rows = session.execute(select(table.c.id, table.c.station_id).where(
            table.c.state.in_(['AWAITING_RETURN', 'RETURN_ACCEPTED', 'AWAITING_PICKUP']))).all()
    for identity, station in rows:
        with db.sessions.begin() as session:
            station_locks(session, db, station)
            try:
                with session.begin_nested():
                    advance(session, db, identity)
            except DomainError as error:
                swap = assets.get_row(session, db, 'swap_transactions', identity, lock=True)
                if swap['state'] in ('AWAITING_RETURN', 'RETURN_ACCEPTED', 'AWAITING_PICKUP'):
                    review(session, db, swap, error.code)
