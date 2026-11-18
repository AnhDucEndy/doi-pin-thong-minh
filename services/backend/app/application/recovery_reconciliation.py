"""Read-only successor to an expired foreign handover. Station locks cover every decision."""
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select, update

from app.application import recovery as r
from app.application import recovery_authorization as authorization
from app.application.recovery_closure import command_proof
from app.domain.recovery import canonical_hash

STAGE = 'RECONCILIATION_INSPECTION'
refuse = authorization.refuse


def check_order(session, db, dev, body):
    for name, boot, seq in [('recovery_attestations','source_boot','source_seq'),
            ('recovery_authorization_acks','boot_id','seq'),('recovery_closure_receipts','boot_id','seq')]:
        t = db.table(name)
        last = session.execute(select(t).where(t.c.device_id==dev['id'],t.c[boot]==body.boot_id)
                               .order_by(t.c[seq].desc()).limit(1)).mappings().first()
        if last and (body.seq<=last[seq] or body.observed_at<=last['observed_at']):
            refuse('EVENT_OUT_OF_ORDER',422)


def attested(session, db, op, stage):
    t = db.table('recovery_attestations')
    return {p['source_kind']:p for p in session.execute(select(t).where(t.c.operation_id==op['id'],
            t.c.stage==stage)).mappings()}


def begin(session, db, actor, swap, case, previous, statement, ttl):
    audit_before = r.audit_snapshot(session, db, case)
    from app.application.recovery_closure import intents
    if (previous['protocol_version']!='0.2' or previous['purpose']!='RETURN_FOREIGN_OBJECT'
            or previous['context'].get('reconciliation_only') or r.utcnow()<previous['expires_at']
            or previous['context_hash']!=statement.context_hash or case['operation_id']!=previous['id']
            or previous['consumed_at'] or previous['cancelled_at'] or intents(session,db,previous['id'])):
        refuse()
    if previous['created_by']!=actor['user']['id']:
        refuse('FORBIDDEN',403)
    permits = db.table('recovery_action_authorizations')
    permit = session.execute(select(permits).where(permits.c.operation_id==previous['id'])).mappings().first()
    if not permit:
        refuse()
    identity = uuid4()
    ctx = dict(previous['context'], operation_id=str(identity), predecessor_id=str(previous['id']),
        predecessor_context_hash=previous['context_hash'], reconciliation_only=True,
        base_case_version=case['version'], base_swap_version=swap['version'],
        predecessor_authorization_id=str(permit['id']), predecessor_authorization_hash=permit['authorization_hash'])
    now = r.utcnow()
    session.execute(insert(db.table('recovery_operations')).values(id=identity,protocol_version='0.2',
        **{k:previous[k] for k in ('case_id','swap_id','station_id','customer_id','purpose','created_by','expected_serial')},
        context=ctx,context_hash=canonical_hash(ctx),base_case_version=case['version'],base_swap_version=swap['version'],
        supersedes_id=previous['id'],created_at=now,expires_at=now+timedelta(seconds=ttl)))
    case = r.change_case(session,db,case,operation_id=identity)
    r.audit(session,db,actor['user'],case,'RECOVERY_REINSPECTION_REQUESTED',ctx, before=audit_before)
    return case


