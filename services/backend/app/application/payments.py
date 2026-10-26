"""FR14/15: one durable intent, outbox dispatch, verified results; no actuator work."""
from datetime import timedelta
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.application import assets, reservations
from app.application.identity import DomainError, utcnow
from app.infrastructure.db import advisory_lock


def record(session, db, payment, action, data):
    session.execute(insert(db.table('audit_events')).values(id=uuid4(), actor_type='SYSTEM',
        actor_id='payment-worker', aggregate_type='payment', aggregate_id=payment['id'],
        action=action, after_data=jsonable_encoder(data), correlation_id=uuid4()))


def get(session, db, swap_id):
    table = db.table('payments')
    row = session.execute(select(table).where(table.c.swap_id == swap_id)).mappings().first()
    if not row:
        raise DomainError(404, 'RESOURCE_NOT_FOUND')
    return row


def lock(session, db, payment_id):
    initial = assets.get_row(session, db, 'payments', payment_id)
    swap = assets.get_row(session, db, 'swap_transactions', initial['swap_id'])
    assets.station_lock(session, db, swap['station_id'])
    # Background settlement must continue even if the Customer is subsequently locked.
    assets.get_row(session, db, 'users', swap['customer_id'], lock=True)
    swap = assets.get_row(session, db, 'swap_transactions', swap['id'], lock=True)
    return swap, assets.get_row(session, db, 'payments', payment_id, lock=True)


def resources_valid(session, db, swap, now):
    """Recheck own three holds and physical/BMS evidence under the shared station lock."""
    policy = swap['policy_snapshot']
    station = assets.get_row(session, db, 'stations', swap['station_id'])
    device = assets.available_device(session, db, station['id'])
    if station['state'] != 'ACTIVE' or not assets.online(session, db, device, now, policy):
        return False
    ids = [swap['return_compartment_id'], swap['supply_compartment_id']]
    if None in ids or len(set(ids)) != 2 or not swap['new_battery_id'] or not swap['old_battery_id']:
        return False
    slots = {i: assets.get_row(session, db, 'compartments', i, lock=True) for i in sorted(ids)}
    pins = {i: assets.get_row(session, db, 'batteries', i, lock=True)
            for i in sorted([swap['old_battery_id'], swap['new_battery_id']])}
    holds = db.table('resource_reservations')
    held = session.execute(select(holds).where(holds.c.swap_id == swap['id'], holds.c.released_at.is_(None))).mappings().all()
    if len(held) != 3 or {h['compartment_id'] for h in held if h['compartment_id']} != set(ids) or {
            h['battery_id'] for h in held if h['battery_id']} != {swap['new_battery_id']}:
        return False
    for slot in slots.values():
        if (slot['station_id'] != station['id'] or slot['service_state'] != 'ACTIVE' or slot['door_state'] != 'CLOSED'
                or not assets.fresh(slot['observed_at'], now, policy)
                or not assets.current_observation(session, db, device, slot)
                or assets.has_alert(session, db, station['id'], slot['id'])):
            return False
    old, new = pins[swap['old_battery_id']], pins[swap['new_battery_id']]
    receiving, supplying = slots[ids[0]], slots[ids[1]]
    at_return = session.execute(select(db.table('batteries').c.id).where(
        db.table('batteries').c.compartment_id == receiving['id'])).first()
    valid = bool(not at_return and receiving['observed_present'] is False and receiving['observed_serial'] is None
        and old['location_kind'] == 'CUSTOMER' and old['holder_user_id'] == swap['customer_id']
        and old['family'] == policy['battery_family'] and new['location_kind'] == 'COMPARTMENT'
        and new['compartment_id'] == supplying['id'] and new['holder_user_id'] is None
        and supplying['observed_present'] is True and supplying['observed_serial'] == new['serial']
        and not assets.has_alert(session, db, station['id'], supplying['id'], new['id'])
        and assets.quality(session, db, new, device, now, policy))
    if not valid:
        return False
    # Station/resource locks stabilize evidence, not the clock. Read the BMS
    # timestamps under those same locks, then sample time AFTER the final DB
    # read. Recheck both doors, heartbeat and both BMS clocks at this decision
    # point; do not extend receipt TTL or replace physical measurement time.
    readings = db.table('battery_telemetry')
    reading = session.execute(select(readings.c.received_at, readings.c.measured_at)
        .where(readings.c.battery_id == new['id'])
        .order_by(readings.c.received_at.desc(), readings.c.id.desc()).limit(1)).mappings().first()
    decision_at = utcnow()
    return bool(reading and all(assets.fresh(value, decision_at, policy) for value in (
        device['last_received_at'], receiving['observed_at'], supplying['observed_at'],
        reading['received_at'], reading['measured_at'])))


