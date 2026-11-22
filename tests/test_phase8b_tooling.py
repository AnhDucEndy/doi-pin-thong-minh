"""Synthetic tooling tests; no database fixture, service, migration or provider."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load('harness_under_test', 'tools/run_phase8b.py')
checker = load('portability_under_test', 'tools/validate_phase8b_b1b.py')
windows_launcher = load('windows_launcher_under_test', 'tools/launch_phase8b_windows.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def empty_snapshot():
    return dict(source=[], roles=[], membership=[], defaults=[], evidence={}, schemas=[],
                objects=[], columns=[], definitions=[], data={})


def test_business_profile_retains_all_domain_modules_and_ids():
    selected = runner.profiles('business')
    expected = {p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_*.py')} - set(runner.EXCLUDED)
    assert set(selected) == expected
    assert not set(selected) & set(runner.EXCLUDED)
    # Every declared B1b test function can be explicitly selected without rewriting its ID.
    for p in (ROOT/'tests').glob('test_phase8b_b1b*.py'):
        for node in ast.parse(p.read_text(encoding='utf-8')).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                identity = p.relative_to(ROOT).as_posix()+'::'+node.name
                assert runner.profiles('business', [identity]) == [identity]
    assert runner.profiles('tooling') == ['tests/test_phase8b_tooling.py']


@pytest.mark.parametrize('target', ['tests/test_provision_database.py', 'tests/test_phase8b_tooling.py', '--lf', '--deselect=x'])
def test_reject_profile_bypass(target):
    with pytest.raises(ValueError):
        runner.profiles('business', [target])


def test_compatibility_requires_its_own_launcher():
    with pytest.raises(ValueError, match='launcher'):
        runner.profiles('compatibility')


def test_exclusive_run_and_artifact_creation(tmp_path):
    first = runner.reserve('same', tmp_path)
    runner.write_new(first/'old.json', {'immutable': True})
    with pytest.raises(FileExistsError):
        runner.reserve('same', tmp_path)
    with pytest.raises(FileExistsError):
        runner.write_new(first/'old.json', {'immutable': False})
    assert json.loads((first/'old.json').read_text()) == {'immutable': True}


class Child:
    pid = 12345
    def __init__(self, exit_code=0, interrupt=False):
        self.code, self.interrupt, self.terminated = exit_code, interrupt, False
    def wait(self, timeout=None):
        if self.interrupt and not self.terminated:
            raise KeyboardInterrupt()
        return self.code
    def terminate(self):
        self.terminated = True


@pytest.mark.parametrize('code', [0, 1, 2])
def test_completed_means_finished_checks_not_automatic_pass(tmp_path, code):
    out = runner.reserve(parent=tmp_path)
    def launch(*args, **kwargs):
        events = sorted(out.glob('journal_*.json'))
        assert json.loads(events[0].read_text())['state'] == 'RUNNING'
        assert (out/'protected_before.json').exists()
        return Child(code)
    actual = runner.execute(out, dict(profile='tooling', collect_only=False), empty_snapshot, launch)
    state = runner.inspect_run(out)
    assert actual == code and state['state'] == 'COMPLETED'
    assert state['passed'] == (code == 0) and state['test_exit_code'] == code
    assert (out/'artifacts.json').exists()


def test_postcheck_failure_never_completes(tmp_path):
    out = runner.reserve(parent=tmp_path)
    snapshots = [empty_snapshot(), {**empty_snapshot(), 'source': ['changed']}]
    result = runner.execute(out, dict(profile='tooling', collect_only=False),
                            lambda: snapshots.pop(0), lambda *a, **kw: Child())
    state = runner.inspect_run(out)
    assert result == 1 and state['state'] == 'UNKNOWN' and not state['passed']
    assert state['test_exit_code'] == 0


def test_preflight_exception_leaves_journal_without_launch(tmp_path):
    out = runner.reserve(parent=tmp_path)
    def bad():
        raise OSError('synthetic unavailable')
    def forbidden(*a, **kw):
        raise AssertionError('Must not launch')
    assert runner.execute(out, dict(profile='tooling', collect_only=False), bad, forbidden) == 1
    assert runner.inspect_run(out)['state'] == 'UNKNOWN'


def test_interrupt_records_own_child_and_stale_is_unknown(tmp_path):
    out = runner.reserve(parent=tmp_path)
    child = Child(interrupt=True)
    assert runner.execute(out, dict(profile='tooling', collect_only=False), empty_snapshot,
                          lambda *a, **kw: child) == 130
    assert child.terminated and runner.inspect_run(out)['state'] == 'INTERRUPTED'
    stale = runner.reserve(parent=tmp_path)
    runner.Journal(stale).emit('RUNNING', pid=99999)
    state = runner.inspect_run(stale)
    assert state['state'] == 'UNKNOWN' and state['recorded_state'] == 'RUNNING' and not state['passed']


def test_output_guard_routes_historical_artifact_and_denies_source(tmp_path):
    root = tmp_path/'repo'; root.mkdir()
    (root/'docs').mkdir()
    historical = root/'docs/audit.json'; historical.write_text('old')
    source = root/'app.py'; source.write_text('source')
    out = tmp_path/'run'; out.mkdir()
    with runner.OutputGuard(out, root).install():
        historical.write_text('new report')
        with pytest.raises(PermissionError):
            source.write_text('unauthorized')
        assert source.read_text() == 'source'
    assert historical.read_text() == 'old'
    assert (out/'reports/audit.json').read_text() == 'new report'


@pytest.mark.parametrize('historical,candidate', [(b'a\r\nb\r\n', b'a\nb\n'), (b'a\nb\n', b'a\r\nb\r\n')])
def test_reviewed_eol_anchor_both_checkouts(historical, candidate):
    assert checker.classify_bytes('p', candidate, digest(historical), eol_allowlist={'p'}) == 'HISTORICAL_EOL_EQUIVALENT'
    assert checker.classify_bytes('p', historical, digest(historical), eol_allowlist={'p'}) == 'RAW_MATCH'


@pytest.mark.parametrize('candidate', [b'changed\r\n', b'a \r\n', b'\xef\xbb\xbfa\r\n', b'a\r\nb\n', b'a\rb\r'])
def test_mutation_bom_mixed_and_lone_cr_rejected(candidate):
    assert checker.classify_bytes('p', candidate, digest(b'a\nb\n'), eol_allowlist={'p'}) == 'UNEXPECTED_CONTENT_DELTA'


def test_frozen_and_outside_allowlist_remain_raw_strict():
    expected = digest(b'a\r\n')
    assert checker.classify_bytes('p', b'a\n', expected, eol_allowlist=()) == 'UNEXPECTED_CONTENT_DELTA'
    assert checker.classify_bytes('p', b'a\n', expected, approved={'p'}, frozen={'p'}, eol_allowlist={'p'}) == 'UNEXPECTED_CONTENT_DELTA'
    assert checker.classify_bytes('p', b'authorized change\n', expected, approved={'p'}) == 'APPROVED_CONTENT_DELTA'


def test_unexpected_schema_and_protected_evidence_changes_refused():
    before = empty_snapshot()
    assert not runner.preservation(before, {**before, 'schemas': [{'nspname': 'unexpected'}]})
    before = {**before, 'evidence': {'old': 'hash'}}
    assert not runner.preservation(before, {**before, 'evidence': {'old': 'changed'}})


def test_current_portability_classification_preserves_anchor():
    base = checker.read(ROOT/'docs/PHASE8B_HANDOFF/b1b_transfer_20261119/source_baseline.json')['source_and_environment_hashes']
    proposal = checker.read(ROOT/'docs/PHASE8B_HANDOFF/b1b_preimplementation_20261118_01/FILE_CHANGE_PROPOSAL.json')
    allowed = {p['path'] for p in proposal['paths']} | set(checker.APPROVED_TOOLING) | set(runner.FIXTURE_SOURCE_SCOPE)
    frozen = {p['path'] for p in checker.read(ROOT/'docs/implementation-contracts/P8-REF-0.1/freeze_manifest.json')['files'] if p['path'] != 'docs/IMPLEMENTATION_STATUS.md'}
    result = checker.source_classification(base, allowed, frozen)
    assert 'UNEXPECTED_CONTENT_DELTA' not in result.values()
    assert {p for p,s in result.items() if s=='HISTORICAL_EOL_EQUIVALENT'} == checker.EOL_ALLOWLIST


def isolation_values():
    from sqlalchemy.engine import URL
    values = {'DATABASE_SCHEMA': 'phase5_test_'+'a'*12,
              'POSTGRES_PASSWORD': 'synthetic_admin_'+'x'*32,
              'MIGRATOR_PASSWORD': 'synthetic_migrator_'+'x'*32,
              'RUNTIME_PASSWORD': 'synthetic_runtime_'+'x'*32,
              runner.DERIVATION_SECRET: secrets.token_urlsafe(48)}
    for key, role in runner.DB_ROLES.items():
        secret = {'postgres': 'POSTGRES_PASSWORD', 'doi_pin_migrator': 'MIGRATOR_PASSWORD',
                  'doi_pin_runtime': 'RUNTIME_PASSWORD'}[role]
        values[key] = URL.create('postgresql+psycopg', username=role, password=values[secret],
                                host='127.0.0.1', port=5435, database='doi_pin_r2_rerun').render_as_string(hide_password=False)
    return values


def isolation_identity():
    return dict(host='127.0.0.1', port=5435, database='doi_pin_r2_rerun', system_identifier='new-cluster')


@pytest.mark.parametrize('key,change', [
    ('DATABASE_ADMIN_URL', {'port': 5433}), ('MIGRATION_DATABASE_URL', {'port': 5432}),
    ('DATABASE_ADMIN_URL', {'port': 5434}),
    ('DATABASE_URL', {'database': 'postgres'}), ('DATABASE_URL', {'host': 'localhost'}),
    ('DATABASE_URL', {'username': 'postgres'}), ('DATABASE_URL', {'query': {'service': 'protected'}}),
])
def test_isolated_endpoint_refuses_protected_wrong_or_redirected_url(key, change):
    from sqlalchemy.engine import make_url
    values = isolation_values()
    values[key] = make_url(values[key]).set(**change).render_as_string(hide_password=False)
    with pytest.raises(ValueError, match='isolated credentials'):
        runner.isolated_environment(values, isolation_identity(), {})


@pytest.mark.parametrize('key', [*runner.DB_ROLES, 'POSTGRES_PASSWORD', 'MIGRATOR_PASSWORD', 'RUNTIME_PASSWORD'])
def test_missing_credentials_do_not_inherit_or_fallback(key):
    values = isolation_values()
    inherited = dict(values, DATABASE_URL='original-must-not-be-used', PGSERVICE='protected')
    del values[key]
    with pytest.raises(ValueError):
        runner.isolated_environment(values, isolation_identity(), inherited)


@pytest.mark.parametrize('schema', ['doi_pin', 'pc_dev_b1b', 'public', 'phase5_test_bad', 'x;drop schema x'])
def test_isolated_environment_refuses_non_fixture_schema(schema):
    values = dict(isolation_values(), DATABASE_SCHEMA=schema)
    with pytest.raises(ValueError, match='Fresh test schema'):
        runner.isolated_environment(values, isolation_identity(), {})


def test_clean_environment_disables_real_dotenv_loading(tmp_path, monkeypatch):
    from dotenv import load_dotenv
    env = runner.isolated_environment(isolation_values(), isolation_identity(),
          {'PATH': 'safe', 'PGSERVICE': 'protected', 'PYTEST_PLUGINS': 'unsafe', 'UNKNOWN_SECRET': 'old'})
    assert 'PGSERVICE' not in env and 'UNKNOWN_SECRET' not in env and 'PYTEST_PLUGINS' not in env
    secret_file = tmp_path/'original.env'
    secret_file.write_text('ORIGINAL_FALLBACK_SENTINEL=must-not-load\nDATABASE_URL=protected\n')
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED', env['PYTHON_DOTENV_DISABLED'])
    monkeypatch.delenv('ORIGINAL_FALLBACK_SENTINEL', raising=False)
    assert load_dotenv(secret_file, override=True) is False
    assert 'ORIGINAL_FALLBACK_SENTINEL' not in os.environ


def setup_adapter(tmp_path, monkeypatch, launch=None, schemas=()):
    identity = isolation_identity()
    env = runner.isolated_environment(isolation_values(), identity, {})
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    adapter = runner.MigrationProcesses(tmp_path, identity, env, launch=launch,
          catalog=lambda *args: dict(schemas=[dict(schema=s) for s in schemas]))
    return adapter


@pytest.mark.parametrize('args', [
    ['cmd', '/c', 'anything'], [sys.executable, '-c', 'print(1)'],
    [sys.executable, str(ROOT/'tools/provision_database.py'), 'reset'],
])
def test_unexpected_subprocess_cannot_launch(tmp_path, monkeypatch, args):
    def forbidden(*a, **kw):
        pytest.fail('Rejected command must never reach native launch')
    adapter = setup_adapter(tmp_path, monkeypatch, forbidden)
    with pytest.raises(ValueError, match='Unexpected fixture subprocess'):
        adapter.run(args, check=True)
    assert adapter.failed
    assert json.loads((tmp_path/'subprocesses/0001.json').read_text())['state'] == 'REFUSED'


def test_adapter_refuses_existing_schema_ownership(tmp_path, monkeypatch):
    adapter = setup_adapter(tmp_path, monkeypatch, schemas=['phase5_test_'+'a'*12])
    with pytest.raises(ValueError, match='Existing schema'):
        adapter.run([sys.executable, str(ROOT/'tools/provision_database.py'), 'roles'], check=True)
    assert not adapter.claimed


@pytest.mark.parametrize('code,timed_out', [(0, False), (7, False), (-15, True)])
def test_provision_child_environment_exit_timeout_and_durable_evidence(tmp_path, monkeypatch, code, timed_out):
    seen = {}
    class FakeChild(Child):
        def wait(self, timeout=None):
            if timed_out and not self.terminated:
                raise subprocess.TimeoutExpired('synthetic', timeout)
            return code
    child = FakeChild()
    def launch(args, **kwargs):
        seen.update(kwargs)
        assert kwargs['shell'] is False and kwargs['cwd'] == ROOT
        assert kwargs['env']['PYTHON_DOTENV_DISABLED'] == '1'
        assert kwargs['env']['PGOPTIONS'] == '-cstatement_timeout=15000 -clock_timeout=5000'
        assert all(':5435/doi_pin_r2_rerun' in kwargs['env'][k] for k in runner.DB_ROLES)
        assert runner.DERIVATION_SECRET not in kwargs['env']
        assert 'UNRELATED_ORIGINAL_SECRET' not in kwargs['env']
        return child
    adapter = setup_adapter(tmp_path, monkeypatch, launch)
    monkeypatch.setenv('UNRELATED_ORIGINAL_SECRET', 'must-not-inherit')
    args = [sys.executable, str(ROOT/'tools/provision_database.py'), 'roles']
    if timed_out:
        with pytest.raises(subprocess.TimeoutExpired):
            adapter.run(args, check=True)
    elif code:
        with pytest.raises(subprocess.CalledProcessError) as error:
            adapter.run(args, check=True)
        assert error.value.returncode == code
    else:
        assert adapter.run(args, check=True).returncode == 0
    evidence = json.loads((tmp_path/'subprocesses/0001.json').read_text())
    assert evidence['exit_code'] == code and evidence['timed_out'] == timed_out
    assert (tmp_path/'subprocesses/0001_stdout.log').exists()
    assert (tmp_path/'subprocesses/0001_stderr.log').exists()
    assert adapter.failed == (bool(code) or timed_out)
    with pytest.raises(FileExistsError):
        runner.MigrationProcesses(tmp_path, isolation_identity(), isolation_values())
    assert evidence == json.loads((tmp_path/'subprocesses/0001.json').read_text())


@pytest.mark.parametrize('port', [5433, 5434])
def test_guard_refuses_unsupervised_native_launch_and_raw_protected_connection(tmp_path, monkeypatch, port):
    import psycopg
    adapter = setup_adapter(tmp_path, monkeypatch)
    with adapter.install():
        with pytest.raises(ValueError, match='Unsupervised subprocess'):
            subprocess.Popen(['anything'])
        with pytest.raises(ValueError, match='Non-isolated database'):
            psycopg.connect(host='127.0.0.1', port=port, dbname='doi_pin', user='postgres', password='synthetic')


def test_guard_accepts_sqlalchemy_psycopg_adapter_context(tmp_path, monkeypatch):
    import psycopg
    from sqlalchemy import create_engine
    seen = {}
    sentinel = object()
    def native_connect(**kwargs):
        seen.update(kwargs)
        return sentinel
    monkeypatch.setattr(psycopg, 'connect', native_connect)
    adapter = setup_adapter(tmp_path, monkeypatch)
    engine = create_engine(adapter.env['DATABASE_ADMIN_URL'], hide_parameters=True)
    args, kwargs = engine.dialect.create_connect_args(engine.url)
    assert 'context' in kwargs
    with adapter.install():
        assert psycopg.connect(*args, **kwargs) is sentinel
    assert seen['port'] == 5435 and seen['dbname'] == 'doi_pin_r2_rerun' and not adapter.failed
    engine.dispose()


def test_swallowed_subprocess_failure_cannot_produce_pass_journal(tmp_path, monkeypatch):
    out = runner.reserve(parent=tmp_path)
    env = runner.isolated_environment(isolation_values(), isolation_identity(), {})
    for key in runner.DB_ROLES:
        monkeypatch.setenv(key, env[key].replace('synthetic_', 'other_'))
    monkeypatch.setattr(runner, 'load_isolation', lambda path: (isolation_identity(), env))
    monkeypatch.setattr(runner, 'verify_container', lambda identity: None)
    monkeypatch.setattr(runner, 'isolated_catalog', lambda *a, **kw: dict(schemas=[]))
    def launch(*a, **kw):
        runner.write_new(out/'subprocess_summary.json', dict(failed=True))
        (out/'subprocesses').mkdir()
        runner.write_new(out/'subprocesses/0001.json', dict(state='COMPLETED', exit_code=7))
        return Child(0)
    code = runner.execute(out, dict(profile='business', collect_only=False,
                          targets=runner.MIGRATION_TARGETS, isolation='synthetic'), empty_snapshot, launch)
    assert code == 1
    state = runner.inspect_run(out)
    assert not state['passed'] and state['test_exit_code'] == 0 and state['subprocess_checks'] == 'FAILED'


@pytest.mark.parametrize('invalid', [None, '', 'x'*31, 'REPLACE_'+'x'*40])
def test_derivation_secret_validation_is_fail_closed_and_secret_free(invalid):
    values = isolation_values()
    if invalid is None:
        del values[runner.DERIVATION_SECRET]
    else:
        values[runner.DERIVATION_SECRET] = invalid
    with pytest.raises(ValueError) as error:
        runner.isolated_environment(values, isolation_identity(), isolation_values())
    assert str(error.value) == 'Missing or invalid test-only derivation secret'
    if invalid:
        assert invalid not in str(error.value)


def test_exact_minimum_derivation_secret_is_propagated():
    values = isolation_values()
    values[runner.DERIVATION_SECRET] = secrets.token_hex(16)
    env = runner.isolated_environment(values, isolation_identity(), {})
    assert env[runner.DERIVATION_SECRET] == values[runner.DERIVATION_SECRET]
    assert env['PYTHON_DOTENV_DISABLED'] == '1'


def test_missing_derivation_secret_prevents_worker_launch_and_false_pass(tmp_path, monkeypatch):
    out = runner.reserve(parent=tmp_path)
    values = isolation_values()
    del values[runner.DERIVATION_SECRET]
    def missing(path):
        return isolation_identity(), runner.isolated_environment(values, isolation_identity(), {})
    def forbidden(*args, **kwargs):
        pytest.fail('Worker must not launch with missing derivation secret')
    monkeypatch.setattr(runner, 'load_isolation', missing)
    result = runner.execute(out, dict(profile='business', collect_only=False,
        targets=runner.MIGRATION_TARGETS, isolation='synthetic'), empty_snapshot, forbidden)
    assert result == 1 and not runner.inspect_run(out)['passed']
    assert runner.inspect_run(out)['error_type'] == 'ValueError'
    assert not (out/'command.json').exists()


def test_worker_receives_fresh_secret_and_writes_no_secret_to_evidence(tmp_path, monkeypatch):
    from unittest.mock import patch
    from uuid import uuid4
    from app.application.reservations import qr_token
    out = runner.reserve(parent=tmp_path)
    env = runner.isolated_environment(isolation_values(), isolation_identity(), {})
    for key in runner.DB_ROLES:
        monkeypatch.setenv(key, env[key].replace('synthetic_', 'original_'))
    monkeypatch.setenv(runner.DERIVATION_SECRET, secrets.token_urlsafe(48))
    monkeypatch.setenv('ORIGINAL_UNUSED_SECRET', 'must-not-inherit')
    monkeypatch.setattr(runner, 'load_isolation', lambda path: (isolation_identity(), env))
    monkeypatch.setattr(runner, 'verify_container', lambda identity: None)
    monkeypatch.setattr(runner, 'isolated_catalog', lambda *args, **kwargs: dict(schemas=[]))
    def launch(*args, **kwargs):
        worker_env = kwargs['env']
        assert worker_env[runner.DERIVATION_SECRET] == env[runner.DERIVATION_SECRET]
        assert 'ORIGINAL_UNUSED_SECRET' not in worker_env
        assert all(':5435/doi_pin_r2_rerun' in worker_env[k] for k in runner.DB_ROLES)
        with patch.dict(os.environ, worker_env, clear=True):
            token = qr_token(uuid4(), uuid4())
            assert len(token) == 43
        (out/'subprocesses').mkdir()
        runner.write_new(out/'subprocess_summary.json', dict(failed=False))
        return Child(0)
    result = runner.execute(out, dict(profile='business', collect_only=False,
        targets=runner.MIGRATION_TARGETS, isolation='synthetic'), empty_snapshot, launch)
    assert result == 0 and runner.inspect_run(out)['passed']
    assert all(env[runner.DERIVATION_SECRET] not in p.read_text() for p in out.rglob('*') if p.is_file())


def test_422_observer_retains_public_diagnosis_and_redacts_secret_without_replay(tmp_path, monkeypatch):
    import httpx
    secret = secrets.token_urlsafe(48)
    request = httpx.Request('POST', 'http://testserver/v1/qr-challenges')
    response = httpx.Response(422, request=request, json={
        'code': 'CONFIG_NOT_READY', 'message': 'Approved simulation configuration is required',
        'details': {'secret': secret}, secret: secret})
    calls = []
    def send(*args, **kwargs):
        calls.append(1)
        return response
    monkeypatch.setattr(httpx.Client, 'send', send)
    with runner.observe_422(tmp_path):
        assert httpx.Client().send(request) is response
    assert len(calls) == 1
    saved = json.loads((tmp_path/'http_422_0001.json').read_text())
    assert saved['status'] == 422 and saved['body']['code'] == 'CONFIG_NOT_READY'
    assert saved['body']['details'] == '<redacted>'
    assert secret not in json.dumps(saved)


def round3_identity(port=55436):
    return dict(host='127.0.0.1', port=port, database='doi_pin_b1b_r3_abcdef012345',
                execution_profile='round3', system_identifier='new-round3')


def round3_values(identity):
    from sqlalchemy.engine import make_url
    values = isolation_values()
    for key in runner.DB_ROLES:
        values[key] = make_url(values[key]).set(port=identity['port'], database=identity['database']).render_as_string(hide_password=False)
    return values


def round3_config():
    return dict(profile='business', execution_profile='round3', collect_only=False,
                targets=list(runner.ROUND3_TARGETS), isolation='synthetic')


def test_round3_exact_allowlist_has_declared_cases_and_round2_retained():
    assert len(runner.ROUND3_TARGETS) == len(set(runner.ROUND3_TARGETS)) == 13
    for target in runner.ROUND3_TARGETS:
        module, name = target.split('::')
        functions = {n.name for n in ast.parse((ROOT/module).read_text()).body if isinstance(n, ast.FunctionDef)}
        assert name.split('[')[0] in functions
    assert len(runner.MIGRATION_TARGETS) == 10
    assert all(n.startswith('tests/test_phase8b_b1b_migration.py::') for n in runner.MIGRATION_TARGETS)
    assert not set(runner.MIGRATION_TARGETS) & set(runner.ROUND3_TARGETS)
    runner.validate_isolated_selection(round3_config(), round3_identity())
    runner.validate_isolated_selection(dict(profile='business', collect_only=False,
                                      targets=runner.MIGRATION_TARGETS), isolation_identity())


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'reorder', 'round2_nodes', 'tooling', 'collection', 'wrong_identity'])
def test_round3_selection_cannot_expand_or_bypass_profile(mutation):
    config, identity = round3_config(), round3_identity()
    if mutation == 'missing': config['targets'] = config['targets'][:-1]
    if mutation == 'extra': config['targets'] += ['tests/test_phase8b_b1b_races.py']
    if mutation == 'reorder': config['targets'] = list(reversed(config['targets']))
    if mutation == 'round2_nodes': config['targets'] = runner.MIGRATION_TARGETS
    if mutation == 'tooling': config['profile'] = 'tooling'
    if mutation == 'collection': config['collect_only'] = True
    if mutation == 'wrong_identity': identity = isolation_identity()
    with pytest.raises(ValueError, match='Exact approved'):
        runner.validate_isolated_selection(config, identity)


@pytest.mark.parametrize('port', [5433, 5434, 5435, 0, True, '55436'])
def test_round3_endpoint_refuses_retained_or_invalid_ports(port):
    with pytest.raises(ValueError, match='endpoint'):
        runner.isolated_environment(round3_values(round3_identity()), round3_identity(port), {})


@pytest.mark.parametrize('port', [55436, 56123])
def test_round3_endpoint_comes_from_identity_not_fixed_round2_port(port):
    identity = round3_identity(port)
    env = runner.isolated_environment(round3_values(identity), identity, {})
    assert runner.isolation_endpoint(identity) == ('127.0.0.1', port, identity['database'])
    assert all(':'+str(port)+'/'+identity['database'] in env[k] for k in runner.DB_ROLES)


@pytest.mark.parametrize('port', [5433, 5434, 5435])
def test_round3_raw_connections_to_retained_ports_are_refused(tmp_path, monkeypatch, port):
    import psycopg
    identity = round3_identity()
    env = runner.isolated_environment(round3_values(identity), identity, {})
    adapter = runner.MigrationProcesses(tmp_path, identity, env)
    with adapter.install():
        with pytest.raises(ValueError, match='Non-isolated'):
            psycopg.connect(host='127.0.0.1', port=port, dbname=identity['database'],
                            user='postgres', password=env['POSTGRES_PASSWORD'])
    assert adapter.failed


def test_round3_fixture_subprocess_pattern_is_unchanged_and_environment_is_explicit(tmp_path, monkeypatch):
    identity = round3_identity()
    env = runner.isolated_environment(round3_values(identity), identity, {})
    for key, value in env.items(): monkeypatch.setenv(key, value)
    def launch(args, **kwargs):
        assert args == [sys.executable, str(ROOT/'tools/provision_database.py'), 'roles']
        assert kwargs['shell'] is False and kwargs['cwd'] == ROOT
        assert all(':55436/'+identity['database'] in kwargs['env'][k] for k in runner.DB_ROLES)
        assert runner.DERIVATION_SECRET not in kwargs['env']
        return Child(0)
    adapter = runner.MigrationProcesses(tmp_path, identity, env, launch,
                                       catalog=lambda *args: dict(schemas=[]))
    with adapter.install():
        assert subprocess.run([sys.executable, str(ROOT/'tools/provision_database.py'), 'roles'], check=True).returncode == 0
        with pytest.raises(ValueError, match='Unsupervised'):
            subprocess.Popen([sys.executable, '-c', 'anything'])
    record = json.loads((tmp_path/'subprocesses/0001.json').read_text())
    assert record['cluster'] == 'new-round3' and record['exit_code'] == 0


def test_round3_external_transports_refused_but_inprocess_mock_is_allowed(tmp_path):
    import httpx
    from app.workers import payment
    identity = round3_identity()
    env = runner.isolated_environment(round3_values(identity), identity, {})
    adapter = runner.MigrationProcesses(tmp_path, identity, env)
    with adapter.local_transports():
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
            assert client.get('http://127.0.0.1/mock').status_code == 200
        with httpx.Client(trust_env=False) as client:
            with pytest.raises(ValueError, match='External HTTP'):
                client.get('http://127.0.0.1:8001/mock/v1/charges')
        with pytest.raises(ValueError, match='External HTTP'):
            payment.provider_request({})
    assert adapter.failed and len(list(tmp_path.glob('network_refused_*.json'))) == 2


def test_round3_requires_isolation_before_any_child_launch(tmp_path):
    out = runner.reserve(parent=tmp_path)
    config = round3_config(); del config['isolation']
    def forbidden(*args, **kwargs): pytest.fail('Must not launch without isolation')
    assert runner.execute(out, config, empty_snapshot, forbidden) == 1
    assert not runner.inspect_run(out)['passed']


@pytest.mark.parametrize('code', [0, 3])
def test_round3_journal_keeps_profile_and_real_child_exit(tmp_path, monkeypatch, code):
    out = runner.reserve(parent=tmp_path)
    identity = round3_identity()
    env = runner.isolated_environment(round3_values(identity), identity, {})
    for key in runner.DB_ROLES: monkeypatch.setenv(key, env[key].replace('synthetic_', 'original_'))
    monkeypatch.setattr(runner, 'load_isolation', lambda path: (identity, env))
    monkeypatch.setattr(runner, 'verify_container', lambda value: None)
    monkeypatch.setattr(runner, 'isolated_catalog', lambda *args, **kwargs: dict(schemas=[]))
    def launch(*args, **kwargs):
        start = json.loads((out/'journal_0001.json').read_text())
        assert start['execution_profile'] == 'round3'
        assert all(':55436/' in kwargs['env'][k] for k in runner.DB_ROLES)
        (out/'subprocesses').mkdir()
        runner.write_new(out/'subprocess_summary.json', dict(failed=False))
        return Child(code)
    assert runner.execute(out, round3_config(), empty_snapshot, launch) == code
    journal = runner.inspect_run(out)
    assert journal['execution_profile'] == 'round3' and journal['test_exit_code'] == code
    assert journal['passed'] == (code == 0)


@pytest.mark.parametrize('change', ['none', 'old_container', 'old_volume', 'old_source', 'old_network', 'old_port', 'bind_mount'])
def test_round3_physical_identity_refuses_retained_resources(monkeypatch, change):
    identity = dict(round3_identity(), container='r3', container_id='new-container',
        original_container_id='old-5433', previous_container_id='old-5434',
        original_mounts=[dict(source='source-5433')], previous_mounts=[dict(source='source-5434')],
        volume='new-volume', mount_source='new-source', network='new-network', network_id='new-net-id',
        retained_instances=[dict(port=p, container_id='old-'+str(p), system_identifier='system-'+str(p),
                                mounts=[dict(source='source-'+str(p))], network_ids=['net-'+str(p)]) for p in (5433,5434,5435)])
    value = dict(Id='new-container', State={'Health': {'Status': 'healthy'}},
        Mounts=[dict(Type='volume', Name='new-volume', Source='new-source')],
        NetworkSettings=dict(Ports={'5432/tcp':[dict(HostIp='127.0.0.1',HostPort='55436')]},
                             Networks={'new-network':dict(NetworkID='new-net-id')}))
    if change == 'old_container': value['Id'] = 'old-5435'
    if change == 'old_volume': value['Mounts'][0]['Name'] = 'old-volume'
    if change == 'old_source': value['Mounts'][0]['Source'] = 'source-5435'
    if change == 'old_network': value['NetworkSettings']['Networks']['new-network']['NetworkID'] = 'net-5435'
    if change == 'old_port': value['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort'] = '5435'
    if change == 'bind_mount': value['Mounts'][0]['Type'] = 'bind'
    monkeypatch.setattr(runner.subprocess, 'check_output', lambda *args, **kwargs: json.dumps([value]))
    if change == 'none': runner.verify_container(identity)
    else:
        with pytest.raises(ValueError, match='Physical isolation'):
            runner.verify_container(identity)


def round4_identity(port=55437):
    return dict(host='127.0.0.1', port=port, database='doi_pin_b1b_r4_abcdef012345',
                execution_profile='round4', system_identifier='new-round4')


def round4_config():
    return dict(profile='business', execution_profile='round4', collect_only=False,
                targets=list(runner.ROUND4_TARGETS), isolation='synthetic')


def test_round4_exact_cases_are_declared_and_do_not_repeat_earlier_profiles():
    assert len(runner.ROUND4_TARGETS) == len(set(runner.ROUND4_TARGETS)) == 14
    assert not set(runner.ROUND4_TARGETS) & (set(runner.ROUND3_TARGETS) | set(runner.MIGRATION_TARGETS))
    for target in runner.ROUND4_TARGETS:
        module, name = target.split('::')
        functions = {n.name for n in ast.parse((ROOT/module).read_text()).body if isinstance(n, ast.FunctionDef)}
        assert name.split('[')[0] in functions
    runner.validate_isolated_selection(round4_config(), round4_identity())
    runner.validate_isolated_selection(round3_config(), round3_identity())


@pytest.mark.parametrize('change', ['missing', 'extra', 'reorder', 'round3', 'collection', 'identity'])
def test_round4_allowlist_refuses_any_scope_change(change):
    config, identity = round4_config(), round4_identity()
    if change == 'missing': config['targets'] = config['targets'][:-1]
    if change == 'extra': config['targets'] += ['tests/test_phase8b_b1b_refund.py']
    if change == 'reorder': config['targets'] = list(reversed(config['targets']))
    if change == 'round3': config['targets'] = list(runner.ROUND3_TARGETS)
    if change == 'collection': config['collect_only'] = True
    if change == 'identity': identity = round3_identity()
    with pytest.raises(ValueError, match='Exact approved'):
        runner.validate_isolated_selection(config, identity)


@pytest.mark.parametrize('port', [5433, 5434, 5435, 5436])
def test_round4_refuses_all_retained_endpoints(port):
    with pytest.raises(ValueError, match='endpoint'):
        runner.isolated_environment(round3_values(round4_identity()), round4_identity(port), {})


@pytest.mark.parametrize('port', [55437, 56127])
def test_round4_urls_follow_verified_identity(port):
    identity = round4_identity(port)
    env = runner.isolated_environment(round3_values(identity), identity, {})
    assert all(':'+str(port)+'/'+identity['database'] in env[k] for k in runner.DB_ROLES)
    assert env['PYTHON_DOTENV_DISABLED'] == '1'


def test_round4_thread_cannot_spawn_native_process_or_connect_to_old_cluster(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import psycopg
    identity = round4_identity()
    env = runner.isolated_environment(round3_values(identity), identity, {})
    adapter = runner.MigrationProcesses(tmp_path, identity, env)
    def action():
        with pytest.raises(ValueError, match='Unsupervised'):
            subprocess.Popen([sys.executable, '-m', 'uvicorn'])
        with pytest.raises(ValueError, match='Non-isolated'):
            psycopg.connect(host='127.0.0.1',port=5436,dbname=identity['database'],
                            user='postgres',password=env['POSTGRES_PASSWORD'])
        return True
    with adapter.install(), ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(action).result(timeout=10)
    assert adapter.failed


def test_round4_provider_refusal_and_evidence_retention(tmp_path):
    from app.workers import payment
    identity = round4_identity()
    env = runner.isolated_environment(round3_values(identity), identity, {})
    adapter = runner.MigrationProcesses(tmp_path, identity, env)
    with adapter.local_transports():
        with pytest.raises(ValueError, match='External HTTP'):
            payment.provider_request({})
    old = (tmp_path/'network_refused_0001.json').read_bytes()
    with pytest.raises(FileExistsError):
        runner.MigrationProcesses(tmp_path, identity, env)
    assert (tmp_path/'network_refused_0001.json').read_bytes() == old


@pytest.mark.parametrize('code,blocked', [(0, False), (1, False), (0, True)])
def test_round4_journal_cannot_pass_failed_child_or_caught_guard(tmp_path, monkeypatch, code, blocked):
    out = runner.reserve(parent=tmp_path)
    identity = round4_identity()
    env = runner.isolated_environment(round3_values(identity), identity, {})
    for key in runner.DB_ROLES: monkeypatch.setenv(key, env[key].replace('synthetic_', 'original_'))
    monkeypatch.setattr(runner, 'load_isolation', lambda path: (identity, env))
    monkeypatch.setattr(runner, 'verify_container', lambda value: None)
    monkeypatch.setattr(runner, 'isolated_catalog', lambda *args, **kwargs: dict(schemas=[]))
    def launch(*args, **kwargs):
        assert json.loads((out/'journal_0001.json').read_text())['execution_profile'] == 'round4'
        (out/'subprocesses').mkdir()
        runner.write_new(out/'subprocess_summary.json', dict(failed=blocked))
        return Child(code)
    actual = runner.execute(out, round4_config(), empty_snapshot, launch)
    assert actual == (code or int(blocked))
    assert runner.inspect_run(out)['passed'] == (code == 0 and not blocked)


def round5_config():
    return dict(profile='business', execution_profile='round5', collect_only=False,
                targets=list(runner.ROUND5_TARGETS))


def test_round5_allowlist_preserves_all_parameter_identities_and_exact_counts():
    nodes = runner.ROUND5_TARGETS
    assert len(nodes) == len(set(nodes)) == 40
    groups = {}
    for node in nodes:
        assert node.startswith('tests/test_phase8b_b1b_contract.py::')
        name = node.split('::')[1].split('[')[0]
        groups[name] = groups.get(name, 0)+1
    assert groups == dict(test_all_frozen_definitions_round_trip=12,
        test_inputs_cannot_select_authority_or_financial_state=20,
        test_case_version_is_strict_positive_integer=4, test_bool_and_numeric_literals_do_not_coerce=4)
    assert not set(nodes) & (set(runner.MIGRATION_TARGETS)|set(runner.ROUND3_TARGETS)|set(runner.ROUND4_TARGETS))
    assert 'tests/test_phase8b_b1b_contract.py::test_case_version_is_strict_positive_integer[1]' in nodes
    assert 'tests/test_phase8b_b1b_contract.py::test_case_version_is_strict_positive_integer[1.0]' in nodes
    runner.validate_pure_selection(round5_config())


@pytest.mark.parametrize('change', ['missing', 'extra', 'reorder', 'module', 'collect', 'isolation', 'profile'])
def test_round5_exact_selection_cannot_be_expanded_or_downgraded(change):
    config = round5_config()
    if change == 'missing': config['targets'] = config['targets'][:-1]
    if change == 'extra': config['targets'] += ['tests/test_phase8b_b1b_contract.py::test_checkpoint_a_has_no_action_request_branch']
    if change == 'reorder': config['targets'].reverse()
    if change == 'module': config['targets'] = ['tests/test_phase8b_b1b_contract.py']
    if change == 'collect': config['collect_only'] = True
    if change == 'isolation': config['isolation'] = 'retained-instance'
    if change == 'profile': config['profile'] = 'tooling'
    with pytest.raises(ValueError, match='Exact pure'):
        runner.validate_pure_selection(config)


def test_round5_worker_environment_has_no_db_or_application_credentials():
    inherited = dict(isolation_values(), PGSERVICE='protected', PYTEST_PLUGINS='unexpected',
                     PAYMENT_SERVICE_KEY='old', SOME_SECRET='old', PATH='safe')
    env = runner.pure_environment(inherited)
    assert env['PATH'] == 'safe' and env['PYTHON_DOTENV_DISABLED'] == '1'
    assert set(env) == {'PATH','PYTHON_DOTENV_DISABLED','PYTHONDONTWRITEBYTECODE',
                       'PYTHONUNBUFFERED','PYTHONIOENCODING','PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONPATH'}


@pytest.mark.parametrize('operation', ['postgres', 'engine', 'sqlite', 'process', 'run', 'http', 'provider'])
def test_round5_effects_refused_before_connection_or_launch(tmp_path, operation):
    import httpx,psycopg,sqlite3,sqlalchemy
    from app.workers import payment
    guard = runner.PureContracts(tmp_path)
    with guard.install():
        with pytest.raises(ValueError, match='Effect forbidden'):
            if operation == 'postgres': psycopg.connect(host='127.0.0.1',port=5433)
            if operation == 'engine': sqlalchemy.create_engine('postgresql+psycopg://unused')
            if operation == 'sqlite': sqlite3.connect(':memory:')
            if operation == 'process': subprocess.Popen([sys.executable,'-m','uvicorn'])
            if operation == 'run': subprocess.run(['anything'])
            if operation == 'http':
                with httpx.Client(trust_env=False) as client:client.get('http://127.0.0.1:8001')
            if operation == 'provider': payment.provider_request({})
    assert guard.failed and guard.refusals == 1
    evidence = tmp_path/'pure_refused_0001.json'
    old = evidence.read_bytes()
    with pytest.raises(FileExistsError): runner.write_new(evidence, {})
    assert evidence.read_bytes() == old


@pytest.mark.parametrize('code,blocked', [(0,False),(1,False),(0,True)])
def test_round5_journal_cannot_pass_failed_child_or_caught_effect(tmp_path, code, blocked):
    out = runner.reserve(parent=tmp_path)
    def launch(*args, **kwargs):
        env = kwargs['env']
        assert env['PYTHON_DOTENV_DISABLED'] == '1'
        assert not any(k in env for k in (*runner.DB_ROLES, runner.DERIVATION_SECRET))
        runner.write_new(out/'pure_summary.json', dict(failed=blocked,refusals=int(blocked)))
        return Child(code)
    result = runner.execute(out, round5_config(), empty_snapshot, launch)
    assert result == (code or int(blocked))
    state = runner.inspect_run(out)
    assert state['execution_profile'] == 'round5' and state['passed'] == (code == 0 and not blocked)
    assert state['test_exit_code'] == code


def test_round5_collection_mismatch_stops_before_any_fixture(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import pytest as real_pytest
    out = runner.reserve(parent=tmp_path)
    runner.write_new(out/'command.json', round5_config())
    for key in list(os.environ):
        if key.startswith(('DATABASE_','MIGRATION_','POSTGRES_','PAYMENT_','DEMO_','DEVICE_KEY_','PG')) or key in ('MIGRATOR_PASSWORD','RUNTIME_PASSWORD'):
            monkeypatch.delenv(key)
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED','1')
    for key in ('TEMP','TMP','B1B_REPORT_DIR'): monkeypatch.setenv(key, str(tmp_path))
    def fake_main(args, plugins):
        plugins[0].pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid='unapproved')]))
        pytest.fail('Unexpected collection must stop before fixture execution')
    monkeypatch.setattr(real_pytest,'main',fake_main)
    with pytest.raises(ValueError,match='Unexpected Round 5 collection'):
        runner.worker(out)
    assert json.loads((out/'pure_summary.json').read_text())['failed']


def full_identity(tmp_path):
    path=tmp_path/'collection.json'
    if not path.exists():runner.write_new(path,dict(node_ids=['tests/test_phase1.py::one','tests/test_phase2.py::two']))
    return dict(host='127.0.0.1',port=55438,database='doi_pin_full_abcdef012345',execution_profile='full',
                mock_port=55439,system_identifier='new-full',env_file=str(tmp_path/'private.env'),
                collection_file=str(path),identity_file=str(tmp_path/'instance.json'))


def full_values(identity):
    values=round3_values(identity)
    values.update(PAYMENT_SERVICE_KEY=secrets.token_urlsafe(48),PAYMENT_CALLBACK_KEY=secrets.token_urlsafe(48))
    return values


def test_full_collection_identity_normalizes_only_source_import_uuid4():
    one='tests/test_phase8a_contract.py::test_client_cannot_select_settlement_result[actor_id-11111111-1111-4111-8111-111111111111]'
    two=one.replace('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222')
    assert runner.reconcile_collection([one],[two])['count']==1
    with pytest.raises(ValueError):runner.reconcile_collection([one,one],[two])
    with pytest.raises(ValueError):runner.reconcile_collection([one+'other'],[two])
    other='tests/test_phase8a_staged_fence.py::test_invalid_inspection_cannot_install_fence[station_id-11111111-1111-4111-8111-111111111111-STATION_INVALID]'
    assert runner.canonical_node(other)==other


def test_full_profile_requires_complete_module_inventory(tmp_path):
    ident=full_identity(tmp_path)
    config=dict(profile='business',execution_profile='full',collect_only=False,targets=['tests/test_phase1.py','tests/test_phase2.py'])
    runner.validate_isolated_selection(config,ident)
    config['targets'].pop()
    with pytest.raises(ValueError):runner.validate_isolated_selection(config,ident)


@pytest.mark.parametrize('port',[5433,5434,5435,5436,5437,5438])
def test_full_profile_refuses_all_five_retained_ports(tmp_path,port):
    ident=full_identity(tmp_path);values=full_values(ident);ident['port']=port
    with pytest.raises(ValueError):runner.isolated_environment(values,ident,{})


def test_full_environment_validates_all_payment_dependencies(tmp_path):
    ident=full_identity(tmp_path);values=full_values(ident)
    env=runner.isolated_environment(values,ident,dict(ORIGINAL_SECRET='old'))
    assert 'ORIGINAL_SECRET' not in env and env['PYTHON_DOTENV_DISABLED']=='1'
    assert str(ROOT/'.venv/Lib/site-packages') in env['PYTHONPATH']
    del values['PAYMENT_SERVICE_KEY']
    with pytest.raises(ValueError):runner.isolated_environment(values,ident,{})


def test_full_cache_is_new_and_sqlite_cannot_touch_old_data(tmp_path):
    import sqlite3
    guard=runner.FullOutputGuard(tmp_path)
    old=ROOT/'.cache'/('p6-provider-'+'a'*32)/'ledger.sqlite3'
    mapped=guard.path(old)
    assert mapped.is_relative_to(tmp_path) and guard.path(old)==mapped
    with guard.install():
        with pytest.raises(ValueError):sqlite3.connect(ROOT/'.local/device/S01.sqlite3')
    with pytest.raises(ValueError):guard.path(ROOT/'.cache/unknown/file')


@pytest.mark.parametrize('command', [['cmd','/c','anything'],['-m','unknown'],['-m','app.workers.payment']])
def test_full_native_boundary_rejects_unreviewed_commands(tmp_path,command):
    ident=full_identity(tmp_path);env=runner.isolated_environment(full_values(ident),ident,{})
    adapter=runner.FullProcesses(tmp_path,ident,env)
    with pytest.raises(ValueError):adapter.popen(command,cwd=ROOT,env=env)
    assert adapter.failed


def test_native_expected_worker_failure_is_evidence_not_false_isolation_failure(tmp_path):
    from types import SimpleNamespace
    process=SimpleNamespace(pid=7,poll=lambda:1,wait=lambda timeout=None:1)
    adapter=SimpleNamespace(failed=False)
    child=runner.NativeChild(adapter,process,tmp_path,['-m','app.workers.payment','--once'],True)
    assert child.wait()==1 and not adapter.failed
    assert json.loads((tmp_path/'exit.json').read_text())['expected_nonzero']


def test_native_unexpected_failure_prevents_pass(tmp_path):
    from types import SimpleNamespace
    adapter=SimpleNamespace(failed=False)
    process=SimpleNamespace(pid=8,poll=lambda:2)
    child=runner.NativeChild(adapter,process,tmp_path,['-m','app.workers.payment','--once'],False)
    assert child.poll()==2 and adapter.failed


class CatalogRows:
    def __init__(self, rows): self.rows = rows
    def fetchone(self): return self.rows[0]
    def fetchall(self): return list(self.rows)


class CatalogConnection:
    """Synthetic lock budget: locks survive until the transaction exits."""
    def __init__(self, count=3, mutation=None, fail=False, busy=False):
        self.names = [(i+1, 'phase5_test_'+format(i, '012x'), 'doi_pin_migrator', 'runtime=U') for i in range(count)]
        self.mutation, self.fail, self.busy = mutation, fail, busy
        self.active = self.closed = False
        self.locks = self.maximum_locks = self.transactions = self.releases = self.namespace_reads = 0
    def __enter__(self): return self
    def __exit__(self, *args):
        self.closed = True
        assert not self.active and self.locks == 0
    def transaction(self):
        owner = self
        class Transaction:
            def __enter__(self):
                assert not owner.active and owner.locks == 0
                owner.active = True; owner.transactions += 1
            def __exit__(self, *args):
                owner.active = False; owner.locks = 0; owner.releases += 1
        return Transaction()
    def execute(self, query, params=None):
        from psycopg.errors import OutOfMemory
        value = str(query)
        if 'pg_control_system' in value: return CatalogRows([('new-cluster',)])
        if 'pg_stat_activity' in value: return CatalogRows([(99,)] if self.busy else [])
        if 'FROM pg_namespace' in value:
            self.namespace_reads += 1
            rows = list(self.names)
            if self.mutation and self.namespace_reads >= 2:
                if self.mutation == 'missing': rows.pop()
                if self.mutation == 'extra': rows.append((9999, 'phase5_test_ffffffffffff', 'doi_pin_migrator', None))
                if self.mutation == 'replacement': rows[0] = (9999, *rows[0][1:])
                if self.mutation == 'acl': rows[0] = (*rows[0][:3], 'unexpected=U')
            return CatalogRows(rows)
        if value.startswith('SET TRANSACTION'):
            assert self.active and 'READ ONLY' in value and 'REPEATABLE READ' in value
            return CatalogRows([])
        if 'FROM pg_tables' in value:
            assert self.active
            return CatalogRows([('alembic_version',)]+[('table_'+str(i),) for i in range(39)])
        if 'SELECT count(*)' in value:
            assert self.active
            self.locks += 1; self.maximum_locks = max(self.maximum_locks, self.locks)
            if self.fail or self.locks > 64: raise OutOfMemory('synthetic private SQL detail')
            return CatalogRows([(1, 'content-digest')])
        if 'SELECT version_num' in value: return CatalogRows([('0010_no_delivery_eligibility',)])
        if 'FROM pg_class WHERE' in value: return CatalogRows([('table_0', 'r', 'doi_pin_migrator', 'runtime=r')])
        if any(table in value for table in ('pg_attribute', 'pg_constraint', 'pg_trigger', 'pg_proc')):
            assert self.active
            return CatalogRows([])
        raise AssertionError('Unexpected catalog query')


def catalog_scan(monkeypatch, connection, **kwargs):
    import psycopg
    def connect(**options):
        assert options['autocommit'] is True
        assert '-cdefault_transaction_read_only=on' in options['options']
        assert '-cstatement_timeout=15000' in options['options']
        assert '-clock_timeout=5000' in options['options']
        return connection
    monkeypatch.setattr(psycopg, 'connect', connect)
    identity = dict(isolation_identity(), original_system_identifier='protected', previous_system_identifier='old')
    return runner.isolated_catalog(identity, isolation_values(), **kwargs)


def test_large_catalog_releases_locks_per_schema_and_retains_checks(monkeypatch):
    connection = CatalogConnection(count=200)
    result = catalog_scan(monkeypatch, connection)
    assert len(result['schemas']) == 200
    assert connection.transactions == connection.releases == 200 and connection.closed
    assert connection.maximum_locks == 40 and connection.locks == 0
    assert result['quiescence_verified'] and 'not a global atomic snapshot' in result['snapshot_mode']
    for item in result['schemas']:
        assert item['owner'] == 'doi_pin_migrator' and item['acl'] == 'runtime=U'
        assert item['revision'] == ['0010_no_delivery_eligibility'] and len(item['table_rows']) == 40
        assert item['table_digests']['table_0'] == 'content-digest'
        assert item['objects'][0][3] == 'runtime=r'
        assert all(key in item for key in ('columns','constraints','triggers','functions'))


def test_catalog_53200_releases_transaction_and_connection(monkeypatch):
    from psycopg.errors import OutOfMemory
    connection = CatalogConnection(fail=True)
    with pytest.raises(OutOfMemory) as error: catalog_scan(monkeypatch, connection)
    assert error.value.sqlstate == '53200'
    assert connection.transactions == connection.releases == 1
    assert connection.closed and connection.locks == 0


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'replacement', 'acl'])
def test_catalog_namespace_mutation_fails_closed(monkeypatch, mutation):
    connection = CatalogConnection(mutation=mutation)
    with pytest.raises(ValueError, match='inventory drift'): catalog_scan(monkeypatch, connection)
    assert connection.closed and connection.locks == 0


def test_catalog_missing_quiescence_is_not_a_pass(monkeypatch):
    connection = CatalogConnection(busy=True)
    with pytest.raises(ValueError, match='not quiescent'): catalog_scan(monkeypatch, connection)
    assert connection.transactions == 0 and connection.closed


def test_catalog_pristine_refuses_existing_schema(monkeypatch):
    connection = CatalogConnection()
    with pytest.raises(ValueError, match='Fresh isolated'): catalog_scan(monkeypatch, connection, pristine=True)
    assert connection.transactions == 0 and connection.closed


def test_catalog_wrong_schema_owner_is_refused(monkeypatch):
    connection = CatalogConnection()
    connection.names[0] = (*connection.names[0][:2], 'postgres', connection.names[0][3])
    with pytest.raises(ValueError, match='Unexpected isolated schema or owner'): catalog_scan(monkeypatch, connection)
    assert connection.transactions == 0 and connection.closed


def test_catalog_error_is_unknown_even_when_pytest_passed(tmp_path, monkeypatch):
    from psycopg.errors import OutOfMemory
    out = runner.reserve(parent=tmp_path)
    identity = round3_identity(); env = runner.isolated_environment(round3_values(identity), identity, {})
    for key in runner.DB_ROLES: monkeypatch.setenv(key, env[key].replace('synthetic_', 'original_'))
    monkeypatch.setattr(runner, 'load_isolation', lambda path: (identity, env))
    monkeypatch.setattr(runner, 'verify_container', lambda value: None)
    checks = []
    def catalog(*args, **kwargs):
        checks.append(kwargs)
        if kwargs.get('pristine'): return dict(schemas=[])
        raise OutOfMemory('synthetic private SQL detail')
    monkeypatch.setattr(runner, 'isolated_catalog', catalog)
    def launch(*args, **kwargs): return Child(0)
    assert runner.execute(out, round3_config(), empty_snapshot, launch) == 1
    result = runner.inspect_run(out)
    assert result['state'] == 'UNKNOWN' and result['test_exit_code'] == 0 and not result['passed']
    assert result['sqlstate'] == '53200' and len(checks) == 2
    assert all('private SQL detail' not in p.read_text() for p in out.glob('*.json'))


@pytest.mark.parametrize('failure', ['running_worker', 'running_local', 'missing_exit', 'pid_mismatch'])
def test_full_catalog_cannot_start_without_owned_process_quiescence(tmp_path, monkeypatch, failure):
    out = runner.reserve(parent=tmp_path); identity = full_identity(tmp_path)
    env = runner.isolated_environment(full_values(identity), identity, {})
    for key in runner.DB_ROLES: monkeypatch.setenv(key, env[key].replace('synthetic_', 'original_'))
    monkeypatch.setattr(runner, 'load_isolation', lambda path: (identity, env))
    monkeypatch.setattr(runner, 'verify_container', lambda value: None)
    calls = []
    def catalog(*args, **kwargs): calls.append(kwargs); return dict(schemas=[])
    monkeypatch.setattr(runner, 'isolated_catalog', catalog)
    monkeypatch.setattr(runner, 'full_wait', lambda *args: 0)
    class Finished(Child):
        def poll(self): return None if failure == 'running_worker' else 0
    def launch(*args, **kwargs):
        runner.write_new(out/'full_effect_manifest.json', dict(local_workers_quiescent=failure!='running_local',
            native_children=1 if failure in ('missing_exit','pid_mismatch') else 0))
        folder = out/'native'; folder.mkdir()
        if failure in ('missing_exit','pid_mismatch'):
            folder = folder/'0001'; folder.mkdir()
            runner.write_new(folder/'start.json', dict(pid=1))
            runner.write_new(folder/'actual_pid.json', dict(pid=2 if failure=='pid_mismatch' else 1))
            if failure == 'pid_mismatch': runner.write_new(folder/'exit.json', dict(pid=1,exit_code=0))
        return Finished(0)
    config = dict(profile='business',execution_profile='full',collect_only=False,
        targets=['tests/test_phase1.py','tests/test_phase2.py'],isolation='synthetic')
    assert runner.execute(out, config, empty_snapshot, launch) == 1
    assert len(calls) == 1 and runner.inspect_run(out)['state'] == 'UNKNOWN'
    assert not runner.inspect_run(out)['passed']


@pytest.mark.parametrize('change', ['missing', 'extra', 'order', 'inventory', 'kind'])
def test_fixture_interaction_selection_is_exact_and_ct11_first(tmp_path, change):
    identity = full_identity(tmp_path)
    identity['selection_kind'] = 'fixture_interaction'
    (tmp_path/'collection.json').write_text(json.dumps(dict(node_ids=list(runner.FIX_VERIFY_TARGETS))))
    config = dict(profile='business', execution_profile='full',collect_only=False,targets=list(runner.FIX_VERIFY_TARGETS))
    runner.validate_isolated_selection(config, identity)
    if change == 'missing': config['targets'].pop()
    if change == 'extra': config['targets'].append('tests/test_phase4.py::other')
    if change == 'order': config['targets'].reverse()
    if change == 'inventory': (tmp_path/'collection.json').write_text(json.dumps(dict(node_ids=list(reversed(runner.FIX_VERIFY_TARGETS)))))
    if change == 'kind': identity['selection_kind'] = 'unapproved'
    with pytest.raises(ValueError): runner.validate_isolated_selection(config, identity)


def test_fixture_source_scope_is_explicit_and_does_not_include_business():
    assert runner.FIXTURE_SOURCE_SCOPE == {'tests/conftest.py','tests/test_phase4.py','tests/test_phase8b_fixture_isolation.py'}
    assert set(runner.FIXTURE_REGRESSION_TARGETS).issubset(runner.FIX_VERIFY_TARGETS)
    assert len(runner.FIX_VERIFY_TARGETS) == len(set(runner.FIX_VERIFY_TARGETS)) == 16
    assert runner.FIX_VERIFY_TARGETS[0] == 'tests/test_phase4.py::test_CT11_concurrent_duplicate_event_once'
    assert runner.EXTRA_SOURCE.count('tests/test_phase8b_fixture_isolation.py') == 1


def test_proof_observer_records_status_without_payload_headers_or_secrets(tmp_path, monkeypatch):
    import httpx
    secret = secrets.token_urlsafe(48)
    request = httpx.Request('POST', 'http://testserver/v1/device/recovery-observations',
        headers={'Authorization':secret},json=dict(protocol_version='0.3',stage='NO_DELIVERY_INSPECTION',secret=secret))
    response = httpx.Response(409,request=request,json=dict(code='QUIESCENCE_REQUIRED',details=secret))
    monkeypatch.setattr(httpx.Client, 'send', lambda *args, **kwargs: response)
    with runner.observe_422(tmp_path): assert httpx.Client().send(request) is response
    result = json.loads((tmp_path/'proof_ingress_0001.json').read_text())
    assert result['status'] == 409 and result['code'] == 'QUIESCENCE_REQUIRED'
    assert secret not in json.dumps(result) and set(result) == {'node','status','code'}


def launcher_request(tmp_path, monkeypatch):
    base=tmp_path/'local';base.mkdir();monkeypatch.setattr(windows_launcher,'BASE',base)
    monkeypatch.setattr(windows_launcher,'powershell',lambda script:'TEST\\anhdu')
    path=windows_launcher.prepare('synthetic',2,0)
    return path,windows_launcher.read(path)


def test_windows_api_layout_matches_64_bit_windows():
    import ctypes
    assert ctypes.sizeof(ctypes.c_void_p)==8
    assert ctypes.sizeof(windows_launcher.Startup)==104
    assert ctypes.sizeof(windows_launcher.Process)==24
    assert ctypes.sizeof(windows_launcher.Limits)==144
    assert ctypes.sizeof(windows_launcher.Accounting)==48
    assert ctypes.sizeof(windows_launcher.Entry)==568


def test_launcher_request_is_exclusive_and_does_not_record_credentials(tmp_path,monkeypatch):
    path,q=launcher_request(tmp_path,monkeypatch)
    loaded=windows_launcher.load_request(path,windows_launcher.sha(path),True)
    assert loaded==q and q['mode']=='synthetic' and q['isolation'] is None
    assert not any(k in q for k in ('DATABASE_URL','PASSWORD','SECRET'))
    with pytest.raises(FileExistsError):windows_launcher.write(path,q)
    with pytest.raises(ValueError):windows_launcher.load_request(path,'0'*64)


@pytest.mark.parametrize('change',['field','directory','mode','python','user','seconds','identity'])
def test_launcher_tampered_request_cannot_launch(tmp_path,monkeypatch,change):
    path,q=launcher_request(tmp_path,monkeypatch)
    if change=='field':q['unapproved']='value'
    if change=='directory':q['directory']=str(tmp_path)
    if change=='mode':q['mode']='unbounded'
    if change=='python':q['python']='C:/unapproved.exe'
    if change=='user':q['user']='unknown'
    if change=='seconds':q['seconds']=True
    if change=='identity':q['isolation']='must-not-open-database'
    path.write_text(json.dumps(q))
    with pytest.raises(ValueError):windows_launcher.load_request(path)


def test_synthetic_environment_drops_db_provider_and_dotenv_fallback(monkeypatch):
    for key in ('DATABASE_URL','PGSERVICE','PAYMENT_SERVICE_KEY','PYTEST_PLUGINS','PYTHONPATH'):
        monkeypatch.setenv(key,'must-not-inherit')
    value=windows_launcher.environment('synthetic')
    assert value['PYTHON_DOTENV_DISABLED']=='1'
    assert not any(k in value for k in ('DATABASE_URL','PGSERVICE','PAYMENT_SERVICE_KEY','PYTEST_PLUGINS','PYTHONPATH'))


@pytest.mark.parametrize('failure',['missing','reused','wrong_executable'])
def test_launcher_stale_identity_cannot_report_running_or_pass(tmp_path,monkeypatch,failure):
    path,q=launcher_request(tmp_path,monkeypatch);directory=Path(q['directory'])
    windows_launcher.write(directory/'claim.json',dict(pid=99,creation_ticks=123,executable=q['pythonw'],request_sha=windows_launcher.sha(path)))
    current=dict(pid=99,creation_ticks=124 if failure=='reused' else 123,alive=failure!='missing',executable='C:/other.exe' if failure=='wrong_executable' else q['pythonw'])
    actual=windows_launcher.status(path,lambda pid:current)
    assert actual['state']=='UNKNOWN' and not actual['passed']


def test_live_launcher_is_running_without_claiming_pass(tmp_path,monkeypatch):
    path,q=launcher_request(tmp_path,monkeypatch);me=dict(pid=99,creation_ticks=123,executable=q['pythonw'],alive=True)
    windows_launcher.write(Path(q['directory'])/'claim.json',dict(**me,request_sha=windows_launcher.sha(path)))
    result=windows_launcher.status(path,lambda pid:me)
    assert result['state']=='RUNNING' and result['identity_valid'] and not result['passed']


def test_fake_terminal_pass_without_junit_or_identity_is_unknown(tmp_path,monkeypatch):
    path,q=launcher_request(tmp_path,monkeypatch)
    windows_launcher.write(Path(q['directory'])/'launcher_exit.json',dict(state='COMPLETED',passed=True,child_exit_code=0))
    assert windows_launcher.status(path)['state']=='UNKNOWN'
    assert windows_launcher.status(path)['passed'] is False


def test_submitted_task_without_start_record_is_unknown(tmp_path,monkeypatch):
    path,q=launcher_request(tmp_path,monkeypatch)
    windows_launcher.write(Path(q['directory'])/'submission.json',dict(submitted=True))
    assert windows_launcher.status(path)==dict(state='UNKNOWN',passed=False)


def test_synthetic_nonzero_exit_never_passes(tmp_path,monkeypatch):
    path,q=launcher_request(tmp_path,monkeypatch);folder=Path(q['directory'])/'child';folder.mkdir()
    windows_launcher.write(folder/'final.json',dict(exit_code=7))
    assert not windows_launcher.validate_result(q,7)['passed']
    assert not windows_launcher.validate_result(q,0)['passed']


def test_duplicate_submit_is_refused_before_scheduler_rpc(tmp_path,monkeypatch):
    path,q=launcher_request(tmp_path,monkeypatch)
    windows_launcher.write(Path(q['directory'])/'claim.json',dict(pid=99))
    def forbidden(script):pytest.fail('Duplicate cannot reach Task Scheduler')
    monkeypatch.setattr(windows_launcher,'powershell',forbidden)
    with pytest.raises(FileExistsError):windows_launcher.submit(path)


def scheduler_observation(q, start='false', level='LeastPrivilege'):
    import xml.etree.ElementTree as ET
    ns='http://schemas.microsoft.com/windows/2004/02/mit/task'
    tree=ET.Element('{'+ns+'}Task')
    def add(parent,name,value=None):
        element=ET.SubElement(parent,'{'+ns+'}'+name)
        if value is not None:element.text=value
        return element
    add(tree,'Triggers');principals=add(tree,'Principals');principal=add(principals,'Principal')
    sid='S-1-5-21-111-222-333-1001'
    add(principal,'UserId',sid);add(principal,'LogonType','InteractiveToken')
    if level is not None:add(principal,'RunLevel',level)
    settings=add(tree,'Settings');add(settings,'MultipleInstancesPolicy','IgnoreNew');add(settings,'ExecutionTimeLimit','PT5H')
    if start is not None:add(settings,'StartWhenAvailable',start)
    action=add(add(tree,'Actions'),'Exec')
    args=windows_launcher.action_arguments(q['request'])
    for key,value in (('Command',q['pythonw']),('Arguments',args),('WorkingDirectory',str(ROOT))):add(action,key,value)
    effective=dict(name=q['task'],path='\\'+q['task'],expected_user_sid=sid,user_id=q['user'],user_sid=sid,
        owner_sid=sid,caller_sid=sid,run_level=0,logon_type=3,start_when_available=False,
        restart_count=0,multiple_instances=2,triggers=0,actions=1,execution_limit='PT5H',enabled=True,
        allow_demand_start=True,command=q['pythonw'],arguments=args,cwd=str(ROOT))
    return ET.tostring(tree,encoding='unicode'),effective


@pytest.mark.parametrize('start',[None,'false'])
@pytest.mark.parametrize('level',[None,'LeastPrivilege'])
def test_task_explicit_or_omitted_defaults_require_matching_com(tmp_path,monkeypatch,start,level):
    path,q=launcher_request(tmp_path,monkeypatch);xml,effective=scheduler_observation(q,start,level)
    before=windows_launcher.sha(path)
    windows_launcher.verify_task(q,xml,effective)
    assert windows_launcher.sha(path)==before and not (path.parent/'task_registration.json').exists()


@pytest.mark.parametrize('start',[None,'false','true'])
@pytest.mark.parametrize('com_start',[False,True])
def test_task_catchup_rejected_in_xml_or_com(tmp_path,monkeypatch,start,com_start):
    path,q=launcher_request(tmp_path,monkeypatch);xml,effective=scheduler_observation(q,start)
    effective['start_when_available']=com_start
    if start=='true' or com_start:
        with pytest.raises(ValueError):windows_launcher.verify_task(q,xml,effective)
    else:windows_launcher.verify_task(q,xml,effective)


@pytest.mark.parametrize('level',[None,'LeastPrivilege','HighestAvailable'])
@pytest.mark.parametrize('com_level',[0,1])
def test_task_elevation_and_xml_com_disagreement_rejected(tmp_path,monkeypatch,level,com_level):
    path,q=launcher_request(tmp_path,monkeypatch);xml,effective=scheduler_observation(q,level=level)
    effective['run_level']=com_level
    if level=='HighestAvailable' or com_level:
        with pytest.raises(ValueError):windows_launcher.verify_task(q,xml,effective)
    else:windows_launcher.verify_task(q,xml,effective)


@pytest.mark.parametrize('key,bad',[
    ('start_when_available',None),('start_when_available',0),('start_when_available','false'),
    ('run_level',None),('run_level',False),('run_level','0'),('logon_type',1),
    ('owner_sid','S-1-5-18'),('user_sid','S-1-5-18'),('caller_sid','S-1-5-18'),
    ('expected_user_sid',None),('name','another_task'),('path','\\another_task'),
    ('command','C:/other.exe'),('arguments','-m pytest'),('cwd','C:/'),
    ('triggers',1),('actions',2),('restart_count',1),('multiple_instances',0),
    ('execution_limit','PT0S'),('enabled',False),('allow_demand_start',None)])
def test_unknown_or_unsafe_com_properties_fail_closed(tmp_path,monkeypatch,key,bad):
    path,q=launcher_request(tmp_path,monkeypatch);xml,effective=scheduler_observation(q)
    effective[key]=bad
    with pytest.raises(ValueError):windows_launcher.verify_task(q,xml,effective)


@pytest.mark.parametrize('field',['owner','command','arguments','cwd','trigger','extra_action','retry','logon','principal_group'])
def test_xml_security_checks_survive_optional_default_fix(tmp_path,monkeypatch,field):
    import xml.etree.ElementTree as ET
    path,q=launcher_request(tmp_path,monkeypatch);xml,effective=scheduler_observation(q,None,None)
    tree=ET.fromstring(xml);ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
    paths={'owner':'t:Principals/t:Principal/t:UserId','command':'t:Actions/t:Exec/t:Command',
           'arguments':'t:Actions/t:Exec/t:Arguments','cwd':'t:Actions/t:Exec/t:WorkingDirectory',
           'logon':'t:Principals/t:Principal/t:LogonType'}
    if field in paths:tree.find(paths[field],ns).text='UNAPPROVED'
    else:
        parent,tag={'trigger':('t:Triggers','BootTrigger'),'extra_action':('t:Actions','Exec'),
          'retry':('t:Settings','RestartOnFailure'),'principal_group':('t:Principals/t:Principal','GroupId')}[field]
        element=ET.SubElement(tree.find(parent,ns),'{'+ns['t']+'}'+tag)
        if field=='retry':ET.SubElement(element,'{'+ns['t']+'}Count').text='1'
    with pytest.raises(ValueError):windows_launcher.verify_task(q,ET.tostring(tree,encoding='unicode'),effective)


@pytest.mark.parametrize('filename',['task_registration.json','registration_reservation.json','claim.json'])
def test_registration_evidence_collision_cannot_reach_scheduler_or_overwrite(tmp_path,monkeypatch,filename):
    path,q=launcher_request(tmp_path,monkeypatch);protected=path.parent/filename
    windows_launcher.write(protected,dict(retained='previous evidence'));before=windows_launcher.sha(protected)
    def forbidden(script):pytest.fail('Existing evidence cannot reach mutating RPC')
    monkeypatch.setattr(windows_launcher,'powershell',forbidden)
    with pytest.raises(FileExistsError):windows_launcher.register(path)
    assert windows_launcher.sha(protected)==before


def test_existing_task_collision_uses_create_only_and_never_updates(tmp_path,monkeypatch):
    path,q=launcher_request(tmp_path,monkeypatch);calls=[]
    def existing(script):
        calls.append(script)
        assert '.RegisterTaskDefinition(' in script and ',$d,2,' in script
        raise PermissionError('Existing task: TASK_CREATE rejects collision')
    monkeypatch.setattr(windows_launcher,'powershell',existing)
    with pytest.raises(PermissionError):windows_launcher.register(path)
    assert len(calls)==1 and (path.parent/'registration_reservation.json').exists()
    with pytest.raises(FileExistsError):windows_launcher.register(path)
    assert len(calls)==1 and not (path.parent/'task_registration.json').exists()


@pytest.mark.parametrize('failure',['unreadable','missing_properties'])
def test_submit_cannot_run_without_effective_com_validation(tmp_path,monkeypatch,failure):
    path,q=launcher_request(tmp_path,monkeypatch);xml,effective=scheduler_observation(q)
    windows_launcher.write(path.parent/'task_registration.json',dict(request_sha=windows_launcher.sha(path),xml=xml,effective=effective))
    def info(request):
        if failure=='unreadable':raise PermissionError('COM unavailable')
        return dict(xml=xml,effective=None,instances=[])
    monkeypatch.setattr(windows_launcher,'task_info',info)
    def forbidden(script):pytest.fail('No launch without effective COM validation')
    monkeypatch.setattr(windows_launcher,'powershell',forbidden)
    with pytest.raises((PermissionError,ValueError)):windows_launcher.submit(path)
    assert not (path.parent/'submission_reservation.json').exists()