def current(session, db, swap, case, op, packet):
    r.open_operation(op)
    ctx = op['context']
    predecessor = r.operation_for(session,db,case,op['supersedes_id'])
    if (not ctx.get('reconciliation_only') or case['operation_id']!=op['id']
            or predecessor['consumed_at'] or predecessor['cancelled_at']
            or str(predecessor['id'])!=packet['predecessor_id'] or predecessor['context_hash']!=packet['predecessor_context_hash']
            or packet['context_hash']!=op['context_hash'] or packet['operation_id']!=str(op['id'])):
        refuse()
    dev, snapshot, slots, times = r.current_snapshot(session,db,swap)
    source = r.assets.get_row(session,db,'device_events',UUID(packet['snapshot_event_id']))
    if (source['device_id']!=dev['id'] or not source['accepted'] or not source['processed_at']
            or source['kind']!='SNAPSHOT' or source['boot_id']!=dev['boot_id'] or packet['boot_id']!=str(dev['boot_id'])
            or source['observed_at']>snapshot['observed_at']):
        refuse('EVIDENCE_REQUIRED',422)
    source_slot = next((s for s in source['payload']['slots'] if s['compartment_id']==str(slots[0]['id'])),None)
    if (not source_slot or packet['slot']['compartment_id']!=str(slots[0]['id']) or packet['slot']['lock_released']
            or packet['slot']['present'] or packet['slot']['observed_serial'] is not None or packet['slot']['door_state']!='CLOSED'
            or any(source_slot[k]!=packet['slot'][k] for k in ('present','observed_serial','door_state'))
            or slots[0]['observed_present'] or slots[0]['observed_serial'] is not None):
        refuse('EVIDENCE_REQUIRED',422)
    command_proof(session,db,dev,swap,snapshot,packet['command_entries'])
    pre = attested(session,db,predecessor,authorization.PRE)
    history = attested(session,db,predecessor,'POST_ACTION_RECEIPT')
    if any(p['payload'].get('confirm') is False for p in (*pre.values(),*history.values())):
        refuse()
    past = history.get('SIMULATOR')
    if not past or 'SIMULATOR' not in pre:
        refuse('EVIDENCE_REQUIRED',422)
    historical = past['payload']
    if (packet['historical_receipt']!=historical or past['payload_hash']!=canonical_hash(historical)
            or historical['authorization_id']!=ctx['predecessor_authorization_id']
            or historical['authorization_hash']!=ctx['predecessor_authorization_hash']
            or packet['ledger_id']!=historical['ledger_id'] or packet['fence_generation']!=historical['fence_generation']
            or packet['result']!='OBSERVED' or packet['actual_serial']!=op['expected_serial']
            or packet['recipient_id']!=str(swap['customer_id']) or packet['presenter']!=pre['SIMULATOR']['payload']['presenter']
            or packet['command_entries']!=pre['SIMULATOR']['payload']['command_entries']):
        refuse('EVIDENCE_REQUIRED',422)
    services = packet['service_entries']
    if (len(services)!=1 or services[0]['id']!=str(predecessor['id']) or services[0]['effects']!=1
            or services[0]['state']!='OBSERVED' or services[0]['context_hash']!=predecessor['context_hash']):
        refuse()
    from app.api.recovery_schemas import PostActionReceipt
    try:
        local = PostActionReceipt.model_validate_json(services[0]['observation']).model_dump(mode='json')
    except (ValueError,TypeError):
        refuse('EVIDENCE_REQUIRED',422)
    if local!=historical:
        refuse()
    from datetime import datetime
    observed = datetime.fromisoformat(packet['observed_at'])
    if not op['created_at']<=observed<=r.utcnow() or source['observed_at']>observed:
        refuse('EVENT_STALE',422)
    times.extend((source['observed_at'],source['received_at'],observed))
    if not all(r.assets.fresh(t,r.utcnow(),swap['policy_snapshot']) for t in times):
        refuse('EVENT_STALE',422)
    return dev, predecessor, snapshot, times


def receive(session, db, dev, body, packet):
    op = r.assets.get_row(session,db,'recovery_operations',body.operation_id)
    if op['station_id']!=dev['station_id'] or not op['context'].get('reconciliation_only'):
        refuse('RECOVERY_CONTEXT_MISMATCH',422)
    swap, case = r.lock_context(session,db,op['swap_id'])
    audit_before = r.audit_snapshot(session, db, case)
    current(session,db,swap,case,op,packet)
    check_order(session,db,dev,body)
    if 'SIMULATOR' in attested(session,db,op,STAGE):
        refuse('RECOVERY_ATTESTATION_EXISTS')
    identity = uuid4()
    session.execute(insert(db.table('recovery_attestations')).values(id=identity,event_id=body.event_id,
        operation_id=op['id'],stage=STAGE,source_kind='SIMULATOR',device_id=dev['id'],
        observed_at=body.observed_at,received_at=r.utcnow(),source_seq=body.seq,source_boot=body.boot_id,
        source_event_id=body.snapshot_event_id,payload=packet,payload_hash=canonical_hash(packet)))
    r.audit(session,db,dev,case,'RECOVERY_REINSPECTION_RECORDED',{'attestation_id':identity,'operation_id':op['id']}, before=audit_before)
    return {'id':str(identity),'accepted':True,'duplicate':False}


