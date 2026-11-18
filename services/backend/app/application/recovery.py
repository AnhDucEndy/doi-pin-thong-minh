"""Recovery evidence receipt. All writers serialize on the existing station lock.

No endpoint in this module changes a physical command or payment result.
"""
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select, update

from app.application import assets
from app.application.identity import DomainError, utcnow
from app.domain.recovery import canonical_hash, proof_errors
from app.workers.device import station_locks
from app.application.recovery_audit import snapshot as audit_snapshot, safe as audit_safe


def case_for(session, db, swap_id):
    table = db.table('recovery_cases')
    case = session.execute(select(table).where(table.c.swap_id == swap_id)).mappings().first()
    if not case:
        raise DomainError(404, 'RESOURCE_NOT_FOUND')
    return case


def authorize(session, db, actor, swap, write=False):
    user = assets.get_row(session, db, 'users', actor['user']['id'])
    token = assets.get_row(session, db, 'auth_sessions', actor['session']['id'])
    if user['state'] != 'ACTIVE' or token['revoked_at'] or token['expires_at'] <= utcnow():
        raise DomainError(401, 'SESSION_REVOKED')
    if user['role'] not in (('TECHNICIAN',) if write else ('ADMIN', 'TECHNICIAN')):
        raise DomainError(403, 'FORBIDDEN')
    assets.scope(session, db, user, swap['station_id'])
    return user


def lock_context(session, db, swap_id, actor_id=None):
    initial = assets.get_row(session, db, 'swap_transactions', swap_id)
    # Collect all relevant users BEFORE acquiring any user lock. The station
    # mutex serializes other recovery writers; re-read after it is acquired.
    assets.station_lock(session, db, initial['station_id'])
    ops = db.table('recovery_operations')
    participants = set(session.scalars(select(ops.c.created_by).where(ops.c.station_id == initial['station_id'])))
    participants.add(initial['customer_id'])
    if actor_id:
        participants.add(actor_id)
    station_locks(session, db, initial['station_id'], participants)
    swap = assets.get_row(session, db, 'swap_transactions', swap_id)
    return swap, case_for(session, db, swap_id)


def audit(session, db, actor, case, action, after, *, before, actor_type=None):
    session.execute(insert(db.table('audit_events')).values(id=uuid4(),
        actor_type=actor_type or ('USER' if actor.get('role') else 'DEVICE'), actor_id=str(actor['id']),
        aggregate_type='recovery', aggregate_id=case['id'], action=action,
        before_data=audit_safe({'recovery_snapshot': before}),
        after_data=audit_safe({**after, 'recovery_snapshot': audit_snapshot(session, db, case)}),
        correlation_id=case['swap_id']))


def change_case(session, db, case, **values):
    table = db.table('recovery_cases')
    return session.execute(update(table).where(table.c.id == case['id'])
        .values(version=case['version'] + 1, **values).returning(table)).mappings().one()


def operation_view(session, db, operation):
    table = db.table('recovery_attestations')
    rows = session.execute(select(table).where(table.c.operation_id == operation['id'])
        .order_by(table.c.received_at, table.c.id)).mappings().all()
    permits = db.table('recovery_action_authorizations')
    permit = session.execute(select(permits).where(permits.c.operation_id == operation['id'])).mappings().first()
    summary = None
    if permit:
        acks = db.table('recovery_authorization_acks')
        ack = session.execute(select(acks.c.id).where(acks.c.authorization_id == permit['id'])).scalar()
        summary = {'id': permit['id'], 'authorization_hash': permit['authorization_hash'],
            'acknowledgment_id': ack, 'transport_acknowledged': ack is not None,
            'expires_at': permit['expires_at'], 'revoked_at': permit['revoked_at'], 'effect_allowed': False}
    return {**dict(operation), 'attestations': [dict(r) for r in rows], 'authorization': summary, 'simulation_only': True}


def view(session, db, case):
    result = dict(case)
    result['active_operation'] = (operation_view(session, db,
        assets.get_row(session, db, 'recovery_operations', case['operation_id']))
        if case['operation_id'] else None)
    return result


def get(session, db, actor, swap_id):
    swap = assets.get_row(session, db, 'swap_transactions', swap_id)
    authorize(session, db, actor, swap)
    return view(session, db, case_for(session, db, swap_id))


def commands(session, db, swap_id):
    table = db.table('device_commands')
    return session.execute(select(table).where(table.c.swap_id == swap_id)
        .order_by(table.c.id).with_for_update()).mappings().all()


def quiet(session, db, swap, *, reconciled_commands=frozenset(), decision_at=None):
    # EXPIRED is only assigned to never-dispatched QUEUED commands. UNKNOWN is
    # deliberately not treated as no-effect merely because wall time elapsed.
    dev = assets.available_device(session, db, swap['station_id'])
    now = decision_at or utcnow()
    snapshot = assets.snapshot(session, db, dev, now)
    ledger = {e['command_id']: e['status'] for e in snapshot['payload']['command_ledger']} if snapshot else {}
    for command in commands(session, db, swap['id']):
        status = ledger.get(str(command['id']))
        if command['state'] in ('OBSERVED', 'REJECTED', 'EXPIRED'):
            if status is not None and status != ('EXECUTED' if command['state'] == 'OBSERVED' else 'NOT_EXECUTED'):
                return False
            continue
        deadline = command['created_at'] + timedelta(seconds=swap['policy_snapshot']['physical_step_timeout_seconds'])
        if not (dev and assets.online(session, db, dev, now, swap['policy_snapshot'])
                and command['device_id'] == dev['id']
                and snapshot and assets.fresh(snapshot['observed_at'], now, swap['policy_snapshot'])
                and assets.fresh(snapshot['received_at'], now, swap['policy_snapshot'])
                and snapshot['observed_at'] >= deadline):
            return False
        if status == 'NOT_EXECUTED' and command['id'] not in reconciled_commands:
            continue
        # Only final settlement may supply IDs whose physical outcome has
        # independently passed all custody guards. Poll/begin/action callers
        # never pass this set. EXECUTED alone never establishes delivery.
        if not (status == 'EXECUTED' and command['state'] == 'UNKNOWN'
                and command['id'] in reconciled_commands):
            return False
    return True