def consent(session, db, actor, identity, body):
    row = reservations.lock_swap(session, db, reservations.owned_swap(session, db, actor, identity))
    assets.version(row, body.expected_version)
    if row['state'] != 'RESERVED' or row['consented_at']:
        raise DomainError(409, 'STATE_CONFLICT')
    now = utcnow()
    if not row['reservation_expires_at'] or row['reservation_expires_at'] <= now:
        raise DomainError(409, 'RESERVATION_EXPIRED')
    if body.quoted_amount_minor != row['amount_minor'] or body.currency != row['currency']:
        raise DomainError(409, 'QUOTE_MISMATCH')
    policy = row['policy_snapshot']
    if row['amount_minor'] != policy['fee_minor'] or row['currency'] != policy['currency']:
        raise DomainError(409, 'QUOTE_MISMATCH')
    if not resources_valid(session, db, row, now):
        raise DomainError(409, 'RESOURCE_UNAVAILABLE')
    # Sample time after any waits; never extend a reservation through a slow lock.
    if row['reservation_expires_at'] <= utcnow():
        raise DomainError(409, 'RESERVATION_EXPIRED')
    payment_id, provider_key = uuid4(), uuid4()
    payment = session.execute(insert(db.table('payments')).values(id=payment_id, swap_id=identity,
        provider_key=provider_key, amount_minor=row['amount_minor'], currency=row['currency'])
        .returning(db.table('payments'))).mappings().one()
    session.execute(insert(db.table('outbox_messages')).values(id=uuid4(), aggregate_type='payment',
        aggregate_id=payment_id, kind='CHARGE', dedup_key=str(provider_key), payload={
            'payment_id': str(payment_id), 'swap_id': str(identity), 'provider_key': str(provider_key),
            'amount_minor': row['amount_minor'], 'currency': row['currency']}))
    table = db.table('swap_transactions')
    result = session.execute(update(table).where(table.c.id == identity).values(state='AWAITING_PAYMENT',
        consented_at=utcnow(), version=row['version'] + 1).returning(table)).mappings().one()
    reservations.swap_audit(session, db, actor, 'CONSENT_PAYMENT', identity, reservations.public_swap(result))
    record(session, db, payment, 'CREATE_PAYMENT', dict(payment))
    return reservations.public_swap(result)


def receive(session, db, body):
    data = body.model_dump(mode='json')
    if body.refund_id is not None:
        raise DomainError(422, 'INVALID_ACTION')  # Refund belongs to the later reviewed recovery workflow.
    data.pop('refund_id', None)
    from app.domain.identity import digest
    import json
    hashed = digest(json.dumps(data, sort_keys=True, separators=(',', ':')))
    advisory_lock(session, 'payment-event:' + body.provider_event_id)
    events = db.table('payment_events')
    prior = session.execute(select(events).where(events.c.provider_event_id == body.provider_event_id)).mappings().first()
    if prior:
        if prior['payload_hash'] != hashed:
            raise DomainError(409, 'EVENT_ID_CONFLICT')
        return {'accepted': True, 'duplicate': True}
    swap, payment = lock(session, db, body.payment_id)
    if (body.provider_key != payment['provider_key'] or body.amount_minor != payment['amount_minor']
            or body.currency != payment['currency'] or (payment['provider_reference'] is not None
            and body.provider_reference != payment['provider_reference'])):
        raise DomainError(409, 'PAYMENT_RESULT_MISMATCH')
    session.execute(insert(events).values(id=uuid4(), provider_event_id=body.provider_event_id,
        payment_id=payment['id'], payload_hash=hashed, payload=data))
    return {'accepted': True, 'duplicate': False}


