"""Manual recovery decisions on isolated PostgreSQL; no refund implementation."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.application.identity import utcnow
from app.seed import demo_id
from test_phase2 import owner
from test_phase4 import row
from test_phase8a_api import start_case, begin


def evidence(client, environment, auth, swap, tech, case, *, serial=None, confirm=True, purpose='VERIFY_OLD_POSSESSION', result='OBSERVED'):
    response = client.post(f"/v1/swaps/{swap['id']}/recovery/evidence",
        headers={**tech, 'Idempotency-Key': str(uuid4())}, json={'expected_version': case['version'],
            'statement': {'kind': 'BEGIN_OPERATION', 'purpose': purpose}, 'note': 'independent fixture inspection'})
    assert response.status_code == 200, response.text
    case = response.json()
    op = case['active_operation']
    dev = row(client, 'devices', demo_id('device:S01'))
    packet = {'event_id': str(uuid4()), 'operation_id': op['id'], 'context_hash': op['context_hash'],
        'boot_id': str(dev['boot_id']), 'seq': 1, 'observed_at': utcnow().isoformat(),
        'observation': {'result': result, 'actual_serial': serial or op['expected_serial'],
            'supporting_event_ids': [], 'simulation_only': True}}
    headers = {'X-Device-Key': environment['keys']['S01']}
    response = client.post('/v1/device/recovery-observations', headers=headers, json=packet)
    assert response.status_code == 202, response.text
    duplicate = client.post('/v1/device/recovery-observations', headers=headers, json=packet)
    assert duplicate.status_code == 202 and duplicate.json()['duplicate'] is True
    case = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech).json()
    body = {'expected_version': case['version'], 'note': 'Actual inspection', 'statement': {
        'kind': 'TECHNICIAN_ATTEST', 'operation_id': op['id'], 'context_hash': op['context_hash'],
        'actual_serial': op['expected_serial'], 'observation': 'CONFIRM'}}
    response = client.post(f"/v1/swaps/{swap['id']}/recovery/evidence",
        headers={**tech, 'Idempotency-Key': str(uuid4())}, json=body)
    assert response.status_code == 200, response.text
    response = client.post(f"/v1/swaps/{swap['id']}/recovery/confirmations",
        headers={**auth('customer'), 'Idempotency-Key': str(uuid4())}, json={
            'operation_id': op['id'], 'context_hash': op['context_hash'], 'confirm': confirm})
    assert response.status_code == 201, response.text
    case = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech).json()
    return case, op


def settle(client, swap, tech, case, op, key=None):
    return client.post(f"/v1/swaps/{swap['id']}/recovery/settle",
        headers={**tech, 'Idempotency-Key': key or str(uuid4())}, json={
            'expected_version': case['version'], 'operation_id': op['id'], 'resolution_note': 'Verified manual inspection'})


def test_A_old_possession_settles_only_old_obligation_and_keeps_charge_holds(client, environment, auth):
    swap, tech, case = start_case(client, environment, auth)
    case, op = evidence(client, environment, auth, swap, tech, case)
    old_before = row(client, 'batteries', UUID(swap['old_battery_id']))
    key = str(uuid4())
    response = settle(client, swap, tech, case, op, key)
    assert response.status_code == 200, response.text
    assert response.json()['old_pin_settled'] is True
    assert response.json()['new_pin_delivered'] == 'NO'
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'

    assert row(client, 'batteries', old_before['id']) == old_before
    assert settle(client, swap, tech, case, op, key).json() == response.json()
    db = client.app.state.db
    with db.sessions() as session:
        holds, payments, audit = (db.table(t) for t in ('resource_reservations', 'payments', 'audit_events'))
        assert len(session.execute(select(holds).where(holds.c.swap_id == UUID(swap['id']), holds.c.released_at.is_(None))).all()) == 3
        assert session.scalar(select(payments.c.state).where(payments.c.swap_id == UUID(swap['id']))) == 'SUCCEEDED'
        assert len(session.execute(select(audit.c.id).where(audit.c.action == 'MANUAL_RECOVERY_SETTLED')).all()) == 1


def test_C_unknown_pickup_cannot_complete_even_with_two_human_confirmations(client, environment, auth):
    swap, tech, case = returned_case(client, environment, auth)
    physical_snapshot(client, environment, swap, swap['supply_compartment_id'])
    case, op = evidence(client, environment, auth, swap, tech, case,
        purpose='VERIFY_NEW_DELIVERY', result='UNKNOWN')
    before = row(client, 'batteries', UUID(swap['new_battery_id']))
    response = settle(client, swap, tech, case, op)
    assert response.status_code == 422 and response.json()['code'] == 'EVIDENCE_REQUIRED'
    assert row(client, 'batteries', before['id']) == before
    assert row(client, 'recovery_operations', UUID(op['id']))['consumed_at'] is None
    db = client.app.state.db
    with db.sessions() as session:
        holds = db.table('resource_reservations')
        assert len(session.execute(select(holds).where(holds.c.swap_id == UUID(swap['id']), holds.c.released_at.is_(None))).all()) == 3
        audits = db.table('audit_events')
        assert not session.execute(select(audits.c.id).where(audits.c.action == 'MANUAL_RECOVERY_SETTLED')).first()


def test_valid_caller_cannot_replace_revoked_technician_witness_session(client, environment, auth):
    swap, witness, case = start_case(client, environment, auth)
    case, op = evidence(client, environment, auth, swap, witness, case)
    caller = auth('technician')
    assert caller != witness
    assert client.post('/v1/auth/logout', headers={**witness, 'Idempotency-Key': str(uuid4())}).status_code == 200
    assert client.get('/v1/me', headers=caller).status_code == 200
    response = settle(client, swap, caller, case, op)
    assert response.status_code == 403 and response.json()['code'] == 'RECOVERY_ACTOR_UNAVAILABLE'
    current = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=caller).json()
    assert current['version'] == case['version'] and not current['old_pin_settled']
    assert current['active_operation']['consumed_at'] is None


def test_legacy_settlement_cannot_ignore_unrelated_evidence_id(client, environment, auth):
    swap, tech, case = start_case(client, environment, auth)
    case, op = evidence(client, environment, auth, swap, tech, case)
    response = client.post(f"/v1/swaps/{swap['id']}/recovery/settle",
        headers={**tech, 'Idempotency-Key': str(uuid4())}, json={
            'expected_version': case['version'], 'evidence_event_id': str(uuid4()),
            'resolution_note': 'Unrelated snapshot must not authorize settlement'})
    assert response.status_code == 422 and response.json()['code'] == 'EVIDENCE_REQUIRED'
    assert row(client, 'recovery_operations', UUID(op['id']))['consumed_at'] is None


def test_settlement_audit_failure_rolls_back_custody_consumption_and_holds(client, environment, auth):
    from unittest.mock import patch
    swap, tech, case = returned_case(client, environment, auth)
    physical_snapshot(client, environment, swap, swap['supply_compartment_id'])
    case, op = evidence(client, environment, auth, swap, tech, case, purpose='VERIFY_NEW_DELIVERY')
    before = row(client, 'batteries', UUID(swap['new_battery_id']))
    with patch('app.application.recovery.audit', side_effect=RuntimeError('TEST_AUDIT_FAILURE')):
        with pytest.raises(RuntimeError, match='TEST_AUDIT_FAILURE'):
            settle(client, swap, tech, case, op)
    assert row(client, 'batteries', before['id']) == before
    assert row(client, 'recovery_operations', UUID(op['id']))['consumed_at'] is None
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'
    # Retrying the same business decision after rollback is still permitted.
    assert settle(client, swap, tech, case, op).status_code == 200

def returned_case(client, environment, auth):
    from test_phase7 import paid, drive, physical
    from app.application.swaps import review
    swap = paid(client, environment, auth)
    drive(client, swap['id'])
    physical(client, environment, swap, 'OPEN_RETURN')
    current = row(client, 'swap_transactions', UUID(swap['id']))
    assert current['state'] == 'RETURN_ACCEPTED'
    with client.app.state.db.sessions.begin() as session:
        review(session, client.app.state.db, current, 'TEST_MANUAL_RECOVERY')
    tech = auth('technician')
    case = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech).json()
    return swap, tech, case


def test_expired_handover_reinspection_keeps_fence_until_atomic_settlement(client, environment, auth):
    from unittest.mock import patch
    swap, tech, case = returned_case(client, environment, auth)
    # Inject the operation clock only; custody/snapshots retain their actual
    # fixture history. The first operation has no received service evidence.
    with patch('app.application.recovery.utcnow', return_value=utcnow()-timedelta(seconds=121)):
        response = client.post(f"/v1/swaps/{swap['id']}/recovery/evidence",
            headers={**tech, 'Idempotency-Key': str(uuid4())}, json={
                'expected_version': case['version'], 'statement': {
                    'kind': 'BEGIN_OPERATION', 'purpose': 'RETURN_OLD_TO_CUSTOMER'}, 'note': 'Expired service operation'})
    assert response.status_code == 200, response.text
    prior = response.json()['active_operation']
    # Independent fixture observation models the service effect whose response
    # was lost. This is not a production DB custody update or command ACK.
    physical_snapshot(client, environment, swap, swap['return_compartment_id'])
    case = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech).json()
    case, op = evidence(client, environment, auth, swap, tech, case)
    assert op['supersedes_id'] == prior['id']
    fenced = row(client, 'recovery_operations', UUID(prior['id']))
    assert fenced['consumed_at'] is None and fenced['cancelled_at'] is None
    assert row(client, 'batteries', UUID(swap['old_battery_id']))['location_kind'] == 'COMPARTMENT'
    response = settle(client, swap, tech, case, op)
    assert response.status_code == 200, response.text
    assert response.json()['old_pin_settled'] is True
    assert row(client, 'recovery_operations', UUID(prior['id']))['consumed_at'] is not None
    assert row(client, 'batteries', UUID(swap['old_battery_id']))['holder_user_id'] == demo_id('customer')
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'


def physical_snapshot(client, environment, swap, empty_slot, boot=None):
    from test_phase4 import snapshot_packet, send
    dev = row(client, 'devices', demo_id('device:S01'))
    body = snapshot_packet(str(boot or dev['boot_id']), 1 if boot else dev['last_seq'] + 1)
    db = client.app.state.db
    with db.sessions() as session:
        commands = db.table('device_commands')
        body['payload']['command_ledger'] = [{'command_id': str(c['id']), 'status': 'EXECUTED'}
            for c in session.execute(select(commands).where(commands.c.swap_id == UUID(swap['id']))).mappings()]
        slots = db.table('compartments')
        for slot in body['payload']['slots']:
            current = session.execute(select(slots).where(slots.c.id == UUID(slot['compartment_id']))).mappings().one()
            slot.update(present=current['observed_present'], observed_serial=current['observed_serial'])
            if slot['compartment_id'] == empty_slot:
                slot.update(present=False, observed_serial=None)
    response = send(client, environment, body)
    assert response.status_code == 202, response.text
    assert row(client, 'device_events', UUID(body['event_id']))['accepted']


def test_F_reconnect_does_not_reuse_old_boot_service_proof(client, environment, auth):
    swap, tech, case = start_case(client, environment, auth)
    case, op = evidence(client, environment, auth, swap, tech, case)
    physical_snapshot(client, environment, swap, swap['return_compartment_id'], boot=uuid4())
    response = settle(client, swap, tech, case, op)
    assert response.status_code == 422 and response.json()['code'] == 'EVIDENCE_REQUIRED'
    assert row(client, 'recovery_operations', UUID(op['id']))['consumed_at'] is None
    assert row(client, 'recovery_cases', UUID(case['id']))['old_pin_settled'] is False
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'


@pytest.mark.parametrize('already_returned', [False, True])
def test_resume_uses_normal_custody_workflow_and_closes_case_only_at_completion(client, environment, auth, already_returned):
    from test_phase7 import drive, physical
    swap, tech, case = (returned_case if already_returned else start_case)(client, environment, auth)
    if already_returned:
        # Obtain the current full snapshot as well as the correlated return
        # events; no physical state is changed by this fixture helper.
        physical_snapshot(client, environment, swap, None)
    case, op = evidence(client, environment, auth, swap, tech, case, purpose='RESUME_SWAP')
    response = settle(client, swap, tech, case, op)
    assert response.status_code == 200, response.text
    assert response.json()['state'] == 'EVIDENCE_RECORDED'
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == ('AWAITING_PICKUP' if already_returned else 'AWAITING_RETURN')
    if not already_returned:
        physical(client, environment, swap, 'OPEN_RETURN')
        drive(client, swap['id'])
    physical(client, environment, swap, 'OPEN_SUPPLY')
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'COMPLETED'
    assert row(client, 'recovery_cases', UUID(case['id']))['state'] == 'RESOLVED'


@pytest.mark.parametrize('purpose,empty,terminal', [
    ('RETURN_OLD_TO_CUSTOMER', 'return_compartment_id', False),
    ('VERIFY_NEW_DELIVERY', 'supply_compartment_id', True),
])
def test_B_D_manual_settlement_keeps_finance_separate(client, environment, auth, purpose, empty, terminal):
    swap, tech, case = returned_case(client, environment, auth)
    physical_snapshot(client, environment, swap, swap[empty])
    case = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech).json()
    case, op = evidence(client, environment, auth, swap, tech, case, purpose=purpose)
    response = settle(client, swap, tech, case, op)
    assert response.status_code == 200, response.text
    current = row(client, 'swap_transactions', UUID(swap['id']))
    assert current['state'] == ('COMPLETED' if terminal else 'REVIEW_REQUIRED')
    target = row(client, 'batteries', UUID(swap['new_battery_id' if terminal else 'old_battery_id']))
    assert target['location_kind'] == 'CUSTOMER' and target['holder_user_id'] == current['customer_id']
    db = client.app.state.db
    with db.sessions() as session:
        holds, payments, commands = (db.table(t) for t in ('resource_reservations', 'payments', 'device_commands'))
        assert len(session.execute(select(holds.c.id).where(holds.c.swap_id == current['id'], holds.c.released_at.is_(None))).all()) == (0 if terminal else 3)
        assert session.scalar(select(payments.c.state).where(payments.c.swap_id == current['id'])) == 'SUCCEEDED'
        assert len(session.execute(select(commands.c.id).where(commands.c.swap_id == current['id'])).all()) == 1


@pytest.mark.parametrize('fault', ['reject', 'wrong_serial', 'expired', 'offline', 'customer_revoked'])
def test_missing_or_conflicting_proof_never_consumes_operation(client, environment, auth, fault):
    swap, tech, case = start_case(client, environment, auth)
    case, op = evidence(client, environment, auth, swap, tech, case,
        serial='WRONG' if fault == 'wrong_serial' else None, confirm=fault != 'reject')
    if fault == 'expired':
        # Freeze only the decision clock; do not mutate immutable timestamps.
        from unittest.mock import patch
        from datetime import datetime
        with patch('app.application.recovery.utcnow', return_value=datetime.fromisoformat(op['expires_at'])):
            result = settle(client, swap, tech, case, op)
    else:
        if fault in ('offline', 'customer_revoked'):
            with owner(client) as (connection, db):
                if fault == 'offline':
                    table = db.table('devices')
                    connection.execute(update(table).where(table.c.id == demo_id('device:S01')).values(last_received_at=utcnow()-timedelta(seconds=20)))
                else:
                    table = db.table('auth_sessions')
                    connection.execute(update(table).where(table.c.user_id == demo_id('customer')).values(revoked_at=utcnow()))
        result = settle(client, swap, tech, case, op)
    assert result.status_code in (403, 409, 422), result.text
    assert row(client, 'recovery_operations', UUID(op['id']))['consumed_at'] is None
    assert row(client, 'recovery_cases', UUID(case['id']))['old_pin_settled'] is False
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'
