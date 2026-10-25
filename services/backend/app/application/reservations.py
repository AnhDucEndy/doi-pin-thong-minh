"""UC09/UC10 preparation only: no payment, actuator command or custody transfer."""
import base64
import hashlib
import hmac
import os
from datetime import timedelta
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, or_, select, update

from app.application import assets
from app.application.identity import DomainError, audit, utcnow
from app.config import ConfigNotReady
from app.domain.identity import digest


PRIVATE_SWAP = {'qr_challenge_id', 'credential_id', 'policy_snapshot'}


def public_swap(row):
    return {k: v for k, v in row.items() if k not in PRIVATE_SWAP}


def credential_view(row):
    return {'id': row['id'], 'user_id': row['user_id'], 'revoked': row['revoked_at'] is not None}


def customer(session, db, identity, lock=True):
    user = assets.get_row(session, db, 'users', identity, lock=lock)
    if user['role'] != 'CUSTOMER' or user['state'] != 'ACTIVE':
        raise DomainError(403, 'CUSTOMER_UNAVAILABLE')
    return user


def create_credential(session, db, actor, identity, value):
    customer(session, db, identity)
    table = db.table('credentials')
    row = session.execute(insert(table).values(id=uuid4(), user_id=identity,
        credential_hash=digest(value)).returning(table)).mappings().one()
    view = credential_view(row)
    audit(session, db, actor['id'], 'CREATE_CREDENTIAL', row['id'], after=view, aggregate_type='credential')
    return view


def revoke_credential(session, db, actor, identity):
    initial = assets.get_row(session, db, 'credentials', identity)
    assets.get_row(session, db, 'users', initial['user_id'], lock=True)
    row = assets.get_row(session, db, 'credentials', identity, lock=True)
    if row['revoked_at'] is None:
        table = db.table('credentials')
        row = session.execute(update(table).where(table.c.id == identity)
            .values(revoked_at=utcnow()).returning(table)).mappings().one()
        audit(session, db, actor['id'], 'REVOKE_CREDENTIAL', identity,
              after=credential_view(row), aggregate_type='credential')
    return credential_view(row)