def apply_result(session, db, swap, payment, result, now):
    """Serialize receipt ownership across stations and isolate permanent conflicts.

    The caller commits this disposition/audit with inbox processed_at (or the
    outbox attempt). A rejected receipt is not a successful settlement. Unknown
    outcomes retain holds and may only query the existing provider key.
    """
    reference = result.get('provider_reference')
    if reference and result.get('result') in ('PENDING', 'SUCCEEDED', 'FAILED'):
        advisory_lock(session, 'payment-receipt:' + reference)
        table = db.table('payments')
        other = session.scalar(select(table.c.id).where(table.c.provider_reference == reference,
                                                       table.c.id != payment['id']))
        if other:
            reject_receipt(session, db, swap, payment, result, now)
            return
    try:
        # A legacy writer not taking the receipt lock can still race us. Keep
        # the UNIQUE constraint; roll back the failed SQL/savepoint BEFORE any
        # durable rejection write, leaving the outer inbox transaction usable.
        with session.begin_nested():
            _apply_result(session, db, swap, payment, result, now)
    except IntegrityError as error:
        if getattr(getattr(error.orig, 'diag', None), 'constraint_name', None) != 'payments_provider_reference_key':
            raise  # Do not silently acknowledge unrelated DB/programming faults.
        reject_receipt(session, db, swap, payment, result, now)


def reject_receipt(session, db, swap, payment, result, now):
    if payment['state'] not in ('SUCCEEDED', 'FAILED'):
        _apply_result(session, db, swap, payment, {'result': 'UNKNOWN'}, now)
    record(session, db, payment, 'PAYMENT_RESULT_REJECTED', {
        'code': 'PAYMENT_RESULT_MISMATCH', 'reason': 'PROVIDER_REFERENCE_CONFLICT',
        'provider_event_id': result.get('provider_event_id'),
        'provider_reference': result.get('provider_reference'), 'received_result': result.get('result')})


