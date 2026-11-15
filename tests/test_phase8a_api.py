"""PostgreSQL evidence receipt tests, isolated by the existing fixture."""
from uuid import UUID, uuid4

from sqlalchemy import select

from app.application.swaps import review
from app.application.recovery import lock_context
from test_phase7 import paid
from test_phase4 import row


def start_case(client, environment, auth):
    swap = paid(client, environment, auth)
    db = client.app.state.db
    with db.sessions.begin() as session:
        # Phase7 review is the legitimate fixture entry point; no physical
        # evidence, custody or payment outcome is manufactured by recovery.
        current = row(client, 'swap_transactions', UUID(swap['id']))
        review(session, db, current, 'TEST_RECOVERY_INSPECTION')
    tech = auth('technician')
    case = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech)
    assert case.status_code == 200, case.text
    return swap, tech, case.json()


def begin(client, swap, tech, case):
    return client.post(f"/v1/swaps/{swap['id']}/recovery/evidence",
        headers={**tech, 'Idempotency-Key': str(uuid4())}, json={'expected_version': case['version'],
        'statement': {'kind': 'BEGIN_OPERATION', 'purpose': 'VERIFY_OLD_POSSESSION'}, 'note': 'inspect'})


def test_recovery_read_role_and_station_scope(client, environment, auth):
    swap, tech, case = start_case(client, environment, auth)
    url = f"/v1/swaps/{swap['id']}/recovery"
    assert client.get(url, headers=auth('customer')).status_code == 403
    assert client.get(url, headers=auth('admin')).status_code == 200
    assert client.get(url).status_code == 401
    assert case['old_pin_settled'] is False and case['new_pin_delivered'] == 'UNKNOWN'


def test_begin_has_no_custody_payment_or_hold_effect(client, environment, auth):
    swap, tech, case = start_case(client, environment, auth)
    old = row(client, 'batteries', UUID(swap['old_battery_id']))
    response = begin(client, swap, tech, case)
    assert response.status_code == 200, response.text
    op = response.json()['active_operation']
    from app.api.recovery_schemas import RecoveryOperationView
    RecoveryOperationView.model_validate(op)
    assert op['purpose'] == 'VERIFY_OLD_POSSESSION'
    assert op['attestations'] == []
    assert row(client, 'batteries', old['id']) == old
    current = row(client, 'swap_transactions', UUID(swap['id']))
    assert current['state'] == 'REVIEW_REQUIRED'
    db = client.app.state.db
    with db.sessions() as session:
        holds = db.table('resource_reservations')
        assert len(session.execute(select(holds.c.id).where(holds.c.swap_id == current['id'],
            holds.c.released_at.is_(None))).all()) == 3
        payments = db.table('payments')
        assert session.scalar(select(payments.c.state).where(payments.c.swap_id == current['id'])) == 'SUCCEEDED'


def test_customer_reject_is_append_only_and_idempotent(client, environment, auth):
    swap, tech, case = start_case(client, environment, auth)
    result = begin(client, swap, tech, case)
    assert result.status_code == 200, result.text
    op = result.json()['active_operation']
    customer = auth('customer')
    url = f"/v1/swaps/{swap['id']}/recovery/confirmations"
    headers = {**customer, 'Idempotency-Key': str(uuid4())}
    body = {'operation_id': op['id'], 'context_hash': op['context_hash'], 'confirm': False}
    first = client.post(url, headers=headers, json=body)
    assert first.status_code == 201, first.text
    assert first.json()['confirmed'] is False
    assert client.post(url, headers=headers, json=body).json() == first.json()
    changed = client.post(url, headers=headers, json={**body, 'confirm': True})
    assert changed.status_code == 409 and changed.json()['code'] == 'IDEMPOTENCY_CONFLICT'
    changed = client.post(url, headers={**customer, 'Idempotency-Key': str(uuid4())}, json={**body, 'confirm': True})
    assert changed.status_code == 409 and changed.json()['code'] == 'RECOVERY_ATTESTATION_EXISTS'
    current = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech).json()
    assert current['active_operation']['attestations'][0]['payload']['confirm'] is False
    assert current['old_pin_settled'] is False


def test_admin_cannot_attest_as_technician(client, environment, auth):
    swap, tech, case = start_case(client, environment, auth)
    response = begin(client, swap, auth('admin'), case)
    assert response.status_code == 403
