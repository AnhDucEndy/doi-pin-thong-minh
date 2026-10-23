from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import secrets
from uuid import uuid4

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012
import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import DBAPIError
import yaml

from app.application.identity import DomainError, utcnow
from app.config import ROOT, Settings
from app.domain.identity import digest
from app.main import create_app, require_station
from app.seed import demo_id, seed

SPEC = yaml.safe_load((ROOT / 'doi-pin-giai-doan-2/contracts/openapi.yaml').read_text(encoding='utf-8'))


def validate(name, data):
    registry = Registry().with_resource('urn:doi-pin-openapi', DRAFT202012.create_resource(SPEC))
    Draft202012Validator({'$ref': f'urn:doi-pin-openapi#/components/schemas/{name}'}, registry=registry).validate(data)


def headers(auth, key=None):
    return {**auth, 'Idempotency-Key': str(key or uuid4())}


def create_customer(client, auth, username=None):
    password = secrets.token_urlsafe(20)
    result = client.post('/v1/users', headers=headers(auth), json={
        'username': username or 'test-' + uuid4().hex[:12], 'password': password, 'role': 'CUSTOMER'})
    assert result.status_code == 201, result.text
    return result.json(), password


@pytest.mark.parametrize('role', ['admin', 'customer', 'technician'])
def test_TC01_login_me_roles_no_secret(client, auth, role):
    credential = auth(role)
    result = client.get('/v1/me', headers=credential)
    assert result.status_code == 200
    validate('Users', result.json())
    assert result.json()['role'] == role.upper()
    assert not any(word in result.text for word in ('password', 'hash', 'key', 'token'))
    with client.app.state.db.sessions() as session:
        sessions = client.app.state.db.table('auth_sessions')
        stored = session.execute(select(sessions)).mappings().all()
        token = credential['Authorization'].split()[1]
        assert any(row['token_hash'] == digest(token) for row in stored)
        assert all(row['token_hash'] != token for row in stored)


@pytest.mark.parametrize('role', ['customer', 'technician'])
def test_TC01_cross_role_denied(client, auth, role):
    credential = auth(role)
    assert client.get('/v1/users', headers=credential).status_code == 403
    assert client.post('/v1/users', headers=headers(credential), json={
        'username': 'forbidden', 'password': secrets.token_urlsafe(20), 'role': 'ADMIN'}).status_code == 403
    assert client.patch(f'/v1/users/{demo_id("admin")}', headers=headers(credential), json={
        'expected_version': 1, 'state': 'LOCKED'}).status_code == 403
    assert client.put(f'/v1/users/{demo_id("technician")}/station-assignments', headers=headers(credential),
        json={'station_ids': []}).status_code == 403


def test_TC01_wrong_password_persisted_limit_and_spoofing(client):
    for index in range(5):
        response = client.post('/v1/auth/login', json={'username': 'missing-account', 'password': 'wrong'},
                               headers={'X-Forwarded-For': f'1.2.3.{index}'})
        assert response.status_code == 401
        validate('Error', response.json())
    # New request with a spoofed header cannot reset counters held in PostgreSQL.
    assert client.post('/v1/auth/login', json={'username': 'another-name', 'password': 'wrong'},
                       headers={'X-Forwarded-For': '9.8.7.6'}).status_code == 429
    with client.app.state.db.sessions() as session:
        row = session.execute(select(client.app.state.db.table('login_limits')).where(
            client.app.state.db.table('login_limits').c.bucket_key == digest('username:missing-account'))).mappings().one()
        assert row['failed_count'] == 5


def test_TC01_rate_limit_concurrent_process_sessions(environment):
    # Actual commits and separate app/DB sessions, outside rollback fixture.
    username = 'concurrent-' + uuid4().hex
    app = create_app(environment['settings'])
    with TestClient(app, client=('phase1-rate-' + uuid4().hex, 40000)) as http:
        with ThreadPoolExecutor(max_workers=6) as pool:
            codes = list(pool.map(lambda _: http.post('/v1/auth/login', json={
                'username': username, 'password': 'wrong'}).status_code, range(6)))
    assert sorted(codes) == [401, 401, 401, 401, 401, 429]


