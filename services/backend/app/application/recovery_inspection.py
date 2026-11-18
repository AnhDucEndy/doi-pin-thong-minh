"""Authenticated, read-only P8-REC-0.2 receipt transport; never authorizes action."""
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select
from app.application import recovery as r
from app.domain.recovery import canonical_hash


def receive(session, db, actor, body):
    # Lock the authenticated station BEFORE looking up a client-provided operation.
    r.assets.station_lock(session, db, actor['station_id'])
    dev = r.assets.get_row(session, db, 'devices', actor['id'], lock=True)
    if not dev['enabled'] or dev['key_hash'] != actor['key_hash']:
        raise r.DomainError(403, 'DEVICE_DISABLED')
    inbox = db.table('recovery_inspection_inbox')
    packet = body.model_dump(mode='json')
    hashed = canonical_hash(packet)
    prior = session.execute(select(inbox).where(inbox.c.event_id == body.event_id)).mappings().first()
    if prior:
        if prior['device_id'] != dev['id'] or prior['payload_hash'] != hashed:
            raise r.DomainError(409, 'IDEMPOTENCY_CONFLICT')
        response = dict(prior['response'])
        if prior['status'] == 202:
            response['duplicate'] = True
        return JSONResponse(response, status_code=prior['status'])
    try:
        with session.begin_nested():
            # All staged writers share the monotonic device sequence. Include
            # closure receipts in ordering even for older inspection/ACK paths.
            closures = db.table('recovery_closure_receipts')
            latest = session.execute(select(closures).where(closures.c.device_id==dev['id'],
                closures.c.boot_id==body.boot_id).order_by(closures.c.seq.desc()).limit(1)).mappings().first()
            if latest and (body.seq<=latest['seq'] or body.observed_at<=latest['observed_at']):
                raise r.DomainError(422,'EVENT_OUT_OF_ORDER')
            if getattr(body,'message_kind',None)=='NO_EFFECT_CLOSURE':
                from app.application.recovery_closure import receive as close
                response = close(session,db,dev,body,packet)
            elif getattr(body,'stage',None)=='RECONCILIATION_INSPECTION':
                from app.application.recovery_reconciliation import receive as reinspect
                response = reinspect(session,db,dev,body,packet)
            elif getattr(body, 'message_kind', None) == 'AUTHORIZATION_ACK':
                from app.application.recovery_authorization import acknowledge
                response = acknowledge(session, db, dev, body, packet)
            elif getattr(body, 'stage', None) == 'POST_ACTION_RECEIPT':
                from app.application.recovery_handover import receive_receipt
                response = receive_receipt(session, db, dev, body, packet)
            else:
                response = accept(session, db, dev, body, packet)
        status = 202
    except r.DomainError as exc:
        if exc.status not in (409, 422):
            raise
        status, response = exc.status, {'code': exc.code, 'message': exc.message,
            'correlation_id':str(uuid4()), 'details':{}}
    # Rejection identity and body are durable too. A retry cannot rehabilitate
    # stale/mismatched evidence after the environment or payload changes.
    session.execute(insert(inbox).values(event_id=body.event_id, device_id=dev['id'],
        payload_hash=hashed, payload=packet, status=status, response=response))
    return JSONResponse(jsonable_encoder(response), status_code=status)


