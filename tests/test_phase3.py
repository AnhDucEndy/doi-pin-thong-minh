"""TC06–TC08 F3 contract tests against PostgreSQL; ingestion is outside this phase."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from app.application.identity import utcnow
from app.domain.bms import BMSPayload
from app.main import create_app
from app.seed import demo_id, seed
from test_phase1 import headers, validate
from test_phase2 import observation, owner, swap_fixture

PIN = demo_id('S01:battery:2')


def command(client, auth, action, identity=PIN, version=1, **extra):
    return client.post(f'/v1/batteries/{identity}/actions', headers=headers(auth), json={
        'expected_version': version, 'action': action, 'reason': 'F3 inspection', **extra})


def ready(client, lifecycle='REGISTERED'):
    event = observation(client)
    with owner(client) as (c, db):
        c.execute(update(db.table('batteries')).where(db.table('batteries').c.id == PIN).values(lifecycle=lifecycle))
    return str(event)


def test_TC06_profile_create_unique_idempotency_and_read(client, auth):
    admin = auth(); body = {'serial': 'NEW-PIN', 'family': 'DEMO_FAMILY_A', 'location_kind': 'UNKNOWN'}
    key = uuid4()
    response = client.post('/v1/batteries', headers=headers(admin, key), json=body)
    assert response.status_code == 201, response.text
    validate('Batteries', response.json())
    assert response.json()['lifecycle'] == 'REGISTERED'
    assert client.post('/v1/batteries', headers=headers(admin, key), json=body).json() == response.json()
    assert client.post('/v1/batteries', headers=headers(admin), json=body).status_code == 409
    assert client.post('/v1/batteries', headers=headers(admin, key), json={**body, 'serial': 'other'}).json()['code'] == 'IDEMPOTENCY_CONFLICT'
    page = client.get('/v1/batteries?limit=100', headers=admin)
    validate('BatteriesPage', page.json())
    assert any(p['id'] == response.json()['id'] for p in page.json()['items'])
    assert client.get('/v1/batteries?limit=1', headers=admin).json()['next_cursor']
    assert client.get('/v1/batteries?limit=101', headers=admin).status_code == 422
    assert client.patch(f'/v1/batteries/{PIN}', headers=headers(admin), json={'compartment_id': str(demo_id('S01:slot:1'))}).status_code == 404


@pytest.mark.parametrize('changes', [
    {'family': 'OTHER'}, {'location_kind': 'COMPARTMENT'},
    {'location_kind': 'CUSTOMER'}, {'compartment_id': str(demo_id('S01:slot:1'))},
    {'location_kind': 'CUSTOMER', 'holder_user_id': str(demo_id('admin'))},
    {'location_kind': 'COMPARTMENT', 'compartment_id': str(demo_id('S01:slot:1')), 'holder_user_id': str(demo_id('customer'))},
    {'lifecycle': 'IN_SERVICE'}, {'soc': 90}])
def test_TC06_invalid_profile(client, auth, changes):
    result = client.post('/v1/batteries', headers=headers(auth()), json={
        'serial': uuid4().hex, 'family': 'DEMO_FAMILY_A', 'location_kind': 'UNKNOWN', **changes})
    assert result.status_code == 422, result.text


def test_TC06_initial_location_unique_and_holder(client, auth):
    admin = auth()
    body = {'serial': 'INITIAL', 'family': 'DEMO_FAMILY_A', 'location_kind': 'COMPARTMENT', 'compartment_id': str(demo_id('S01:slot:1'))}
    assert client.post('/v1/batteries', headers=headers(admin), json=body).status_code == 201
    assert client.post('/v1/batteries', headers=headers(admin), json={**body, 'serial': 'SECOND'}).status_code == 409
    assert client.post('/v1/batteries', headers=headers(admin), json={**body, 'serial': 'OCCUPIED', 'compartment_id': str(demo_id('S01:slot:2'))}).status_code == 409
    assert client.post('/v1/batteries', headers=headers(admin), json={'serial': 'SECOND-CUSTOMER', 'family': 'DEMO_FAMILY_A',
        'location_kind': 'CUSTOMER', 'holder_user_id': str(demo_id('customer'))}).status_code == 409
    with owner(client) as (c, db):
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(insert(db.table('batteries')).values(id=uuid4(), serial='DDL-CONFLICT', family='DEMO_FAMILY_A',
                location_kind='COMPARTMENT', compartment_id=demo_id('S01:slot:2')))


def test_TC06_scope_and_missing(client, auth):
    admin, tech, customer = auth(), auth('technician'), auth('customer')
    assert client.get('/v1/batteries').status_code == 401
    assert client.get('/v1/batteries', headers=customer).status_code == 403
    pins = client.get('/v1/batteries?limit=100', headers=tech).json()['items']
    assert len(pins) == 5 and all(p['serial'].startswith('S01-') for p in pins)
    assert client.get(f'/v1/batteries/{demo_id("S02:battery:2")}/telemetry', headers=tech).status_code == 403
    assert client.get(f'/v1/batteries/{PIN}/telemetry', headers=customer).status_code == 403
    assert client.get(f'/v1/batteries/{uuid4()}/telemetry', headers=admin).status_code == 404
    assert command(client, tech, 'QUARANTINE', identity=demo_id('S02:battery:2')).status_code == 403
    assert command(client, customer, 'QUARANTINE').status_code == 403
    assert command(client, admin, 'QUARANTINE').status_code == 403
    assert command(client, tech, 'RETIRE').status_code == 403
    assert command(client, admin, 'RETIRE', identity=uuid4()).status_code == 404


@pytest.mark.parametrize('field,value', [('soc', -0.01), ('soc', 100.01), ('soh', -1), ('soh', 101),
    ('soc', float('nan')), ('temperature_c', float('inf')), ('temperature_c', float('nan')), ('soc', '80')])
def test_TC07_bms_payload_domain_validation(field, value):
    body = {'battery_id': str(PIN), 'soc': 80, 'soh': 80, 'temperature_c': 40, 'fault_codes': []}
    body[field] = value
    with pytest.raises(ValidationError): BMSPayload.model_validate(body)


@pytest.mark.parametrize('soc,soh,temp,available', [(80,80,40,True), (79.99,80,40,False),
    (80,79.99,40,False), (80,80,40.01,False), (100,100,0,True), (0,0,0,False)])
def test_TC07_boundaries_metadata_and_f2_consistency(client, auth, soc, soh, temp, available):
    admin = auth(); ready(client, 'IN_SERVICE')
    with owner(client) as (c, db):
        c.execute(update(db.table('battery_telemetry')).where(db.table('battery_telemetry').c.battery_id == PIN).values(
            soc=soc, soh=soh, temperature_c=temp))
    result = client.get(f'/v1/batteries/{PIN}/telemetry', headers=admin)
    assert result.status_code == 200, result.text
    validate('BatteryTelemetryPage', result.json())
    assert result.headers['X-Battery-Available'] == str(available).lower()
    stations = client.get('/v1/stations', headers=admin).json()['items']
    assert next(s['available_count'] for s in stations if s['station_id'] == str(demo_id('S01'))) == int(available)


@pytest.mark.parametrize('problem', ['missing', 'stale', 'fault', 'quality', 'boot', 'door', 'location', 'quarantine', 'reservation'])
def test_TC07_valid_numbers_are_not_sufficient(client, auth, problem):
    admin = auth(); ready(client, 'IN_SERVICE')
    with owner(client) as (c, db):
        if problem in ('missing', 'stale', 'fault', 'quality'):
            values = {'missing': {'soh': None}, 'stale': {'received_at': utcnow()-timedelta(seconds=30)},
                'fault': {'fault_codes': ['BMS_FAULT']}, 'quality': {'quality_ok': False}}[problem]
            c.execute(update(db.table('battery_telemetry')).where(db.table('battery_telemetry').c.battery_id == PIN).values(**values))
        if problem == 'boot': c.execute(update(db.table('devices')).values(boot_id=uuid4()))
        if problem == 'door': c.execute(update(db.table('compartments')).values(door_state='OPEN'))
        if problem == 'location': c.execute(update(db.table('compartments')).values(observed_serial='MISMATCH'))
        if problem == 'quarantine': c.execute(update(db.table('batteries')).where(db.table('batteries').c.id == PIN).values(lifecycle='QUARANTINED'))
    if problem == 'reservation': swap_fixture(client)
    response = client.get(f'/v1/batteries/{PIN}/telemetry', headers=admin)
    assert response.status_code == 200 and response.headers['X-Battery-Available'] == 'false'


def test_TC07_history_pagination_and_unverified_seed(client, auth):
    admin = auth(); ready(client)
    path = f'/v1/batteries/{PIN}/telemetry'
    page = client.get(path+'?limit=1', headers=admin).json()
    assert page['next_cursor']
    second = client.get(path+'?limit=1&cursor='+page['next_cursor'], headers=admin)
    assert second.status_code == 200
    assert second.json()['items'][0]['id'] != page['items'][0]['id']
    assert second.json()['items'][0]['quality_ok'] is False
    assert client.get(path+f'?cursor={uuid4()}', headers=admin).status_code == 422
    empty = client.get(f'/v1/batteries/{demo_id("customer:initial-battery")}/telemetry', headers=admin)
    assert empty.json()['items'] == [] and empty.headers['X-Battery-Available'] == 'false'


def test_TC08_activation_then_compartment_restore_no_deadlock(client, auth):
    tech = auth('technician'); evidence = ready(client)
    with owner(client) as (c, db):
        c.execute(update(db.table('compartments')).where(db.table('compartments').c.id == demo_id('S01:slot:2')).values(service_state='BLOCKED'))
    response = command(client, tech, 'ACTIVATE', evidence_event_id=evidence)
    assert response.status_code == 200, response.text
    assert response.json()['lifecycle'] == 'IN_SERVICE'
    assert client.get(f'/v1/batteries/{PIN}/telemetry', headers=tech).headers['X-Battery-Available'] == 'false'
    response = client.post(f'/v1/compartments/{demo_id("S01:slot:2")}/actions', headers=headers(tech), json={
        'expected_version': 1, 'action': 'RESTORE', 'reason': 'Verified', 'evidence_event_id': evidence})
    assert response.status_code == 200, response.text
    assert client.get(f'/v1/batteries/{PIN}/telemetry', headers=tech).headers['X-Battery-Available'] == 'true'


def test_TC08_quarantine_restore_atomic_alerts(client, auth):
    tech = auth('technician'); evidence = ready(client, 'IN_SERVICE')
    assert command(client, tech, 'QUARANTINE').status_code == 200
    alert_id = uuid4()
    with owner(client) as (c, db):
        c.execute(insert(db.table('alerts')).values(id=alert_id, station_id=demo_id('S01'), battery_id=PIN,
            dedup_key='F3-FIXTURE', code='BMS_FAULT', state='ACKNOWLEDGED', acknowledged_by=demo_id('technician')))
    response = command(client, tech, 'RESTORE', version=2, evidence_event_id=evidence)
    assert response.status_code == 422 and response.json()['code'] == 'UNRESOLVED_ALERTS'
    response = command(client, tech, 'RESTORE', version=2, evidence_event_id=evidence, resolve_alert_ids=[str(alert_id)])
    assert response.status_code == 200 and response.json()['lifecycle'] == 'IN_SERVICE', response.text
    with client.app.state.db.sessions() as session:
        alert = session.execute(select(client.app.state.db.table('alerts')).where(client.app.state.db.table('alerts').c.id == alert_id)).mappings().one()
        assert alert['state'] == 'RESOLVED' and alert['resolved_by'] == demo_id('technician')
        audit = session.execute(select(client.app.state.db.table('audit_events'))).mappings().all()
        assert any(a['action'] == 'BATTERY_RESTORE_RESOLVE' for a in audit)


@pytest.mark.parametrize('problem', ['missing', 'stale', 'fault', 'wrong_boot', 'wrong_snapshot', 'foreign_alert'])
def test_TC08_restore_fails_closed_and_rolls_back(client, auth, problem):
    tech = auth('technician'); evidence = ready(client, 'QUARANTINED')
    with owner(client) as (c, db):
        if problem in ('missing','stale','fault'):
            values = {'missing': {'soc': None}, 'stale': {'measured_at': utcnow()-timedelta(seconds=30)}, 'fault': {'fault_codes': ['FAULT']}}[problem]
            c.execute(update(db.table('battery_telemetry')).where(db.table('battery_telemetry').c.battery_id == PIN).values(**values))
        if problem == 'wrong_boot': c.execute(update(db.table('devices')).values(boot_id=uuid4()))
        if problem == 'wrong_snapshot': evidence = str(uuid4())
    result = command(client, tech, 'RESTORE', evidence_event_id=evidence,
        **({'resolve_alert_ids': [str(uuid4())]} if problem == 'foreign_alert' else {}))
    assert result.status_code == 422
    pin = next(p for p in client.get('/v1/batteries?limit=100', headers=tech).json()['items'] if p['id'] == str(PIN))
    assert pin['lifecycle'] == 'QUARANTINED' and pin['version'] == 1


def test_TC08_state_guards_retirement_and_version(client, auth):
    admin, tech = auth(), auth('technician')
    assert command(client, tech, 'RESTORE').status_code == 409
    assert command(client, tech, 'ACTIVATE').status_code == 422
    assert command(client, admin, 'RETIRE', identity=demo_id('customer:initial-battery')).status_code == 409
    assert command(client, tech, 'QUARANTINE', version=99).json()['code'] == 'VERSION_CONFLICT'
    assert command(client, admin, 'RETIRE').status_code == 200
    assert command(client, admin, 'RETIRE', version=2).status_code == 409
    assert command(client, tech, 'ACTIVATE', version=2).status_code == 409


def test_TC08_active_swap_and_reservation_preserved(client, auth):
    tech, admin = auth('technician'), auth(); swap_fixture(client)
    for actor, action in [(tech,'QUARANTINE'), (admin,'RETIRE')]:
        result = command(client, actor, action)
        assert result.status_code == 409 and result.json()['code'] == 'ACTIVE_TRANSACTION'


def test_TC08_concurrent_version(environment):
    with TestClient(create_app(environment['settings']), client=('F3-'+uuid4().hex, 40000)) as http:
        token = http.post('/v1/auth/login', json={'username':'admin', 'password':environment['passwords']['admin']}).json()['access_token']
        admin = {'Authorization':'Bearer '+token}
        created = http.post('/v1/batteries', headers=headers(admin), json={'serial':'CONCURRENT-'+uuid4().hex,
            'family':'DEMO_FAMILY_A','location_kind':'UNKNOWN'})
        assert created.status_code == 201
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(lambda _: command(http, admin, 'RETIRE', identity=created.json()['id']).status_code, range(2)))
        assert sorted(codes) == [200,409]


def test_TC07_seed_repeat_preserves_samples_and_no_proof(environment):
    db = environment['seed_db']
    ids = [demo_id(f'f3:reading:{code}:{slot}') for code in ('S01','S02') for slot in range(2,7)]
    def samples():
        with db.sessions() as s: return s.execute(select(db.table('battery_telemetry')).where(db.table('battery_telemetry').c.id.in_(ids)).order_by(db.table('battery_telemetry').c.id)).mappings().all()
    before = samples()
    seed(db, environment['passwords'], environment['keys']); seed(db, environment['passwords'], environment['keys'])
    assert len(before) == 10 and before == samples()
    assert all(not row['quality_ok'] for row in before)


def test_TC08_activation_is_not_supply_eligibility(client, auth):
    tech = auth('technician'); evidence = ready(client)
    with owner(client) as (c, db):
        c.execute(update(db.table('battery_telemetry')).where(db.table('battery_telemetry').c.battery_id == PIN).values(soc=20, soh=70))
    response = command(client, tech, 'ACTIVATE', evidence_event_id=evidence)
    assert response.status_code == 200 and response.json()['lifecycle'] == 'IN_SERVICE'
    assert client.get(f'/v1/batteries/{PIN}/telemetry', headers=tech).headers['X-Battery-Available'] == 'false'
