"""ER-02 durable no-effect closure. No payment/custody/resource mutations."""
from datetime import datetime, timedelta
import hashlib
import json
from uuid import UUID, uuid4
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, insert, update

from app.application import recovery as r
from app.application.recovery_authorization import refuse
from app.domain.recovery import canonical_hash


def intents(session, db, operation_id):
    table = db.table('recovery_closure_intents')
    return session.execute(select(table).where(table.c.operation_id == operation_id)).mappings().first()


def current_commands(session, db, device):
    table = db.table('device_commands')
    return session.execute(select(table).where(table.c.device_id == device['id']).order_by(table.c.id)).mappings().all()


def command_proof(session, db, device, swap, snapshot, entries):
    known = current_commands(session, db, device)
    indexed = {e['id']:e for e in entries}
    projected = {e['command_id']:e['status'] for e in snapshot['payload']['command_ledger']}
    if len(indexed) != len(entries) or set(indexed) != {str(c['id']) for c in known} or set(projected) != set(indexed):
        refuse()
    for c in known:
        e = indexed[str(c['id'])]
        try:
            body = json.loads(e['body'])
            wire = {k:body[k] for k in ('id','device_id','swap_id','compartment_id','kind','expires_at','payload')}
            valid = (e['hash'] == hashlib.sha256(json.dumps(wire, sort_keys=True).encode()).hexdigest()
                and all(wire[k] == str(c[k]) for k in ('id','device_id','swap_id','compartment_id','kind'))
                and wire['payload'] == c['payload'] and datetime.fromisoformat(wire['expires_at'].replace('Z','+00:00')) == c['expires_at'])
        except (KeyError, TypeError, ValueError):
            valid = False
        if (not valid or projected[str(c['id'])] != e['status']
                or (e['status'],e['effects']) not in (('EXECUTED',1),('NOT_EXECUTED',0))
                or c['state'] not in ('UNKNOWN','OBSERVED','REJECTED','EXPIRED')
                or snapshot['observed_at'] < c['created_at'] + timedelta(seconds=swap['policy_snapshot']['physical_step_timeout_seconds'])):
            refuse()
    return known


def issue(session, db, actor, swap, case, op, body):
    audit_before = r.audit_snapshot(session, db, case)
    if (op['protocol_version'] != '0.2' or op['context'].get('reconciliation_only')
            or op['consumed_at'] or op['cancelled_at'] or case['operation_id'] != op['id']
            or actor['user']['id'] != op['created_by'] or body.context_hash != op['context_hash']):
        refuse('RECOVERY_CONTEXT_MISMATCH')
    if r.utcnow() < op['expires_at'] or intents(session, db, op['id']):
        refuse('RECOVERY_STAGE_CONFLICT')
    token = r.assets.get_row(session, db, 'auth_sessions', actor['session']['id'], lock=True)
    user = r.authorize(session, db, actor, swap, write=True)
    t = db.table('recovery_attestations')
    proof = session.execute(select(t).where(t.c.operation_id == op['id'],t.c.stage == 'PRE_ACTION_INSPECTION',t.c.source_kind=='SIMULATOR')).mappings().first()
    if not proof or session.execute(select(t.c.id).where(t.c.operation_id==op['id'],t.c.stage=='POST_ACTION_RECEIPT')).first():
        refuse()
    dev, snapshot, _, times = r.current_snapshot(session, db, swap)
    if proof['device_id'] != dev['id']:
        refuse()
    # The local proof may be historical, but the command set and projection must
    # still agree. Closure receipt will independently prove the durable interlock.
    known = command_proof(session, db, dev, swap, snapshot, proof['payload']['command_entries'])
    if proof['payload']['service_entries']:
        refuse()
    now = r.utcnow()
    if token['revoked_at'] or token['expires_at'] <= now or not all(r.assets.fresh(t,now,swap['policy_snapshot']) for t in times):
        refuse('EVENT_STALE',422)
    identity = uuid4()
    payload = jsonable_encoder({'closure_id':identity,'operation_id':op['id'],'context_hash':op['context_hash'],
        'case_version':case['version']+1,
        'station_id':op['station_id'],'device_id':dev['id'],'ledger_id':proof['payload']['ledger_id'],
        'inspection_event_id':proof['event_id'], 'actual_slot':proof['payload']['slot'],
        'fence_generation':proof['payload']['fence_generation'],'command_ids':[str(c['id']) for c in known]})
    session.execute(insert(db.table('recovery_closure_intents')).values(id=identity,operation_id=op['id'],
        created_by=user['id'],auth_session_id=token['id'],created_at=now,payload=payload,payload_hash=canonical_hash(payload)))
    case = r.change_case(session,db,case)
    r.audit(session,db,user,case,'RECOVERY_NO_EFFECT_CLOSURE_REQUESTED',{'closure_id':identity,'operation_id':op['id']}, before=audit_before)
    return case