def settle(session, db, actor, swap, case, op, body):
    audit_before = r.audit_snapshot(session, db, case)
    if getattr(body,'operation_id',None)!=op['id'] or actor['user']['id']!=op['created_by']:
        refuse('RECOVERY_CONTEXT_MISMATCH')
    proof = attested(session,db,op,STAGE)
    if set(proof)!={'SIMULATOR','TECHNICIAN','CUSTOMER'}:
        refuse('EVIDENCE_REQUIRED',422)
    inspection = proof['SIMULATOR']
    _, previous, snapshot, times = current(session,db,swap,case,op,inspection['payload'])
    ids = {UUID(proof[k]['payload']['auth_session_id']) for k in ('CUSTOMER','TECHNICIAN')}
    ids.add(actor['session']['id'])
    # Use existing physical/financial guards, including original wrong-return
    # history. Only the successor is eligible to make a new decision.
    pre, _, _ = authorization.guards(session,db,swap,case,previous,ids,settled_receipt=inspection,successor=op)
    ids.update(UUID(pre[k]['payload']['auth_session_id']) for k in ('CUSTOMER','TECHNICIAN'))
    for source in ('TECHNICIAN','CUSTOMER'):
        row = proof[source]
        p = row['payload']
        who = op['created_by'] if source=='TECHNICIAN' else swap['customer_id']
        user = r.assets.get_row(session,db,'users',who)
        token = r.assets.get_row(session,db,'auth_sessions',UUID(p['auth_session_id']))
        if (user['role']!=source or user['state']!='ACTIVE' or token['user_id']!=who or row['actor_user_id']!=who):
            refuse('RECOVERY_ACTOR_UNAVAILABLE',403)
        if (p['confirm'] is not True or p['stage']!=STAGE or p['actual_serial']!=op['expected_serial']
                or row['reference_receipt_id']!=inspection['id'] or p['receipt_hash']!=inspection['payload_hash']
                or row['observed_at']<inspection['received_at'] or row['payload_hash']!=canonical_hash(p)):
            refuse('EVIDENCE_REQUIRED',422)
        times.extend((row['observed_at'],row['received_at']))
    tokens = [r.assets.get_row(session,db,'auth_sessions',i) for i in ids]
    user = r.authorize(session,db,actor,swap,write=True)
    now = r.utcnow()
    r.open_operation(op)
    if any(t['revoked_at'] or t['expires_at']<=now for t in tokens):
        refuse('RECOVERY_ACTOR_UNAVAILABLE',403)
    if not all(r.assets.fresh(t,now,swap['policy_snapshot']) for t in times):
        refuse('EVENT_STALE',422)
    operations = db.table('recovery_operations')
    rows = session.execute(update(operations).where(operations.c.id.in_([op['id'],previous['id']]),
        operations.c.consumed_at.is_(None),operations.c.cancelled_at.is_(None)).values(consumed_at=now))
    if rows.rowcount!=2:
        refuse()
    case = r.change_case(session,db,case,state='EVIDENCE_RECORDED',evidence_event_id=snapshot['id'],
                         resolution_note=body.resolution_note,assigned_to=user['id'])
    r.audit(session,db,user,case,'FOREIGN_OBJECT_RETURN_SETTLED',{'operation_id':op['id'],
        'predecessor_id':previous['id'],'receipt_event_id':inspection['payload']['historical_receipt']['event_id'],
        'attestation_ids':[p['id'] for p in proof.values()],'holds_released':False}, before=audit_before)
    return r.view(session,db,case)
