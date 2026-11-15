"""P8-REC-0.2 foreign-object settlement; never settles network-pin custody."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from app.application import recovery as r, recovery_authorization as a
from app.domain.recovery import canonical_hash


def settle_foreign(session, db, actor, swap, case, op, body):
    # Caller holds station -> sorted users -> swap/resources and case version.
    audit_before = r.audit_snapshot(session, db, case)
    r.open_operation(op)
    if getattr(body, 'operation_id', None) != op['id']:
        a.refuse('RECOVERY_STAGE_CONFLICT')
    if (op['purpose'] != 'RETURN_FOREIGN_OBJECT' or case['operation_id'] != op['id']
            or actor['user']['id'] != op['created_by']):
        a.refuse('RECOVERY_CONTEXT_MISMATCH')
    attest = db.table('recovery_attestations')
    rows = session.execute(select(attest).where(attest.c.operation_id == op['id'],
        attest.c.stage == 'POST_ACTION_RECEIPT')).mappings().all()
    post = {p['source_kind']: p for p in rows}
    permits = db.table('recovery_action_authorizations')
    intent = session.execute(select(permits).where(permits.c.operation_id == op['id'])).mappings().first()
    acts = db.table('recovery_action_activations')
    activation = session.execute(select(acts).where(acts.c.operation_id == op['id'])).mappings().first()
    if not intent or not activation or intent['revoked_at']:
        a.refuse()
    if set(post) != {'SIMULATOR', 'TECHNICIAN', 'CUSTOMER'}:
        a.refuse('EVIDENCE_REQUIRED', 422)
    receipt = post['SIMULATOR']; packet = receipt['payload']
    ack = r.assets.get_row(session, db, 'recovery_authorization_acks', activation['acknowledgment_id'])
    for record, key in ((intent, 'authorization_hash'), (activation, 'payload_hash'), (ack, 'payload_hash')):
        if record[key] != canonical_hash(record['payload']):
            a.refuse('EVIDENCE_REQUIRED', 422)
    if (activation['authorization_id'] != intent['id'] or ack['authorization_id'] != intent['id']
            or activation['activated_by'] != op['created_by'] or intent['context_hash'] != op['context_hash']
            or intent['expires_at'] != op['expires_at'] or activation['expires_at'] != op['expires_at']
            or activation['payload']['effect_allowed'] is not True
            or activation['payload']['acknowledgment_hash'] != ack['payload_hash']
            or activation['payload']['authorization_hash'] != intent['authorization_hash']):
        a.refuse()
    if (packet['authorization_id'] != str(intent['id']) or packet['authorization_hash'] != intent['authorization_hash']
            or packet['activation_id'] != str(activation['id']) or packet['activation_hash'] != activation['payload_hash']
            or packet['operation_id'] != str(op['id']) or packet['context_hash'] != op['context_hash']
            or packet['stage'] != 'POST_ACTION_RECEIPT' or packet['result'] != 'OBSERVED'
            or packet['actual_serial'] != op['expected_serial'] or packet['recipient_id'] != str(op['customer_id'])
            or packet['source_compartment_id'] != str(swap['return_compartment_id'])
            or packet['ledger_id'] != str(intent['ledger_id']) or packet['fence_generation'] != intent['fence_generation']
            or packet['command_digest'] != intent['payload']['command_digest']
            or packet['effect_count_delta'] != 1 or receipt['source_boot'] != intent['boot_id']):
        a.refuse('EVIDENCE_REQUIRED', 422)
    start, end = [datetime.fromisoformat(packet[k]) for k in ('effect_started_at', 'effect_completed_at')]
    if not (intent['issued_at'] <= ack['observed_at'] <= activation['issued_at'] <= start <= end
            <= receipt['observed_at'] <= receipt['received_at'] and end < op['expires_at']
            and end <= datetime.fromisoformat(activation['payload']['proof_valid_until'])):
        a.refuse('EVIDENCE_REQUIRED', 422)
    expected_entry = {'operation_id':str(op['id']), 'activation_id':str(activation['id']),
        'authorization_id':str(intent['id']), 'context_hash':op['context_hash'], 'state':'OBSERVED',
        'effects':1, 'actual_serial':op['expected_serial'], 'recipient_id':str(op['customer_id']),
        'source_compartment_id':str(swap['return_compartment_id']), 'destination':'CUSTOMER',
        'boot_id':str(intent['boot_id']), 'effect_started_at':start.isoformat(), 'effect_completed_at':end.isoformat()}
    if packet['service_entry'] != expected_entry or packet['service_entry_hash'] != canonical_hash(expected_entry):
        a.refuse('EVIDENCE_REQUIRED', 422)
    # Lock ALL referenced sessions in one sorted pass, including PRE witnesses,
    # before any actor revalidation (logout does not use the station mutex).
    token_ids = {UUID(post[k]['payload']['auth_session_id']) for k in ('TECHNICIAN', 'CUSTOMER')}
    token_ids.add(actor['session']['id'])
    pre, dev, _ = a.guards(session, db, swap, case, op, token_ids, settled_receipt=receipt)
    if (intent['inspection_id'] != pre['SIMULATOR']['id']
            or intent['technician_attestation_id'] != pre['TECHNICIAN']['id']
            or intent['customer_attestation_id'] != pre['CUSTOMER']['id']
            or intent['payload']['inspection_hash'] != pre['SIMULATOR']['payload_hash']
            or intent['ledger_id'] != UUID(pre['SIMULATOR']['payload']['ledger_id'])
            or intent['fence_generation'] != pre['SIMULATOR']['payload']['fence_generation']
            or intent['payload']['command_digest'] != canonical_hash(pre['SIMULATOR']['payload']['command_entries'])):
        a.refuse()
    dev, snapshot, slots, times = r.current_snapshot(session, db, swap)
    source = r.assets.get_row(session, db, 'device_events', receipt['source_event_id'])
    if (receipt['device_id'] != dev['id'] or receipt['source_boot'] != dev['boot_id']
            or snapshot['observed_at'] < receipt['observed_at']
            or source['id'] != UUID(packet['snapshot_event_id']) or source['device_id'] != dev['id']
            or source['boot_id'] != dev['boot_id'] or not source['accepted'] or not source['processed_at']
            or not start <= source['observed_at'] <= end
            or snapshot['payload']['command_ledger'] != source['payload']['command_ledger']):
        a.refuse()
    tokens = [r.assets.get_row(session, db, 'auth_sessions', identity) for identity in
        token_ids | {UUID(pre[k]['payload']['auth_session_id']) for k in ('TECHNICIAN', 'CUSTOMER')}]
    for kind, proof in post.items():
        p = proof['payload']
        if proof['payload_hash'] != canonical_hash(p):
            a.refuse('EVIDENCE_REQUIRED', 422)
        times.extend((proof['observed_at'], proof['received_at']))
        if kind == 'SIMULATOR':
            continue
        identity = op['created_by'] if kind == 'TECHNICIAN' else op['customer_id']
        user = r.assets.get_row(session, db, 'users', identity)
        token = r.assets.get_row(session, db, 'auth_sessions', UUID(p['auth_session_id']))
        tokens.append(token)
        if (proof['actor_user_id'] != identity or user['role'] != kind or user['state'] != 'ACTIVE'
                or token['user_id'] != identity or token['revoked_at']):
            a.refuse('RECOVERY_ACTOR_UNAVAILABLE', 403)
        if kind == 'TECHNICIAN':
            r.assets.scope(session, db, user, swap['station_id'])
        if (proof['reference_receipt_id'] != receipt['id'] or p['receipt_hash'] != receipt['payload_hash']
                or p['context_hash'] != op['context_hash'] or p['stage'] != 'POST_ACTION_RECEIPT'
                or p['actual_serial'] != op['expected_serial'] or p['recipient_id'] != str(op['customer_id'])
                or p['confirm'] is not True or proof['observed_at'] < receipt['received_at']):
            a.refuse('EVIDENCE_REQUIRED', 422)
    user = r.authorize(session, db, actor, swap, write=True)
    # Final decision after all potentially blocking reads. No HTTP or actuation.
    now = r.utcnow(); r.open_operation(op)
    if any(t['expires_at'] <= now for t in tokens):
        a.refuse('RECOVERY_ACTOR_UNAVAILABLE', 403)
    if not all(r.assets.fresh(t, now, swap['policy_snapshot']) for t in times):
        a.refuse('EVENT_STALE', 422)
    operations = db.table('recovery_operations')
    session.execute(update(operations).where(operations.c.id == op['id']).values(consumed_at=now))
    case = r.change_case(session, db, case, state='EVIDENCE_RECORDED',
        evidence_event_id=snapshot['id'], resolution_note=body.resolution_note, assigned_to=user['id'])
    r.audit(session, db, user, case, 'FOREIGN_OBJECT_RETURN_SETTLED', {
        'operation_id':op['id'], 'inspection_id':pre['SIMULATOR']['id'], 'authorization_id':intent['id'],
        'activation_id':activation['id'], 'receipt_id':receipt['id'], 'snapshot_id':snapshot['id'],
        'post_attestation_ids':[p['id'] for p in post.values()], 'case_version':case['version'],
        'old_custody_changed':False, 'new_custody_changed':False, 'holds_released':False}, before=audit_before)
    return r.view(session, db, case)