def operation_for(session, db, case, identity):
    op = assets.get_row(session, db, 'recovery_operations', identity)
    if op['case_id'] != case['id'] or op['swap_id'] != case['swap_id']:
        raise DomainError(403, 'RECOVERY_CONTEXT_FORBIDDEN')
    return op


def open_operation(op):
    if op['consumed_at'] or op['cancelled_at']:
        raise DomainError(409, 'RECOVERY_OPERATION_CLOSED')
    if utcnow() >= op['expires_at']:
        raise DomainError(409, 'RECOVERY_OPERATION_EXPIRED')


def add_attestation(session, db, case, op, source, payload, actor, *,
                    observed_at=None, event_id=None, boot=None, seq=None):
    audit_before = audit_snapshot(session, db, case)
    table = db.table('recovery_attestations')
    previous = session.execute(select(table.c.id).where(table.c.operation_id == op['id'],
        table.c.source_kind == source)).first()
    if previous:
        raise DomainError(409, 'RECOVERY_ATTESTATION_EXISTS')
    now = utcnow()
    payload = {**payload, 'context_hash': op['context_hash'], 'simulation_only': True}
    row = session.execute(insert(table).values(id=uuid4(), event_id=event_id or uuid4(),
        operation_id=op['id'], source_kind=source,
        actor_user_id=actor['id'] if source != 'SIMULATOR' else None,
        device_id=actor['id'] if source == 'SIMULATOR' else None,
        observed_at=observed_at or now, received_at=now, payload=payload,
        payload_hash=canonical_hash(payload), source_boot=boot, source_seq=seq)
        .returning(table)).mappings().one()
    updated = change_case(session, db, case, state='EVIDENCE_RECORDED', operation_id=op['id'],
                          new_pin_delivered='UNKNOWN')
    audit(session, db, actor, updated, 'RECOVERY_ATTESTATION_RECORDED',
          {'attestation_id': row['id'], 'source': source, 'operation_id': op['id']}, before=audit_before)
    return row, updated


