"""Real-process AD-02b checks; fresh PostgreSQL schemas and durable test ledgers."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'services/backend'), str(ROOT/'tests'), str(ROOT/'tools')]
import httpx
from sqlalchemy import select, update
from app.config import Settings
from app.infrastructure.db import Database
from app.seed import demo_id
from conftest import environment
from test_phase5 import login, qr, verify, reserve
from test_phase6 import consent, counts
from smoke_phase4 import fingerprints, wait


def scenario(mode, serve=False):
    for port in (8020, 8021, 8022):
        def available():
            with socket.socket() as probe:
                return probe.connect_ex(('127.0.0.1', port)) != 0
        wait(available, f'Test port {port} occupied; no existing service was stopped', 15)
    factory = environment.__wrapped__(); env_fixture = next(factory)
    db = env_fixture['seed_db']
    run = 'phase7_' + uuid4().hex[:10]
    directory = ROOT/'.cache'/run; directory.mkdir()
    ledger = ROOT/'.local'/run
    # Create the shared parent before launching both Windows simulator processes.
    # Keep each ledger separate; do not relax Simulator's workspace boundary.
    (ledger/'devices').mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, DATABASE_SCHEMA=env_fixture['settings'].schema,
        PYTHONPATH=str(ROOT/'services/backend'), PYTHONIOENCODING='utf-8',
        PAYMENT_SERVICE_KEY=secrets.token_urlsafe(32), PAYMENT_CALLBACK_KEY=secrets.token_urlsafe(32),
        PAYMENT_MOCK_URL='http://127.0.0.1:8022', PAYMENT_LEDGER_PATH=str(ledger/'payment.sqlite3'),
        **{'DEMO_DEVICE_KEY_'+code:key for code, key in env_fixture['keys'].items()})
    processes = []; logs = []; checks = []

    def launch(args, name):
        log = (directory/(name+'.log')).open('w', encoding='utf-8'); logs.append(log)
        proc = subprocess.Popen([sys.executable, *args], cwd=ROOT, env=env, stdout=log,
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(proc); return proc

    def row(name, identity):
        with db.sessions() as session:
            table = db.table(name)
            return dict(session.execute(select(table).where(table.c.id == identity)).mappings().one())

    try:
        for port in (8020, 8021):
            launch(['-m', 'uvicorn', 'app.main:create_app', '--factory', '--host', '127.0.0.1',
                '--port', str(port), '--no-access-log'], 'api-'+str(port))
            wait(lambda:httpx.get(f'http://127.0.0.1:{port}/health', timeout=1).status_code == 200, 'API ready')
        worker = launch(['-m', 'app.workers.device'], 'device-worker')
        launch(['-m', 'simulators.payment.main', '--port', '8022', '--scenario', 'success'], 'provider')
        launch(['-m', 'app.workers.payment'], 'payment-worker')
        for code in ('S01', 'S02'):
            launch(['-m', 'simulators.device.main', '--station', code, '--url', 'http://127.0.0.1:8020',
                '--ledger-dir', str(ledger/'devices'), '--scenario', mode if code == 'S01' else 'normal'], code)
        wait(lambda:row('devices', demo_id('device:S01'))['last_received_at'] is not None, 'Device online', 30)
        def measured():
            with db.sessions() as session:
                t = db.table('battery_telemetry')
                return session.scalar(select(t.c.id).where(t.c.battery_id == demo_id('S01:battery:2'),
                    t.c.quality_ok.is_(True)).limit(1)) is not None
        wait(measured, 'Accepted BMS', 20)
        # Only fixture activation; no fabricated physical evidence or demo writes.
        with db.sessions.begin() as session:
            t = db.table('compartments')
            session.execute(update(t).where(t.c.id.in_([demo_id('S01:slot:1'), demo_id('S01:slot:2')]))
                .values(service_state='ACTIVE'))
            t = db.table('batteries')
            session.execute(update(t).where(t.c.id == demo_id('S01:battery:2')).values(lifecycle='IN_SERVICE'))
        with httpx.Client(base_url='http://127.0.0.1:8020', timeout=15) as first, httpx.Client(
                base_url='http://127.0.0.1:8021', timeout=15) as second:
            actor = login(first, env_fixture)
            verified = verify(first, env_fixture, qr(first, actor)['qr_token'])
            assert verified.status_code == 201
            booked = reserve(first, actor, verified.json()); assert booked.status_code == 200
            swap = booked.json(); identity = UUID(swap['id'])
            if serve:
                (directory/'connection.json').write_text(json.dumps({'passwords':env_fixture['passwords'],
                    'schema':env_fixture['settings'].schema,'swap_id':swap['id']}),encoding='utf-8')
                print('Browser fixture login ready: '+str(directory.relative_to(ROOT)),flush=True)
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(consent, first, actor, swap); b = pool.submit(consent, second, actor, swap)
                assert sorted([a.result().status_code, b.result().status_code]) == [202, 409]
            checks.append('two HTTP processes: one consent/intent')
            expected = 'COMPLETED' if mode == 'physical' else 'REVIEW_REQUIRED'
            if mode == 'crash-after-ledger':
                wait(lambda:counts(db)['device_commands'] == 1, 'Command dispatched', 20)
                worker.terminate(); worker.wait(timeout=10)
                launch(['-m', 'app.workers.device'], 'device-worker-restarted')
                checks.append('worker restart after command creation')
            wait(lambda:row('swap_transactions', identity)['state'] == expected, 'Swap '+expected, 85)
            current = row('swap_transactions', identity)
            old = row('batteries', UUID(swap['old_battery_id']))
            new = row('batteries', UUID(swap['new_battery_id']))
            c = counts(db)
            assert c['payments'] == 1
            with db.sessions() as session:
                p = db.table('payments')
                assert session.scalar(select(p.c.state).where(p.c.swap_id == identity)) == 'SUCCEEDED'
                commands = list(session.execute(select(db.table('device_commands'))).mappings())
                audits = list(session.scalars(select(db.table('audit_events').c.action)))
            if mode == 'physical':
                assert old['compartment_id'] == UUID(swap['return_compartment_id']) and old['holder_user_id'] is None
                assert new['holder_user_id'] == current['customer_id'] and new['compartment_id'] is None
                assert c['holds'] == 0 and len(commands) == 2 and all(x['state']=='OBSERVED' for x in commands)
                assert audits.count('SWAP_COMPLETED') == 1 and audits.count('SWAP_RETURN_ACCEPTED') == 1
            else:
                assert c['holds'] == 3 and len(commands) == 1 and current['closed_at'] is None
                assert old['location_kind'] == 'CUSTOMER' and new['location_kind'] == 'COMPARTMENT'
                assert 'SWAP_COMPLETED' not in audits
            checks.append('PostgreSQL custody, holds, commands and audit verified')
            with sqlite3.connect(ledger/'payment.sqlite3') as conn:
                assert conn.execute('SELECT COUNT(*) FROM charges').fetchone()[0] == 1
            with sqlite3.connect(ledger/'devices/S01.sqlite3') as conn:
                effects = [r[0] for r in conn.execute('SELECT effects FROM commands')]
                assert len(effects) == len(commands) and max(effects) <= 1
                if mode == 'physical': assert effects == [1, 1]
            checks.append('provider one charge; persistent command ledger at most one effect per command')
            assert first.get('/v1/swaps/'+swap['id'], headers=actor).json()['state'] == expected
            checks.append('authenticated HTTP final state')
            if serve:
                (directory/'connection.json').write_text(json.dumps({'passwords':env_fixture['passwords'],
                    'schema':env_fixture['settings'].schema,'swap_id':swap['id']}),encoding='utf-8')
                print('Browser fixture ready: '+str(directory.relative_to(ROOT)),flush=True)
                while not (directory/'STOP').exists():time.sleep(.5)
        return {'scenario': mode, 'checks': checks, 'schema': env_fixture['settings'].schema,
            'ledger': str(ledger.relative_to(ROOT)), 'logs': str(directory.relative_to(ROOT))}
    finally:
        for proc in reversed(processes):
            if proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
        for log in logs: log.close()
        try: next(factory)
        except StopIteration: pass


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--scenario',choices=['physical','ack-only','wrong-return','crash-after-ledger'])
    args=parser.parse_args()
    demo = Database(Settings.from_env())
    def fingerprint():
        with demo.sessions() as session:
            extra={name:hashlib.sha256(json.dumps([dict(row) for row in session.execute(
                select(demo.table(name)).order_by(demo.table(name).c.id)).mappings()],
                default=str,sort_keys=True).encode()).hexdigest() for name in
                ('payments','payment_events','outbox_messages','device_commands','audit_events')}
        return {**fingerprints(demo),**extra}
    before = fingerprint()
    try:
        results = [scenario(mode,args.serve) for mode in ([args.scenario] if args.scenario else
            ('physical', 'ack-only', 'wrong-return', 'crash-after-ledger'))]
        assert fingerprint() == before
        output = ROOT/'docs/PHASE7_TESTS/E2E_RESULTS.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps({'result':'Passed', 'scenarios':results,
            'demo_unchanged': True, 'schema_and_ledgers_retained': True}, indent=2)+'\n', encoding='utf-8')
        print(f'{sum(len(r["checks"]) for r in results)} Phase7 real-process checks Passed; demo unchanged')
    finally: demo.engine.dispose()


if __name__ == '__main__': main()