def test_TC01_logout_replay_and_expiry(client, auth):
    credential = auth('customer')
    key = uuid4()
    result = client.post('/v1/auth/logout', headers=headers(credential, key))
    assert result.status_code == 200
    assert client.post('/v1/auth/logout', headers=headers(credential, key)).json() == result.json()
    assert client.get('/v1/me', headers=credential).status_code == 401
    credential = auth('customer')
    with client.app.state.db.sessions.begin() as session:
        sessions = client.app.state.db.table('auth_sessions')
        session.execute(update(sessions).where(sessions.c.token_hash == digest(credential['Authorization'].split()[1]))
                        .values(expires_at=utcnow() - timedelta(seconds=1)))
    assert client.get('/v1/me', headers=credential).status_code == 401


def test_TC01_unauthenticated_and_bad_payload_sanitized(client):
    assert client.get('/v1/me').status_code == 401
    assert client.get('/v1/users', headers={'Authorization': 'Bearer invalid'}).status_code == 401
    secret = secrets.token_urlsafe(20)
    result = client.post('/v1/auth/login', json={'username': 'admin', 'password': secret, 'role': 'ADMIN'})
    assert result.status_code == 422
    assert secret not in result.text
    validate('Error', result.json())


def test_TC02_create_replay_conflict_and_pagination(client, auth):
    admin = auth()
    body = {'username': '  New-Customer  ', 'password': secrets.token_urlsafe(20), 'role': 'CUSTOMER'}
    key = uuid4()
    first = client.post('/v1/users', headers=headers(admin, key), json=body)
    second = client.post('/v1/users', headers=headers(admin, key), json=body)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert first.json()['username'] == 'new-customer'
    validate('Users', first.json())
    assert client.post('/v1/users', headers=headers(admin, key), json={**body, 'role': 'ADMIN'}).status_code == 409
    assert client.post('/v1/users', headers=headers(admin), json=body).status_code == 409
    page = client.get('/v1/users?limit=1', headers=admin)
    validate('UsersPage', page.json())
    next_page = client.get('/v1/users', params={'limit': 1, 'cursor': page.json()['next_cursor']}, headers=admin)
    assert page.json()['items'][0]['id'] != next_page.json()['items'][0]['id']


def test_TC02_lock_revokes_sessions_keeps_history(client, auth, environment):
    db = client.app.state.db
    # Historical fixture belongs only to the new test schema, not the demo DB schema.
    with environment['owner'].begin() as connection:
        credential = uuid4()
        connection.execute(text("INSERT INTO credentials(id,user_id,credential_hash) VALUES (:id,:user,:hash)"),
                           {'id': credential, 'user': demo_id('customer'), 'hash': digest(str(credential))})
        historical = uuid4()
        connection.execute(text("""INSERT INTO swap_transactions(id,customer_id,station_id,verified_via,credential_id,
            state,policy_id,policy_snapshot,closed_at) VALUES (:id,:user,:station,'RFID',:credential,'CANCELLED',:policy,'{}',now())"""),
            {'id': historical, 'user': demo_id('customer'), 'station': demo_id('S01'), 'credential': credential, 'policy': demo_id('policy:1')})
    admin, customer = auth(), auth('customer')
    result = client.patch(f'/v1/users/{demo_id("customer")}', headers=headers(admin),
                          json={'expected_version': 1, 'state': 'LOCKED'})
    assert result.status_code == 200
    assert client.get('/v1/me', headers=customer).status_code == 401
    assert client.post('/v1/auth/login', json={'username': 'customer', 'password': environment['passwords']['customer']}).status_code == 401
    with db.sessions() as session:
        assert session.scalar(select(db.table('swap_transactions').c.id).where(db.table('swap_transactions').c.id == historical)) == historical
    assert client.delete(f'/v1/users/{demo_id("customer")}', headers=admin).status_code == 405


def test_TC02_role_change_revokes_and_stale_version(client, auth):
    admin = auth()
    created, password = create_customer(client, admin)
    login = client.post('/v1/auth/login', json={'username': created['username'], 'password': password}).json()
    result = client.patch(f'/v1/users/{created["id"]}', headers=headers(admin),
                          json={'expected_version': 1, 'role': 'TECHNICIAN'})
    assert result.status_code == 200
    assert client.get('/v1/me', headers={'Authorization': 'Bearer ' + login['access_token']}).status_code == 401
    assert client.patch(f'/v1/users/{created["id"]}', headers=headers(admin),
                        json={'expected_version': 1, 'state': 'LOCKED'}).status_code == 409
    assert client.patch(f'/v1/users/{demo_id("customer")}', headers=headers(admin),
                        json={'expected_version': 1, 'role': 'TECHNICIAN'}).status_code == 409


