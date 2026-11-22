"""Fixture-only regressions: committed ingress isolation and the unchanged guard."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from conftest import device_event_snapshot, fixture_evidence
from test_phase4 import snapshot_packet
from test_phase8b_b1b_no_delivery import physical_review, begin
from simulators.device.no_delivery import inspect


def test_committed_ingress_does_not_leak_to_session_schema(environment, committed_environment):
    before = device_event_snapshot(environment)
    isolated = committed_environment
    packet = snapshot_packet()
    with TestClient(create_app(isolated['settings'])) as http:
        def submit(_):
            return http.post('/v1/device/events',
                headers={'X-Device-Key': isolated['keys']['S01']}, json=packet)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(submit, range(2)))
    assert [response.status_code for response in responses] == [202, 202]
    assert sorted(response.json()['duplicate'] for response in responses) == [False, True]
    # Observe through another DB session after the application committed.
    rows = device_event_snapshot(isolated)
    pending = [row for row in rows if row['id'] == packet['event_id']]
    assert len(pending) == 1 and not pending[0]['accepted'] and pending[0]['processed_at'] is None
    assert isolated['settings'].schema != environment['settings'].schema
    assert device_event_snapshot(environment) == before


def test_pending_snapshot_still_requires_quiescence(client, environment, auth, tmp_path):
    swap, sim, customer, tech = physical_review(client, environment, auth, tmp_path)
    try:
        # A valid authenticated inbox input absent from this simulator's ledger.
        # Do not process it or fabricate an accepted state to obtain proof.
        pending = snapshot_packet(boot=sim.boot, seq=999999)
        device = {'X-Device-Key': environment['keys']['S01']}
        received = client.post('/v1/device/events', headers=device, json=pending)
        assert received.status_code == 202
        begin(client, swap, tech)
        task = client.get('/v1/device/recovery-tasks', headers=device).json()['items'][0]
        packet = inspect(sim, task)
        response = client.post('/v1/device/recovery-observations', headers=device, json=packet)
        assert (response.status_code, response.json()['code']) == (409, 'QUIESCENCE_REQUIRED')
        table = client.app.state.db.table('device_events')
        with client.app.state.db.sessions() as session:
            stored = session.execute(select(table).where(table.c.id == UUID(pending['event_id']))).mappings().one()
            assert not stored['accepted'] and stored['processed_at'] is None
        case = client.get('/v1/swaps/'+str(swap['id'])+'/recovery', headers=tech).json()
        assert case['certificate'] is None and case['new_pin_delivered'] == 'UNKNOWN'
        fixture_evidence('pending_'+uuid4().hex, dict(schema=environment['settings'].schema,
            pending_event_id=pending['event_id'], accepted=stored['accepted'],
            processed_at=stored['processed_at'], proof_status=response.status_code,
            proof_code=response.json()['code'], certificate=None))
    finally:
        sim.close()