def record(session, db, actor, swap_id, body, ttl):
    swap, case = lock_context(session, db, swap_id, actor['user']['id'])
    user = authorize(session, db, actor, swap, write=True)
    assets.version(case, body.expected_version)
    if case['state'] == 'RESOLVED' or swap['state'] not in ('REVIEW_REQUIRED', 'COMPENSATING'):
        raise DomainError(409, 'STATE_CONFLICT')
    if hasattr(body, 'evidence_event_id'):
        event = assets.get_row(session, db, 'device_events', body.evidence_event_id)
        dev = assets.get_row(session, db, 'devices', event['device_id'])
        if (dev['station_id'] != swap['station_id'] or not event['accepted'] or not event['processed_at']
                or event['kind'] != 'SNAPSHOT'):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        audit_before = audit_snapshot(session, db, case)
        case = change_case(session, db, case, state='EVIDENCE_RECORDED', evidence_event_id=event['id'],
            assigned_to=user['id'], resolution_note=body.note, new_pin_delivered='UNKNOWN')
        audit(session, db, user, case, 'RECOVERY_EVIDENCE_RECORDED', {'event_id': event['id']}, before=audit_before)
        return view(session, db, case)
    statement = body.statement
    if statement.kind == 'BEGIN_OPERATION':
        if user['id'] == swap['customer_id']:
            raise DomainError(403, 'RECOVERY_ACTOR_CONFLICT')
        table = db.table('recovery_operations')
        existing = session.execute(select(table).where(table.c.case_id == case['id'],
            table.c.consumed_at.is_(None), table.c.cancelled_at.is_(None))
            .order_by(table.c.created_at, table.c.id)).mappings().all()
        effect_predecessor = None
        # Never close an outstanding effect-capable operation on TTL alone.
        for previous in existing:
            # Read-only inspections can be superseded after rejection/expiry.
            # Handover operations cannot: expiry/rejection does not prove that
            # an external effect never happened. Keep their durable fence.
            attest = db.table('recovery_attestations')
            prior = session.execute(select(attest).where(attest.c.operation_id == previous['id'])).mappings().all()
            rejected = any(r['source_kind'] in ('CUSTOMER', 'TECHNICIAN')
                and r['payload'].get('confirm') is False for r in prior)
            expired = utcnow() >= previous['expires_at']
            # Reinspect possession after an uncertain old-pin handover; do not
            # authorize another handover or remove the predecessor's fence.
            if (previous['purpose'] == 'RETURN_OLD_TO_CUSTOMER'
                    and statement.purpose == 'VERIFY_OLD_POSSESSION' and (expired or rejected)):
                effect_predecessor = previous['id']
                continue
            if (previous['purpose'] in ('RETURN_OLD_TO_CUSTOMER', 'RETURN_FOREIGN_OBJECT')
                    or not (rejected or expired)):
                raise DomainError(409, 'RECOVERY_OPERATION_ACTIVE')
            audit_before = audit_snapshot(session, db, case)
            session.execute(update(table).where(table.c.id == previous['id']).values(cancelled_at=utcnow()))
            audit(session, db, user, case, 'RECOVERY_OPERATION_SUPERSEDED', {'operation_id': previous['id']}, before=audit_before)
        purpose = statement.purpose
        if purpose == 'RETURN_FOREIGN_OBJECT' and session.execute(select(table.c.id).where(
                table.c.station_id == swap['station_id'], table.c.protocol_version == '0.2',
                table.c.consumed_at.is_(None), table.c.cancelled_at.is_(None))).first():
            # Expiry does not prove that the durable device fence can be removed.
            raise DomainError(409, 'RECOVERY_OPERATION_ACTIVE')
        old = assets.get_row(session, db, 'batteries', swap['old_battery_id'])
        new = assets.get_row(session, db, 'batteries', swap['new_battery_id'])
        ret = assets.get_row(session, db, 'compartments', swap['return_compartment_id'])
        pin = new if purpose == 'VERIFY_NEW_DELIVERY' else old
        serial = ret['observed_serial'] if purpose == 'RETURN_FOREIGN_OBJECT' else pin['serial']
        if not serial or (purpose == 'RETURN_FOREIGN_OBJECT' and serial in (old['serial'], new['serial'])):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        if purpose in ('RETURN_OLD_TO_CUSTOMER', 'RESUME_SWAP') and not quiet(session, db, swap):
            raise DomainError(409, 'RECONCILIATION_REQUIRED')
        identity, now = uuid4(), utcnow()
        context = jsonable_encoder({'operation_id': identity, 'case_id': case['id'],
            'swap_id': swap_id, 'station_id': swap['station_id'], 'customer_id': swap['customer_id'],
            'purpose': purpose, 'expected_serial': serial, 'return_compartment_id': ret['id'],
            'supply_compartment_id': swap['supply_compartment_id'], 'created_by': user['id'],
            'base_case_version': case['version'], 'base_swap_version': swap['version'],
            'commands': [{'id': c['id'], 'state': c['state']} for c in commands(session, db, swap_id)]})
        audit_before = audit_snapshot(session, db, case)
        session.execute(insert(table).values(id=identity, case_id=case['id'], swap_id=swap_id,
            protocol_version='0.2' if purpose == 'RETURN_FOREIGN_OBJECT' else None,
            station_id=swap['station_id'], customer_id=swap['customer_id'],
            pin_id=None if purpose == 'RETURN_FOREIGN_OBJECT' else pin['id'], expected_serial=serial,
            purpose=purpose, context=context, context_hash=canonical_hash(context), created_by=user['id'],
            created_at=now, expires_at=now + timedelta(seconds=ttl),
            base_case_version=case['version'], base_swap_version=swap['version'],
            supersedes_id=effect_predecessor or (existing[-1]['id'] if existing else None)))
        case = change_case(session, db, case, operation_id=identity, assigned_to=user['id'],
            resolution_note=body.note, new_pin_delivered='UNKNOWN')
        audit(session, db, user, case, 'RECOVERY_OPERATION_CREATED', context, before=audit_before)
    else:
        op = operation_for(session, db, case, statement.operation_id)
        if statement.kind in ('REINSPECT_OPERATION','CLOSE_NO_EFFECT'):
            if statement.kind == 'REINSPECT_OPERATION':
                from app.application.recovery_reconciliation import begin
                case = begin(session,db,actor,swap,case,op,statement,ttl)
            else:
                from app.application.recovery_closure import issue
                case = issue(session,db,actor,swap,case,op,statement)
            return view(session,db,case)
        if op['protocol_version'] == '0.2':
            from app.application import recovery_authorization as staged
            if statement.kind == 'AUTHORIZE_ACTION':
                if statement.phase == 'ACTIVATE':
                    from app.application.recovery_handover import activate
                    case = activate(session, db, swap, case, op, actor, statement)
                else:
                    case = staged.issue(session, db, swap, case, op, actor, statement)
            elif statement.kind == 'TECHNICIAN_ATTEST':
                _, case = staged.human(session, db, swap, case, op, actor, statement, 'TECHNICIAN')
            else:
                raise DomainError(409, 'RECONCILIATION_REQUIRED')
            return view(session, db, case)
        if statement.kind == 'AUTHORIZE_ACTION' or getattr(statement, 'stage', None) is not None:
            raise DomainError(409, 'RECOVERY_STAGE_CONFLICT')
        open_operation(op)
        if statement.kind == 'ATTACH_OPERATION':
            audit_before = audit_snapshot(session, db, case)
            case = change_case(session, db, case, operation_id=op['id'])
            audit(session, db, user, case, 'RECOVERY_OPERATION_ATTACHED', {'operation_id': op['id']}, before=audit_before)
        else:
            if op['created_by'] != user['id'] or statement.context_hash != op['context_hash']:
                raise DomainError(403, 'RECOVERY_CONTEXT_FORBIDDEN')
            _, case = add_attestation(session, db, case, op, 'TECHNICIAN',
                {'actual_serial': statement.actual_serial, 'confirm': statement.observation == 'CONFIRM',
                 'auth_session_id': str(actor['session']['id'])}, user)
    return view(session, db, case)


