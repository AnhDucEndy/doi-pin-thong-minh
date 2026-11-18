"""Explicit activation and storage of physical history; never settles custody."""
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy import insert, select
from app.application import recovery as r, recovery_authorization as authorization
from app.domain.recovery import canonical_hash


def human_post(session, db, swap, case, op, actor, body, source):
    """Record a separate person's statement; never infer settlement or ownership."""
    audit_before = r.audit_snapshot(session, db, case)
    authorization.context(op, case, body)
    user = r.assets.get_row(session, db, 'users', actor['user']['id'])
    token = r.assets.get_row(session, db, 'auth_sessions', actor['session']['id'], lock=True)
    now = r.utcnow()
    if user['state'] != 'ACTIVE' or token['revoked_at'] or token['expires_at'] <= now:
        authorization.refuse('SESSION_REVOKED', 401)
    if user['role'] != source or user['id'] != op['created_by' if source=='TECHNICIAN' else 'customer_id']:
        authorization.refuse('FORBIDDEN', 403)
    if source=='TECHNICIAN':
        r.assets.scope(session, db, user, swap['station_id'])
    if swap['state'] not in ('REVIEW_REQUIRED','COMPENSATING'):
        authorization.refuse('STATE_CONFLICT')
    if body.receipt_id is None or body.receipt_hash is None:
        authorization.refuse('RECOVERY_STAGE_CONFLICT')
    proof = r.assets.get_row(session, db, 'recovery_attestations', body.receipt_id)
    p = proof['payload']
    if (proof['operation_id']!=op['id'] or proof['source_kind']!='SIMULATOR'
            or proof['stage']!='POST_ACTION_RECEIPT' or proof['payload_hash']!=body.receipt_hash
            or proof['payload_hash']!=canonical_hash(p) or p['context_hash']!=op['context_hash']
            or p['actual_serial']!=op['expected_serial'] or p['recipient_id']!=str(op['customer_id'])
            or p['result']!='OBSERVED' or p['effect_count_delta']!=1):
        authorization.refuse('RECOVERY_STAGE_CONFLICT')
    if source=='TECHNICIAN' and body.actual_serial!=p['actual_serial']:
        authorization.refuse('EVIDENCE_REQUIRED',422)
    dev, snapshot, slots, times = r.current_snapshot(session, db, swap)
    new = r.assets.get_row(session, db, 'batteries', swap['new_battery_id'])
    intent = r.assets.get_row(session, db, 'recovery_action_authorizations', UUID(p['authorization_id']))
    command_table=db.table('device_commands')
    commands=session.execute(select(command_table).where(command_table.c.device_id==dev['id'])).mappings().all()
    ledger={e['command_id']:e['status'] for e in snapshot['payload']['command_ledger']}
    if (dev['id']!=proof['device_id'] or dev['boot_id']!=proof['source_boot']
            or snapshot['observed_at']<proof['observed_at'] or slots[0]['observed_present']
            or slots[0]['observed_serial'] is not None or not slots[1]['observed_present']
            or slots[1]['observed_serial']!=new['serial']
            or any(c['state'] not in ('UNKNOWN','OBSERVED','REJECTED','EXPIRED') for c in commands)
            or ledger!={e['command_id']:e['status'] for e in r.assets.get_row(session,db,'device_events',proof['source_event_id'])['payload']['command_ledger']}
            or intent['operation_id']!=op['id']):
        authorization.refuse('RECONCILIATION_REQUIRED')
    table=db.table('recovery_attestations')
    if session.execute(select(table.c.id).where(table.c.operation_id==op['id'],
            table.c.stage=='POST_ACTION_RECEIPT',table.c.source_kind==source)).first():
        authorization.refuse('RECOVERY_ATTESTATION_EXISTS')
    now=r.utcnow(); r.open_operation(op)
    if token['expires_at']<=now:
        authorization.refuse('SESSION_REVOKED',401)
    if (not proof['received_at']<=now
            or not all(r.assets.fresh(t,now,swap['policy_snapshot']) for t in times+[proof['observed_at'],proof['received_at']])):
        authorization.refuse('EVENT_STALE',422)
    confirmed=body.observation=='CONFIRM' if source=='TECHNICIAN' else body.confirm
    payload={'stage':'POST_ACTION_RECEIPT','receipt_id':str(proof['id']),'receipt_hash':proof['payload_hash'],
        'context_hash':op['context_hash'],'actual_serial':p['actual_serial'],'recipient_id':p['recipient_id'],
        'confirm':confirmed,'auth_session_id':str(token['id']),'simulation_only':True}
    identity=uuid4()
    session.execute(insert(table).values(id=identity,event_id=uuid4(),operation_id=op['id'],
        stage='POST_ACTION_RECEIPT',reference_receipt_id=proof['id'],source_kind=source,
        actor_user_id=user['id'],observed_at=now,received_at=now,payload=payload,payload_hash=canonical_hash(payload)))
    case=r.change_case(session,db,case)
    r.audit(session,db,user,case,'RECOVERY_POST_ACTION_CONFIRMED',
        {'operation_id':op['id'],'attestation_id':identity,'receipt_id':proof['id'],'source_kind':source,'confirmed':confirmed}, before=audit_before)
    return identity,case


