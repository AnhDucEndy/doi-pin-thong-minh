"""Real HTTP/payment-worker/private-provider E2E, isolated PostgreSQL and ledger only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from uuid import UUID, uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'services/backend'),str(ROOT/'tests')]
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.config import Settings, approved_policy
from app.infrastructure.db import Database
from app.main import create_app
from app.application.identity import utcnow
from app.application import reservations
from app.seed import demo_id
from test_phase5 import prepare, login, qr, verify, reserve
from test_phase6 import consent, payment, callback, counts
from conftest import environment
from smoke_phase4 import fingerprints, wait
import httpx


def run_scenario(scenario, checks, serve=False):
    for port in (8010,8011,8012):
        def available():
            with socket.socket() as probe:
                return probe.connect_ex(('127.0.0.1',port)) != 0
        # Windows may briefly retain the previous scenario's listener after
        # process exit; wait for closure rather than stopping an unknown process.
        wait(available, f'Isolated Phase6 port {port} occupied', 15)
    factory=environment.__wrapped__();fixture=next(factory)
    directory=ROOT/'.cache'/('phase6_e2e_'+uuid4().hex[:10]);directory.mkdir(parents=True)
    ledger=ROOT/'.local'/directory.name/'payment.sqlite3'
    env=dict(os.environ,DATABASE_SCHEMA=fixture['settings'].schema, PYTHONPATH=str(ROOT/'services/backend'),
        PYTHONIOENCODING='utf-8',PAYMENT_SERVICE_KEY=secrets.token_urlsafe(32),PAYMENT_CALLBACK_KEY=secrets.token_urlsafe(32),
        PAYMENT_MOCK_URL='http://127.0.0.1:8012',PAYMENT_LEDGER_PATH=str(ledger),
        PAYMENT_CALLBACK_URL='http://127.0.0.1:8010/v1/payment-events')
    processes=[];logs=[]
    def launch(args,name):
        log=(directory/(name+'.log')).open('w',encoding='utf-8');logs.append(log)
        p=subprocess.Popen([sys.executable,*args],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW);processes.append(p);return p
    try:
        for port in (8010,8011):
            launch(['-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(port),
                '--no-access-log','--no-proxy-headers'],f'api-{port}')
            wait(lambda:httpx.get(f'http://127.0.0.1:{port}/health',timeout=1).status_code==200,'Phase6 API ready')
        provider_scenario='delayed' if scenario=='success' else scenario
        launch(['-m','simulators.payment.main','--port','8012','--scenario',provider_scenario],'provider')
        wait(lambda:httpx.get('http://127.0.0.1:8012/mock/v1/charges/'+str(uuid4()),headers={
            'X-Service-Key':env['PAYMENT_SERVICE_KEY']},timeout=1).status_code==200,'Provider ready')
        # Genuine inbox+worker accepted evidence, scoped to fixture. No fabricated accepted flag.
        with TestClient(create_app(fixture['settings'])) as setup:prepare(setup,fixture,fixture['seed_db'])
        with httpx.Client(base_url='http://127.0.0.1:8010',timeout=15) as first, httpx.Client(base_url='http://127.0.0.1:8011',timeout=15) as second:
            actor=login(first,fixture);code=qr(first,actor);verified=verify(first,fixture,code['qr_token'])
            assert verified.status_code==201
            booked=reserve(first,actor,verified.json());assert booked.status_code==200 and booked.json()['state']=='RESERVED'
            swap=booked.json();key=uuid4()
            # Competing independent processes and different HTTP keys, same aggregate.
            with ThreadPoolExecutor(max_workers=2) as pool:
                a=pool.submit(consent,first,actor,swap,key);b=pool.submit(consent,second,actor,swap)
                results=[a.result(),b.result()]
            assert sorted(r.status_code for r in results)==[202,409]
            winner=first if results[0].status_code==202 else second
            accepted=next(r.json() for r in results if r.status_code==202)
            assert counts(fixture['seed_db'])['payments']==1
            checks.append(scenario+': two Backend processes create exactly one intent/outbox')
            launch(['-m','app.workers.payment'],'payment-worker')
            if scenario=='success':
                # Provider first returns PENDING. Its independent callback sender
                # delivers the final result before the 30-second query deadline.
                launch(['-m','simulators.payment.callbacks'],'callback-loop')
            expected='FAILED' if scenario=='failure' else 'UNKNOWN' if scenario=='lost-response' else 'SUCCEEDED'
            wait(lambda:payment(first,actor,swap)['state']==expected,'Initial payment outcome',20)
            if scenario=='lost-response':
                # Restart the worker after the provider committed and the response was lost.
                proc=processes[-1];proc.terminate();proc.wait(timeout=10)
                assert counts(fixture['seed_db'])['holds']==3
                # No active simulator refreshes this fixture: query must not treat
                # stale physical/BMS evidence as permission to proceed.
                print('Waiting approved 30-second payment timeout with worker restart',flush=True)
                launch(['-m','app.workers.payment'],'payment-worker-restarted')
                wait(lambda:payment(first,actor,swap)['state']=='SUCCEEDED','Query same provider key after restart',40)
                current=first.get('/v1/swaps/'+swap['id'],headers=actor).json()
                # With deliberately stale fixture BMS/door, paid intent stays in REVIEW_REQUIRED.
                assert current['state']=='REVIEW_REQUIRED' and counts(fixture['seed_db'])['holds']==3
                checks.append('lost-response: worker restart queries same charge, keeps stale assets under review')
            current=first.get('/v1/swaps/'+swap['id'],headers=actor).json();p=payment(first,actor,swap)
            if scenario=='success':
                assert p['state']=='SUCCEEDED' and current['state']=='AWAITING_RETURN'
                with fixture['seed_db'].sessions() as s:
                    t=fixture['seed_db'].table('payment_events')
                    assert s.scalar(select(t.c.processed_at)) is not None
                    t=fixture['seed_db'].table('outbox_messages')
                    assert s.scalar(select(t.c.attempts))==1
                checks.append('success: final state driven by verified HTTP callback before any reconciliation query')
            elif scenario=='failure':assert p['state']=='FAILED' and current['state']=='CANCELLED' and counts(fixture['seed_db'])['holds']==0
            assert consent(first,actor,swap).status_code==409
            assert counts(fixture['seed_db'])['device_commands']==0
            checks.append(scenario+': verified outcome and swap transition, no actuator or second charge')
            sender=launch(['-m','simulators.payment.callbacks','--once'],'callbacks')
            assert sender.wait(timeout=15)==0
            wait(lambda:counts(fixture['seed_db'])['payment_events']==1,'Authenticated callback inbox')
            def processed():
                with fixture['seed_db'].sessions() as s:
                    t=fixture['seed_db'].table('payment_events')
                    return bool(s.scalar(select(t.c.processed_at)))
            wait(processed,'Callback processed atomically')
            sender=launch(['-m','simulators.payment.callbacks','--once'],'callbacks-restarted')
            assert sender.wait(timeout=15)==0
            assert counts(fixture['seed_db'])['payment_events']==1
            assert payment(first,actor,swap)['state']==p['state']
            checks.append(scenario+': real authenticated callback delivery, inbox processed, restart no duplicate')
            # Real SQL provider ledger: one charge survives worker/process retries.
            import sqlite3
            with sqlite3.connect(ledger) as conn:assert conn.execute('SELECT COUNT(*) FROM charges').fetchone()[0]==1
            if serve and scenario=='success':
                data={'api':'http://127.0.0.1:8010','schema':fixture['settings'].schema,
                      'passwords':fixture['passwords'],'keys':fixture['keys'],'swap_id':swap['id']}
                (directory/'connection.json').write_text(json.dumps(data),encoding='utf-8')
                print('Browser fixture ready: '+str(directory.relative_to(ROOT)),flush=True)
                while not (directory/'STOP').exists():time.sleep(.5)
            return {'scenario':scenario,'schema':fixture['settings'].schema,'ledger':str(ledger.relative_to(ROOT)),
                    'logs':str(directory.relative_to(ROOT)),'payment_state':p['state'],'swap_state':current['state']}
    finally:
        for p in reversed(processes):
            if p.poll() is None:p.terminate();p.wait(timeout=10)
        for f in logs:f.close()
        try:next(factory)
        except StopIteration:pass


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true');args=parser.parse_args()
    demo=Database(Settings.from_env());checks=[]
    # Include all financial rows in the unchanged-demo check as well as previous phase assets.
    def fingerprint():
        from hashlib import sha256
        with demo.sessions() as s:
            finance={n:sha256(json.dumps([dict(r) for r in s.execute(select(demo.table(n)).order_by(demo.table(n).c.id)).mappings()],default=str,sort_keys=True).encode()).hexdigest()
                for n in ('payments','payment_events','outbox_messages')}
        return {**fingerprints(demo),**finance}
    before=fingerprint()
    try:
        scenarios=[run_scenario(s,checks,args.serve) for s in ('failure','lost-response','success')]
        assert fingerprint()==before;checks.append('Primary demo financial/assets/evidence unchanged')
        output=ROOT/'docs/PHASE6_TESTS';output.mkdir(exist_ok=True)
        (output/'E2E_FINAL_RESULTS.json').write_text(json.dumps({'result':'Passed','checks':checks,
            'scenarios':scenarios,'production_modified':False,'test_schemas_and_ledgers_retained':True},indent=2)+'\n',encoding='utf-8')
        print(f'{len(checks)} Phase6 real-process E2E checks Passed; credentials omitted',flush=True)
    finally:demo.engine.dispose()


if __name__=='__main__':main()