def confirmation(session, db, actor, swap_id, body):
    swap, case = lock_context(session, db, swap_id, actor['user']['id'])
    user = assets.get_row(session, db, 'users', actor['user']['id'])
    token = assets.get_row(session, db, 'auth_sessions', actor['session']['id'])
    if user['state'] != 'ACTIVE' or token['revoked_at'] or token['expires_at'] <= utcnow():
        raise DomainError(401, 'SESSION_REVOKED')
    if user['role'] != 'CUSTOMER' or user['id'] != swap['customer_id']:
        raise DomainError(403, 'FORBIDDEN')
    op = operation_for(session, db, case, body.operation_id)
    if op['protocol_version'] == '0.2':
        open_operation(op)
        if op['context_hash'] != body.context_hash or case['operation_id'] != op['id']:
            raise DomainError(409, 'RECOVERY_CONTEXT_MISMATCH')
        from app.application.recovery_projection import project
        reference = project(session, db, swap, case, op)
        if (body.stage != reference['stage'] or body.receipt_id != reference['receipt_id']
                or body.receipt_hash != reference['receipt_hash'] or reference['receipt_id'] is None):
            raise DomainError(409, 'RECOVERY_STAGE_CONFLICT')
        if reference['confirmation_status'] == 'REVOKED':
            raise DomainError(409, 'RECONCILIATION_REQUIRED')
        # Shared human PRE guard checks current boot/provenance for both actors
        # after taking the exact actor-session lock. POST/successor stay separate.
        # Existing human handlers recheck freshness, actors and append-only
        # uniqueness. The projection is a hint, not permission to skip them.
        from app.application import recovery_authorization as staged
        identity, _ = staged.human(session, db, swap, case, op, actor, body, 'CUSTOMER')
        return {'id': identity, 'operation_id': op['id'], 'accepted': True, 'confirmed': body.confirm}
    if body.stage is not None:
        raise DomainError(409, 'RECOVERY_STAGE_CONFLICT')
    open_operation(op)
    if op['context_hash'] != body.context_hash or op['created_by'] == user['id']:
        raise DomainError(409, 'RECOVERY_CONTEXT_MISMATCH')
    row, _ = add_attestation(session, db, case, op, 'CUSTOMER',
        {'confirm': body.confirm, 'auth_session_id': str(actor['session']['id'])}, user)
    return {'id': row['id'], 'operation_id': op['id'], 'accepted': True, 'confirmed': body.confirm}


def observe(session, db, actor, body):
    initial = assets.get_row(session, db, 'recovery_operations', body.operation_id)
    if initial['protocol_version'] == '0.2':
        raise DomainError(409, 'RECONCILIATION_REQUIRED')
    if initial['station_id'] != actor['station_id']:
        raise DomainError(403, 'DEVICE_STATION_FORBIDDEN')
    swap, case = lock_context(session, db, initial['swap_id'])
    dev = assets.get_row(session, db, 'devices', actor['id'], lock=True)
    if not dev['enabled'] or dev['key_hash'] != actor['key_hash']:
        raise DomainError(403, 'DEVICE_DISABLED')
    op = operation_for(session, db, case, body.operation_id)
    payload = {**body.observation.model_dump(mode='json'), 'context_hash': body.context_hash,
               'request_hash': canonical_hash(body.model_dump(mode='json'))}
    table = db.table('recovery_attestations')
    prior = session.execute(select(table).where(table.c.event_id == body.event_id)).mappings().first()
    if prior:
        if (prior['device_id'] != dev['id'] or prior['operation_id'] != op['id']
                or prior['payload'].get('request_hash') != payload['request_hash']):
            raise DomainError(409, 'IDEMPOTENCY_CONFLICT')
        return {'accepted': True, 'duplicate': True, 'id': prior['id']}
    open_operation(op)
    now = utcnow()
    if body.context_hash != op['context_hash'] or body.boot_id != dev['boot_id']:
        raise DomainError(422, 'RECOVERY_CONTEXT_MISMATCH')
    if not op['created_at'] <= body.observed_at <= now or not assets.fresh(body.observed_at, now, swap['policy_snapshot']):
        raise DomainError(422, 'EVENT_STALE')
    last = session.execute(select(table).where(table.c.device_id == dev['id'],
        table.c.source_boot == body.boot_id).order_by(table.c.source_seq.desc()).limit(1)).mappings().first()
    if last and (body.seq <= last['source_seq'] or body.observed_at <= last['observed_at']):
        raise DomainError(422, 'EVENT_OUT_OF_ORDER')
    for identity in body.observation.supporting_event_ids:
        event = assets.get_row(session, db, 'device_events', identity)
        if (event['device_id'] != dev['id'] or not event['accepted'] or not event['processed_at']
                or event['swap_id'] not in (None, swap['id'])):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
    result, _ = add_attestation(session, db, case, op, 'SIMULATOR', payload, dev,
        event_id=body.event_id, observed_at=body.observed_at, boot=body.boot_id, seq=body.seq)
    return {'accepted': True, 'duplicate': False, 'id': result['id']}


