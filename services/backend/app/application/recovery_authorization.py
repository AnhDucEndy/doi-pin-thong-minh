"""Staged foreign-object permit intent. No action, custody or settlement here."""
from datetime import datetime, timedelta
import hashlib
import json
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from fastapi.encoders import jsonable_encoder
from app.application import recovery as r
from app.domain.recovery import canonical_hash

PRE = 'PRE_ACTION_INSPECTION'


def refuse(code='RECONCILIATION_REQUIRED', status=409):
    raise r.DomainError(status, code)


def context(op, case, body):
    r.open_operation(op)
    if (op['protocol_version'] != '0.2' or op['purpose'] != 'RETURN_FOREIGN_OBJECT'
            or case['operation_id'] != op['id'] or body.context_hash != op['context_hash']):
        refuse('RECOVERY_CONTEXT_MISMATCH')


def human(session, db, swap, case, op, actor, body, source):
    successor = op['context'].get('reconciliation_only')
    stage = 'RECONCILIATION_INSPECTION' if successor else PRE
    if successor and body.stage != stage:
        refuse('RECOVERY_STAGE_CONFLICT')
    if body.stage == 'POST_ACTION_RECEIPT':
        from app.application.recovery_handover import human_post
        return human_post(session, db, swap, case, op, actor, body, source)
    audit_before = r.audit_snapshot(session, db, case)
    context(op, case, body)
    token = r.assets.get_row(session, db, 'auth_sessions', actor['session']['id'], lock=True)
    if token['revoked_at'] or token['expires_at'] <= r.utcnow():
        refuse('SESSION_REVOKED', 401)
    if swap['state'] not in ('REVIEW_REQUIRED', 'COMPENSATING'):
        refuse('STATE_CONFLICT')
    if (body.stage != stage or body.receipt_id is None or body.receipt_hash is None):
        refuse('RECOVERY_STAGE_CONFLICT')
    proof = r.assets.get_row(session, db, 'recovery_attestations', body.receipt_id)
    if (proof['operation_id'] != op['id'] or proof['stage'] != stage
            or proof['source_kind'] != 'SIMULATOR' or proof['payload_hash'] != body.receipt_hash):
        refuse('RECOVERY_STAGE_CONFLICT')
    if actor['user']['id'] != op['created_by' if source == 'TECHNICIAN' else 'customer_id']:
        refuse('FORBIDDEN', 403)
    confirmed = body.observation == 'CONFIRM' if source == 'TECHNICIAN' else body.confirm
    if successor:
        from app.application.recovery_reconciliation import current
        current(session,db,swap,case,op,proof['payload'])
    if source == 'TECHNICIAN' and body.actual_serial != proof['payload']['actual_serial']:
        refuse('EVIDENCE_REQUIRED', 422)
    table = db.table('recovery_attestations')
    if session.execute(select(table.c.id).where(table.c.operation_id == op['id'],
            table.c.stage == stage, table.c.source_kind == source)).first():
        refuse('RECOVERY_ATTESTATION_EXISTS')
    # Caller holds station -> users/resources -> exact actor session. Device
    # projections cannot change under that station mutex; read them only after
    # any session lock wait. Both PRE actors must use current authenticated proof.
    if not successor:
        device = r.assets.available_device(session, db, swap['station_id'])
        if (not device or not device['enabled'] or proof['device_id'] != device['id']
                or proof['source_boot'] != device['boot_id']):
            refuse()
        packet = proof['payload']
        event = r.assets.get_row(session, db, 'device_events', proof['source_event_id'])
        if (proof['payload_hash'] != canonical_hash(packet)
                or packet.get('context_hash') != op['context_hash']
                or packet.get('result') != 'OBSERVED' or packet.get('read_only') is not True
                or packet.get('actual_serial') != op['expected_serial']
                or event['device_id'] != device['id'] or event['boot_id'] != device['boot_id']
                or event['kind'] != 'SNAPSHOT' or not event['accepted'] or not event['processed_at']):
            refuse('EVIDENCE_REQUIRED', 422)
    now = r.utcnow()
    r.open_operation(op)
    if token['revoked_at'] or token['expires_at'] <= now:
        refuse('SESSION_REVOKED', 401)
    if not r.assets.fresh(proof['observed_at'], now, swap['policy_snapshot']):
        refuse('EVENT_STALE', 422)
    payload = {'stage': stage, 'receipt_id': str(proof['id']), 'receipt_hash': proof['payload_hash'],
        'context_hash': op['context_hash'], 'actual_serial': proof['payload']['actual_serial'],
        'confirm': confirmed, 'auth_session_id': str(actor['session']['id']), 'simulation_only': True}
    identity = uuid4()
    session.execute(insert(table).values(id=identity, event_id=uuid4(), operation_id=op['id'],
        stage=stage, reference_receipt_id=proof['id'], source_kind=source,
        actor_user_id=actor['user']['id'], observed_at=now, received_at=now,
        payload=payload, payload_hash=canonical_hash(payload)))
    case = r.change_case(session, db, case)
    r.audit(session, db, actor['user'], case, 'RECOVERY_REINSPECTION_ATTESTED' if successor else 'RECOVERY_PRE_ACTION_CONFIRMED',
            {'operation_id': op['id'], 'attestation_id': identity, 'confirmed': confirmed}, before=audit_before)
    return identity, case


