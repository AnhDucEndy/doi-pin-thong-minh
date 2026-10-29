"""P7-A01 real wall-clock fault injection, isolated PG + HTTP API + child worker.

No production clock/TTL changes. A test-only slow evidence read crosses the real
60s deadline while observations remain fresh. Provider setup uses the existing
verified mock transport; the separate Phase7 E2E covers provider/simulators.
"""
from datetime import timedelta
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'services/backend'), str(ROOT/'tests'), str(ROOT/'tools')]
import httpx
from app.application import assets, swaps
from app.application.identity import utcnow
from app.config import Settings, approved_policy
from app.infrastructure.db import Database
from app.seed import demo_id
from app.workers.device import process_one


def child(event_id, report):
    db = Database(Settings.from_env())
    inside = {'deadline':None, 'slept':False}
    original, latest = swaps.physical_context, assets.latest_observation
    evidence_times = []
    def context(session, db, swap, items, receiving, supplying, command=None, issuing=False):
        inside['deadline'] = command['created_at']+timedelta(seconds=swap['policy_snapshot']['physical_step_timeout_seconds'])
        assert utcnow() < inside['deadline'], 'Test must enter custody before deadline'
        try: return original(session, db, swap, items, receiving, supplying, command, issuing)
        finally: inside['deadline'] = None
    def delayed_read(*args, **kwargs):
        result = latest(*args, **kwargs)
        if inside['deadline']:
            evidence_times.extend([result['observed_at'], result['received_at']])
            if not inside['slept']:
                deadline = inside['deadline']
                time.sleep(max(0, (deadline-utcnow()).total_seconds())+.05)
                inside['slept'] = True
        return result
    swaps.physical_context, assets.latest_observation = context, delayed_read
    try:
        with db.sessions.begin() as session:
            assert process_one(session, db, UUID(event_id), approved_policy())
        now = utcnow()
        assert inside['slept'] and evidence_times
        assert all(assets.fresh(t, now, approved_policy()) for t in evidence_times)
        Path(report).write_text(json.dumps({'real_delay':True, 'evidence_still_fresh':True,
            'max_evidence_age_seconds':max((now-t).total_seconds() for t in evidence_times)}), encoding='utf-8')
    finally: db.engine.dispose()


def main(step):
    from conftest import environment
    from smoke_phase4 import wait, fingerprints
    from test_phase4 import row, send, snapshot_packet, telemetry
    from test_phase5 import login
    from test_phase6 import book, consent, outcome
    from test_phase7 import physical, drive
    from test_phase7_deadline import acknowledged, observations, assert_review
    from app.workers import payment
    with socket.socket() as sock:
        assert sock.connect_ex(('127.0.0.1', 8030)) != 0, 'Test port occupied; no service stopped'
    demo = Database(Settings.from_env()); before_demo = fingerprints(demo)
    factory = environment.__wrapped__(); fixture = next(factory)
    db = fixture['seed_db']
    directory = ROOT/'.cache'/('p7-deadline-'+uuid4().hex[:10]); directory.mkdir()
    env = dict(os.environ, DATABASE_SCHEMA=fixture['settings'].schema,
        PYTHONPATH=str(ROOT/'services/backend'), PYTHONIOENCODING='utf-8')
    processes = []
    try:
        with (directory/'api.log').open('w', encoding='utf-8') as log:
            api = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:create_app', '--factory',
                '--host','127.0.0.1','--port','8030','--no-access-log'], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            processes.append(api)
            wait(lambda:httpx.get('http://127.0.0.1:8030/health', timeout=1).status_code == 200, 'API ready')
            with httpx.Client(base_url='http://127.0.0.1:8030', timeout=15) as http:
                http.app = SimpleNamespace(state=SimpleNamespace(db=db))
                actor = login(http, fixture); swap = book(http, fixture, actor, db)
                assert consent(http, actor, swap).status_code == 202
                payment.tick(db, transport=outcome)
                kind, cmd = acknowledged(http, fixture, swap, step)
                # Real elapsed time, no command timestamp rewrite. Keep accepted
                # observations live via the normal authenticated event inbox.
                while (utcnow()-cmd['created_at']).total_seconds() < 53:
                    dev = row(http, 'devices', demo_id('device:S01'))
                    snapshot = snapshot_packet(str(dev['boot_id']), dev['last_seq']+1)
                    if step == 'pickup':
                        old = row(http, 'batteries', UUID(swap['old_battery_id']))
                        slot = snapshot['payload']['slots'][0]
                        slot.update(present=True, observed_serial=old['serial'])
                    assert send(http, fixture, snapshot).status_code == 202
                    assert send(http, fixture, telemetry(str(dev['boot_id']), dev['last_seq']+2)).status_code == 202
                    time.sleep(1)
                before = row(http, 'batteries', UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id']))
                p, _ = observations(http, swap)
                physical(http, fixture, swap, kind, ('open','presence'))
                closing = physical(http, fixture, swap, kind, ('close',), process_it=False)[0]
                report = directory/'timing.json'
                with (directory/'worker.log').open('w', encoding='utf-8') as log_worker:
                    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker',
                        closing['event_id'], '--report', str(report)], cwd=ROOT, env=env,
                        stdout=log_worker, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                    processes.append(proc); assert proc.wait(timeout=25) == 0, 'See retained worker.log'
                timing = json.loads(report.read_text())
                assert (utcnow()-cmd['created_at']).total_seconds() >= 60
                assert row(http, 'device_commands', cmd['id'])['state'] == 'OBSERVED'
                assert_review(http, swap, step, before, p)
                assert http.get('/v1/swaps/'+swap['id'], headers=actor).json()['state'] == 'REVIEW_REQUIRED'
                # A fresh service invocation/replay cannot restart the deadline.
                drive(http, swap['id']); assert send(http, fixture, closing).status_code == 202
                assert_review(http, swap, step, before, p)
                assert fingerprints(demo) == before_demo
                output = {'result':'Passed','step':step,'schema':fixture['settings'].schema,
                    'elapsed_seconds':(utcnow()-cmd['created_at']).total_seconds(), **timing,
                    'HTTP_review':True,'custody_unchanged':True,'holds':3,'payment_unchanged':True,
                    'no_success_audit':True,'no_extra_command':True,'replay_safe':True,
                    'demo_unchanged':True,'logs':str(directory.relative_to(ROOT))}
                (ROOT/'docs/PHASE7_TESTS/DEADLINE_E2E.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
                print(json.dumps(output, indent=2))
    finally:
        for proc in reversed(processes):
            if proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
        try: next(factory)
        except StopIteration: pass
        demo.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--step', choices=['return','pickup'], default='return')
    parser.add_argument('--worker'); parser.add_argument('--report')
    args = parser.parse_args()
    if args.worker: child(args.worker, args.report)
    else: main(args.step)
