"""Real-process receipt-conflict recovery, isolated PostgreSQL and provider ledger."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'services/backend'), str(ROOT/'tests'), str(ROOT/'tools')]
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
import secrets
import socket
import sqlite3
import subprocess
from uuid import UUID, uuid4
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from app.config import Settings
from app.infrastructure.db import Database
from app.main import create_app
from app.application.identity import utcnow
from conftest import environment
from test_phase5 import prepare, verified, reserve, login
from test_phase6 import consent, payment, counts
from test_phase6_blocker_fix import audit_count
from smoke_phase4 import fingerprints, wait


def main():
    for port in (8010, 8011, 8012):
        with socket.socket() as s:
            assert s.connect_ex(('127.0.0.1', port)) != 0, 'Test port occupied; do not stop another process'
    demo = Database(Settings.from_env())
    def fingerprint():
        from hashlib import sha256
        with demo.sessions() as s:
            finance = {n: sha256(json.dumps([dict(r) for r in s.execute(select(demo.table(n)).order_by(demo.table(n).c.id)).mappings()],
                default=str, sort_keys=True).encode()).hexdigest() for n in ('payments','payment_events','outbox_messages')}
        return {**fingerprints(demo), **finance}
    before = fingerprint()
    factory = environment.__wrapped__(); fixture = next(factory)
    directory = ROOT/'.cache'/('phase6_fix_e2e_'+uuid4().hex[:10]); directory.mkdir()
    ledger = ROOT/'.local'/directory.name/'payment.sqlite3'
    env = dict(os.environ, DATABASE_SCHEMA=fixture['settings'].schema,
        PYTHONPATH=str(ROOT/'services/backend'), PYTHONIOENCODING='utf-8',
        PAYMENT_SERVICE_KEY=secrets.token_urlsafe(32), PAYMENT_CALLBACK_KEY=secrets.token_urlsafe(32),
        PAYMENT_MOCK_URL='http://127.0.0.1:8012', PAYMENT_LEDGER_PATH=str(ledger),
        PAYMENT_CALLBACK_URL='http://127.0.0.1:8010/v1/payment-events')
    processes = []; logs = []; checks = []
    def launch(args, name):
        log = (directory/(name+'.log')).open('w', encoding='utf-8'); logs.append(log)
        process = subprocess.Popen([sys.executable, *args], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW); processes.append(process); return process
    def provider_ready():
        return httpx.get('http://127.0.0.1:8012/mock/v1/charges/'+str(uuid4()),
            headers={'X-Service-Key':env['PAYMENT_SERVICE_KEY']}, timeout=1).status_code == 200
    try:
        for port in (8010,8011):
            launch(['-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(port),
                    '--no-access-log','--no-proxy-headers'],f'api-{port}')
            wait(lambda: httpx.get(f'http://127.0.0.1:{port}/health',timeout=1).status_code==200,'API ready')
        provider = launch(['-m','simulators.payment.main','--port','8012','--scenario','failure'],'provider-failure')
        wait(provider_ready,'Provider ready')
        with httpx.Client(base_url='http://127.0.0.1:8010', timeout=15) as http:
            actor = login(http, fixture)
            def booking():
                with TestClient(create_app(fixture['settings'])) as setup: prepare(setup,fixture,fixture['seed_db'])
                result = reserve(http,actor,verified(http,fixture,actor)); assert result.json()['state']=='RESERVED'
                swap=result.json(); assert consent(http,actor,swap).status_code==202; return swap
            first = booking()
            assert launch(['-m','app.workers.payment','--once'],'worker-first').wait(timeout=20)==0
            a=payment(http,actor,first); assert a['state']=='FAILED'
            provider.terminate(); provider.wait(timeout=10)
            def port_free():
                with socket.socket() as s: return s.connect_ex(('127.0.0.1',8012))!=0
            wait(port_free,'Provider old listener closes',15)
            launch(['-m','simulators.payment.main','--port','8012','--scenario','success'],'provider-restarted')
            wait(provider_ready,'Provider restarted with same ledger')
            second=booking(); b=payment(http,actor,second); db=fixture['seed_db']; box=db.table('outbox_messages')
            with db.sessions.begin() as s:
                payload=dict(s.execute(select(box.c.payload).where(box.c.aggregate_id==UUID(b['id']))).scalar_one())
                # Controlled test schedule: observe callback disposition before
                # automatic reconciliation can consume the valid provider result.
                s.execute(update(box).where(box.c.aggregate_id==UUID(b['id'])).values(next_attempt_at=utcnow()+timedelta(minutes=5)))
            charge=httpx.post('http://127.0.0.1:8012/mock/v1/charges',json=payload,headers={
                'X-Service-Key':env['PAYMENT_SERVICE_KEY'],'Idempotency-Key':b['provider_key']},timeout=5)
            assert charge.status_code==202 and charge.json()['result']=='SUCCEEDED'
            checks.append('Provider restarted with durable ledger; A failed and B charged once with distinct receipts')
            event_id=uuid4().hex
            bad={'provider_event_id':event_id,'payment_id':b['id'],'provider_key':b['provider_key'],
                'provider_reference':a['provider_reference'],'result':'SUCCEEDED','amount_minor':9000,'currency':'VND'}
            response=http.post('/v1/payment-events',json=bad,headers={'X-Payment-Key':env['PAYMENT_CALLBACK_KEY']})
            assert response.status_code==202
            for attempt in range(2):
                assert launch(['-m','app.workers.payment','--once'],f'worker-conflict-{attempt}').wait(timeout=20)==0
            assert payment(http,actor,second)['state']=='UNKNOWN'
            assert http.get('/v1/swaps/'+second['id'],headers=actor).json()['state']=='REVIEW_REQUIRED'
            assert counts(db)['holds']==3 and counts(db)['device_commands']==0
            assert audit_count(db,b['id'],'PAYMENT_RESULT_REJECTED')==1
            checks.append('Conflicting callback durably rejected; two real worker restarts exit0, UNKNOWN/review retains three holds')
            assert http.post('/v1/payment-events',json=bad,headers={'X-Payment-Key':env['PAYMENT_CALLBACK_KEY']}).json()['duplicate']
            assert launch(['-m','simulators.payment.callbacks','--once'],'real-callback-sender').wait(timeout=20)==0
            workers=[launch(['-m','app.workers.payment','--once'],f'worker-valid-{n}') for n in range(2)]
            assert all(p.wait(timeout=20)==0 for p in workers)
            assert payment(http,actor,second)['state']=='SUCCEEDED'
            assert audit_count(db,b['id'],'PAYMENT_SUCCEEDED')==1
            assert audit_count(db,b['id'],'PAYMENT_RESULT_REJECTED')==1
            with db.sessions() as s:
                assert all(s.scalars(select(db.table('payment_events').c.processed_at)))
            checks.append('Authentic callback sender delivers B success behind conflict; two workers settle exactly once')
            with db.sessions.begin() as s:
                s.execute(update(box).where(box.c.aggregate_id==UUID(b['id'])).values(next_attempt_at=utcnow()))
            assert launch(['-m','app.workers.payment','--once'],'worker-outbox-final').wait(timeout=20)==0
            assert launch(['-m','simulators.payment.callbacks','--once'],'callback-restart').wait(timeout=20)==0
            with sqlite3.connect(ledger) as s:
                assert s.execute('SELECT COUNT(*) FROM charges').fetchone()[0]==2
                assert s.execute('SELECT COUNT(DISTINCT reference) FROM charges').fetchone()[0]==2
            assert counts(db)['holds']==3 and counts(db)['device_commands']==0
            with db.sessions() as s:
                assert s.scalar(select(box.c.delivered_at).where(box.c.aggregate_id==UUID(b['id']))) is not None
            checks.append('Terminal outbox acknowledged; ledger two intents/two charges, zero double charge or actuator effects')
        assert fingerprint()==before; checks.append('Primary demo fingerprints unchanged')
        out=ROOT/'docs/PHASE6_FIX'; out.mkdir(exist_ok=True)
        (out/'RECEIPT_E2E.json').write_text(json.dumps({'result':'Passed','checks':checks,'schema':fixture['settings'].schema,
            'ledger':str(ledger.relative_to(ROOT)),'logs':str(directory.relative_to(ROOT))},indent=2)+'\n',encoding='utf-8')
        print(f'{len(checks)} receipt-conflict real-process E2E checks Passed')
    finally:
        for p in reversed(processes):
            if p.poll() is None: p.terminate(); p.wait(timeout=10)
        for log in logs: log.close()
        try: next(factory)
        except StopIteration: pass
        demo.engine.dispose()


if __name__=='__main__': main()
