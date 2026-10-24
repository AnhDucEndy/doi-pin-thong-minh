"""PostgreSQL-only integration tests in a new schema, with per-test rollback.

No DROP DATABASE/SCHEMA, TRUNCATE or volume removal. The test schema is retained
as evidence; only transactions created by each test are rolled back.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import ROOT, Settings
from app.infrastructure.db import Database
from app.main import create_app
from app.seed import seed


@pytest.fixture(scope='session')
def environment():
    schema = 'phase2_test_' + uuid4().hex[:12]
    previous = os.environ.get('DATABASE_SCHEMA')
    os.environ['DATABASE_SCHEMA'] = schema
    subprocess.run([sys.executable, str(ROOT / 'tools/provision_database.py'), 'roles'], check=True)
    config = Config(str(ROOT / 'services/backend/alembic.ini'))
    command.upgrade(config, '0001_baseline')
    migration_url = os.environ['MIGRATION_DATABASE_URL']
    owner = create_engine(migration_url, hide_parameters=True, connect_args={'options': f'-csearch_path={schema},public -cstatement_timeout=15000 -clock_timeout=5000'})
    marker = uuid4()
    with owner.begin() as conn:
        conn.execute(text("INSERT INTO users(id,username,password_hash,role) VALUES (:id,'migration-survivor','not-a-login-account','CUSTOMER')"), {'id': marker})
    command.upgrade(config, 'head')
    command.upgrade(config, 'head')  # Repeated upgrade must not recreate tables or lose rows.
    with owner.connect() as conn:
        assert conn.scalar(text('SELECT id FROM users WHERE id=:id'), {'id': marker}) == marker
    subprocess.run([sys.executable, str(ROOT / 'tools/provision_database.py'), 'grants'], check=True)
    db = Database(Settings(migration_url, schema))
    passwords = {name: secrets.token_urlsafe(24) for name in ('admin', 'customer', 'technician')}
    keys = {code: secrets.token_urlsafe(32) for code in ('S01', 'S02')}
    seed(db, passwords, keys)
    settings = Settings(os.environ['DATABASE_URL'], schema)
    evidence = {'schema': schema, 'postgresql': None, 'migration_empty_and_upgrade': 'Passed',
                'production_schema_modified_by_tests': False, 'schema_retained': True}
    with owner.connect() as conn:
        evidence['postgresql'] = conn.scalar(text('SHOW server_version'))
    (ROOT / 'docs/PHASE2_TEST_ENVIRONMENT.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    yield {'settings': settings, 'owner': owner, 'seed_db': db, 'passwords': passwords, 'keys': keys}
    db.engine.dispose()
    owner.dispose()
    if previous is None:
        os.environ.pop('DATABASE_SCHEMA', None)
    else:
        os.environ['DATABASE_SCHEMA'] = previous


@pytest.fixture
def client(environment):
    app = create_app(environment['settings'])
    with TestClient(app) as client:
        # Authenticate test fixture connection as the bootstrap role, then run every API
        # request as the real runtime role. F2 fixtures can briefly reset the role to
        # insert evidence into future-module tables inside this same rollback transaction.
        fixture_engine = create_engine(os.environ['DATABASE_ADMIN_URL'], hide_parameters=True,
            connect_args={'options': f'-csearch_path={environment["settings"].schema},public -cstatement_timeout=15000 -clock_timeout=5000'})
        connection = fixture_engine.connect()
        transaction = connection.begin()
        connection.exec_driver_sql('SET LOCAL ROLE doi_pin_runtime')
        app.state.test_connection = connection
        app.state.db.sessions = sessionmaker(bind=connection, expire_on_commit=False,
                                            join_transaction_mode='create_savepoint')
        yield client
        transaction.rollback()
        connection.close()
        fixture_engine.dispose()


@pytest.fixture
def auth(client, environment):
    def authenticate(name='admin'):
        response = client.post('/v1/auth/login', json={'username': name, 'password': environment['passwords'][name]})
        assert response.status_code == 200
        return {'Authorization': 'Bearer ' + response.json()['access_token']}
    return authenticate