def tasks(session, db, actor):
    assets.station_lock(session, db, actor['station_id'])
    dev = assets.get_row(session, db, 'devices', actor['id'], lock=True)
    if not dev['enabled'] or dev['key_hash'] != actor['key_hash']:
        raise DomainError(403, 'DEVICE_DISABLED')
    table = db.table('recovery_operations')
    from app.application.recovery_closure import tasks as closure_tasks
    result = closure_tasks(session, db, dev)
    closing = {task['operation_id'] for task in result}
    for op in session.execute(select(table).where(table.c.station_id == dev['station_id'],
            table.c.consumed_at.is_(None), table.c.cancelled_at.is_(None), table.c.expires_at > utcnow())
            .order_by(table.c.created_at)).mappings().all():
        swap = assets.get_row(session, db, 'swap_transactions', op['swap_id'])
        if swap['state'] not in ('REVIEW_REQUIRED', 'COMPENSATING'):
            continue
        if op['protocol_version'] == '0.2':
            if op['id'] in closing:
                continue
            if op['context'].get('reconciliation_only'):
                result.append({**op['context'], 'protocol_version':'0.2','task_kind':'RECONCILE_INSPECT',
                    'context_hash':op['context_hash'],'expires_at':op['expires_at'],
                    'effect_allowed':False,'simulation_only':True})
                continue
            permits = db.table('recovery_action_authorizations')
            permit = session.execute(select(permits).where(permits.c.operation_id == op['id'])).mappings().first()
            if permit:
                from app.application.recovery_authorization import guards
                swap, case = lock_context(session, db, op['swap_id'])
                if permit['revoked_at'] or permit['boot_id'] != dev['boot_id']:
                    continue
                try:
                    guards(session, db, swap, case, op)
                except DomainError:
                    continue
                activations = db.table('recovery_action_activations')
                activation = session.execute(select(activations).where(activations.c.operation_id == op['id'])).mappings().first()
                if activation:
                    from app.application.recovery_handover import action_task
                    action = action_task(session, db, swap, op, permit, activation)
                    if action:
                        result.append(action)
                    continue
                result.append({**op['context'], 'protocol_version': '0.2', 'task_kind': 'AUTHORIZATION_INTENT',
                    'context_hash': op['context_hash'], 'expires_at': op['expires_at'], 'simulation_only': True,
                    'authorization_id': permit['id'], 'authorization_hash': permit['authorization_hash'],
                    'authorization_payload': permit['payload'], 'effect_allowed': False})
                continue
            result.append({**op['context'], 'protocol_version': '0.2', 'task_kind': 'INSPECT',
                'context_hash': op['context_hash'], 'expires_at': op['expires_at'], 'simulation_only': True})
            continue
        if op['purpose'] in ('RETURN_OLD_TO_CUSTOMER', 'RETURN_FOREIGN_OBJECT'):
            from app.application.payments import get as get_payment
            payment = get_payment(session, db, swap['id'])
            holds = db.table('resource_reservations')
            held = session.execute(select(holds).where(holds.c.swap_id == swap['id'], holds.c.released_at.is_(None))).mappings().all()
            if (payment['state'] != 'SUCCEEDED' or not payment['verified_at'] or not swap['consented_at']
                    or payment['amount_minor'] != swap['amount_minor'] or payment['currency'] != swap['currency']
                    or len(held) != 3 or {h['compartment_id'] for h in held if h['compartment_id']} != {
                        swap['return_compartment_id'], swap['supply_compartment_id']}
                    or {h['battery_id'] for h in held if h['battery_id']} != {swap['new_battery_id']}):
                continue
            _, _, slots, timestamps = current_snapshot(session, db, swap)
            new = assets.get_row(session, db, 'batteries', swap['new_battery_id'])
            old = assets.get_row(session, db, 'batteries', swap['old_battery_id'])
            manual_return = (old['holder_user_id'] == swap['customer_id']
                and old['location_kind'] == 'CUSTOMER' and assets.pin_at(session, db, slots[0]) is None
                and historical_return(session, db, swap, old) is not None)
            if (not quiet(session, db, swap) or not all(assets.fresh(t, utcnow(), swap['policy_snapshot']) for t in timestamps)
                    or slots[1]['observed_serial'] != new['serial'] or not slots[1]['observed_present']
                    or new['compartment_id'] != slots[1]['id'] or new['holder_user_id'] is not None
                    or new['location_kind'] != 'COMPARTMENT'
                    or slots[0]['observed_serial'] != op['expected_serial'] or not slots[0]['observed_present']
                    or (op['purpose'] == 'RETURN_OLD_TO_CUSTOMER'
                        and old['compartment_id'] != slots[0]['id'] and not manual_return)):
                continue
        result.append({**op['context'], 'context_hash': op['context_hash'], 'expires_at': op['expires_at'],
                       'simulation_only': True})
    return {'items': result}


def confirmation_context(session, db, actor, swap):
    if actor['user']['role'] != 'CUSTOMER' or actor['user']['id'] != swap['customer_id']:
        return None
    table = db.table('recovery_cases')
    case = session.execute(select(table).where(table.c.swap_id == swap['id'])).mappings().first()
    if not case or not case['operation_id']:
        return None
    op = assets.get_row(session, db, 'recovery_operations', case['operation_id'])
    if (op['swap_id'] != swap['id'] or op['case_id'] != case['id']
            or op['customer_id'] != swap['customer_id'] or op['station_id'] != swap['station_id']):
        return None
    from app.application.recovery_projection import project
    return project(session, db, swap, case, op)