def _apply_result(session, db, swap, payment, result, now):
    state = result['result']
    if state not in ('PENDING', 'SUCCEEDED', 'FAILED'):
        state = 'UNKNOWN'
    if state != 'UNKNOWN' and (str(result['provider_key']) != str(payment['provider_key'])
            or result['amount_minor'] != payment['amount_minor'] or result['currency'] != payment['currency']
            or not result['provider_reference'] or (payment['provider_reference'] and
                result['provider_reference'] != payment['provider_reference'])):
        state = 'UNKNOWN'
    if payment['state'] in ('SUCCEEDED', 'FAILED'):
        if state in ('SUCCEEDED', 'FAILED') and state != payment['state']:
            review(session, db, swap, 'PAYMENT_RESULT_CONFLICT')
            record(session, db, payment, 'PAYMENT_RESULT_CONFLICT', {'received_result': state})
        return  # A late PENDING/FAILED cannot overwrite confirmed SUCCEEDED.
    if payment['state'] == 'UNKNOWN' and state == 'PENDING':
        return  # Pending is not a final reconciliation of an unknown outcome.
    if payment['state'] == 'CREATED' and state in ('SUCCEEDED', 'FAILED'):
        # An authenticated callback may win the response race. Preserve SM-04's
        # dispatch transition inside this same transaction before final settlement.
        table = db.table('payments')
        payment = session.execute(update(table).where(table.c.id == payment['id']).values(
            state='PENDING', version=payment['version'] + 1).returning(table)).mappings().one()
        record(session, db, payment, 'PAYMENT_DISPATCH_EVIDENCE', {'source':'verified-result'})
    if payment['state'] == state and payment['provider_reference'] == result.get('provider_reference'):
        return
    table = db.table('payments')
    payment = session.execute(update(table).where(table.c.id == payment['id']).values(state=state,
        provider_reference=payment['provider_reference'] or (result.get('provider_reference') if state != 'UNKNOWN' else None),
        verified_at=now if state in ('SUCCEEDED', 'FAILED') else None,
        version=payment['version'] + 1).returning(table)).mappings().one()
    record(session, db, payment, 'PAYMENT_' + state, dict(payment))
    if state == 'UNKNOWN':
        review(session, db, swap, 'PAYMENT_UNKNOWN')
    elif state == 'SUCCEEDED':
        if (swap['state'] in ('AWAITING_PAYMENT', 'REVIEW_REQUIRED') and not swap['return_observed_at']
                and not swap['pickup_observed_at'] and not has_commands(session, db, swap['id'])
                and resources_valid(session, db, swap, now)):
            change_swap(session, db, swap, 'AWAITING_RETURN', None)
        else:
            review(session, db, swap, 'PAYMENT_RESOURCE_REVIEW')
    elif state == 'FAILED':
        if (swap['state'] in ('AWAITING_PAYMENT', 'REVIEW_REQUIRED') and not swap['return_observed_at']
                and not swap['pickup_observed_at'] and not has_commands(session, db, swap['id'])):
            holds = db.table('resource_reservations')
            session.execute(update(holds).where(holds.c.swap_id == swap['id'], holds.c.released_at.is_(None)).values(released_at=now))
            change_swap(session, db, swap, 'CANCELLED', 'PAYMENT_FAILED', closed_at=now)
        else:
            review(session, db, swap, 'PAYMENT_FAILURE_REVIEW')


def has_commands(session, db, identity):
    t = db.table('device_commands')
    return bool(session.execute(select(t.c.id).where(t.c.swap_id == identity)).first())


def change_swap(session, db, swap, state, reason, **fields):
    table = db.table('swap_transactions')
    result = session.execute(update(table).where(table.c.id == swap['id']).values(state=state,
        review_reason=reason, version=swap['version'] + 1, **fields).returning(table)).mappings().one()
    reservations.swap_audit(session, db, None, 'PAYMENT_SWAP_' + state, swap['id'], reservations.public_swap(result))


def review(session, db, swap, reason):
    # Minimal handoff to the later recovery workflow, not a refund or manual
    # custody decision. Preserve terminal states when contradictory evidence
    # arrives after closure; keep a durable case instead of silently dropping it.
    if reason in ('PAYMENT_RESULT_CONFLICT', 'PAYMENT_RESOURCE_REVIEW', 'PAYMENT_FAILURE_REVIEW'):
        cases = db.table('recovery_cases')
        session.execute(pg_insert(cases).values(id=uuid4(), swap_id=swap['id'])
            .on_conflict_do_nothing(index_elements=[cases.c.swap_id]))
    if swap['state'] not in assets.CLOSED_SWAPS and (swap['state'] != 'REVIEW_REQUIRED' or swap['review_reason'] != reason):
        change_swap(session, db, swap, 'REVIEW_REQUIRED', reason)


def reconcile(session, db, identity, version, reason):
    swap, payment = lock(session, db, identity)
    assets.version(payment, version)
    if payment['state'] not in ('UNKNOWN', 'PENDING'):
        raise DomainError(409, 'STATE_CONFLICT')
    box = db.table('outbox_messages')
    session.execute(update(box).where(box.c.aggregate_id == identity, box.c.kind == 'CHARGE')
        .values(next_attempt_at=utcnow(), delivered_at=None))
    record(session, db, payment, 'RECONCILE_PAYMENT', {'reason': reason})
    return dict(payment)
