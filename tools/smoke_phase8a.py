"""Recovery A: two API processes, device worker, explicit simulator service.

Uses a fresh PostgreSQL schema and fresh workspace ledgers. Retains all evidence.
Only children created by this runner are stopped. No demo mutations.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'services/backend'), str(ROOT/'tests'), str(ROOT/'tools')]
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app
from app.config import Settings
from app.infrastructure.db import Database
from app.application.swaps import review
from app.workers import payment
from conftest import environment
from test_phase5 import login
from test_phase6 import book, consent, outcome
from smoke_phase4 import fingerprints, wait


def main():
    if '--branch' in sys.argv:
        from phase8a_branches import run
        return run(sys.argv[sys.argv.index('--branch')+1])
    handover = '--handover' in sys.argv[1:]
    race_actor = sys.argv[sys.argv.index('--logout-race') + 1] if '--logout-race' in sys.argv else None
    session_order = '--session-order' in sys.argv
    gate = sys.argv[sys.argv.index('--final-gate')+1] if '--final-gate' in sys.argv else None
    if race_actor and race_actor not in ('customer', 'technician'):
        raise ValueError('Expected customer or technician')
    for port in (8030, 8031):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError('Test port occupied; existing process was not stopped')
    demo = Database(Settings.from_env())
    before = fingerprints(demo)
    factory = environment.__wrapped__()
    fixture = next(factory)
    db = fixture['seed_db']
    directory = ROOT/'.cache'/('phase8a_'+uuid4().hex[:12])
    directory.mkdir()
    ledgers = ROOT/'.local'/directory.name
    ledgers.mkdir()
    processes, logs, checks = [], [], []
    env = dict(os.environ, PYTHONPATH=str(ROOT/'services/backend'), PYTHONIOENCODING='utf-8',
        DATABASE_SCHEMA=fixture['settings'].schema,
        **{'DEMO_DEVICE_KEY_'+code: key for code, key in fixture['keys'].items()})
    env['P7_BOUNDARY'] = str(directory/'return-committed.txt')
    if race_actor or session_order or gate:
        env['P8_RACE_DIR'] = str(directory)

    def launch(arguments, name):
        log = (directory/(name+'.log')).open('w', encoding='utf-8')
        logs.append(log)
        process = subprocess.Popen([sys.executable, *arguments], cwd=ROOT, env=env,
            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process)
        return process

    try:
        # Legitimate application services prepare a paid/review fixture. The
        # recovery flow itself, all evidence and settlement use real HTTP.
        with TestClient(create_app(fixture['settings'])) as http:
            customer = login(http, fixture)
            swap = book(http, fixture, customer, db)
            assert consent(http, customer, swap).status_code == 202
            payment.tick(http.app.state.db, transport=outcome)
            with db.sessions.begin() as session:
                table = db.table('swap_transactions')
                current = session.execute(select(table).where(table.c.id == UUID(swap['id']))).mappings().one()
                if not handover:
                    review(session, db, current, 'TEST_SERVICE_INSPECTION')
        for port in (8030, 8031):
            if race_actor or session_order or gate:
                env['PGAPPNAME'] = f'{directory.name}-{port}'
            factory_name = 'tools.phase8a_logout_race:app' if race_actor and port == 8030 else 'app.main:create_app'
            if session_order and port == 8030:
                factory_name = 'tools.phase8a_session_order:app'
            if gate:
                factory_name = 'tools.phase8a_final_races:app'
            launch(['-m', 'uvicorn', factory_name, '--factory', '--host', '127.0.0.1',
                '--port', str(port), '--no-access-log'], 'api-'+str(port))
            wait(lambda: httpx.get(f'http://127.0.0.1:{port}/health', timeout=1).status_code == 200, 'Recovery API ready')
        if race_actor or session_order or gate:
            env.pop('PGAPPNAME')
        if handover:
            worker = launch(['tools/phase7_acceptance_process.py', 'worker'], 'return-boundary-worker')
            physical = launch(['-m', 'simulators.device.main', '--station', 'S01',
                '--url', 'http://127.0.0.1:8030', '--ledger-dir', str(ledgers), '--scenario', 'physical'], 'S01-return')
            wait(lambda: (directory/'return-committed.txt').exists(), 'Real return custody committed', 45)
            for child in (worker, physical):
                child.terminate()
                child.wait(timeout=15)
            with db.sessions.begin() as session:
                table = db.table('swap_transactions')
                current = session.execute(select(table).where(table.c.id == UUID(swap['id']))).mappings().one()
                assert current['state'] == 'RETURN_ACCEPTED'
                review(session, db, current, 'TEST_SERVICE_HANDOVER')
            checks.append('Real simulator return committed before manual recovery')
        worker_module = 'tools.phase8a_final_races' if gate in ('snapshot-first','settle-before-snapshot') else 'app.workers.device'
        launch(['-m', worker_module], 'device-worker')
        with httpx.Client(base_url='http://127.0.0.1:8030', timeout=20) as first, httpx.Client(base_url='http://127.0.0.1:8031', timeout=20) as second:
            tech = login(first, fixture, 'technician')
            customer = login(first, fixture)
            base = f"/v1/swaps/{swap['id']}/recovery"
            case = first.get(base, headers=tech).json()
            response = first.post(base+'/evidence', headers={**tech, 'Idempotency-Key': str(uuid4())}, json={
                'expected_version': case['version'], 'note': 'Service inspection',
                'statement': {'kind': 'BEGIN_OPERATION', 'purpose': 'RETURN_OLD_TO_CUSTOMER' if handover else 'VERIFY_OLD_POSSESSION'}})
            assert response.status_code == 200, response.text
            op = response.json()['active_operation']
            env['SERVICE_TECHNICIAN_TOKEN'] = tech['Authorization'].removeprefix('Bearer ')
            launch(['-m', 'simulators.device.main', '--station', 'S01', '--url', 'http://127.0.0.1:8030',
                '--ledger-dir', str(ledgers), '--service-operation', op['id']], 'S01-service')
            launch(['-m', 'simulators.device.main', '--station', 'S02', '--url', 'http://127.0.0.1:8030',
                '--ledger-dir', str(ledgers)], 'S02')
            def observed():
                result = first.get(base, headers=tech).json()
                return any(a['source_kind'] == 'SIMULATOR' for a in result['active_operation']['attestations'])
            wait(observed, 'Durable service observation', 45)
            case = first.get(base, headers=tech).json()
            item = next(a for a in case['active_operation']['attestations'] if a['source_kind'] == 'SIMULATOR')
            assert item['payload']['result'] == 'OBSERVED'
            if handover:
                # Receipt transport and device inbox processing are independent.
                # Race settlement only after the actual post-effect snapshot is
                # processed; receipt/ACK alone is not current physical proof.
                def projected():
                    events=db.table('device_events')
                    with db.sessions() as current_session:
                        rows=current_session.execute(select(events).where(events.c.kind=='SNAPSHOT',
                            events.c.accepted.is_(True),events.c.processed_at.is_not(None),
                            events.c.observed_at>=datetime.fromisoformat(item['observed_at']))).mappings()
                        return any(any(slot['compartment_id']==str(swap['return_compartment_id'])
                            and slot['present'] is False and slot['door_state']=='CLOSED'
                            for slot in event['payload']['slots']) for event in rows)
                wait(projected,'Actual post-handover snapshot processed before settlement race',10)
            checks.append('Simulator reads durable external model')
            response = first.post(base+'/evidence', headers={**tech, 'Idempotency-Key': str(uuid4())}, json={
                'expected_version': case['version'], 'note': 'Checked actual observation', 'statement': {
                    'kind': 'TECHNICIAN_ATTEST', 'operation_id': op['id'], 'context_hash': op['context_hash'],
                    'actual_serial': item['payload']['actual_serial'], 'observation': 'CONFIRM'}})
            assert response.status_code == 200, response.text
            if gate:
                from phase8a_final_races import verify
                verify(gate, first, second, fixture, base, op, tech, customer, directory, ledgers,
                       demo, before, processes)
                return
            response = first.post(base+'/confirmations', headers={**customer, 'Idempotency-Key': str(uuid4())},
                json={'operation_id': op['id'], 'context_hash': op['context_hash'], 'confirm': True})
            assert response.status_code == 201, response.text
            case = first.get(base, headers=tech).json()
            body = {'expected_version': case['version'], 'operation_id': op['id'], 'resolution_note': 'Manual proof'}
            if session_order:
                from phase8a_session_order import verify_order
                verify_order(first, second, base, body, tech, customer, directory, ledgers,
                             fixture, swap, op, demo, before, [child.pid for child in processes[:2]])
                return
            if race_actor:
                from phase8a_logout_race import verify
                verify(first, second, base, body, tech, customer, race_actor, directory, ledgers,
                       db, fixture['settings'].schema, swap, op, demo, before,
                       [child.pid for child in processes[:2]])
                return
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda http: http.post(base+'/settle',
                    headers={**tech, 'Idempotency-Key': str(uuid4())}, json=body), (first, second)))
            assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
            checks.append('Two Backend processes: one settlement')
            with db.sessions() as session:
                case_table, swap_table, holds, audit = (db.table(t) for t in ('recovery_cases','swap_transactions','resource_reservations','audit_events'))
                identity = UUID(swap['id'])
                assert session.scalar(select(case_table.c.old_pin_settled).where(case_table.c.swap_id == identity)) is True
                assert session.scalar(select(swap_table.c.state).where(swap_table.c.id == identity)) == 'REVIEW_REQUIRED'
                assert len(session.execute(select(holds.c.id).where(holds.c.swap_id == identity, holds.c.released_at.is_(None))).all()) == 3
                assert len(session.execute(select(audit.c.id).where(audit.c.action == 'MANUAL_RECOVERY_SETTLED')).all()) == 1
                pins = db.table('batteries')
                assert session.scalar(select(pins.c.holder_user_id).where(pins.c.id == UUID(swap['old_battery_id']))) == current['customer_id']
            checks.append('Review and three holds retained; one manual audit')
            with sqlite3.connect((ledgers/'S01.sqlite3').as_uri()+'?mode=ro', uri=True) as conn:
                assert conn.execute('SELECT effects FROM service_operations WHERE id=?', (op['id'],)).fetchone()[0] == (1 if handover else 0)
                assert conn.execute('SELECT count(*) FROM commands').fetchone()[0] == (1 if handover else 0)
            checks.append('One handover effect and no extra command' if handover else 'Inspection has zero service/command effects')
            if handover and '--restart-after-settlement' in sys.argv:
                # The effect and settlement are already durable. Kill only the
                # S01 fixture child, restart on the same ledger, retry the exact
                # committed HTTP request and verify its durable identity.
                station_process = processes[3]
                station_process.terminate()
                station_process.wait(timeout=15)
                winner = next(r for r in results if r.status_code == 200)
                prior_boot = db.table('devices')
                with db.sessions() as session:
                    old_boot = session.scalar(select(prior_boot.c.boot_id).where(prior_boot.c.station_id == UUID(swap['station_id'])))
                launch(['-m','simulators.device.main','--station','S01','--url','http://127.0.0.1:8030',
                        '--ledger-dir',str(ledgers),'--service-operation',op['id']], 'S01-after-settlement-restart')
                def rebooted():
                    with db.sessions() as session:
                        return session.scalar(select(prior_boot.c.boot_id).where(
                            prior_boot.c.station_id == UUID(swap['station_id']))) != old_boot
                wait(rebooted,'Actual simulator reboot after committed return',20)
                replay=second.post(base+'/settle',headers={**tech,'Idempotency-Key':winner.request.headers['Idempotency-Key']},json=body)
                assert replay.status_code==200 and replay.json()==winner.json(), replay.text
                with sqlite3.connect((ledgers/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                    assert conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
                with db.sessions() as session:
                    assert session.scalar(select(db.table('audit_events').c.id).where(
                        db.table('audit_events').c.action=='MANUAL_RECOVERY_SETTLED').limit(1))
                    assert len(session.execute(select(db.table('audit_events').c.id).where(
                        db.table('audit_events').c.action=='MANUAL_RECOVERY_SETTLED')).all())==1
                checks.append('Actual simulator restart and exact committed HTTP retry retain one effect and audit')
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
        for log in logs:
            log.close()
        try:
            next(factory)
        except StopIteration:
            pass
    assert fingerprints(demo) == before, 'Demo fingerprint changed'
    demo.engine.dispose()
    checks.append('Demo fingerprint unchanged')
    report = {'branch': 'B' if handover else 'A', 'checks': checks, 'passed': len(checks), 'schema': fixture['settings'].schema,
              'runtime': str(directory.relative_to(ROOT)), 'ledger': str(ledgers.relative_to(ROOT))}
    (ROOT/'docs/PHASE8A_E2E.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
