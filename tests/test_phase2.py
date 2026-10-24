"""F2 PostgreSQL integration tests. Synthetic observations are fixtures, not ingestion APIs."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

from app.application.identity import utcnow
from app.seed import demo_id, seed
from app.main import create_app
from test_phase1 import headers, validate


@contextmanager
def owner(client):
    connection = client.app.state.test_connection
    connection.exec_driver_sql('RESET ROLE')
    try:
        yield connection, client.app.state.db
    finally:
        connection.exec_driver_sql('SET LOCAL ROLE doi_pin_runtime')


def action(client, auth, slot=1, station='S01', **changes):
    return client.post(f'/v1/compartments/{demo_id(f"{station}:slot:{slot}")}/actions',
        headers=headers(auth), json={'expected_version': 1, 'action': 'SET_MAINTENANCE', 'reason': 'Kiểm tra F2', **changes})


def observation(client, empty=False):
    now, boot, event_id = utcnow(), uuid4(), uuid4()
    slot_id = demo_id('S01:slot:1' if empty else 'S01:slot:2')
    serial = None if empty else 'S01-B002'
    with owner(client) as (c, db):
        c.execute(update(db.table('devices')).where(db.table('devices').c.id == demo_id('device:S01')).values(
            boot_id=boot, last_received_at=now, last_seq=10))
        c.execute(update(db.table('compartments')).where(db.table('compartments').c.id == slot_id).values(
            service_state='BLOCKED' if empty else 'ACTIVE', door_state='CLOSED', observed_present=not empty,
            observed_serial=serial, observed_at=now))
        c.execute(insert(db.table('device_events')).values(id=event_id, device_id=demo_id('device:S01'), boot_id=boot,
            seq=1, kind='SNAPSHOT', observed_at=now, received_at=now, payload_hash='fixture', accepted=True,
            processed_at=now, payload={'command_ledger': [], 'slots': [{'compartment_id': str(slot_id), 'door_state': 'CLOSED',
                'present': not empty, 'observed_serial': serial}]}))
        if not empty:
            c.execute(update(db.table('batteries')).where(db.table('batteries').c.id == demo_id('S01:battery:2')).values(lifecycle='IN_SERVICE'))
            telemetry_event = uuid4()
            c.execute(insert(db.table('device_events')).values(id=telemetry_event, device_id=demo_id('device:S01'),
                boot_id=boot, seq=2, kind='TELEMETRY', compartment_id=slot_id, observed_at=now, received_at=now,
                payload_hash='fixture', payload={}, accepted=True, processed_at=now))
            c.execute(insert(db.table('battery_telemetry')).values(id=uuid4(), event_id=telemetry_event,
                battery_id=demo_id('S01:battery:2'), soc=80, soh=80, temperature_c=40, measured_at=now,
                received_at=now, quality_ok=True))
    return event_id


def swap_fixture(client, reserved=True):
    identity, credential = uuid4(), uuid4()
    with owner(client) as (c, db):
        c.execute(insert(db.table('credentials')).values(id=credential, user_id=demo_id('customer'),
            credential_hash='fixture-' + uuid4().hex))
        data = dict(id=identity, customer_id=demo_id('customer'), station_id=demo_id('S01'),
            verified_via='RFID', credential_id=credential, policy_id=demo_id('policy:1'), policy_snapshot={}, state='VERIFIED')
        if reserved:
            data.update(state='RESERVED', old_battery_id=demo_id('customer:initial-battery'),
                new_battery_id=demo_id('S01:battery:2'), return_compartment_id=demo_id('S01:slot:1'),
                supply_compartment_id=demo_id('S01:slot:2'), amount_minor=9000,
                reservation_expires_at=utcnow()-timedelta(seconds=30))
        c.execute(insert(db.table('swap_transactions')).values(**data))
        if reserved:
            c.execute(insert(db.table('resource_reservations')).values(id=uuid4(), swap_id=identity,
                compartment_id=demo_id('S01:slot:1')))
    return identity


@pytest.mark.parametrize('role', ['admin', 'customer', 'technician'])
def test_TC03_demo_public_projection(client, auth, role):
    result = client.get('/v1/stations', headers=auth(role))
    assert result.status_code == 200
    validate('StationAvailabilityPage', result.json())
    assert len(result.json()['items']) == 2
    assert all(s['available_count'] == 0 for s in result.json()['items'])
    assert 'serial' not in result.text and 'temperature' not in result.text
    if role == 'admin':
        for code in ['S01', 'S02']:
            response = client.get(f'/v1/stations/{demo_id(code)}/compartments', headers=auth('admin'))
            validate('CompartmentsPage', response.json())
            assert sorted(x['slot_no'] for x in response.json()['items']) == list(range(1, 7))


def test_TC03_scope_auth_and_not_found(client, auth):
    tech, customer, admin = auth('technician'), auth('customer'), auth('admin')
    assert client.get('/v1/stations').status_code == 401
    for suffix in ['', '/compartments']:
        assert client.get(f'/v1/stations/{demo_id("S01")}{suffix}', headers=tech).status_code == 200
        assert client.get(f'/v1/stations/{demo_id("S02")}{suffix}', headers=tech).status_code == 403
        assert client.get(f'/v1/stations/{demo_id("S01")}{suffix}', headers=customer).status_code == 403
    assert client.get(f'/v1/stations/{uuid4()}', headers=admin).status_code == 404
    assert client.get('/v1/devices', headers=customer).status_code == 403
    devices = client.get('/v1/devices', headers=tech)
    validate('DevicesPage', devices.json())
    assert len(devices.json()['items']) == 1 and 'key_hash' not in devices.text
    assert action(client, customer).status_code == 403
    assert action(client, tech, station='S02').status_code == 403
    for actor in [tech, customer]:
        assert client.post('/v1/stations', headers=headers(actor), json={'code': 'X', 'name': 'X', 'address': 'X'}).status_code == 403


def test_TC03_station_device_crud_idempotency(client, auth):
    admin = auth(); payload = {'code': 'NEW', 'name': 'Trạm mới', 'address': 'Demo'}
    result = client.post('/v1/stations', headers=headers(admin), json=payload)
    assert result.status_code == 201, result.text
    validate('Stations', result.json()); station = result.json()
    assert client.post('/v1/stations', headers=headers(admin), json=payload).status_code == 409
    path = f'/v1/stations/{station["id"]}'
    result = client.patch(path, headers=headers(admin), json={'expected_version': 1, 'state': 'MAINTENANCE'})
    assert result.status_code == 200 and result.json()['version'] == 2
    assert client.patch(path, headers=headers(admin), json={'expected_version': 1, 'name': 'stale'}).status_code == 409
    assert client.patch(path, headers=headers(admin), json={'expected_version': 2, 'state': 'UNKNOWN'}).status_code == 422
    key = uuid4(); body = {'station_id': station['id'], 'serial': 'DEVICE-NEW'}
    result = client.post('/v1/devices', headers=headers(admin, key), json=body)
    assert result.status_code == 201, result.text
    validate('DeviceCreated', result.json())
    assert client.post('/v1/devices', headers=headers(admin, key), json=body).json() == result.json()
    secret = result.json()['device_key_once']
    with client.app.state.db.sessions() as session:
        assert secret not in str(session.execute(select(client.app.state.db.table('idempotency_records'))).mappings().all())
        assert secret not in str(session.execute(select(client.app.state.db.table('audit_events'))).mappings().all())
    assert client.post('/v1/devices', headers=headers(admin), json=body).status_code == 409
    device = result.json()['device']
    assert client.patch(f'/v1/devices/{device["id"]}', headers=headers(admin), json={'expected_version': 1, 'enabled': False}).status_code == 200
    assert client.get('/v1/stations?limit=1', headers=admin).json()['next_cursor']
    assert client.get('/v1/stations?limit=0', headers=admin).status_code == 422


def test_TC04_create_maintenance_separate_door_and_terminal(client, auth):
    admin = auth(); path = f'/v1/stations/{demo_id("S01")}/compartments'
    result = client.post(path, headers=headers(admin), json={'slot_no': 7})
    assert result.status_code == 201
    validate('Compartments', result.json())
    assert (result.json()['service_state'], result.json()['door_state']) == ('BLOCKED', 'UNKNOWN')
    assert client.post(path, headers=headers(admin), json={'slot_no': 7}).status_code == 409
    assert client.post(path, headers=headers(admin), json={'slot_no': 0}).status_code == 422
    assert client.post(path, headers=headers(admin), json={'slot_no': 8, 'door_state': 'OPEN'}).status_code == 422
    with owner(client) as (c, db):
        c.execute(update(db.table('compartments')).where(db.table('compartments').c.id == demo_id('S01:slot:1')).values(
            door_state='OPEN', observed_present=False, observed_at=utcnow()))
    result = action(client, admin)
    assert result.status_code == 200, result.text
    assert result.json()['service_state'] == 'MAINTENANCE' and result.json()['door_state'] == 'OPEN'
    others = client.get(path, headers=admin).json()['items']
    assert next(s for s in others if s['slot_no'] == 2)['service_state'] == 'BLOCKED'
    assert action(client, admin).status_code == 409
    assert action(client, auth('technician'), action='RETIRE', expected_version=2).status_code == 403
    result = action(client, admin, action='RETIRE', expected_version=2)
    assert result.status_code == 200 and result.json()['service_state'] == 'RETIRED'
    assert action(client, admin, action='RESTORE', expected_version=3).status_code == 409


def test_TC04_restore_requires_snapshot_and_does_not_issue_commands(client, auth):
    admin = auth()
    assert action(client, admin, action='RESTORE').status_code == 422
    event = observation(client, empty=True)
    assert action(client, admin, action='RESTORE', evidence_event_id=str(uuid4())).status_code == 422
    result = action(client, auth('technician'), action='RESTORE', evidence_event_id=str(event))
    assert result.status_code == 200, result.text
    assert result.json()['door_state'] == 'CLOSED' and result.json()['service_state'] == 'ACTIVE'
    with client.app.state.db.sessions() as session:
        assert session.execute(select(client.app.state.db.table('device_commands'))).first() is None


def test_TC04_active_transaction_guards_and_device_review(client, auth):
    admin = auth(); identity = swap_fixture(client)
    assert action(client, admin).status_code == 409
    assert action(client, admin, slot=2).status_code == 409
    assert client.patch(f'/v1/stations/{demo_id("S01")}', headers=headers(admin), json={'expected_version': 1, 'state': 'INACTIVE'}).status_code == 409
    result = client.patch(f'/v1/devices/{demo_id("device:S01")}', headers=headers(admin), json={'expected_version': 1, 'enabled': False})
    assert result.status_code == 200, result.text
    with client.app.state.db.sessions() as session:
        swaps, reservations = client.app.state.db.table('swap_transactions'), client.app.state.db.table('resource_reservations')
        assert session.scalar(select(swaps.c.state).where(swaps.c.id == identity)) == 'REVIEW_REQUIRED'
        assert session.scalar(select(reservations.c.released_at).where(reservations.c.swap_id == identity)) is None


def test_TC04_unreserved_verification_disable_fails_atomically(client, auth):
    admin = auth(); swap_fixture(client, reserved=False)
    result = client.patch(f'/v1/devices/{demo_id("device:S01")}', headers=headers(admin), json={'expected_version': 1, 'enabled': False})
    assert result.status_code == 409
    devices = client.get('/v1/devices', headers=admin).json()['items']
    assert next(d for d in devices if d['id'] == str(demo_id('device:S01')))['enabled'] is True


@pytest.mark.parametrize('change', ['valid', 'soc', 'soh', 'temperature', 'fault', 'quality', 'stale', 'boot', 'door', 'quarantined', 'family', 'offline', 'maintenance'])
def test_TC05_availability_fail_closed(client, auth, change):
    admin = auth(); observation(client)
    with owner(client) as (c, db):
        if change in ['soc', 'soh', 'temperature', 'fault', 'quality', 'stale']:
            values = {'soc': {'soc': 79}, 'soh': {'soh': 79}, 'temperature': {'temperature_c': 41},
                'fault': {'fault_codes': ['TEST_FAULT']}, 'quality': {'quality_ok': False},
                'stale': {'measured_at': utcnow()-timedelta(seconds=30)}}[change]
            c.execute(update(db.table('battery_telemetry')).values(**values))
        if change == 'boot': c.execute(update(db.table('devices')).values(boot_id=uuid4()))
        if change == 'door': c.execute(update(db.table('compartments')).values(door_state='OPEN'))
        if change == 'quarantined': c.execute(update(db.table('batteries')).values(lifecycle='QUARANTINED'))
        if change == 'family': c.execute(update(db.table('batteries')).values(family='OTHER'))
        if change == 'offline': c.execute(update(db.table('devices')).values(last_received_at=utcnow()-timedelta(seconds=30)))
        if change == 'maintenance': c.execute(update(db.table('stations')).values(state='MAINTENANCE'))
    result = client.get('/v1/stations', headers=admin)
    assert result.status_code == 200, result.text
    assert next(s for s in result.json()['items'] if s['station_id'] == str(demo_id('S01')))['available_count'] == (1 if change == 'valid' else 0)


def test_TC03_seed_rerun_preserves_config(environment):
    seed(environment['seed_db'], environment['passwords'], environment['keys'])
    seed(environment['seed_db'], environment['passwords'], environment['keys'])
    with environment['owner'].connect() as c:
        assert len(c.execute(select(environment['seed_db'].table('stations'))).all()) == 2
        assert len(c.execute(select(environment['seed_db'].table('compartments'))).all()) == 12


@pytest.mark.parametrize('problem', ['old_boot', 'stale', 'unaccepted', 'open_door', 'mismatch', 'alert', 'pending_command'])
def test_TC04_restore_rejects_unsafe_evidence(client, auth, problem):
    admin = auth(); event = observation(client, empty=True)
    with owner(client) as (c, db):
        events, slots = db.table('device_events'), db.table('compartments')
        if problem == 'old_boot': c.execute(update(db.table('devices')).values(boot_id=uuid4()))
        if problem == 'stale': c.execute(update(events).values(received_at=utcnow()-timedelta(seconds=30)))
        if problem == 'unaccepted': c.execute(update(events).values(accepted=False))
        if problem == 'open_door': c.execute(update(slots).values(door_state='OPEN'))
        if problem == 'mismatch': c.execute(update(events).values(payload={'slots': []}))
        if problem == 'alert':
            c.execute(insert(db.table('alerts')).values(id=uuid4(), station_id=demo_id('S01'),
                compartment_id=demo_id('S01:slot:1'), dedup_key='fixture', code='FAULT', state='ACKNOWLEDGED', acknowledged_by=demo_id('admin')))
    if problem == 'pending_command':
        swap = swap_fixture(client, reserved=False)
        # A cancelled verification fixture isolates the pending-command guard from the active-swap guard.
        with owner(client) as (c, db):
            c.execute(update(db.table('swap_transactions')).where(db.table('swap_transactions').c.id == swap).values(state='CANCELLED', closed_at=utcnow()))
            c.execute(insert(db.table('device_commands')).values(id=uuid4(), device_id=demo_id('device:S01'), swap_id=swap,
                compartment_id=demo_id('S01:slot:1'), kind='OPEN_RETURN', state='ACKNOWLEDGED',
                expires_at=utcnow()-timedelta(seconds=20), payload_hash='fixture', payload={}))
    result = action(client, admin, action='RESTORE', evidence_event_id=str(event))
    assert result.status_code == 422, result.text
    assert result.json()['code'] == 'EVIDENCE_REQUIRED'


def test_TC05_latest_bad_sample_never_falls_back(client, auth):
    admin = auth(); observation(client)
    with owner(client) as (c, db):
        device = c.execute(select(db.table('devices')).where(db.table('devices').c.id == demo_id('device:S01'))).mappings().one()
        event, now = uuid4(), utcnow()
        c.execute(insert(db.table('device_events')).values(id=event, device_id=device['id'], boot_id=device['boot_id'],
            seq=3, kind='TELEMETRY', compartment_id=demo_id('S01:slot:2'), observed_at=now, received_at=now,
            payload_hash='fixture', payload={}, accepted=True, processed_at=now))
        c.execute(insert(db.table('battery_telemetry')).values(id=uuid4(), event_id=event, battery_id=demo_id('S01:battery:2'),
            soc=100, soh=100, temperature_c=20, measured_at=now, received_at=now, quality_ok=False))
    result = client.get('/v1/stations', headers=admin)
    assert all(s['available_count'] == 0 for s in result.json()['items'])


def test_TC04_occupied_quarantined_restore_rejected(client, auth):
    admin = auth(); event = observation(client)
    with owner(client) as (c, db):
        c.execute(update(db.table('compartments')).where(db.table('compartments').c.id == demo_id('S01:slot:2')).values(service_state='BLOCKED'))
        c.execute(update(db.table('batteries')).values(lifecycle='QUARANTINED'))
    assert action(client, admin, slot=2, action='RESTORE', evidence_event_id=str(event)).status_code == 422


def test_TC04_battery_only_reservation_blocks_maintenance(client, auth):
    admin = auth(); swap = swap_fixture(client)
    with owner(client) as (c, db):
        # Retained reservation on a third pin, with no active swap referencing its slot.
        c.execute(insert(db.table('resource_reservations')).values(id=uuid4(), swap_id=swap, battery_id=demo_id('S01:battery:3')))
    assert action(client, admin, slot=3).status_code == 409


def test_TC03_concurrent_version_conflict(environment):
    app = create_app(environment['settings'])
    with TestClient(app, client=('phase2-concurrent-' + uuid4().hex, 40000)) as http:
        login = http.post('/v1/auth/login', json={'username': 'admin', 'password': environment['passwords']['admin']})
        auth = {'Authorization': 'Bearer ' + login.json()['access_token']}
        path = f'/v1/stations/{demo_id("S02")}'
        version = http.get(path, headers=auth).json()['version']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda i: http.patch(path, headers=headers(auth), json={
                'expected_version': version, 'name': f'Trạm kiểm thử đồng thời {i}'}).status_code, range(2)))
        assert sorted(results) == [200, 409]


@pytest.mark.parametrize('guard', ['maintenance', 'reservation', 'presence'])
def test_TC05_supply_guards(client, auth, guard):
    admin = auth(); observation(client)
    if guard == 'reservation': swap_fixture(client)
    else:
        with owner(client) as (c, db):
            c.execute(update(db.table('compartments')).where(db.table('compartments').c.id == demo_id('S01:slot:2')).values(
                **({'service_state': 'MAINTENANCE'} if guard == 'maintenance' else {'observed_serial': 'WRONG'})))
    assert all(s['available_count'] == 0 for s in client.get('/v1/stations', headers=admin).json()['items'])