def accept(session, db, dev, body, packet):
    op = r.assets.get_row(session, db, 'recovery_operations', body.operation_id)
    if op['station_id'] != dev['station_id']:
        raise r.DomainError(422, 'RECOVERY_CONTEXT_MISMATCH')
    swap, case = r.lock_context(session, db, op['swap_id'])
    audit_before = r.audit_snapshot(session, db, case)
    r.open_operation(op)
    now = r.utcnow()
    if (op['protocol_version'] != '0.2' or op['purpose'] != 'RETURN_FOREIGN_OBJECT' or op['context'].get('reconciliation_only')
            or body.context_hash != op['context_hash'] or body.boot_id != dev['boot_id']
            or swap['state'] not in ('REVIEW_REQUIRED', 'COMPENSATING')):
        raise r.DomainError(422, 'RECOVERY_CONTEXT_MISMATCH')
    if not (op['created_at'] <= body.observed_at <= now
            and r.assets.fresh(body.observed_at, now, swap['policy_snapshot'])):
        raise r.DomainError(422, 'EVENT_STALE')
    table = db.table('recovery_attestations')
    last = session.execute(select(table).where(table.c.device_id==dev['id'],
        table.c.source_boot==body.boot_id).order_by(table.c.source_seq.desc()).limit(1)).mappings().first()
    if last and (body.seq <= last['source_seq'] or body.observed_at <= last['observed_at']):
        raise r.DomainError(422, 'EVENT_OUT_OF_ORDER')
    acknowledgments = db.table('recovery_authorization_acks')
    last_ack = session.execute(select(acknowledgments).where(acknowledgments.c.device_id==dev['id'],
        acknowledgments.c.boot_id==body.boot_id).order_by(acknowledgments.c.seq.desc()).limit(1)).mappings().first()
    if last_ack and (body.seq <= last_ack['seq'] or body.observed_at <= last_ack['observed_at']):
        raise r.DomainError(422, 'EVENT_OUT_OF_ORDER')
    if session.execute(select(table.c.id).where(table.c.event_id==body.event_id)).first():
        raise r.DomainError(409, 'IDEMPOTENCY_CONFLICT')
    snapshot = r.assets.get_row(session, db, 'device_events', body.snapshot_event_id)
    if (snapshot['device_id'] != dev['id'] or snapshot['boot_id'] != body.boot_id
            or snapshot['kind'] != 'SNAPSHOT' or not snapshot['accepted'] or not snapshot['processed_at']
            or snapshot['observed_at'] > body.observed_at
            or not r.assets.fresh(snapshot['observed_at'], now, swap['policy_snapshot'])):
        raise r.DomainError(422, 'EVIDENCE_REQUIRED')
    _, current, slots, times = r.current_snapshot(session, db, swap)
    slot = body.slot
    observed = next((s for s in snapshot['payload']['slots'] if s['compartment_id']==str(slot.compartment_id)), None)
    if (slot.compartment_id != swap['return_compartment_id'] or not observed
            or body.result != 'OBSERVED' or slot.door_state != 'CLOSED' or not slot.present
            or slot.observed_serial != body.actual_serial or body.actual_serial != op['expected_serial']
            or slots[0]['observed_serial'] != body.actual_serial or not slots[0]['observed_present']
            or any(observed[k] != getattr(slot, k) for k in ('door_state','present','observed_serial'))
            or not all(r.assets.fresh(t, now, swap['policy_snapshot']) for t in times)):
        raise r.DomainError(422, 'EVIDENCE_REQUIRED')
    # Record complete history, including UNKNOWN, without interpreting execution
    # as delivery or as permission to move anything. Authorization checks follow
    # in a separate phase; an unresolved entry is valid inspection information.
    entries = {str(e.id): e for e in body.command_entries}
    if len(entries) != len(body.command_entries):
        raise r.DomainError(422, 'EVIDENCE_REQUIRED')
    commands = db.table('device_commands')
    known = session.execute(select(commands).where(commands.c.device_id==dev['id'])).mappings().all()
    if any(c['state'] not in ('QUEUED','EXPIRED') and str(c['id']) not in entries for c in known):
        raise r.DomainError(422, 'EVIDENCE_REQUIRED')
    snapshot_ledger = {e['command_id']: e['status'] for e in snapshot['payload']['command_ledger']}
    if any(key not in entries or entries[key].status != value for key,value in snapshot_ledger.items()):
        raise r.DomainError(422, 'EVIDENCE_REQUIRED')
    for identity in body.wrong_return_event_ids:
        event = r.assets.get_row(session, db, 'device_events', identity)
        if (event['device_id'] != dev['id'] or event['swap_id'] != swap['id']
                or event['compartment_id'] != swap['return_compartment_id']
                or event['kind'] not in ('COMMAND_ACK','DOOR','PRESENCE')):
            raise r.DomainError(422, 'EVIDENCE_REQUIRED')
    presenter = body.presenter
    if presenter and (presenter.serial != body.actual_serial or presenter.swap_id != swap['id']
                      or presenter.customer_id != swap['customer_id']):
        raise r.DomainError(422, 'RECOVERY_PRESENTER_UNVERIFIED')
    identity = uuid4()
    session.execute(insert(table).values(id=identity,event_id=body.event_id,operation_id=op['id'],
        source_kind='SIMULATOR',stage=body.stage,device_id=dev['id'],source_boot=body.boot_id,
        source_seq=body.seq,observed_at=body.observed_at,received_at=now,payload=packet,
        payload_hash=canonical_hash(packet),source_event_id=snapshot['id']))
    r.audit(session, db, dev, case, 'RECOVERY_INSPECTION_RECORDED',
            {'operation_id':op['id'],'attestation_id':identity,'stage':body.stage,'effect_count_delta':0}, before=audit_before)
    return {'id':str(identity),'accepted':True,'duplicate':False}