def guards(session, db, swap, case, op, extra_session_ids=(), *, settled_receipt=None, successor=None):
    """All callers hold station/resource locks; nothing here calls HTTP."""
    decision_op = op if successor is None else successor
    if successor is not None and (settled_receipt is None or successor['supersedes_id'] != op['id']
            or not successor['context'].get('reconciliation_only') or op['consumed_at'] or op['cancelled_at']
            or r.utcnow() < op['expires_at']):
        refuse()
    r.open_operation(decision_op)
    if case['operation_id'] != decision_op['id'] or swap['state'] not in ('REVIEW_REQUIRED', 'COMPENSATING'):
        refuse('STATE_CONFLICT')
    operations = db.table('recovery_operations')
    if session.execute(select(operations.c.id).where(operations.c.station_id==op['station_id'],
            operations.c.id.not_in({op['id'], decision_op['id']}),operations.c.consumed_at.is_(None),operations.c.cancelled_at.is_(None))).first():
        refuse('RECOVERY_FENCE_CONFLICT')
    dev, snapshot, slots, times = r.current_snapshot(session, db, swap)
    table = db.table('recovery_attestations')
    rows = session.execute(select(table).where(table.c.operation_id == op['id'], table.c.stage == PRE)).mappings().all()
    proof = {p['source_kind']: p for p in rows}
    if set(proof) != {'SIMULATOR', 'TECHNICIAN', 'CUSTOMER'}:
        refuse('EVIDENCE_REQUIRED', 422)
    # Logout updates auth_sessions without taking a user row lock. Lock the exact
    # proof/current sessions too, in UUID order, so revocation cannot commit
    # between the proof check and authorization commit.
    token_ids = {UUID(proof[k]['payload']['auth_session_id']) for k in ('TECHNICIAN','CUSTOMER')}
    tokens = {identity:r.assets.get_row(session,db,'auth_sessions',identity,lock=True)
              for identity in sorted(token_ids | set(extra_session_ids))}
    inspection = proof['SIMULATOR']; packet = inspection['payload']
    if (inspection['device_id'] != dev['id'] or (successor is None and inspection['source_boot'] != dev['boot_id'])
            or packet.get('read_only') is not True or packet.get('effect_count_delta') != 0
            or packet.get('result') != 'OBSERVED' or packet.get('stage') != PRE
            or packet.get('context_hash') != op['context_hash']
            or packet.get('presenter') != {'serial': op['expected_serial'],
                'customer_id': str(swap['customer_id']), 'swap_id': str(swap['id'])}):
        refuse('RECOVERY_PRESENTER_UNVERIFIED', 422)
    for source, p in proof.items():
        if p['payload_hash'] != canonical_hash(p['payload']):
            refuse('EVIDENCE_REQUIRED', 422)
        # Settlement retains the original inspection as history. Only the
        # independently validated POST receipt/current snapshot are current proof.
        if settled_receipt is None:
            times.extend([p['observed_at'], p['received_at']])
        if source == 'SIMULATOR':
            continue
        expected = op['created_by'] if source == 'TECHNICIAN' else swap['customer_id']
        user = r.assets.get_row(session, db, 'users', expected)
        token = tokens[UUID(p['payload']['auth_session_id'])]
        if (p['actor_user_id'] != expected or user['role'] != source or user['state'] != 'ACTIVE'
                or token['user_id'] != expected or token['revoked_at'] or token['expires_at'] <= r.utcnow()):
            refuse('RECOVERY_ACTOR_UNAVAILABLE', 403)
        if source == 'TECHNICIAN':
            r.assets.scope(session, db, user, swap['station_id'])
        if (p['reference_receipt_id'] != inspection['id'] or p['payload']['confirm'] is not True
                or p['payload']['receipt_hash'] != inspection['payload_hash']):
            refuse('EVIDENCE_REQUIRED', 422)
    ret, supply = slots
    old = r.assets.get_row(session, db, 'batteries', swap['old_battery_id'])
    new = r.assets.get_row(session, db, 'batteries', swap['new_battery_id'])
    source_valid = (ret['observed_serial'] == op['expected_serial'] and ret['observed_present'])
    if settled_receipt is not None:
        source_valid = (ret['observed_serial'] is None and ret['observed_present'] is False)
        times.extend([settled_receipt['observed_at'], settled_receipt['received_at']])
    if (not source_valid
            or packet['actual_serial'] != op['expected_serial'] or packet['slot']['lock_released']
            or supply['observed_serial'] != new['serial'] or not supply['observed_present']
            or new['location_kind'] != 'COMPARTMENT' or new['compartment_id'] != supply['id']
            or new['holder_user_id'] is not None or old['location_kind'] != 'CUSTOMER'
            or old['holder_user_id'] != swap['customer_id'] or r.assets.pin_at(session, db, ret)):
        refuse('EVIDENCE_REQUIRED', 422)
    from app.application.payments import get
    payment = get(session, db, swap['id'])
    refunds = db.table('refunds'); holds = db.table('resource_reservations')
    held = session.execute(select(holds).where(holds.c.swap_id == swap['id'], holds.c.released_at.is_(None))).mappings().all()
    if (payment['state'] != 'SUCCEEDED' or not payment['verified_at'] or not swap['consented_at']
            or payment['amount_minor'] != swap['amount_minor'] or payment['currency'] != swap['currency']
            or session.execute(select(refunds.c.id).where(refunds.c.payment_id == payment['id'])).first()
            or len(held) != 3 or {h['compartment_id'] for h in held if h['compartment_id']} != {s['id'] for s in slots}
            or {h['battery_id'] for h in held if h['battery_id']} != {new['id']}):
        refuse()
    # Foreign exceptions are purpose-specific; never broaden quiet(). All device
    # history must match the durable inspection. Unresolved services block.
    if packet['service_entries']:
        refuse()  # No service closure proof protocol yet; fail closed, even terminal history.
    entries = {e['id']: e for e in packet['command_entries']}
    commands = db.table('device_commands')
    known = session.execute(select(commands).where(commands.c.device_id == dev['id'])).mappings().all()
    if set(entries) != {str(c['id']) for c in known if c['state'] != 'QUEUED'}:
        refuse()
    if any(c['state'] == 'QUEUED' for c in known):
        refuse()
    ledger = {x['command_id']: x['status'] for x in snapshot['payload']['command_ledger']}
    for c in known:
        entry = entries[str(c['id'])]
        try:
            body = json.loads(entry['body'])
        except (ValueError, TypeError):
            refuse()
        wire = {k: body[k] for k in ('id','device_id','swap_id','compartment_id','kind','expires_at','payload') if k in body}
        if (len(wire) != 7 or entry['hash'] != hashlib.sha256(json.dumps(wire, sort_keys=True).encode()).hexdigest()
                or any(wire[k] != str(c[k]) for k in ('id','device_id','swap_id','compartment_id','kind'))
                or wire['payload'] != c['payload'] or ledger.get(str(c['id'])) != entry['status']):
            refuse()
        try:
            if datetime.fromisoformat(wire['expires_at'].replace('Z','+00:00')) != c['expires_at']:
                refuse()
        except (ValueError, TypeError):
            refuse()
        if entry['status'] == 'NOT_EXECUTED' and entry['effects'] == 0:
            continue
        if not (entry['status'] == 'EXECUTED' and entry['effects'] == 1 and c['kind'] == 'OPEN_RETURN'
                and c['swap_id'] == swap['id'] and c['compartment_id'] == ret['id']
                and c['state'] in ('UNKNOWN', 'OBSERVED')):
            refuse()
        deadline = c['created_at'] + timedelta(seconds=swap['policy_snapshot']['physical_step_timeout_seconds'])
        if inspection['observed_at'] < deadline or snapshot['observed_at'] < deadline:
            refuse()
        events = [r.assets.get_row(session, db, 'device_events', UUID(e)) for e in packet['wrong_return_event_ids']]
        chain = sorted([e for e in events if e['command_id'] == c['id']], key=lambda e:e['seq'])
        if not chain or len({e['boot_id'] for e in chain}) != 1 or any(e['device_id'] != dev['id']
                or e['swap_id'] != swap['id'] or e['compartment_id'] != ret['id']
                or e['observed_at'] > inspection['observed_at'] for e in chain):
            refuse()
        # Wrong-return history is allowed only for this precise mismatch, never
        # unauthenticated/reordered/stale rejected input.
        if any(not e['processed_at'] or (not e['accepted'] and e['processing_error'] != 'PRESENCE_MISMATCH') for e in chain):
            refuse()
        stages = [e for e in chain if (e['kind']=='COMMAND_ACK' and e['payload'].get('result')=='ACCEPTED')
                  or e['kind'] in ('DOOR','PRESENCE')]
        if (len(stages) != 4 or [e['kind'] for e in stages] != ['COMMAND_ACK','DOOR','PRESENCE','DOOR']
                or stages[1]['payload']['door_state'] != 'OPEN'
                or any(not e['payload']['present'] or e['payload']['observed_serial'] != op['expected_serial'] for e in stages[2:])
                or stages[3]['payload']['door_state'] != 'CLOSED'):
            refuse()
    now = r.utcnow()
    r.open_operation(decision_op)
    if any(t['revoked_at'] or t['expires_at'] <= now for t in tokens.values()):
        refuse('RECOVERY_ACTOR_UNAVAILABLE', 403)
    if not all(r.assets.fresh(t, now, swap['policy_snapshot']) for t in times):
        refuse('EVENT_STALE', 422)
    return proof, dev, now