def test_TC02_assignments_atomic_and_scope(client, auth):
    admin = auth()
    path = f'/v1/users/{demo_id("technician")}/station-assignments'
    assert client.put(path, headers=headers(admin), json={'station_ids': [str(uuid4())]}).status_code == 422
    db = client.app.state.db
    with db.sessions() as session:
        tech = session.execute(select(db.table('users')).where(db.table('users').c.id == demo_id('technician'))).mappings().one()
        require_station(session, db, tech, demo_id('S01'))
        with pytest.raises(DomainError):
            require_station(session, db, tech, demo_id('S02'))
        administrator = session.execute(select(db.table('users')).where(db.table('users').c.id == demo_id('admin'))).mappings().one()
        with pytest.raises(DomainError):
            require_station(session, db, administrator, demo_id('S01'))
    assert client.put(path, headers=headers(admin), json={'station_ids': [str(demo_id('S02'))]}).status_code == 200
    assert client.put(f'/v1/users/{demo_id("customer")}/station-assignments', headers=headers(admin),
                      json={'station_ids': []}).status_code == 422


def test_TC02_last_admin_and_immutable_audit(client, auth):
    admin = auth()
    assert client.patch(f'/v1/users/{demo_id("admin")}', headers=headers(admin),
                        json={'expected_version': 1, 'state': 'LOCKED'}).status_code == 409
    with pytest.raises(DBAPIError):
        with client.app.state.db.sessions.begin() as session:
            session.execute(text("UPDATE audit_events SET action='tampered'"))
    with pytest.raises(DBAPIError):
        with client.app.state.db.sessions.begin() as session:
            session.execute(text('DELETE FROM audit_events'))
    with client.app.state.db.sessions() as session:
        logs = session.execute(select(client.app.state.db.table('audit_events'))).mappings().all()
        assert logs and all('password' not in json.dumps(row['after_data']) for row in logs)


def test_foundation_runtime_not_owner_and_policy_immutable(client):
    with client.app.state.db.sessions() as session:
        assert session.scalar(text('SELECT current_user')) == 'doi_pin_runtime'
        assert session.scalar(text('SHOW server_version_num')).startswith('17')
    with pytest.raises(DBAPIError):
        with client.app.state.db.sessions.begin() as session:
            session.execute(text('CREATE TABLE forbidden_runtime_table (id int)'))
    with pytest.raises(DBAPIError):
        with client.app.state.db.sessions.begin() as session:
            session.execute(text("UPDATE demo_policies SET revision=2"))


def test_foundation_seed_repeat_preserves_accounts(environment):
    db = environment['seed_db']
    with db.sessions() as session:
        before = session.execute(select(db.table('users')).order_by(db.table('users').c.id)).mappings().all()
    seed(db, environment['passwords'], environment['keys'])
    with db.sessions() as session:
        after = session.execute(select(db.table('users')).order_by(db.table('users').c.id)).mappings().all()
        assert before == after
        assert len(session.execute(select(db.table('stations'))).all()) == 2
        assert len(session.execute(select(db.table('compartments'))).all()) == 12
        assert session.scalar(select(db.table('demo_policies').c.review_status)) == 'APPROVED_FOR_SIMULATION_BY_USER'


def test_P003_missing_config_fail_closed(environment, tmp_path):
    source = tmp_path / 'policy.yaml'
    source.write_text((ROOT / 'doi-pin-giai-doan-2/contracts/demo-config.approved.yaml').read_text(encoding='utf-8'), encoding='utf-8')
    app = create_app(Settings(environment['settings'].database_url, environment['settings'].schema, str(source)))
    with TestClient(app) as http:
        source.write_text(source.read_text(encoding='utf-8').replace('fee_minor: 9000', 'fee_minor: null'), encoding='utf-8')
        response = http.get('/health')
        assert response.status_code == 422 and response.json()['code'] == 'CONFIG_NOT_READY'
        assert http.post('/v1/auth/login', json={'username': 'admin', 'password': environment['passwords']['admin']}).status_code == 422


def test_phase1_contract_and_no_future_endpoints(client):
    from openapi_spec_validator import validate_spec
    validate_spec(client.app.openapi())
    paths = client.app.openapi()['paths']
    assert set(path for path in paths if path.startswith('/v1/')) == {
        '/v1/auth/login', '/v1/auth/logout', '/v1/me', '/v1/users', '/v1/users/{user_id}',
        '/v1/users/{user_id}/station-assignments'}
    for path, methods in paths.items():
        if path == '/health':
            continue
        for method, operation in methods.items():
            assert operation['operationId'] == SPEC['paths'][path][method]['operationId']
            assert operation['x-roles'] == SPEC['paths'][path][method]['x-roles']