def current_snapshot(session, db, swap):
    dev = assets.available_device(session, db, swap['station_id'])
    now = utcnow()
    snap = assets.snapshot(session, db, dev, now)
    if not dev or not dev['enabled'] or not snap or not assets.online(session, db, dev, now, swap['policy_snapshot']):
        raise DomainError(422, 'EVIDENCE_REQUIRED')
    slots = [assets.get_row(session, db, 'compartments', swap[key])
             for key in ('return_compartment_id', 'supply_compartment_id')]
    timestamps = [dev['last_received_at'], snap['observed_at'], snap['received_at']]
    by_id = {s['compartment_id']: s for s in snap['payload']['slots']}
    for slot in slots:
        observed = by_id.get(str(slot['id']))
        latest = assets.latest_observation(session, db, dev['id'], slot['id'])
        if (not observed or not latest or not assets.current_observation(session, db, dev, slot)
                or slot['door_state'] != 'CLOSED' or observed['door_state'] != 'CLOSED'
                or observed['present'] != slot['observed_present']
                or observed['observed_serial'] != slot['observed_serial']):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        timestamps.extend([slot['observed_at'], latest['observed_at']])
    return dev, snap, slots, timestamps


def historical_return(session, db, swap, old):
    """Accepted historical close can support MANUAL reconciliation, not advance.

    Never mutate the command/event deadline/status or pretend its evidence is
    current. Current slot evidence and three independent sources are separate.
    """
    for command in commands(session, db, swap['id']):
        if command['kind'] != 'OPEN_RETURN' or command['state'] != 'OBSERVED' or not command['evidence_event_id']:
            continue
        event = assets.get_row(session, db, 'device_events', command['evidence_event_id'])
        if (event['accepted'] and event['processed_at'] and event['kind'] == 'DOOR'
                and event['command_id'] == command['id'] and event['swap_id'] == swap['id']
                and event['compartment_id'] == swap['return_compartment_id']
                and event['payload']['door_state'] == 'CLOSED' and event['payload']['present'] is True
                and event['payload']['observed_serial'] == old['serial']):
            return event
    return None


def close_resumed(session, db, swap, event):
    cases = db.table('recovery_cases')
    case = session.execute(select(cases).where(cases.c.swap_id == swap['id'])).mappings().first()
    if not case or case['state'] == 'RESOLVED' or not case['operation_id']:
        return
    op = operation_for(session, db, case, case['operation_id'])
    if op['purpose'] != 'RESUME_SWAP' or not op['consumed_at']:
        return
    audit_before = audit_snapshot(session, db, case)
    case = change_case(session, db, case, state='RESOLVED', old_pin_settled=True,
        new_pin_delivered='YES', evidence_event_id=event['id'])
    audit(session, db, {'id': 'device-worker'}, case, 'RECOVERY_RESUMED_COMPLETED',
        {'operation_id': str(op['id']), 'evidence_event_id': str(event['id'])},
        before=audit_before, actor_type='SYSTEM')