def issue(session, db, swap, case, op, actor, body):
    audit_before = r.audit_snapshot(session, db, case)
    if op['context'].get('reconciliation_only'):
        refuse('RECOVERY_STAGE_CONFLICT')
    context(op, case, body)
    if actor['user']['id'] != op['created_by']:
        refuse('FORBIDDEN', 403)
    table = db.table('recovery_action_authorizations')
    if session.execute(select(table.c.id).where(table.c.operation_id == op['id'])).first():
        refuse('RECOVERY_STAGE_CONFLICT')
    proof, dev, now = guards(session, db, swap, case, op, (actor['session']['id'],))
    r.authorize(session, db, actor, swap, write=True)
    p = proof['SIMULATOR']['payload']; identity = uuid4()
    payload = jsonable_encoder({'authorization_id':identity,'operation_id':op['id'],'context_hash':op['context_hash'],
        'inspection_id':proof['SIMULATOR']['id'],'inspection_hash':proof['SIMULATOR']['payload_hash'],
        'technician_attestation_id':proof['TECHNICIAN']['id'],'customer_attestation_id':proof['CUSTOMER']['id'],
        'device_id':dev['id'],'boot_id':dev['boot_id'],'ledger_id':p['ledger_id'],'fence_generation':p['fence_generation'],
        'command_digest':canonical_hash(p['command_entries']),'source_compartment_id':swap['return_compartment_id'],
        'actual_serial':op['expected_serial'],'recipient_id':swap['customer_id'],'destination':'CUSTOMER',
        'issued_at':now,'expires_at':op['expires_at'],'effect_allowed':False,'simulation_only':True})
    session.execute(insert(table).values(id=identity,operation_id=op['id'],context_hash=op['context_hash'],
        inspection_id=proof['SIMULATOR']['id'],technician_attestation_id=proof['TECHNICIAN']['id'],
        customer_attestation_id=proof['CUSTOMER']['id'],device_id=dev['id'],boot_id=dev['boot_id'],
        ledger_id=UUID(p['ledger_id']),fence_generation=p['fence_generation'],authorized_by=op['created_by'],
        issued_at=now,expires_at=op['expires_at'],authorization_hash=canonical_hash(payload),payload=payload))
    case = r.change_case(session, db, case)
    r.audit(session, db, actor['user'], case, 'RECOVERY_AUTHORIZATION_INTENT_CREATED', {'authorization_id':identity}, before=audit_before)
    return case