def activate(session, db, swap, case, op, actor, body):
    audit_before = r.audit_snapshot(session, db, case)
    authorization.context(op, case, body)
    if actor['user']['id'] != op['created_by']:
        authorization.refuse('FORBIDDEN', 403)
    intent = r.assets.get_row(session, db, 'recovery_action_authorizations', body.authorization_id)
    ack = r.assets.get_row(session, db, 'recovery_authorization_acks', body.acknowledgment_id)
    if (intent['operation_id'] != op['id'] or ack['authorization_id'] != intent['id']
            or intent['revoked_at'] or intent['context_hash'] != op['context_hash']):
        authorization.refuse('RECOVERY_CONTEXT_MISMATCH')
    table = db.table('recovery_action_activations')
    if session.execute(select(table.c.id).where(table.c.operation_id == op['id'])).first():
        authorization.refuse('RECOVERY_STAGE_CONFLICT')
    proof, dev, now = authorization.guards(session, db, swap, case, op, (actor['session']['id'],))
    r.authorize(session, db, actor, swap, write=True)
    if (dev['id'] != intent['device_id'] or dev['boot_id'] != intent['boot_id']
            or ack['boot_id'] != intent['boot_id']
            or not r.assets.fresh(ack['observed_at'], now, swap['policy_snapshot'])):
        authorization.refuse('RECOVERY_FENCE_CONFLICT')
    identity = uuid4()
    _, _, _, snapshot_times = r.current_snapshot(session, db, swap)
    proof_until = min(snapshot_times + [p['observed_at'] for p in proof.values()]) + timedelta(seconds=swap['policy_snapshot']['telemetry_stale_seconds'])
    payload = {**intent['payload'], 'activation_id':str(identity), 'authorization_hash':intent['authorization_hash'],
        'acknowledgment_id':str(ack['id']), 'acknowledgment_event_id':str(ack['event_id']),
        'acknowledgment_hash':ack['payload_hash'], 'activated_by':str(actor['user']['id']),
        'activation_issued_at':now.isoformat(), 'proof_valid_until':proof_until.isoformat(), 'effect_allowed':True}
    session.execute(insert(table).values(id=identity, authorization_id=intent['id'], acknowledgment_id=ack['id'],
        operation_id=op['id'], activated_by=actor['user']['id'], issued_at=now,
        expires_at=intent['expires_at'], payload=payload, payload_hash=canonical_hash(payload)))
    case = r.change_case(session, db, case)
    r.audit(session, db, actor['user'], case, 'RECOVERY_ACTION_ACTIVATED',
            {'activation_id':identity, 'authorization_id':intent['id'], 'acknowledgment_id':ack['id']}, before=audit_before)
    return case


def action_task(session, db, swap, op, intent, activation):
    """Only live, unconsumed scoped action; GET never creates or renews permission."""
    attestations = db.table('recovery_attestations')
    if session.execute(select(attestations.c.id).where(attestations.c.operation_id == op['id'],
            attestations.c.stage == 'POST_ACTION_RECEIPT')).first():
        return None
    return {**op['context'], 'protocol_version':'0.2','task_kind':'ACTION',
        'context_hash':op['context_hash'],'expires_at':op['expires_at'],'simulation_only':True,
        'authorization_id':intent['id'],'authorization_hash':intent['authorization_hash'],
        'activation_id':activation['id'],'activation_hash':activation['payload_hash'],
        'activation_payload':activation['payload'],'effect_allowed':True}


