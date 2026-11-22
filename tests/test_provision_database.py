"""Opt-in PC provisioning checks. Never use the repository's environment fixture.

Only pcprov_<uuid> schemas are mutated. Every schema and evidence file is retained.
"""
import importlib.util
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pc_provision_tool', ROOT/'tools/provision_database.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
V = dict(dotenv_values(ROOT/'.env'))
RUNS = ROOT/'.local/pc-b1b/reference-compat-runs'
RUN = None  # Bound once by the fixture to a freshly reserved launcher identity.


def write_new(path, value):
    """Never replace a previous artifact, including within the current run."""
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvidenceRun:
    def __init__(self, path, identity):
        self.path, self.identity = path, identity
        self.records = []
        self.sequence = 0

    @classmethod
    def reserve(cls, run_id=None):
        run_id = run_id or uuid4().hex
        if not re.fullmatch('[0-9a-f]{32}', run_id):
            raise ValueError('Run ID must be a canonical UUID hex value')
        RUNS.mkdir(parents=True, exist_ok=True)
        path = RUNS/run_id
        path.mkdir(exist_ok=False)  # Collision, old path or symlink: refuse, no retry/reuse.
        identity = {'run_id': run_id, 'token': uuid4().hex,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    'source_sha256': {p: digest(ROOT/p) for p in
                                      ('tests/test_provision_database.py', 'tools/provision_database.py')},
                    'evidence_dir': str(path.resolve())}
        (path/'events').mkdir()
        write_new(path/'run.json', identity)
        return cls(path, identity)

    def write(self, name, value):
        if Path(name).name != name:
            raise ValueError('Artifact name must be a basename')
        write_new(self.path/name, value)

    def event(self, record, stage):
        self.sequence += 1
        write_new(self.path/'events'/f'{self.sequence:06}.json',
                  {'run_id': self.identity['run_id'], 'at': datetime.now(timezone.utc).isoformat(),
                   'stage': stage, 'schema': dict(record)})

    def owns(self, name):
        return any(r['schema'] == name and r['creation'] == 'confirmed' for r in self.records)


def current_run():
    if RUN is None:
        raise RuntimeError('Use the evidence-isolated module launcher; no implicit run01 output')
    return RUN


def connect(role='admin', schema=None, readonly=False):
    key = {'admin': 'DATABASE_ADMIN_URL', 'runtime': 'DATABASE_URL', 'migrator': 'MIGRATION_DATABASE_URL'}[role]
    u = make_url(V[key])
    assert (u.host, u.port, u.database) == ('127.0.0.1', 5433, 'doi_pin')
    options = '-cstatement_timeout=10000 -clock_timeout=5000'
    if readonly:
        options += ' -cdefault_transaction_read_only=on'
    if schema:
        assert re.fullmatch('pcprov_[0-9a-f]{32}', schema) and current_run().owns(schema)
        options += ' -csearch_path='+schema+',public'
    return psycopg.connect(host=u.host, port=u.port, dbname=u.database, user=u.username,
                           password=u.password, autocommit=True, connect_timeout=5, options=options)


