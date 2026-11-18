"""Allowlisted actual snapshots. Caller owns locks and the surrounding transaction."""
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select

REFUND_FIELDS = ('id', 'payment_id', 'requested_by', 'provider_key', 'provider_reference',
                 'state', 'amount_minor', 'verified_at', 'version', 'created_at')


def snapshot(session, db, refund_id):
    table = db.table('refunds')
    row = session.execute(select(table).where(table.c.id == refund_id)).mappings().first()
    if row is None:
        return None
    payment = db.table('payments')
    charge = session.execute(select(payment.c.swap_id, payment.c.state, payment.c.currency)
        .where(payment.c.id == row['payment_id'])).mappings().one()
    return jsonable_encoder({**{k: row[k] for k in REFUND_FIELDS},
        'swap_id': charge['swap_id'], 'charge_state': charge['state'], 'currency': charge['currency']})


def record(session, db, actor_id, action, refund_id, *, before, correlation_id, references=None):
    # Do not copy arbitrary reason, provider payload, headers or caller metadata.
    safe_refs = {}
    for key, value in (references or {}).items():
        if key in ('attempt_id', 'permit_id', 'certificate_id', 'operation_id', 'outbox_id'):
            safe_refs[key] = UUID(str(value))
        elif key == 'generation' and type(value) is int and value >= 0:
            safe_refs[key] = value
    # Before-data comes from snapshot(), but keep the boundary allowlisted too.
    before = ({k: before[k] for k in (*REFUND_FIELDS, 'swap_id', 'charge_state', 'currency') if k in before}
              if before is not None else None)
    session.execute(insert(db.table('audit_events')).values(id=uuid4(), actor_type='USER',
        actor_id=str(actor_id), aggregate_type='refund', aggregate_id=refund_id, action=action,
        before_data={'refund': before} if before is not None else None,
        after_data={'refund': snapshot(session, db, refund_id),
            'references': jsonable_encoder(safe_refs)}, correlation_id=correlation_id))