def receive_receipt(session, db, dev, body, packet):
    """Accept authenticated historical evidence even after TTL/reboot, not current proof.

    This path deliberately does NOT run pre-action guards after the object moved.
    It checks the immutable grant, original effect window and accepted source event.
    Human POST confirmations and settlement remain disabled.
    """
    activation = r.assets.get_row(session, db, 'recovery_action_activations', body.activation_id)
    intent = r.assets.get_row(session, db, 'recovery_action_authorizations', activation['authorization_id'])
    op = r.assets.get_row(session, db, 'recovery_operations', activation['operation_id'])
    if dev['id'] != intent['device_id'] or op['station_id'] != dev['station_id']:
        authorization.refuse('RECOVERY_CONTEXT_MISMATCH',422)
    swap, case = r.lock_context(session, db, op['swap_id'])
    audit_before = r.audit_snapshot(session, db, case)
    if (body.operation_id != op['id'] or body.context_hash != op['context_hash']
            or body.authorization_id != intent['id'] or body.authorization_hash != intent['authorization_hash']
            or body.activation_hash != activation['payload_hash'] or body.boot_id != intent['boot_id']
            or body.ledger_id != intent['ledger_id'] or body.fence_generation != intent['fence_generation']
            or body.actual_serial != op['expected_serial'] or body.recipient_id != op['customer_id']
            or body.source_compartment_id != swap['return_compartment_id']
            or body.command_digest != intent['payload']['command_digest']):
        authorization.refuse('RECOVERY_CONTEXT_MISMATCH',422)
    now = r.utcnow()
    if not (activation['issued_at'] <= body.effect_started_at <= body.effect_completed_at
            <= body.observed_at <= now and body.effect_completed_at < activation['expires_at']
            and body.effect_completed_at <= datetime.fromisoformat(activation['payload']['proof_valid_until'])):
        authorization.refuse('EVENT_STALE',422)
    source = r.assets.get_row(session, db, 'device_events', body.snapshot_event_id)
    slots = source['payload'].get('slots',[])
    ret = next((s for s in slots if s['compartment_id']==str(body.source_compartment_id)),None)
    if (source['kind'] != 'SNAPSHOT' or source['device_id'] != dev['id'] or source['boot_id'] != body.boot_id
            or not source['accepted'] or not source['processed_at']
            or not body.effect_started_at <= source['observed_at'] <= body.effect_completed_at
            or not ret or ret['present'] or ret['observed_serial'] is not None or ret['door_state']!='CLOSED'):
        authorization.refuse('EVIDENCE_REQUIRED',422)
    expected_entry = {'operation_id':str(op['id']),'activation_id':str(activation['id']),
        'authorization_id':str(intent['id']),'context_hash':op['context_hash'],
        'state':'OBSERVED','effects':1,'actual_serial':body.actual_serial,
        'recipient_id':str(body.recipient_id),'source_compartment_id':str(body.source_compartment_id),
        'destination':'CUSTOMER','boot_id':str(body.boot_id),
        'effect_started_at':body.effect_started_at.isoformat(),'effect_completed_at':body.effect_completed_at.isoformat()}
    if body.service_entry != expected_entry or canonical_hash(body.service_entry)!=body.service_entry_hash:
        authorization.refuse('EVIDENCE_REQUIRED',422)
    table = db.table('recovery_attestations')
    if session.execute(select(table.c.id).where(table.c.operation_id==op['id'],table.c.stage=='POST_ACTION_RECEIPT',
            table.c.source_kind=='SIMULATOR')).first():
        authorization.refuse('IDEMPOTENCY_CONFLICT')
    for name, boot, seq in [('recovery_attestations','source_boot','source_seq'),('recovery_authorization_acks','boot_id','seq')]:
        t=db.table(name)
        last=session.execute(select(t).where(t.c.device_id==dev['id'],t.c[boot]==body.boot_id)
                             .order_by(t.c[seq].desc()).limit(1)).mappings().first()
        if last and (body.seq<=last[seq] or body.observed_at<=last['observed_at']):
            authorization.refuse('EVENT_OUT_OF_ORDER',422)
    identity=uuid4()
    session.execute(insert(table).values(id=identity,event_id=body.event_id,operation_id=op['id'],
        source_kind='SIMULATOR',stage='POST_ACTION_RECEIPT',device_id=dev['id'],
        source_boot=body.boot_id,source_seq=body.seq,observed_at=body.observed_at,received_at=now,
        payload=packet,payload_hash=canonical_hash(packet),source_event_id=source['id']))
    r.audit(session,db,dev,case,'RECOVERY_POST_ACTION_RECEIPT_STORED',
        {'operation_id':op['id'],'activation_id':activation['id'],'attestation_id':identity,
         'settled':False,'historical':body.boot_id!=dev['boot_id'] or now>=op['expires_at']
             or not r.assets.fresh(body.observed_at,now,swap['policy_snapshot'])}, before=audit_before)
    return {'id':str(identity),'accepted':True,'duplicate':False}
