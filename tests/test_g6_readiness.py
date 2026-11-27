"""Actual coordinator.api control flow, synthetic processes/clock, no database/API."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/g6_acceptance/coordinate.py'
ORIGINAL_CHECKPOINT = '79d663022d74f1305462d3ce27414f7fcf171646'


def harness(monkeypatch, tmp_path, outcomes, *, exited=False, original=False):
    spec = importlib.util.spec_from_file_location('readiness_coordinator', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if original:
        text = subprocess.check_output(['git', 'show', ORIGINAL_CHECKPOINT + ':tools/g6_acceptance/coordinate.py'], cwd=ROOT).decode('utf8')
        node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == 'api')
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<original-HEAD-api>', 'exec'), module.__dict__)
    out = tmp_path / 'run'
    out.mkdir()
    (tmp_path / 'config.json').write_text('{}', encoding='utf8')
    clock = SimpleNamespace(value=0, calls=0)
    def monotonic():
        clock.value += .25
        return clock.value
    module.time = SimpleNamespace(monotonic=monotonic, sleep=lambda seconds: None)
    child = SimpleNamespace(pid=123, code=1 if exited else None, terminated=False, waits=0)
    child.poll = lambda: child.code
    def terminate():
        child.terminated = True
        child.code = 1
    def wait(timeout):
        child.waits += 1
        return child.code
    child.terminate, child.wait = terminate, wait
    module.subprocess = SimpleNamespace(Popen=lambda *a, **kw: child, STDOUT=subprocess.STDOUT)
    module.ROOT = tmp_path
    module.validate_config = lambda config: ({'protected_ports': [5432, 5448], 'port': 5449}, {})
    module.fixture_read = lambda *args: {'identity': 'synthetic', 'audit_rows': 0}
    module.new_output = lambda path: out
    module.free_port = lambda excluded: 12345
    module.environment = lambda *args: {}
    def owned_wait(proc, seconds):
        assert (out / 'api-stop.json').exists()
        module.write(out / 'api-exit.json', dict(pid=123, code=0, started=True, intentional_stop=True, deadline=False))
        module.write(out / 'guard-ready-synthetic.json', {'pid': 123})
        child.code = 0
        return 0, False
    module.wait_owned = owned_wait
    class Client:
        def __init__(self, **kw):
            assert kw == dict(trust_env=False, timeout=1)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url):
            assert url == 'http://127.0.0.1:12345/health'
            clock.calls += 1
            value = outcomes[min(clock.calls - 1, len(outcomes) - 1)]
            if isinstance(value, Exception): raise value
            return value
    monkeypatch.setattr(httpx, 'Client', Client)
    return module, child, clock, out


def health():
    return httpx.Response(200, json={'status': 'ok'})


@pytest.mark.parametrize('error', [httpx.ConnectError('synthetic'), httpx.ConnectTimeout('synthetic')])
def test_transient_connect_then_ready(monkeypatch, tmp_path, error):
    module, child, clock, out = harness(monkeypatch, tmp_path, [error, health()])
    assert module.api(SimpleNamespace(config='config.json', output='run')) == 0
    assert clock.calls == 2 and not child.terminated and child.waits == 1
    assert json.loads((out / 'exit.json').read_text())['passed'] is True


def test_persistent_timeout_is_bounded(monkeypatch, tmp_path):
    module, child, clock, out = harness(monkeypatch, tmp_path, [httpx.ConnectTimeout('synthetic')])
    with pytest.raises(ValueError, match='API readiness deadline'):
        module.api(SimpleNamespace(config='config.json', output='run'))
    assert 1 < clock.calls < 100 and clock.value < 22
    assert child.terminated and child.waits == 1
    assert not (out / 'health.json').exists()


def test_child_exits_before_readiness(monkeypatch, tmp_path):
    module, child, clock, out = harness(monkeypatch, tmp_path, [health()], exited=True)
    with pytest.raises(ValueError, match='API exited before readiness'):
        module.api(SimpleNamespace(config='config.json', output='run'))
    assert clock.calls == 0 and not child.terminated and child.waits == 1


@pytest.mark.parametrize('outcome', [httpx.ReadTimeout('synthetic'), RuntimeError('synthetic'),
    httpx.Response(503, json={'status': 'ok'}), httpx.Response(200, json={'status': 'bad'})])
def test_invalid_or_unexpected_never_ready(monkeypatch, tmp_path, outcome):
    module, child, clock, out = harness(monkeypatch, tmp_path, [outcome])
    with pytest.raises((httpx.ReadTimeout, RuntimeError, ValueError)):
        module.api(SimpleNamespace(config='config.json', output='run'))
    assert clock.calls == 1 and child.terminated and child.waits == 1
    assert json.loads((out / 'exit.json').read_text())['passed'] is False


def test_original_head_aborts_timeout_recovery(monkeypatch, tmp_path):
    module, child, clock, out = harness(monkeypatch, tmp_path,
        [httpx.ConnectTimeout('synthetic'), health()], original=True)
    with pytest.raises(httpx.ConnectTimeout):
        module.api(SimpleNamespace(config='config.json', output='run'))
    assert clock.calls == 1 and child.terminated and child.waits == 1
    assert not (out / 'health.json').exists()
