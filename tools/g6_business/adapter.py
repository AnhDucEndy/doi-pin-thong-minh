"""Fail-closed admission/transport/process controls, separate from startup guard.

Business child bootstrap/native-transport integration is deliberately NOT armed.
Python controls are not an OS sandbox. No provisioning or effects on import.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit
import uuid

import httpx

CLUSTER = '7712738307604140070'
PROTECTED = frozenset({5432, 5448, 5449})
SMOKE = 'phase5_test_ecfa77274ae3'


class Denied(ValueError): pass
class PendingIntegration(Denied): pass


def require(condition, code):
    if not condition: raise Denied(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class Config:
    run_id: str
    schema: str
    role: str
    database: str
    system_identifier: str
    ports: tuple
    routes: tuple

    def validate(self):
        require(bool(re.fullmatch('[a-f0-9]{12}', self.run_id)), 'RUN_ID')
        require(self.schema == 'phase5_test_' + self.run_id and self.schema != SMOKE, 'FRESH_SCHEMA')
        require(self.role == 'g6r_' + self.run_id, 'DEDICATED_ROLE')
        require(self.database == 'g6_laptop' and self.system_identifier == CLUSTER, 'CLUSTER')
        require(bool(self.ports) and len(set(self.ports)) == len(self.ports), 'PORTS')
        require(all(type(p) is int and 1024 <= p <= 65535 and p not in PROTECTED for p in self.ports), 'PROTECTED_PORT')
        require(bool(self.routes), 'ROUTES')
        for port, method, path in self.routes:
            require(port in self.ports and method in ('GET', 'POST', 'PUT', 'PATCH'), 'ROUTE')
            require(path.startswith('/') and not any(x in path for x in ('*', '?', '#', '%', '..', '\\')), 'EXACT_PATH')
            require(not path.startswith('/mock/v1/refunds'), 'REFUND_DISPATCH')
        return self


def validate_catalog(config, facts):
    """Checks facts from trusted read-only collector, not caller API claims."""
    config.validate()
    require(facts['system_identifier'] == CLUSTER and facts['database'] == config.database, 'CLUSTER')
    require(facts['schema'] == config.schema and facts['role'] == config.role, 'BINDING')
    require(facts['revision'] == '0010_no_delivery_eligibility', 'REVISION')
    require(facts['owner_marker'] == 'g6_business:' + config.run_id, 'OWNERSHIP_MARKER')
    require(facts['schema_owner'] != config.role, 'RUNTIME_OWNER')
    require(not any(facts['role_flags']) and not facts['memberships'], 'EXCESS_PRIVILEGES')
    require(not facts['cross_schema_privileges'] and not facts['cross_schema_definers'], 'CROSS_SCHEMA')
    require(not facts['schema_create'] and not facts['public_create'], 'SCHEMA_CREATE')
    require(facts['audit_privileges'] == [True, True, False, False, False], 'AUDIT_ACL')
    require(facts['audit_trigger'] and facts['runtime_plan_verified'], 'RUNTIME_GRANT_PLAN')
    # This gate is not returned as a bearer credential/cached reusable authority.
    return True


def inspect_live(config, connection):
    """Read-only collector; never connects/provisions. Use dedicated runtime session.

    Exact table/column grants must additionally pass the revision-aware official
    plan review. Until that collector is integrated, no business launch is armed.
    """
    config.validate()
    info = connection.info
    require(info.host == '127.0.0.1' and info.port == 5449 and info.dbname == config.database, 'DB_ENDPOINT')
    require(info.user == config.role and connection.execute('SHOW transaction_read_only').fetchone()[0] == 'on', 'READONLY_INSPECTION')
    identity = connection.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]
    require(identity == CLUSTER, 'CLUSTER')
    # Runtime normally cannot read pg_control_system: a separate trusted readonly
    # identity collector is needed, without granting runtime this authority.
    raise PendingIntegration('SEPARATE_IDENTITY_AND_EXACT_GRANT_COLLECTOR_REQUIRED')


def check_endpoint(config, host, port):
    config.validate()
    require(host == '127.0.0.1' and port in config.ports and port not in PROTECTED, 'ENDPOINT')


class ExactTransport(httpx.BaseTransport):
    """Actual HTTPX transport wrapper; injected native/mock transport for controls."""
    def __init__(self, config, inner, record):
        self.config = config.validate(); self.inner = inner; self.record = record

    def handle_request(self, request):
        u = request.url
        check_endpoint(self.config, u.host, u.port)
        require(u.scheme == 'http' and not u.userinfo and not u.query, 'URL')
        require(not u.path.startswith('/mock/v1/refunds'), 'REFUND_DISPATCH')
        require((u.port, request.method, u.path) in self.config.routes, 'HTTP_ROUTE')
        require(u.raw_path.decode('ascii') == u.path, 'ENCODED_PATH')
        response = self.inner.handle_request(request)
        self.record(dict(method=request.method, path=u.path, port=u.port, status=response.status_code,
                         key_hash=digest(request.headers.get('Idempotency-Key', '')),
                         body_hash=hashlib.sha256(request.content).hexdigest()))
        require(not 300 <= response.status_code < 400, 'REDIRECT')
        return response

    def close(self): self.inner.close()


def client(config, inner, record):
    return httpx.Client(transport=ExactTransport(config, inner, record), trust_env=False,
                        follow_redirects=False, timeout=5)


class Supervisor:
    """Owned mock-control processes only until complete integration is verified."""
    def __init__(self, root, output, config):
        self.root = Path(root).resolve(); self.output = Path(output).resolve(); self.config = config.validate()
        require(self.output.is_relative_to(self.root / '.local'), 'OUTPUT_SCOPE')
        require(subprocess.run(['git', 'check-ignore', '--quiet', '--', str(self.output)], cwd=self.root).returncode == 0, 'OUTPUT_IGNORED')
        require(not self.output.exists(), 'OUTPUT_COLLISION')
        self.output.mkdir(parents=True, exist_ok=False)
        self.owned = {}; self.exits = set(); self.sequence = 0

    def record(self, event):
        self.sequence += 1
        with (self.output / f'event_{self.sequence:04d}.json').open('x', encoding='utf8') as f:
            json.dump(dict(run_id=self.config.run_id, supervisor_pid=os.getpid(), monotonic=time.monotonic(), **event), f)
            f.flush(); os.fsync(f.fileno())

    def ledger_path(self, name):
        require(bool(re.fullmatch(r'[a-zA-Z0-9_-]+\.sqlite3', name)), 'LEDGER_NAME')
        path = self.output / name
        require(not path.exists(), 'LEDGER_REUSE')
        return path

    def launch_control(self, script):
        expected = self.root / 'tools/g6_business/mock_probe.py'
        require(Path(script).resolve() == expected and expected.is_file(), 'ENTRYPOINT')
        allowed = {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'COMSPEC'}
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        env.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1')
        # Native base interpreter avoids Windows venv redirector PID ambiguity.
        proc = subprocess.Popen([sys._base_executable, '-I', '-B', str(expected)], env=env,
            cwd=self.output, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.owned[proc.pid] = proc
        self.record(dict(event='start', pid=proc.pid, parent_pid=os.getpid(), executable=sys._base_executable,
                         source_hash=hashlib.sha256(expected.read_bytes()).hexdigest()))
        return proc

    def wait(self, proc, timeout=5):
        require(self.owned.get(proc.pid) is proc, 'NOT_OWNED')
        stdout, stderr = proc.communicate(timeout=timeout)
        require(proc.returncode == 0 and not stderr, 'CHILD_FAILED')
        identity = json.loads(stdout)
        require(identity == dict(pid=proc.pid, parent_pid=os.getpid(), kind='mock-only'), 'PID_IDENTITY')
        self.exits.add(proc.pid)
        self.record(dict(event='wait', pid=proc.pid, exit_code=proc.returncode, identity=identity))
        return proc.returncode

    def terminate(self, proc):
        require(self.owned.get(proc.pid) is proc and proc.poll() is None, 'NOT_OWNED_RUNNING')
        self.record(dict(event='terminate', pid=proc.pid)); proc.terminate()
        code = proc.wait(timeout=5); self.exits.add(proc.pid)
        self.record(dict(event='wait', pid=proc.pid, exit_code=code))

    def finish(self):
        require(set(self.owned) == self.exits, 'MISSING_EXIT_WAIT')
        self.record(dict(event='complete', owned_count=len(self.owned)))

    def launch_business(self, *args, **kwargs):
        # Synthetic catalog facts must never unlock an unguarded real child.
        raise PendingIntegration('BUSINESS_BOOTSTRAP_NETWORK_NATIVE_DB_AND_GRANTS_NOT_VERIFIED')
