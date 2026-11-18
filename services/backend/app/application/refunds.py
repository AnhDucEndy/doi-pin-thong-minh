"""B1a Refund repository/API gates. No certificate issuer, dispatch or effects."""
from sqlalchemy import select

from app.application import assets
from app.application.identity import DomainError, utcnow
from app.domain.refunds import reconcile_mode
from app.workers.device import station_locks


def for_payment(session, db, payment_id):
    table = db.table('refunds')
    row = session.execute(select(table).where(table.c.payment_id == payment_id)).mappings().first()
    if not row:
        raise DomainError(404, 'RESOURCE_NOT_FOUND')
    return dict(row)


def get(session, db, actor, payment_id):
    # Scope is checked before looking up whether the other customer's refund exists.
    if actor['user']['role'] not in ('ADMIN', 'CUSTOMER'):
        raise DomainError(403, 'FORBIDDEN')
    payment = assets.get_row(session, db, 'payments', payment_id)
    swap = assets.get_row(session, db, 'swap_transactions', payment['swap_id'])
    if actor['user']['role'] == 'CUSTOMER' and swap['customer_id'] != actor['user']['id']:
        raise DomainError(403, 'FORBIDDEN')
    return for_payment(session, db, payment_id)


def lock_context(session, db, actor, payment_id, refund_id=None):
    initial = assets.get_row(session, db, 'payments', payment_id)
    swap = assets.get_row(session, db, 'swap_transactions', initial['swap_id'])
    assets.station_lock(session, db, swap['station_id'])
    operations = db.table('recovery_operations')
    participants = set(session.scalars(select(operations.c.created_by)
        .where(operations.c.station_id == swap['station_id'])))
    participants.update((swap['customer_id'], actor['user']['id']))
    station_locks(session, db, swap['station_id'], participants)
    swap = assets.get_row(session, db, 'swap_transactions', swap['id'])
    payment = assets.get_row(session, db, 'payments', payment_id, lock=True)
    refund = assets.get_row(session, db, 'refunds', refund_id, lock=True) if refund_id else None
    # There are no certificate witnesses in B1a. B1b must gather and sort their
    # exact session IDs BEFORE this step, not acquire new user locks afterwards.
    user = assets.get_row(session, db, 'users', actor['user']['id'])
    token = assets.get_row(session, db, 'auth_sessions', actor['session']['id'], lock=True)
    if (token['user_id'] != user['id'] or user['state'] != 'ACTIVE'
            or token['revoked_at'] or token['expires_at'] <= utcnow()):
        raise DomainError(401, 'SESSION_REVOKED')
    if user['role'] != 'ADMIN':
        raise DomainError(403, 'FORBIDDEN')
    return swap, payment, refund


def request(session, db, actor, payment_id, body):
    swap, payment, _ = lock_context(session, db, actor, payment_id)
    assets.version(payment, body.expected_version)
    if payment['state'] != 'SUCCEEDED' or not payment['verified_at'] or not payment['provider_reference']:
        raise DomainError(409, 'STATE_CONFLICT')
    table = db.table('refunds')
    if session.scalar(select(table.c.id).where(table.c.payment_id == payment_id)):
        raise DomainError(409, 'STATE_CONFLICT')
    # NO flag / empty slot / ACK / ledger EXECUTED are NOT eligibility proof.
    # B1b is deliberately not implemented by this increment. Refuse before any
    # refund, attempt, swap, audit, outbox, certificate redemption or receipt write.
    raise DomainError(422, 'REFUND_EVIDENCE_REQUIRED')


def reconcile(session, db, actor, refund_id, body):
    initial = assets.get_row(session, db, 'refunds', refund_id)
    _, _, refund = lock_context(session, db, actor, initial['payment_id'], refund_id)
    assets.version(refund, body.expected_version)
    reconcile_mode(refund['state'])  # FAILED cannot retry without provider permit.
    # UNKNOWN is query-only, but B3 query/outbox processing is not yet available.
    # Do not accept a reconciliation job or generate a new attempt in B1a.
    raise DomainError(422, 'REFUND_EVIDENCE_REQUIRED')
