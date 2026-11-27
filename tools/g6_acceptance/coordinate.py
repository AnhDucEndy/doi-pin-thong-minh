"""Portable explicit controls/API startup entrypoints; never provisions a DB."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit, unquote

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent
URL_KEYS = ('DATABASE_ADMIN_URL', 'MIGRATION_DATABASE_URL', 'DATABASE_URL')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def ignored(path):
    return subprocess.run(['git', 'check-ignore', '--quiet', '--', str(path)],
        cwd=ROOT, capture_output=True).returncode == 0


def ports(values):
    require(isinstance(values, list) and bool(values), 'Explicit protected port inventory required')
    require(all(type(p) is int and 1 <= p <= 65535 for p in values), 'Invalid port inventory')
    return sorted(set(values))


def validate_config(config):
    require(isinstance(config, dict), 'Configuration object required')
    require(set(config) == {'database_port', 'database_name', 'schema',
        'expected_system_identifier', 'env_file', 'protected_ports'}, 'Unexpected configuration fields')
    protected = ports(config['protected_ports'])
    port = config['database_port']
    require(type(port) is int and 1 <= port <= 65535, 'Explicit test database port required')
    require(isinstance(config['database_name'], str) and
        re.fullmatch(r'[a-z][a-z0-9_]{0,62}', config['database_name']), 'Explicit test database required')
    require(isinstance(config['schema'], str) and
        re.fullmatch(r'phase5_test_[a-f0-9]{12}', config['schema']), 'Explicit isolated fixture schema required')
    require(isinstance(config['expected_system_identifier'], str) and
        re.fullmatch(r'[0-9]{10,22}', config['expected_system_identifier']), 'Explicit cluster identity required')
    require(isinstance(config['env_file'], str) and config['env_file'], 'Private test configuration required')
    path = (ROOT/config['env_file']).resolve()
    require(path.is_relative_to(ROOT) and path.is_file() and ignored(path), 'Use an existing Git-ignored workspace test env file')
    values = dict(dotenv_values(path, interpolate=False))
    expected_roles = ('postgres', 'doi_pin_migrator', 'doi_pin_runtime')
    for key, role in zip(URL_KEYS, expected_roles):
        require(isinstance(values.get(key), str), 'Missing explicit database URL')
        url = urlsplit(values[key].replace('postgresql+psycopg://', 'postgresql://'))
        require(values[key].startswith('postgresql+psycopg://') and url.hostname == '127.0.0.1'
            and url.port == port and url.path == '/'+config['database_name'] and not url.query
            and unquote(url.username or '') == role and bool(url.password), 'Invalid test database URL binding')
    fixture = dict(port=port, database=config['database_name'], schema=config['schema'],
        protected_ports=protected, expected_system_identifier=config['expected_system_identifier'])
    return fixture, {key: values[key] for key in URL_KEYS}


def new_output(path):
    path = (ROOT/path).resolve()
    require(path.is_relative_to(ROOT/'.local') and ignored(path), 'Output must be a NEW ignored workspace .local directory')
    path.mkdir(parents=True, exist_ok=False)
    (path/'reports').mkdir(exist_ok=False)
    return path


def free_port(excluded):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    require(port not in excluded, 'Port collision; stop without automatic retry')
    return port


def environment(out, fixture, urls):
    allowed = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE',
        'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
        'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS', 'OS', 'SYSTEMDRIVE', 'PATH'}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update(urls)
    env.update(PYTHONPATH=os.pathsep.join([str(SOURCE), str(ROOT/'.venv/Lib/site-packages'),
        str(ROOT/'services/backend'), str(ROOT)]), PYTHON_DOTENV_DISABLED='1',
        PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', G6_OUTPUT=str(out),
        G6_WORKSPACE=str(ROOT), G6_SCENARIO_OUTPUT=str(out), G6_ISOLATION_PORT=str(fixture['port']),
        G6_DATABASE=fixture['database'], DATABASE_SCHEMA=fixture['schema'],
        __PYVENV_LAUNCHER__=sys.executable)
    return env


def wait_owned(child, seconds):
    try:
        return child.wait(timeout=seconds), False
    except subprocess.TimeoutExpired:
        child.terminate()
        return child.wait(timeout=5), True


def controls(args):
    protected = ports(args.protected_port)
    out = new_output(args.output)
    database_port = free_port(protected)
    fixture = dict(port=database_port, database='g6_controls_'+secrets.token_hex(6),
        schema='phase5_test_'+secrets.token_hex(6), protected_ports=protected)
    # Synthetic, never connected to a PostgreSQL server. No local env is read.
    urls = {key: f"postgresql+psycopg://{role}:{secrets.token_urlsafe(36)}@127.0.0.1:{database_port}/{fixture['database']}"
        for key, role in zip(URL_KEYS, ('postgres', 'doi_pin_migrator', 'doi_pin_runtime'))}
    port = free_port(set(protected)|{database_port})
    write(out/'authorized_fixture.json', fixture)
    with (out/('owned-port-'+str(port))).open('x') as stream:
        stream.write('single owned ping mock, no application DB')
    env = environment(out, fixture, urls)
    env['G6_PING_PORT'] = str(port)
    command = [sys._base_executable, '-B', str(SOURCE/'controls.py')]
    write(out/'invocation.json', dict(command=command, invocations=1,
        API_startups=0, database_connections=0, source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in SOURCE.glob('*.py')}))
    with (out/'controller.log').open('x', encoding='utf-8') as log:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
            stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        write(out/'process.json', dict(pid=child.pid, command=command))
        code, timeout = wait_owned(child, 40)
    write(out/'exit.json', dict(pid=child.pid, exit=code, wait_record=True,
        timeout=timeout, intentional_stop=timeout))
    return 1 if timeout else code


def fixture_read(config, urls):
    """Read-only identity/fixture gate; called ONLY by explicit api mode."""
    import psycopg
    from psycopg import sql
    url = urlsplit(urls['DATABASE_ADMIN_URL'].replace('postgresql+psycopg://', 'postgresql://'))
    with psycopg.connect(host='127.0.0.1', hostaddr='127.0.0.1', port=config['database_port'],
        dbname=config['database_name'], user=unquote(url.username), password=unquote(url.password),
        connect_timeout=5, autocommit=True,
        options='-cdefault_transaction_read_only=on -cstatement_timeout=15000 -clock_timeout=5000') as connection:
        identity = connection.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]
        require(identity == config['expected_system_identifier'], 'Cluster identity mismatch')
        version = connection.execute(sql.SQL('SELECT version_num FROM {}.alembic_version').format(
            sql.Identifier(config['schema']))).fetchone()[0]
        require(version == '0010_no_delivery_eligibility', 'Wrong fixture revision')
        count = connection.execute(sql.SQL('SELECT count(*) FROM {}.audit_events').format(
            sql.Identifier(config['schema']))).fetchone()[0]
        return dict(system_identifier=identity, revision=version, audit_rows=count)


def api(args):
    """Exactly one supervised health-only launch; no provisioning or Docker calls."""
    config = json.loads((ROOT/args.config).read_text(encoding='utf-8-sig'))
    fixture, urls = validate_config(config)
    before = fixture_read(config, urls)
    out = new_output(args.output)
    write(out/'authorized_fixture.json', fixture)
    write(out/'database_before.json', before)
    port = free_port(set(fixture['protected_ports'])|{fixture['port']})
    with (out/('owned-port-'+str(port))).open('x') as stream:
        stream.write('single owned read-only API startup')
    env = environment(out, fixture, urls)
    nonce = secrets.token_hex(24)
    env.update(G6_API_PORT=str(port), G6_API_NONCE=nonce)
    command = [sys._base_executable, '-B', str(SOURCE/'api_smoke.py')]
    write(out/'invocation.json', dict(command=command, invocations=1, retry=False))
    passed = False
    with (out/'controller.log').open('x', encoding='utf-8') as log:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
            stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        write(out/'process.json', dict(pid=child.pid, command=command))
        try:
            import httpx
            deadline = time.monotonic()+20
            with httpx.Client(trust_env=False, timeout=1) as client:
                while True:
                    require(child.poll() is None, 'API exited before readiness')
                    require(time.monotonic() < deadline, 'API readiness deadline')
                    try:
                        response = client.get(f'http://127.0.0.1:{port}/health')
                    except httpx.ConnectError:
                        time.sleep(.05)  # Bounded readiness polling, no process retry.
                        continue
                    require(response.status_code == 200 and response.json().get('status') == 'ok', 'API health failed')
                    write(out/'health.json', dict(pid=child.pid, status=200, body=response.json()))
                    break
            write(out/'api-stop.json', dict(pid=child.pid, nonce=nonce))
            code, timeout = wait_owned(child, 7)
            after = fixture_read(config, urls)
            write(out/'database_after.json', after)
            require(before == after, 'Read-only fixture preservation mismatch')
            completion = json.loads((out/'api-exit.json').read_text(encoding='utf-8'))
            guarded = any(json.loads(p.read_text())['pid'] == child.pid for p in out.glob('guard-ready-*.json'))
            passed = (code == 0 and not timeout and guarded
                and completion == dict(pid=child.pid, code=0, started=True,
                    intentional_stop=True, deadline=False))
        finally:
            intentional = child.poll() is None
            if intentional:
                child.terminate()
            code = child.wait(timeout=5)
            write(out/'exit.json', dict(pid=child.pid, exit=code, wait_record=True,
                forced_stop=intentional, passed=passed))
    return 0 if passed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    focused = modes.add_parser('controls', help='Nine focused controls; synthetic DB URLs; no API/DB')
    focused.add_argument('--output', required=True)
    focused.add_argument('--protected-port', type=int, action='append', required=True)
    startup = modes.add_parser('api', help='Explicit authorized read-only API startup; no business workflow')
    startup.add_argument('--config', required=True)
    startup.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        require(os.name == 'nt', 'Reviewed Windows CPython socketpair environment required')
        return controls(args) if args.mode == 'controls' else api(args)
    except Exception as error:
        # Configuration/connection values never enter an error report.
        print(json.dumps(dict(passed=False, error_type=type(error).__name__)), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