def settle(session, db, actor, swap_id, body):
    from app.application import device, payments, swaps
    swap, case = lock_context(session, db, swap_id, actor['user']['id'])
    audit_before = audit_snapshot(session, db, case)
    user = authorize(session, db, actor, swap, write=True)
    assets.version(case, body.expected_version)
    if case['state'] == 'RESOLVED' or swap['state'] not in ('REVIEW_REQUIRED', 'COMPENSATING'):
        raise DomainError(409, 'STATE_CONFLICT')
    identity = getattr(body, 'operation_id', None) or case['operation_id']
    if not identity:
        raise DomainError(422, 'EVIDENCE_REQUIRED')
    op = operation_for(session, db, case, identity)
    if op['protocol_version'] == '0.2':
        if op['context'].get('reconciliation_only'):
            from app.application.recovery_reconciliation import settle as settle_chain
            return settle_chain(session, db, actor, swap, case, op, body)
        from app.application.recovery_settlement import settle_foreign
        return settle_foreign(session, db, actor, swap, case, op, body)
    open_operation(op)
    if hasattr(body, 'evidence_event_id'):
        # Legacy callers still bind their decision to the recorded snapshot.
        # A valid structured operation must not make an unrelated UUID valid.
        if body.evidence_event_id != case['evidence_event_id']:
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        event = assets.get_row(session, db, 'device_events', body.evidence_event_id)
        source = assets.get_row(session, db, 'devices', event['device_id'])
        if (source['station_id'] != swap['station_id'] or event['kind'] != 'SNAPSHOT'
                or not event['accepted'] or not event['processed_at']):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
    attest = db.table('recovery_attestations')
    evidence = session.execute(select(attest).where(attest.c.operation_id == op['id'])).mappings().all()
    dev, snapshot, slots, timestamps = current_snapshot(session, db, swap)
    witness_sessions = []
    for item in evidence:
        if item['source_kind'] == 'SIMULATOR':
            if item['device_id'] != dev['id']:
                raise DomainError(422, 'EVIDENCE_REQUIRED')
            continue
        participant = assets.get_row(session, db, 'users', item['actor_user_id'])
        role = 'TECHNICIAN' if item['source_kind'] == 'TECHNICIAN' else 'CUSTOMER'
        if participant['role'] != role or participant['state'] != 'ACTIVE':
            raise DomainError(403, 'RECOVERY_ACTOR_UNAVAILABLE')
        if role == 'TECHNICIAN':
            assets.scope(session, db, participant, swap['station_id'])
        token_id = item['payload'].get('auth_session_id')
        if not token_id:
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        witness_sessions.append((UUID(token_id), participant['id']))
    holds = db.table('resource_reservations')
    held = session.execute(select(holds).where(holds.c.swap_id == swap_id, holds.c.released_at.is_(None))).mappings().all()
    if (len(held) != 3 or {h['compartment_id'] for h in held if h['compartment_id']} != {s['id'] for s in slots}
            or {h['battery_id'] for h in held if h['battery_id']} != {swap['new_battery_id']}):
        raise DomainError(409, 'RESOURCE_CONFLICT')
    old, new = [assets.get_row(session, db, 'batteries', swap[k]) for k in ('old_battery_id', 'new_battery_id')]
    ret, supply = slots
    payment = payments.get(session, db, swap_id)
    refund = db.table('refunds')
    if session.execute(select(refund.c.id).where(refund.c.payment_id == payment['id'])).first():
        raise DomainError(409, 'RECONCILIATION_REQUIRED')
    no_delivery = (supply['observed_present'] is True and supply['observed_serial'] == new['serial']
                   and new['compartment_id'] == supply['id'] and new['holder_user_id'] is None)
    returned = (ret['observed_present'] is True and ret['observed_serial'] == old['serial']
                and old['compartment_id'] == ret['id'] and old['holder_user_id'] is None and swap['return_observed_at'])
    old_external = old['location_kind'] == 'CUSTOMER' and old['holder_user_id'] == swap['customer_id']
    return_event = historical_return(session, db, swap, old)
    reconcile_return = bool(old_external and return_event and ret['observed_present'] is True
        and ret['observed_serial'] == old['serial'] and assets.pin_at(session, db, ret) is None)
    paid = (payment['state'] == 'SUCCEEDED' and payment['verified_at'] and swap['consented_at']
            and payment['amount_minor'] == swap['amount_minor'] and payment['currency'] == swap['currency'])
    state, delivered, settled, move_old, move_new, resume = swap['state'], 'UNKNOWN', False, False, False, None
    predecessor = None
    purpose = op['purpose']
    if purpose == 'VERIFY_NEW_DELIVERY':
        if not (paid and (returned or reconcile_return) and supply['observed_present'] is False and supply['observed_serial'] is None
                and new['compartment_id'] == supply['id'] and new['holder_user_id'] is None):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        state, delivered, settled, move_new = 'COMPLETED', 'YES', True, True
    elif purpose == 'RETURN_OLD_TO_CUSTOMER':
        if not (paid and no_delivery and (old['compartment_id'] == ret['id'] or (old_external and return_event))
                and ret['observed_present'] is False and ret['observed_serial'] is None):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        delivered, settled, move_old = 'NO', True, not old_external
    elif purpose == 'VERIFY_OLD_POSSESSION':
        if op['supersedes_id']:
            prior = operation_for(session, db, case, op['supersedes_id'])
            if (prior['purpose'] == 'RETURN_OLD_TO_CUSTOMER' and not prior['consumed_at']
                    and not prior['cancelled_at'] and prior['pin_id'] == old['id']
                    and prior['customer_id'] == swap['customer_id']):
                predecessor = prior
        reconciled_external = bool(predecessor and paid and old['compartment_id'] == ret['id']
            and old['holder_user_id'] is None)
        if not ((old_external or reconciled_external) and no_delivery
                and ret['observed_present'] is False and ret['observed_serial'] is None):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        move_old = reconciled_external
        delivered, settled = 'NO', True
        if payment['state'] == 'FAILED' and payment['verified_at'] and not any(c['state'] == 'OBSERVED' for c in commands(session, db, swap_id)):
            state = 'CANCELLED'
    elif purpose == 'RETURN_FOREIGN_OBJECT':
        # This resolves only the foreign object, never the customer's network pin.
        if not (no_delivery and ret['observed_present'] is False and old_external):
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        delivered = 'NO'
    elif purpose == 'RESUME_SWAP':
        issued = commands(session, db, swap_id)
        if not paid or not no_delivery:
            raise DomainError(422, 'EVIDENCE_REQUIRED')
        if (returned or reconcile_return) and not any(c['kind'] == 'OPEN_SUPPLY' for c in issued):
            projected_old = ({**old, 'location_kind': 'COMPARTMENT', 'holder_user_id': None, 'compartment_id': ret['id']}
                             if reconcile_return else old)
            items = (ret, supply, projected_old, new)
            if not swaps.supply_ready(session, db, swap, items) or not swaps.physical_context(session, db, swap, items, old['serial'], new['serial'], issuing=True):
                raise DomainError(409, 'COMMAND_INTERLOCK_FAILED')
            state, resume = 'AWAITING_PICKUP', ('OPEN_SUPPLY', supply['id'])
        elif old_external and not issued and payments.resources_valid(session, db, swap, utcnow()):
            state, resume = 'AWAITING_RETURN', ('OPEN_RETURN', ret['id'])
        else:
            raise DomainError(409, 'RECONCILIATION_REQUIRED')
        delivered = 'NO'
    # Final decision clock AFTER all reads: manual proof never calls the
    # automatic advance with its deadline bypassed or rewrites old event times.
    now = utcnow()
    if proof_errors(op, evidence, now, dev['boot_id']) or not all(assets.fresh(t, now, swap['policy_snapshot']) for t in timestamps):
        raise DomainError(422, 'EVIDENCE_REQUIRED')
    # A complete positive delivery proof may reconcile only the original
    # pickup command in this immutable operation. It never authorizes a new
    # physical action, repairs command history, or resolves an unrelated UNKNOWN.
    reconciled = set()
    if purpose == 'VERIFY_NEW_DELIVERY' and state == 'COMPLETED' and move_new:
        context_ids = {str(c['id']) for c in op['context']['commands']}
        for command in commands(session, db, swap_id):
            if (command['state'] == 'UNKNOWN' and command['kind'] == 'OPEN_SUPPLY'
                    and command['compartment_id'] == supply['id'] and command['device_id'] == dev['id']
                    and str(command['id']) in context_ids
                    and command['payload'].get('expected_serial') == new['serial']
                    and command['payload'].get('expected_battery_id') == str(new['id'])):
                reconciled.add(command['id'])
    active_ops = db.table('recovery_operations')
    allowed_ops = [op['id']] + ([predecessor['id']] if predecessor else [])
    if session.execute(select(active_ops.c.id).where(active_ops.c.swap_id == swap_id,
            active_ops.c.consumed_at.is_(None), active_ops.c.cancelled_at.is_(None),
            active_ops.c.id.not_in(allowed_ops))).first():
        raise DomainError(409, 'RECONCILIATION_REQUIRED')
    if not quiet(session, db, swap, reconciled_commands=reconciled, decision_at=now):
        raise DomainError(409, 'RECONCILIATION_REQUIRED')
    # Users/assignments and station evidence are serialized by lock_context.
    # Logout only locks its auth_sessions row. Match the UUID order of 0.2,
    # including a caller using a different login from the Technician witness.
    caller_id = actor['session']['id']
    session_ids = {identity for identity, _ in witness_sessions} | {caller_id}
    tokens = {identity: assets.get_row(session, db, 'auth_sessions', identity, lock=True)
              for identity in sorted(session_ids)}
    user = authorize(session, db, actor, swap, write=True)
    assets.version(case_for(session, db, swap_id), body.expected_version)
    current_device, current_event, _, timestamps = current_snapshot(session, db, swap)
    if current_device['boot_id'] != dev['boot_id'] or current_event['id'] != snapshot['id']:
        raise DomainError(422, 'EVIDENCE_REQUIRED')
    now = utcnow()
    caller = tokens[caller_id]
    if caller['user_id'] != user['id'] or caller['revoked_at'] or caller['expires_at'] <= now:
        raise DomainError(401, 'SESSION_REVOKED')
    for identity, participant_id in witness_sessions:
        token = tokens[identity]
        if token['user_id'] != participant_id or token['revoked_at'] or token['expires_at'] <= now:
            raise DomainError(403, 'RECOVERY_ACTOR_UNAVAILABLE')
    if proof_errors(op, evidence, now, dev['boot_id']) or not all(assets.fresh(t, now, swap['policy_snapshot']) for t in timestamps):
        raise DomainError(422, 'EVIDENCE_REQUIRED')
    pins = db.table('batteries')
    if reconcile_return and purpose in ('VERIFY_NEW_DELIVERY', 'RESUME_SWAP'):
        session.execute(update(pins).where(pins.c.id == old['id']).values(location_kind='COMPARTMENT',
            compartment_id=ret['id'], holder_user_id=None, version=old['version'] + 1))
    for pin, moving in ((old, move_old), (new, move_new)):
        if moving:
            session.execute(update(pins).where(pins.c.id == pin['id']).values(location_kind='CUSTOMER',
                compartment_id=None, holder_user_id=swap['customer_id'], version=pin['version'] + 1))
    operations = db.table('recovery_operations')
    session.execute(update(operations).where(operations.c.id == op['id']).values(consumed_at=now))
    if predecessor:
        # Both fences close in the same transaction as custody and audit.
        session.execute(update(operations).where(operations.c.id == predecessor['id']).values(consumed_at=now))
    terminal = state in ('COMPLETED', 'CANCELLED')
    if state != swap['state']:
        table = db.table('swap_transactions')
        values = {'state': state, 'version': swap['version'] + 1}
        if reconcile_return:
            values['return_observed_at'] = return_event['observed_at']
        if terminal:
            values['closed_at'] = now
        if move_new:
            values['pickup_observed_at'] = next(e['observed_at'] for e in evidence if e['source_kind'] == 'SIMULATOR')
        session.execute(update(table).where(table.c.id == swap_id).values(**values))
    if resume:
        device.enqueue_command(session, db, swap_id, resume[1], resume[0], swap['policy_snapshot'])
    if terminal:
        session.execute(update(holds).where(holds.c.swap_id == swap_id, holds.c.released_at.is_(None)).values(released_at=now))
    case = change_case(session, db, case, state='RESOLVED' if terminal else 'EVIDENCE_RECORDED',
        old_pin_settled=settled, new_pin_delivered=delivered, evidence_event_id=snapshot['id'],
        resolution_note=body.resolution_note, assigned_to=user['id'])
    audit(session, db, user, case, 'MANUAL_RECOVERY_SETTLED', {'operation_id': op['id'],
        'attestation_ids': [e['id'] for e in evidence], 'state': state,
        'reconciled_command_ids': sorted(str(i) for i in reconciled), 'snapshot_id': snapshot['id'],
        'old_custody_changed': move_old or reconcile_return, 'new_custody_changed': move_new}, before=audit_before)
    return view(session, db, case)
