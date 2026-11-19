"""Decision-boundary probes. Each test states its actual concurrency layer."""
from copy import deepcopy
import json
from uuid import uuid4

from sqlalchemy import select

from test_phase1 import headers
from test_phase8b_b1b_refund import eligible
from test_phase8b_b1b_no_delivery import facts


def test_accepted_uncertainty_after_certificate_blocks_first_intent(client,environment,auth,tmp_path):
    """Sequential ordering probe, not a two-OS race.

    An actual cached-body conflict makes the Simulator emit UNKNOWN without
    re-executing an effect. The terminal command row stays REJECTED historically;
    0.3 must additionally consider this newly accepted conflicting source.
    """
    admin,swap,sim,customer,tech,cert=eligible(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap)
        cached=json.loads(sim.conn.execute('SELECT body FROM commands').fetchone()[0])
        conflicting=deepcopy(cached)
        conflicting['payload']['expected_serial']='CACHED-CONTEXT-MISMATCH'
        assert sim.handle(conflicting)=='UNKNOWN'
        receipts=sim.flush();sim.settle(receipts)
        payment=before['payments'][0]
        response=client.post('/v1/payments/'+str(payment['id'])+'/refund',headers=headers(admin),json={
            'expected_version':payment['version'],'reason':'New accepted uncertainty must block intent'})
        assert response.status_code in (409,422)
        assert facts(client,swap)==before
        assert sim.conn.execute('SELECT sum(effects) FROM commands').fetchone()[0]==0
        db=client.app.state.db
        with db.sessions() as s:
            assert not list(s.scalars(select(db.table('refunds').c.id)))
    finally:sim.close()


import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from time import monotonic
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine,insert,text
from app.application.identity import utcnow
from app.application.assets import station_lock
from app.domain.identity import digest
from app.main import create_app
from app.config import ROOT
from pathlib import Path
from app.seed import demo_id
from test_phase5 import login,race_environment
from test_phase8b_b1b_no_delivery import physical_review,begin,inspect,reference
from test_phase8b_b1b_certificate import decide


@pytest.mark.parametrize('expiring',['caller','customer_witness'])
def test_native_session_expiry_after_observed_station_wait_has_no_certificate(race_environment,tmp_path,expiring):
    """Native separate PG connections, same OS. No historic timestamp edits."""
    env=race_environment;db=env['seed_db']
    observer_engine=create_engine(os.environ['DATABASE_ADMIN_URL'],hide_parameters=True,
        connect_args={'options':'-cdefault_transaction_read_only=on'})
    with TestClient(create_app(env['settings'])) as http:
        auth=lambda name:login(http,env,name)
        swap,sim,customer,tech=physical_review(http,env,auth,tmp_path)
        try:
            secret=secrets.token_urlsafe(48);expiry=utcnow()+timedelta(seconds=8)
            principal='technician' if expiring=='caller' else 'customer'
            with db.sessions.begin() as s:
                s.execute(insert(db.table('auth_sessions')).values(id=uuid4(),user_id=demo_id(principal),
                    token_hash=digest(secret),expires_at=expiry))
            short={'Authorization':'Bearer '+secret}
            assert http.get('/v1/me',headers=short).status_code==200
            begin(http,swap,tech);_,packet,accepted=inspect(http,env,sim)
            url='/v1/swaps/'+str(swap['id'])+'/recovery';case=http.get(url,headers=tech).json();ref=reference(case,accepted)
            response=http.post(url+'/evidence',headers=headers(tech),json={'protocol_version':'0.3',
                'expected_version':case['version'],'note':'Witness current actual model',
                'statement':{**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':packet['actual_serial'],'observation':'CONFIRM'}})
            assert response.status_code==200,response.json().get('code')
            response=http.post(url+'/confirmations',headers=headers(short if expiring=='customer_witness' else customer),
                               json={**ref,'confirm':True})
            assert response.status_code==201,response.json().get('code')
            case=http.get(url,headers=tech).json();before=facts(http,swap)
            deadline=monotonic()+9
            while (expiry-utcnow()).total_seconds()>2 and monotonic()<deadline:Event().wait(.02)
            assert utcnow()<expiry
            body={'protocol_version':'0.3','expected_version':case['version'],'note':'Recheck after actual lock wait',
                  'statement':{**ref,'kind':'VERIFY_NO_DELIVERY_DECIDE'}}
            with db.sessions() as held,observer_engine.connect().execution_options(isolation_level='AUTOCOMMIT') as observer,ThreadPoolExecutor(max_workers=1) as pool:
                station_lock(held,db,demo_id('S01'));holder=held.scalar(text('select pg_backend_pid()'))
                pending=pool.submit(http.post,url+'/evidence',headers=headers(short if expiring=='caller' else tech),json=body)
                diagnostic=[];until=monotonic()+1
                try:
                    while monotonic()<until:
                        diagnostic=[dict(r) for r in observer.execute(text(
                            'select pid,wait_event_type,pg_blocking_pids(pid) blockers from pg_stat_activity where :holder=any(pg_blocking_pids(pid))'),{'holder':holder}).mappings()]
                        if diagnostic:break
                        Event().wait(.02)
                    assert diagnostic and all(r['pid']!=holder and r['wait_event_type']=='Lock' for r in diagnostic)
                    Event().wait(max(0,(expiry-utcnow()).total_seconds())+.03)
                finally:held.rollback()
                result=pending.result(timeout=10)
            assert (result.status_code,result.json()['code'])==(401,'SESSION_REVOKED')
            assert http.get(url,headers=tech).json()==case and facts(http,swap)==before
            (ROOT/'docs/PHASE8B_TESTS'/('b1b_expiry_'+expiring+'_'+uuid4().hex+'.json')).write_text(json.dumps({
                'layer':'native PostgreSQL connections / same OS TestClient','pytest_os_pid':os.getpid(),
                'schema':env['settings'].schema,'holder_pg_pid':holder,'waiters':diagnostic,
                'session_expired_at':expiry.isoformat(),'http_status':result.status_code,
                'business_code':result.json()['code'],'protected_facts_unchanged':True},indent=2),encoding='utf8')
            with db.sessions() as s:
                assert not list(s.scalars(select(db.table('refund_eligibility_certificates').c.id)))
                audit=db.table('audit_events')
                assert not list(s.scalars(select(audit.c.id).where(audit.c.action=='ND_CERTIFICATE_ISSUED')))
        finally:
            sim.close();observer_engine.dispose()