def acknowledge(session, db, dev, body, packet):
    permit = r.assets.get_row(session, db, 'recovery_action_authorizations', body.authorization_id)
    op = r.assets.get_row(session, db, 'recovery_operations', permit['operation_id'])
    if permit['device_id'] != dev['id'] or op['station_id'] != dev['station_id']:
        refuse('RECOVERY_CONTEXT_MISMATCH', 422)
    swap, case = r.lock_context(session, db, op['swap_id'])
    audit_before = r.audit_snapshot(session, db, case)
    context(op, case, body)
    if (permit['revoked_at'] or body.operation_id != op['id'] or body.authorization_hash != permit['authorization_hash']
            or body.boot_id != permit['boot_id'] or dev['boot_id'] != body.boot_id
            or body.ledger_id != permit['ledger_id'] or body.fence_generation != permit['fence_generation']):
        refuse('RECOVERY_FENCE_CONFLICT')
    _, _, now = guards(session, db, swap, case, op)
    if not (permit['issued_at'] <= body.observed_at <= now and r.assets.fresh(body.observed_at,now,swap['policy_snapshot'])):
        refuse('EVENT_STALE', 422)
    for name, boot, seq in [('recovery_attestations','source_boot','source_seq'),('recovery_authorization_acks','boot_id','seq')]:
        t = db.table(name)
        last = session.execute(select(t).where(t.c.device_id==dev['id'],t.c[boot]==body.boot_id).order_by(t.c[seq].desc()).limit(1)).mappings().first()
        if last and (body.seq <= last[seq] or body.observed_at <= last['observed_at']):
            refuse('EVENT_OUT_OF_ORDER',422)
    table = db.table('recovery_authorization_acks')
    if session.execute(select(table.c.id).where(table.c.authorization_id==permit['id'])).first():
        refuse('IDEMPOTENCY_CONFLICT')
    identity = uuid4()
    session.execute(insert(table).values(id=identity,authorization_id=permit['id'],event_id=body.event_id,
        device_id=dev['id'],boot_id=body.boot_id,seq=body.seq,observed_at=body.observed_at,
        received_at=now,payload_hash=canonical_hash(packet),payload=packet))
    r.audit(session,db,dev,case,'RECOVERY_AUTHORIZATION_ACKNOWLEDGED',{'authorization_id':permit['id'],'ack_id':identity,'effect_allowed':False}, before=audit_before)
    return {'id':str(identity),'accepted':True,'duplicate':False}