def qr_token(user_id, key):
    # Same opaque 256-bit delivery pattern as device registration, domain separated.
    # The response cache and database contain no plaintext QR token.
    secret = os.getenv('DEVICE_KEY_DERIVATION_SECRET', '')
    if len(secret) < 32 or secret.startswith('REPLACE_'):
        raise ConfigNotReady('CONFIG_NOT_READY')
    value = hmac.new(secret.encode(), f'createQr:v1:{user_id}:{key}'.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def create_qr(session, db, actor, station_id, token, policy):
    assets.station_lock(session, db, station_id)
    customer(session, db, actor['id'])
    now = utcnow()
    table = db.table('qr_challenges')
    row = session.execute(insert(table).values(id=uuid4(), user_id=actor['id'], station_id=station_id,
        token_hash=digest(token), created_at=now, expires_at=now + timedelta(seconds=policy['qr_ttl_seconds']))
        .returning(table)).mappings().one()
    view = {'challenge_id': row['id'], 'station_id': station_id, 'expires_at': row['expires_at']}
    audit(session, db, actor['id'], 'CREATE_QR', row['id'], after=view, aggregate_type='qr_challenge')
    return view


def policy_revision(session, db, policy):
    table = db.table('demo_policies')
    row = session.execute(select(table).order_by(table.c.revision.desc()).limit(1)).mappings().first()
    if not row or row['parameters'] != policy or row['review_status'] != policy['decision_status']:
        raise ConfigNotReady('CONFIG_NOT_READY')
    return row['id']


def station_online(session, db, station_id, policy, now):
    station = assets.get_row(session, db, 'stations', station_id)
    device = assets.available_device(session, db, station_id)
    if station['state'] != 'ACTIVE' or not assets.online(session, db, device, now, policy):
        raise DomainError(503, 'STATION_OFFLINE')
    return station, device


def swap_audit(session, db, actor, action, identity, after, device=False):
    session.execute(insert(db.table('audit_events')).values(id=uuid4(),
        actor_type='DEVICE' if device else 'USER' if actor else 'SYSTEM',
        actor_id=str(actor['id']) if actor else 'reservation-worker', aggregate_type='swap',
        aggregate_id=identity, action=action, after_data=jsonable_encoder(after), correlation_id=uuid4()))


def verify(session, db, device, method, value, policy):
    assets.station_lock(session, db, device['station_id'])
    table = db.table('qr_challenges' if method == 'QR' else 'credentials')
    column = table.c.token_hash if method == 'QR' else table.c.credential_hash
    initial = session.execute(select(table).where(column == digest(value))).mappings().first()
    if not initial:
        raise DomainError(401, 'CREDENTIAL_INVALID')
    user = customer(session, db, initial['user_id'])
    row = assets.get_row(session, db, table.name, initial['id'], lock=True)
    now = utcnow()  # Sample after locks, so waiting cannot extend an expired QR.
    current_device = assets.get_row(session, db, 'devices', device['id'], lock=True)
    if not current_device['enabled']:
        raise DomainError(403, 'DEVICE_DISABLED')
    if method == 'QR':
        if row['station_id'] != device['station_id']:
            raise DomainError(403, 'QR_STATION_FORBIDDEN')
        if row['consumed_at'] is not None:
            raise DomainError(409, 'QR_ALREADY_USED')
        if row['expires_at'] <= now:
            raise DomainError(409, 'QR_EXPIRED')
    elif row['revoked_at'] is not None:
        raise DomainError(401, 'CREDENTIAL_INVALID')
    station_online(session, db, device['station_id'], policy, now)
    swaps = db.table('swap_transactions')
    if session.execute(select(swaps.c.id).where(swaps.c.customer_id == user['id'],
            swaps.c.state.not_in(assets.CLOSED_SWAPS))).first():
        raise DomainError(409, 'ACTIVE_TRANSACTION')
    values = {'qr_challenge_id' if method == 'QR' else 'credential_id': row['id']}
    result = session.execute(insert(swaps).values(id=uuid4(), customer_id=user['id'],
        station_id=device['station_id'], verified_via=method, policy_id=policy_revision(session, db, policy),
        policy_snapshot=policy, created_at=now, **values).returning(swaps)).mappings().one()
    if method == 'QR':
        session.execute(update(table).where(table.c.id == row['id']).values(consumed_at=now))
    swap_audit(session, db, device, 'VERIFY_' + method, result['id'], public_swap(result), device=True)
    return public_swap(result)


def owned_swap(session, db, actor, identity):
    row = assets.get_row(session, db, 'swap_transactions', identity)
    if actor['role'] == 'CUSTOMER' and row['customer_id'] != actor['id']:
        raise DomainError(404, 'RESOURCE_NOT_FOUND')
    if actor['role'] not in ('CUSTOMER', 'ADMIN'):
        raise DomainError(403, 'FORBIDDEN')
    return row


def lock_swap(session, db, initial):
    assets.station_lock(session, db, initial['station_id'])
    customer(session, db, initial['customer_id'])
    return assets.get_row(session, db, 'swap_transactions', initial['id'], lock=True)


def safe_to_release(session, db, row):
    if row['state'] not in ('VERIFIED', 'RESERVED') or row['consented_at'] or row['return_observed_at'] or row['pickup_observed_at']:
        return False
    for name, column in [('payments', 'swap_id'), ('device_commands', 'swap_id')]:
        table = db.table(name)
        if session.execute(select(table.c.id).where(getattr(table.c, column) == row['id'])).first():
            return False
    outbox = db.table('outbox_messages')
    return not session.execute(select(outbox.c.id).where(outbox.c.aggregate_id == row['id'])).first()


def close(session, db, row, reason, actor=None):
    if not safe_to_release(session, db, row):
        raise DomainError(409, 'RECONCILIATION_REQUIRED')
    now = utcnow()
    holds = db.table('resource_reservations')
    session.execute(update(holds).where(holds.c.swap_id == row['id'], holds.c.released_at.is_(None)).values(released_at=now))
    table = db.table('swap_transactions')
    result = session.execute(update(table).where(table.c.id == row['id']).values(state='CANCELLED',
        closed_at=now, review_reason=reason, version=row['version'] + 1).returning(table)).mappings().one()
    swap_audit(session, db, actor, 'CANCEL_RESERVATION', row['id'], public_swap(result))
    return public_swap(result)


def reserve(session, db, actor, identity, version):
    row = lock_swap(session, db, owned_swap(session, db, actor, identity))
    assets.version(row, version)
    if row['state'] != 'VERIFIED':
        raise DomainError(409, 'STATE_CONFLICT')
    policy = row['policy_snapshot']
    now = utcnow()
    if now >= row['created_at'] + timedelta(seconds=policy['verification_ttl_seconds']):
        return close(session, db, row, 'VERIFICATION_EXPIRED', actor)
    station, device = station_online(session, db, row['station_id'], policy, now)
    slots, pins = db.table('compartments'), db.table('batteries')
    slot_rows = session.execute(select(slots).where(slots.c.station_id == row['station_id'])
        .order_by(slots.c.id).with_for_update()).mappings().all()
    # The customer-held old pin and all station pins use the same UUID ordering.
    pin_rows = session.execute(select(pins).where(or_(pins.c.compartment_id.in_([s['id'] for s in slot_rows]),
        pins.c.holder_user_id == actor['id'])).order_by(pins.c.id).with_for_update()).mappings().all()
    now = utcnow()  # Recheck TTL and freshness after resource locks.
    if now >= row['created_at'] + timedelta(seconds=policy['verification_ttl_seconds']):
        return close(session, db, row, 'VERIFICATION_EXPIRED', actor)
    station_online(session, db, row['station_id'], policy, now)
    old = next((p for p in pin_rows if p['holder_user_id'] == actor['id'] and p['location_kind'] == 'CUSTOMER'), None)
    if not old or old['family'] != policy['battery_family']:
        raise DomainError(422, 'CUSTOMER_BATTERY_REQUIRED')
    active = assets.active_swaps(session, db, row['station_id'])
    returns = [s for s in slot_rows if s['service_state'] == 'ACTIVE' and s['door_state'] == 'CLOSED'
        and s['observed_present'] is False and s['observed_serial'] is None and assets.fresh(s['observed_at'], now, policy)
        and assets.current_observation(session, db, device, s)
        and not any(p['compartment_id'] == s['id'] for p in pin_rows)
        and not assets.held(session, db, s['id'])
        and not assets.has_alert(session, db, row['station_id'], s['id'])
        and not any(s['id'] in (a['return_compartment_id'], a['supply_compartment_id']) for a in active)]
    supply = [(s, p) for s in slot_rows for p in pin_rows if p['compartment_id'] == s['id']
        and assets.eligible(session, db, p, policy, now, s, station, device, active)]
    if not returns or not supply:
        # AD-02a/SM-03a: a successful preparation outcome may be CANCELLED,
        # never pretend a quote/reservation was made when no resources exist.
        return close(session, db, row, 'RESOURCE_UNAVAILABLE', actor)
    receiving, (supplying, new) = returns[0], supply[0]
    holds = db.table('resource_reservations')
    for values in ({'compartment_id': receiving['id']}, {'compartment_id': supplying['id']}, {'battery_id': new['id']}):
        session.execute(insert(holds).values(id=uuid4(), swap_id=identity, **values))
    table = db.table('swap_transactions')
    result = session.execute(update(table).where(table.c.id == identity).values(state='RESERVED',
        old_battery_id=old['id'], new_battery_id=new['id'], return_compartment_id=receiving['id'],
        supply_compartment_id=supplying['id'], amount_minor=policy['fee_minor'], currency=policy['currency'],
        reservation_expires_at=now + timedelta(seconds=policy['reservation_ttl_seconds']),
        version=row['version'] + 1).returning(table)).mappings().one()
    swap_audit(session, db, actor, 'RESERVE_RESOURCES', identity, public_swap(result))
    return public_swap(result)


def cancel(session, db, actor, identity, version, reason):
    row = lock_swap(session, db, owned_swap(session, db, actor, identity))
    assets.version(row, version)
    return close(session, db, row, reason, actor)


def expire(db, now=None):
    """Durable timeout job: release only pre-payment reservations of this aggregate."""
    now = now or utcnow()
    with db.sessions() as session:
        table = db.table('swap_transactions')
        candidates = session.execute(select(table).where(table.c.state.in_(['VERIFIED', 'RESERVED']))).mappings().all()
    count = 0
    for candidate in candidates:
        if candidate['state'] == 'VERIFIED' and 'verification_ttl_seconds' not in candidate['policy_snapshot']:
            continue  # Missing policy cannot authorize a timeout/release.
        deadline = candidate['reservation_expires_at'] if candidate['state'] == 'RESERVED' else (
            candidate['created_at'] + timedelta(seconds=candidate['policy_snapshot']['verification_ttl_seconds']))
        if deadline is None or now < deadline:
            continue
        with db.sessions.begin() as session:
            # Do not depend on a live Customer role to expire safely after a lock/revocation.
            assets.station_lock(session, db, candidate['station_id'])
            assets.get_row(session, db, 'users', candidate['customer_id'], lock=True)
            row = assets.get_row(session, db, 'swap_transactions', candidate['id'], lock=True)
            if row['state'] != candidate['state'] or not safe_to_release(session, db, row):
                continue
            close(session, db, row, 'RESERVATION_EXPIRED' if row['state'] == 'RESERVED' else 'VERIFICATION_EXPIRED')
            count += 1
    return count