def tasks(session, db, device):
    i, o, receipts = [db.table(n) for n in ('recovery_closure_intents','recovery_operations','recovery_closure_receipts')]
    rows = session.execute(select(i).join(o,i.c.operation_id==o.c.id).where(o.c.station_id==device['station_id'])).mappings().all()
    result = []
    for row in rows:
        receipt = session.execute(select(receipts).where(receipts.c.closure_id==row['id'])).mappings().first()
        if not receipt:
            operation = r.assets.get_row(session,db,'recovery_operations',row['operation_id'])
            swap,case = r.lock_context(session,db,operation['swap_id'])
            if case['operation_id']!=operation['id'] or case['version']!=row['payload']['case_version']:
                continue
            user = r.assets.get_row(session,db,'users',row['created_by'])
            token = r.assets.get_row(session,db,'auth_sessions',row['auth_session_id'])
            try:
                r.authorize(session,db,{'user':user,'session':token},swap,write=True)
            except r.DomainError:
                continue
        result.append({'protocol_version':'0.2','task_kind':'CLOSURE_COMMITTED' if receipt else 'CLOSE_NO_EFFECT',
            'closure_id':row['id'],'operation_id':row['operation_id'],'context_hash':row['payload']['context_hash'],
            'station_id':device['station_id'],'payload':row['payload'],'payload_hash':row['payload_hash'],
            'receipt_hash':receipt['payload_hash'] if receipt else None,'effect_allowed':False,'simulation_only':True})
    return result


def receive(session, db, dev, body, packet):
    intent = r.assets.get_row(session,db,'recovery_closure_intents',body.closure_id)
    op = r.assets.get_row(session,db,'recovery_operations',intent['operation_id'])
    if op['station_id'] != dev['station_id']:
        refuse('RECOVERY_CONTEXT_MISMATCH',422)
    swap, case = r.lock_context(session,db,op['swap_id'])
    audit_before = r.audit_snapshot(session, db, case)
    p = intent['payload']
    r.assets.version(case,p['case_version'])
    if (swap['state'] not in ('REVIEW_REQUIRED','COMPENSATING') or case['state']=='RESOLVED'
            or op['consumed_at'] or op['cancelled_at'] or case['operation_id'] != op['id']
            or body.operation_id!=op['id'] or body.context_hash!=op['context_hash']
            or body.closure_hash!=intent['payload_hash'] or canonical_hash(p)!=intent['payload_hash']
            or body.ledger_id!=UUID(p['ledger_id']) or body.fence_generation!=p['fence_generation']
            or str(body.inspection_event_id)!=p['inspection_event_id'] or packet['actual_slot']!=p['actual_slot']
            or body.boot_id!=dev['boot_id'] or body.service_entries
            or sorted(map(str,body.denied_command_ids)) != sorted(p['command_ids'])):
        refuse()
    token = r.assets.get_row(session,db,'auth_sessions',intent['auth_session_id'],lock=True)
    user = r.assets.get_row(session,db,'users',intent['created_by'])
    r.authorize(session,db,{'user':user,'session':token},swap,write=True)
    _, snapshot, _, times = r.current_snapshot(session,db,swap)
    source = r.assets.get_row(session,db,'device_events',body.snapshot_event_id)
    observed = next((s for s in snapshot['payload']['slots'] if s['compartment_id']==str(swap['return_compartment_id'])), None)
    if (not observed or any(observed[k]!=packet['actual_slot'][k] for k in ('present','observed_serial','door_state'))
            or source['device_id']!=dev['id'] or source['kind']!='SNAPSHOT' or not source['accepted']
            or not source['processed_at'] or source['payload']['command_ledger']!=snapshot['payload']['command_ledger']
            or next((s for s in source['payload']['slots'] if s['compartment_id']==str(swap['return_compartment_id'])),None)!=observed
            or source['boot_id']!=body.boot_id
            or source['observed_at']>body.observed_at or body.observed_at<intent['created_at']):
        refuse('EVIDENCE_REQUIRED',422)
    known = command_proof(session,db,dev,swap,snapshot,packet['command_entries'])
    if sorted(str(c['id']) for c in known)!=sorted(p['command_ids']):
        refuse()
    t = db.table('recovery_attestations')
    if session.execute(select(t.c.id).where(t.c.operation_id==op['id'],t.c.stage=='POST_ACTION_RECEIPT')).first():
        refuse()
    now = r.utcnow()
    if token['expires_at']<=now or token['revoked_at']:
        refuse('SESSION_REVOKED',401)
    if body.observed_at>now or not all(r.assets.fresh(t,now,swap['policy_snapshot']) for t in times+[source['observed_at'],body.observed_at]):
        refuse('EVENT_STALE',422)
    from app.application.recovery_reconciliation import check_order
    check_order(session,db,dev,body)
    identity = uuid4()
    session.execute(insert(db.table('recovery_closure_receipts')).values(id=identity,closure_id=intent['id'],
        event_id=body.event_id,device_id=dev['id'],boot_id=body.boot_id,seq=body.seq,
        observed_at=body.observed_at,received_at=now,payload=packet,payload_hash=canonical_hash(packet)))
    session.execute(update(db.table('recovery_operations')).where(db.table('recovery_operations').c.id==op['id']).values(cancelled_at=now))
    case = r.change_case(session,db,case)
    r.audit(session,db,user,case,'RECOVERY_NO_EFFECT_CLOSED',{'closure_id':intent['id'],'receipt_id':identity,
        'operation_id':op['id'],'custody_changed':False,'holds_released':False}, before=audit_before)
    return {'id':str(identity),'accepted':True,'duplicate':False}