def command(schema, args):
    run = current_run()
    assert re.fullmatch('pcprov_[0-9a-f]{32}', schema) and run.owns(schema)
    env = dict(os.environ, **V)
    env.update(DATABASE_SCHEMA=schema, PYTHONPATH=str(ROOT/'services/backend'),
               PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    result = subprocess.run([sys.executable, '-B', *args], cwd=ROOT, env=env,
                            capture_output=True, text=True, encoding='utf-8', timeout=90)
    # Keep diagnostics without exposing raw credentials or connection URLs.
    output = result.stdout+'\n'+result.stderr
    for key, value in sorted(V.items(), key=lambda item: len(item[1]), reverse=True):
        if any(part in key for part in ('PASSWORD', 'KEY', 'SECRET', '_URL')):
            output = output.replace(value, '[REDACTED]')
    name = schema+'_'+uuid4().hex+'.json'
    run.write(name, {'run_id': run.identity['run_id'], 'schema': schema, 'args': args,
                     'exit': result.returncode, 'output': output})
    assert result.returncode == 0, 'Official command failed; see redacted evidence '+name


def effective(c, schema):
    """Independent complete effective table/column matrix, including grant options."""
    tables = {}
    for table, in c.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY 1", (schema,)).fetchall():
        qualified = sql.Identifier(schema, table).as_string(c)
        tp = {p: c.execute('SELECT has_table_privilege(%s,%s,%s)', ('doi_pin_runtime', qualified, p)).fetchone()[0]
              for p in tool.TABLE_PRIVILEGES}
        cols = {}
        for name, in c.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY column_name', (schema, table)).fetchall():
            cols[name] = {p: c.execute('SELECT has_column_privilege(%s,%s,%s,%s)', ('doi_pin_runtime', qualified, name, p)).fetchone()[0]
                          for p in tool.COLUMN_PRIVILEGES}
        tables[table] = {'table': tp, 'columns': cols}
    return tables


@pytest.fixture(scope='module')
def schemas(request):
    global RUN
    assert os.getenv('PC_PROVISIONING_REVIEW') == '1', 'Explicit PC-only opt-in required'
    run_id = os.environ['PC_PROVISIONING_RUN_ID']
    assert re.fullmatch('[0-9a-f]{32}', run_id)
    path = RUNS/run_id
    identity = json.loads((path/'run.json').read_text(encoding='utf-8'))
    assert identity['run_id'] == run_id and identity['token'] == os.environ['PC_PROVISIONING_RUN_TOKEN']
    assert identity['evidence_dir'] == str(path.resolve())
    assert Path(request.config.option.xmlpath).resolve() == (path/'results.xml').resolve()
    assert request.config.option.noconftest
    assert not request.config.pluginmanager.hasplugin('cacheprovider')
    assert not request.config.pluginmanager.hasplugin('recovery_audit_checks')
    assert not (path/'results.xml').exists() and (path/'protected_before.json').is_file()
    run = EvidenceRun(path, identity)
    run.write('fixture_claim.json', {'run_id': run_id, 'pid': os.getpid()})
    RUN = run

    def make(revision='0002_user_approval', profile=None, seed=False):
        name = 'pcprov_'+uuid4().hex
        record = {'schema': name, 'revision': revision, 'profile': profile, 'seed': seed,
                  'creation': 'pending', 'status': 'planned', 'run_id': run_id}
        run.records.append(record)
        run.event(record, 'before-create')
        try:
            # No IF NOT EXISTS: a collision must never adopt or modify an old schema.
            with connect() as c:
                record['creation'] = 'unknown'  # Connection loss during CREATE is not confirmation.
                c.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION doi_pin_migrator').format(sql.Identifier(name)))
            record.update(creation='confirmed', status='partial')
            run.event(record, 'created')
            for stage, args in (
                ('roles', ['tools/provision_database.py', 'roles']),
                ('migration', ['-m', 'alembic', '-c', 'services/backend/alembic.ini', 'upgrade', revision]),
                *([('seed', ['-m', 'app.seed'])] if seed else []),
                *([('grants', ['tools/provision_database.py', 'grants', '--profile', profile])] if profile else []),
            ):
                run.event(record, 'before-'+stage)
                command(name, args)
            record['status'] = 'ready'
            run.event(record, 'ready')
        except BaseException as error:
            if isinstance(error, psycopg.errors.DuplicateSchema):
                record['creation'] = 'not-created'
            record.update(status='partial' if record['creation'] == 'confirmed' else 'failed-or-unknown',
                          error_type=type(error).__name__)
            run.event(record, 'setup-failed')  # No exception text/credentials.
            raise
        return name

    try:
        yield make
    finally:
        # Final inventory is the current run's ledger, never a prefix-wide ownership claim.
        run.write('schemas.json', {'run_id': run_id, 'records': run.records})
        owned = [r['schema'] for r in run.records if r['creation'] == 'confirmed']
        observations = []
        try:
            with connect(readonly=True) as c:
                for name in owned:
                    row = c.execute('SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=%s', (name,)).fetchone()
                    observations.append({'schema': name, 'exists': row is not None,
                                         'catalog_owner': row[0] if row else None})
        finally:
            run.write('retained_schemas.json', {'run_id': run_id, 'owned_schemas': owned,
                      'observations': observations, 'cleanup': 'none; retain all',
                      'unknown_candidates': [r['schema'] for r in run.records if r['creation'] == 'unknown']})


def grant(c, schema, profile='runtime'):
    with c.transaction():
        with c.cursor() as cursor:
            return tool.apply_grants(cursor, schema, profile)


def denied(c, statement):
    # 42501 proves permission refusal, not a missing row/constraint failure.
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc:
        with c.transaction():
            c.execute(statement)
    assert exc.value.sqlstate == '42501'


def test_0002_reference_seed_fingerprint_and_permissions(schemas):
    s = schemas(profile='reference-readonly', seed=True)
    with connect('runtime', s) as c:
        assert c.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0002_user_approval'
        assert c.execute('SELECT count(*) FROM users').fetchone()[0] == 3
        assert c.execute('SELECT count(*) FROM battery_telemetry').fetchone()[0] == 10
        assert c.execute('SELECT count(*) FROM demo_policies').fetchone()[0] == 1
        for statement in ('INSERT INTO users SELECT * FROM users LIMIT 0',
                          'UPDATE users SET version=version+1', 'DELETE FROM users', 'TRUNCATE users',
                          "UPDATE alembic_version SET version_num=version_num",
                          'CREATE TABLE forbidden(id integer)', 'ALTER TABLE users ADD COLUMN forbidden int',
                          'DROP TABLE login_limits'):
            denied(c, statement)
        # All reference tables deny mutation, not merely the eight fingerprint tables.
        for table in tool.BASE_COLUMNS:
            q = sql.Identifier(s, table)
            for statement in (sql.SQL('INSERT INTO {} DEFAULT VALUES').format(q),
                              sql.SQL('DELETE FROM {}').format(q), sql.SQL('TRUNCATE {}').format(q)):
                denied(c, statement)
        first = c.execute('SELECT password_hash FROM users ORDER BY username').fetchall()
    # Official idempotent owner seed path; runtime SELECT cannot substitute for this.
    command(s, ['-m', 'app.seed'])
    with connect('runtime', s) as c:
        assert c.execute('SELECT password_hash FROM users ORDER BY username').fetchall() == first
    runner_spec = importlib.util.spec_from_file_location('pc_fingerprint_only', ROOT/'tools/run_phase8b.py')
    runner = importlib.util.module_from_spec(runner_spec)
    runner_spec.loader.exec_module(runner)
    a, b = runner.demo(s), runner.demo(s)  # Never invoke runner.main()/pytest fixtures.
    assert a == b and a['revision'] == '0002_user_approval' and len(a) == 9
    current_run().write('reference_fixture_fingerprint.json', {'schema': s, 'first': a, 'second': b})


@pytest.mark.parametrize('revision', tool.REVISIONS)
def test_runtime_plans_and_idempotency(schemas, revision):
    s = schemas(revision, 'runtime')
    with connect() as c:
        before = effective(c, s)
        grant(c, s)
        assert effective(c, s) == before
        current_run().write(s+'_effective.json', before)
        if revision == tool.REVISIONS[2]:
            # Independent snapshot from original, already-provisioned development.
            assert before == effective(c, 'pc_dev_b1b')
        if revision == tool.REVISIONS[1]:
            assert not before['refund_eligibility_certificates']['table']['INSERT']
            assert not before['refund_certificate_redemptions']['table']['INSERT']
            assert 'refund_certificate_revocations' not in before
    with connect('runtime', s) as c:
        # Positive writes with real valid data and rollback, no domain effects.
        with c.transaction(force_rollback=True):
            identity = uuid4()
            c.execute("INSERT INTO audit_events(id,actor_type,actor_id,aggregate_type,aggregate_id,action,correlation_id) VALUES (%s,'SYSTEM','provision-review','fixture',%s,'PRIVILEGE_CHECK',%s)", (identity, uuid4(), uuid4()))
            assert c.execute('SELECT id FROM audit_events WHERE id=%s', (identity,)).fetchone()[0] == identity
            for statement in (sql.SQL('UPDATE audit_events SET action=action WHERE id={}').format(sql.Literal(identity)),
                              sql.SQL('DELETE FROM audit_events WHERE id={}').format(sql.Literal(identity)),
                              'TRUNCATE audit_events', 'CREATE TABLE forbidden(id int)',
                              'UPDATE alembic_version SET version_num=version_num'):
                denied(c, statement)
        if revision != tool.REVISIONS[0]:
            for table in ('refund_eligibility_certificates', 'refund_certificate_redemptions'):
                denied(c, sql.SQL('UPDATE {} SET {}={}').format(sql.Identifier(table), sql.Identifier('certificate_id' if 'redemptions' in table else 'id'), sql.Identifier('certificate_id' if 'redemptions' in table else 'id')))
                denied(c, sql.SQL('DELETE FROM {}').format(sql.Identifier(table)))
                if revision == tool.REVISIONS[1]:
                    denied(c, sql.SQL('INSERT INTO {} DEFAULT VALUES').format(sql.Identifier(table)))


@pytest.mark.parametrize('mutation', ['unknown_revision', 'missing_table', 'missing_column', 'revision_mismatch',
                                     'wrong_owner', 'wrong_table_owner', 'extra_table', 'disabled_audit',
                                     'table_privilege', 'column_privilege', 'public_privilege', 'grant_option', 'schema_create'])
def test_fail_closed_catalog_and_privilege_drift(schemas, mutation):
    s = schemas()
    statements = {
        'unknown_revision': "UPDATE alembic_version SET version_num='unsupported'",
        'missing_table': 'ALTER TABLE login_limits RENAME TO unexpected_limits',
        'missing_column': 'ALTER TABLE users RENAME COLUMN version TO unexpected_version',
        'revision_mismatch': "UPDATE alembic_version SET version_num='0010_no_delivery_eligibility'",
        'wrong_owner': sql.SQL('ALTER SCHEMA {} OWNER TO postgres').format(sql.Identifier(s)),
        'wrong_table_owner': 'ALTER TABLE users OWNER TO postgres',
        'extra_table': 'CREATE TABLE unexpected(id int)',
        'disabled_audit': 'ALTER TABLE audit_events DISABLE TRIGGER audit_append_only',
        'table_privilege': 'GRANT UPDATE ON audit_events TO doi_pin_runtime',
        'column_privilege': 'GRANT UPDATE(action) ON audit_events TO doi_pin_runtime',
        'public_privilege': 'GRANT DELETE ON audit_events TO PUBLIC',
        'grant_option': 'GRANT SELECT ON users TO doi_pin_runtime WITH GRANT OPTION',
        'schema_create': sql.SQL('GRANT CREATE ON SCHEMA {} TO doi_pin_runtime').format(sql.Identifier(s)),
    }
    with connect('admin', s) as c:
        # Persist the adversarial state in this new schema as review evidence.
        c.execute(statements[mutation])
        before = effective(c, s)
        with pytest.raises(tool.ProvisioningError):
            grant(c, s)
        assert effective(c, s) == before  # No grants/revokes even when drift is present.


def test_wrong_schema_and_readonly_profile_revision(schemas):
    s = schemas(tool.REVISIONS[1])
    with connect() as c:
        with pytest.raises(tool.ProvisioningError):
            grant(c, 'pcprov_absent_'+uuid4().hex)
        with pytest.raises(ValueError):
            grant(c, 'invalid;schema')
        with pytest.raises(tool.ProvisioningError):
            grant(c, s, 'reference-readonly')


def test_atomic_rollback_on_real_postgres_grant_error(schemas, monkeypatch):
    s = schemas()
    original = tool.execute_grant
    calls = []

    def injected(cursor, statement):
        calls.append(statement)
        if len(calls) == 4:
            # A real PostgreSQL error after successful preceding GRANT statements.
            cursor.execute(sql.SQL('GRANT SELECT ON {} TO doi_pin_runtime').format(sql.Identifier(s, 'absent_table')))
        original(cursor, statement)

    monkeypatch.setattr(tool, 'execute_grant', injected)
    with connect() as c:
        before = effective(c, s)
        with pytest.raises(psycopg.errors.UndefinedTable):
            grant(c, s)
        assert len(calls) == 4 and effective(c, s) == before


def test_audit_owner_trigger_with_real_row(schemas):
    s = schemas()
    with connect('migrator', s) as c:
        identity = uuid4()
        c.execute("INSERT INTO audit_events(id,actor_type,actor_id,aggregate_type,aggregate_id,action,correlation_id) VALUES (%s,'SYSTEM','review','fixture',%s,'APPEND_ONLY',%s)", (identity, uuid4(), uuid4()))
        for statement in ('UPDATE audit_events SET action=action', 'DELETE FROM audit_events'):
            with pytest.raises(psycopg.errors.RaiseException, match='append-only'):
                with c.transaction():
                    c.execute(statement)
        assert c.execute('SELECT count(*) FROM audit_events').fetchone()[0] == 1


def protected_snapshot():
    """Read-only launch guard; no fixture/schema creation or old evidence writes."""
    old = ROOT/'.local/pc-b1b/reference-compat-implementation'
    result = {'env_sha256': digest(ROOT/'.env'),
              'incidental_audit_sha256': digest(ROOT/'docs/PHASE8A_NFR06_AUDIT_COVERAGE.json'),
              'run01_files': {p.relative_to(old).as_posix(): digest(p) for p in sorted(old.rglob('*')) if p.is_file()}}
    with connect(readonly=True) as c:
        assert c.execute("SELECT to_regnamespace('doi_pin')").fetchone()[0] is None
        assert c.execute('SELECT version_num FROM pc_dev_b1b.alembic_version').fetchone()[0] == tool.REVISIONS[2]
        tables = c.execute("SELECT tablename FROM pg_tables WHERE schemaname='pc_dev_b1b' ORDER BY 1").fetchall()
        result['development_data'] = {table: c.execute(sql.SQL("SELECT count(*),md5(COALESCE(string_agg(to_jsonb(t)::text,'' ORDER BY to_jsonb(t)::text),'')) FROM {} t").format(sql.Identifier('pc_dev_b1b', table))).fetchone() for table, in tables}
        result['development_privileges'] = effective(c, 'pc_dev_b1b')
        result['roles'] = c.execute("SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolcanlogin,rolbypassrls,rolconfig FROM pg_roles WHERE rolname IN ('doi_pin_migrator','doi_pin_runtime') ORDER BY 1").fetchall()
    return result


def launch():
    """Supported future invocation; reserve log/JUnit identity before pytest starts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', help='Optional canonical UUID hex; existing directory is refused')
    args = parser.parse_args()
    if os.getenv('PC_PROVISIONING_REVIEW') != '1':
        raise RuntimeError('Explicit PC-only opt-in required')
    run = EvidenceRun.reserve(args.run_id)
    print(json.dumps({'run_id': run.identity['run_id'], 'evidence_dir': str(run.path.resolve())}), flush=True)
    code = None
    try:
        before = protected_snapshot()
        run.write('protected_before.json', before)
        env = dict(os.environ, **V)
        for name in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS'):
            env.pop(name, None)
        env.update(PC_PROVISIONING_REVIEW='1', PC_PROVISIONING_RUN_ID=run.identity['run_id'],
                   PC_PROVISIONING_RUN_TOKEN=run.identity['token'], PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        # Log is opened exclusively in the newly reserved directory. JUnit never targets run01.
        with (run.path/'pytest.log').open('x', encoding='utf-8') as stream:
            result = subprocess.run([sys.executable, '-B', '-m', 'pytest', 'tests/test_provision_database.py',
                '--noconftest', '-p', 'no:cacheprovider', '-q', '--tb=short',
                '--junitxml='+str(run.path/'results.xml'), '--basetemp='+str(run.path/'pytest-tmp')],
                cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        code = result.returncode
        after = protected_snapshot()
        run.write('protected_after.json', after)
        if before != after:
            raise RuntimeError('Protected data/evidence changed; preserve state and stop')
        return code
    finally:
        run.write('exit.json', {'run_id': run.identity['run_id'], 'pytest_exit': code,
                  'launcher_complete': sys.exc_info()[0] is None})


if __name__ == '__main__':
    try:
        sys.exit(launch())
    except Exception as error:
        print('Compatibility launcher stopped: '+type(error).__name__, file=sys.stderr)
        sys.exit(1)
