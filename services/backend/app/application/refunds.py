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


def protected_request(request,session,actor,key,payment_id,body):
    """B1b first intent. No provider dispatch or positive reconcile/retry."""
    from uuid import UUID
    from app.application.identity import idempotent
    from app.application import recovery as r, no_delivery as nd
    db=request.app.state.db;state={}
    def authorize():
        initial=assets.get_row(session,db,'payments',payment_id)
        swap=assets.get_row(session,db,'swap_transactions',initial['swap_id'])
        assets.station_lock(session,db,swap['station_id'])
        ops=db.table('recovery_operations')
        participants=set(session.scalars(select(ops.c.created_by).where(ops.c.station_id==swap['station_id'])))
        participants.update((actor['user']['id'],swap['customer_id']))
        station_locks(session,db,swap['station_id'],participants)
        swap=assets.get_row(session,db,'swap_transactions',swap['id'])
        charge=assets.get_row(session,db,'payments',payment_id,lock=True)
        refunds=db.table('refunds')
        existing=session.execute(select(refunds).where(refunds.c.payment_id==payment_id).with_for_update()).mappings().first()
        cases=db.table('recovery_cases')
        case=session.execute(select(cases).where(cases.c.swap_id==swap['id'])).mappings().first()
        certificates=db.table('refund_eligibility_certificates');proofs=db.table('recovery_attestations')
        operation_ids=list(session.scalars(select(ops.c.id).where(ops.c.swap_id==swap['id'])))
        # Append-only certificates have no UPDATE grant. The held station
        # mutex serializes issuance/revocation/redemption; UNIQUE/FKs protect
        # insertion. Do not ask PostgreSQL for an UPDATE-privileged row mark.
        certs=session.execute(select(certificates).where(certificates.c.operation_id.in_(operation_ids))
                             .order_by(certificates.c.id)).mappings().all()
        identities={actor['session']['id']}
        for p in session.execute(select(proofs).where(proofs.c.operation_id.in_(operation_ids),
                                  proofs.c.source_kind.in_(['TECHNICIAN','CUSTOMER']))).mappings():
            try:identities.add(UUID(p['payload']['auth_session_id']))
            except (KeyError,ValueError,TypeError):nd.refuse('REFUND_EVIDENCE_REQUIRED')
        identities.update(c['issuer_session_id'] for c in certs if c['issuer_session_id'] is not None)
        tokens={identity:assets.get_row(session,db,'auth_sessions',identity,lock=True) for identity in sorted(identities)}
        nd.authority(session,db,actor,swap,tokens,'ADMIN')
        state.update(swap=swap,charge=charge,case=case,certs=certs,tokens=tokens,existing=existing)
    return idempotent(session,db,actor['user']['id'],request.method+' '+request.url.path,key,
        body.model_dump(mode='json'),202,lambda:first_intent(session,db,actor,body,**state),authorize=authorize)


def first_intent(session,db,actor,body,swap,charge,case,certs,tokens,existing):
    from uuid import uuid4
    from fastapi.encoders import jsonable_encoder
    from sqlalchemy import insert,update
    from app.application import no_delivery as nd, recovery as r, refund_audit
    from app.domain.recovery import canonical_hash
    assets.version(charge,body.expected_version)
    if (charge['state']!='SUCCEEDED' or not charge['verified_at'] or not charge['provider_reference']
            or charge['currency']!='VND' or charge['amount_minor']!=swap['amount_minor']):
        raise DomainError(409,'STATE_CONFLICT')
    if existing:raise DomainError(409,'STATE_CONFLICT')
    cert=next((c for c in certs if case and c['operation_id']==case['operation_id']),None)
    if not case or not cert:raise DomainError(422,'REFUND_EVIDENCE_REQUIRED')
    op=nd.operation(session,db,swap,case,cert['operation_id'])
    revocations=db.table('refund_certificate_revocations');redemptions=db.table('refund_certificate_redemptions')
    if (cert['payment_id']!=charge['id'] or case['new_pin_delivered']!='NO' or case['state']!='EVIDENCE_RECORDED'
            or cert['payload_hash']!=canonical_hash(cert['payload']) or cert['payload']['case_version']!=case['version']
            or cert['payload']['swap_version']!=swap['version']
            or session.execute(select(revocations.c.id).where(revocations.c.certificate_id==cert['id'])).first()
            or session.execute(select(redemptions.c.certificate_id).where(redemptions.c.certificate_id==cert['id'])).first()):
        nd.refuse('REFUND_EVIDENCE_REQUIRED')
    if cert['issuer_session_id'] is None or cert['issued_by']!=op['created_by']:nd.refuse('REFUND_EVIDENCE_REQUIRED')
    nd.authority(session,db,{'user':{'id':cert['issued_by']},'session':{'id':cert['issuer_session_id']}},swap,tokens,'TECHNICIAN')
    nd.certificate_proof(session,db,swap,case,op,tokens)
    before=nd.audit_snapshot(session,db,case)
    nd.authority(session,db,actor,swap,tokens,'ADMIN')
    now=utcnow()
    if not cert['validated_at']<=now<cert['valid_until']:nd.refuse('REFUND_EVIDENCE_REQUIRED')
    refund_id,provider_key,attempt_id,outbox_id=[uuid4() for _ in range(4)]
    table=db.table('refunds')
    refund=session.execute(insert(table).values(id=refund_id,payment_id=charge['id'],requested_by=actor['user']['id'],
        provider_key=provider_key,state='REQUESTED',amount_minor=charge['amount_minor'],reason=body.reason)
        .returning(table)).mappings().one()
    session.execute(insert(db.table('refund_attempts')).values(id=attempt_id,refund_id=refund_id,generation=0,permit_id=None))
    session.execute(insert(redemptions).values(certificate_id=cert['id'],refund_id=refund_id,payment_id=charge['id'],redeemed_at=now))
    swaps=db.table('swap_transactions')
    session.execute(update(swaps).where(swaps.c.id==swap['id']).values(state='COMPENSATING',version=swap['version']+1))
    command=jsonable_encoder(dict(protocol_version='P8-REF-0.1',command='ATTEMPT_REFUND',payment_id=charge['id'],
        refund_id=refund_id,provider_key=provider_key,original_provider_reference=charge['provider_reference'],
        amount_minor=charge['amount_minor'],currency='VND',attempt_id=attempt_id,generation=0))
    # This is a durable registry/outbox record, NOT a financial dispatch claim.
    session.execute(insert(db.table('outbox_messages')).values(id=outbox_id,aggregate_type='refund',aggregate_id=refund_id,
        kind='REFUND',dedup_key='refund:'+str(refund_id)+':attempt:'+str(attempt_id),payload={
            'command':command,'eligibility':{'certificate_id':str(cert['id']),'operation_id':str(op['id'])}}))
    refund_audit.request_record(session,db,actor['user']['id'],refund_id,case,before,
        certificate_id=cert['id'],operation_id=op['id'],attempt_id=attempt_id,outbox_id=outbox_id)
    nd.audit(session,db,actor['user'],case,'ND_CERTIFICATE_REDEEMED',before,certificate_id=cert['id'],refund_id=refund_id)
    nd.authority(session,db,actor,swap,tokens,'ADMIN')
    nd.certificate_proof(session,db,swap,case,op,tokens)
    if utcnow()>=cert['valid_until']:nd.refuse('REFUND_EVIDENCE_REQUIRED')
    return dict(refund)
