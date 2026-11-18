"""Independent re-review probes: real endpoints/native PG locks, no auth SQL writes.

ASGI clients share an OS process; distinct PostgreSQL sessions are not two OS APIs.
Barriers only pause SQL execution. No physical proof, time or authority is forged.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import DBAPIError

from app.application import assets
from app.config import ROOT
from app.infrastructure.db import advisory_lock
from app.main import create_app
from app.seed import demo_id
from test_phase1 import headers
from test_phase5 import race_environment, login
from test_phase8b_b1a_transactions import waiters
from test_phase8b_ia01_fix import state, target


def evidence(name, result):
    path=ROOT/'docs/PHASE8B_TESTS'/f'rereview_{name}_{uuid4().hex}.json'
    path.write_text(json.dumps(result,indent=2,default=str),encoding='utf8')


@pytest.mark.parametrize('revoke',['logout','role'])
def test_cached_replay_revocation_wins_after_initial_auth(race_environment,revoke):
    env=race_environment;db=env['seed_db'];key=uuid4()
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin');path,body=target(db,'compartment')
        initial=http.post(path,headers=headers(tech,key),json=body);assert initial.status_code==200
        committed=state(db,path)
        assert len(committed['audit'])==len(committed['receipts'])==1
        with db.sessions() as blocker,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            advisory_lock(blocker,f'idem:{demo_id("technician")}:POST {path}:{key}')
            holder=blocker.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(http.post,path,headers=headers(tech,key),json=body)
                try:
                    waits=waiters(observer,holder,1)  # Auth/scope passed, now blocked at idempotency.
                    if revoke=='logout':
                        changed=http.post('/v1/auth/logout',headers=headers(tech))
                    else:
                        removed=http.put(f'/v1/users/{demo_id("technician")}/station-assignments',headers=headers(admin),json={'station_ids':[]})
                        assert removed.status_code==200
                        changed=http.patch(f'/v1/users/{demo_id("technician")}',headers=headers(admin),
                            json={'expected_version':removed.json()['version'],'role':'CUSTOMER'})
                    assert changed.status_code==200,changed.text
                    assert http.get('/v1/me',headers=tech).status_code==401
                    observed=observer.scalar(text('select clock_timestamp()'))
                finally:blocker.rollback()
                response=pending.result(timeout=10)
        after=state(db,path)
        evidence('cached_revoke_first',{'revoke':revoke,'schema':env['settings'].schema,'holder_pid':holder,'waiters':waits,
            'revocation_commit_observed_at':observed,'response_http':response.status_code,'business_code':response.json().get('code'),
            'before':committed,'after':after})
        assert (response.status_code,response.json()['code'])==(401,'SESSION_REVOKED')
        assert after==committed  # No stale response-cache acceptance or new mutation/audit/receipt.


def test_cached_replay_authority_wins_logout_waits(race_environment):
    env=race_environment;db=env['seed_db'];key=uuid4();ready=Event();release=Event();winner={}
    app=create_app(env['settings'])
    with TestClient(app) as http:
        tech=login(http,env,'technician');path,body=target(db,'compartment')
        initial=http.post(path,headers=headers(tech,key),json=body);assert initial.status_code==200
        committed=state(db,path)
        def lookup(conn,cursor,statement,parameters,context,many):
            if 'FROM idempotency_records' in statement and not ready.is_set():
                winner['pid']=conn.connection.driver_connection.info.backend_pid
                ready.set();assert release.wait(6),'Reviewer cache-lookup barrier not released'
        event.listen(app.state.db.engine,'after_cursor_execute',lookup)
        try:
            with env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer,ThreadPoolExecutor(max_workers=2) as pool:
                pending=pool.submit(http.post,path,headers=headers(tech,key),json=body)
                assert ready.wait(4),'No protected cache lookup'
                logout=pool.submit(http.post,'/v1/auth/logout',headers=headers(tech))
                try:
                    waits=waiters(observer,winner['pid'],1)
                    assert not logout.done()
                    assert state(db,path)==committed
                finally:release.set()
                response=pending.result(timeout=10);revoked=logout.result(timeout=10)
        finally:event.remove(app.state.db.engine,'after_cursor_execute',lookup)
        after=state(db,path)
        evidence('cached_replay_first',{'schema':env['settings'].schema,'winner':winner,'waiters':waits,
            'replay_http':response.status_code,'logout_http':revoked.status_code,'before':committed,'after':after})
        assert response.status_code==200 and response.json()==initial.json()
        assert revoked.status_code==200 and http.get('/v1/me',headers=tech).status_code==401
        assert after==committed
        assert http.post(path,headers=headers(tech,key),json=body).status_code==401


def test_preliminary_savepoint_releases_resource_but_retains_outer_authority_locks(race_environment):
    env=race_environment;db=env['seed_db'];ready=Event();release=Event();winner={};app=create_app(env['settings'])
    with TestClient(app) as http:
        tech=login(http,env,'technician');path,body=target(db,'compartment');before=state(db,path)
        def acquired(conn,cursor,statement,parameters,context,many):
            if 'FROM users' in statement and 'FOR UPDATE' in statement and not ready.is_set():
                winner['pid']=conn.connection.driver_connection.info.backend_pid
                ready.set();assert release.wait(6),'Reviewer user-lock barrier not released'
        event.listen(app.state.db.engine,'after_cursor_execute',acquired)
        diagnostics={}
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(http.post,path,headers=headers(tech),json=body)
                assert ready.wait(4)
                try:
                    # Actual PG NOWAIT checks, not a mocked get_row or inferred timing.
                    for name,identity,allowed,keyshare in (
                        ('compartments',demo_id('S01:slot:1'),True,False),
                        ('users',demo_id('technician'),False,False),
                        ('stations',demo_id('S01'),False,False),
                        ('stations',demo_id('S01'),True,True)):
                        with db.sessions() as probe:
                            pid=probe.scalar(text('select pg_backend_pid()'))
                            assert pid!=winner['pid']
                            table=db.table(name);mode='KEY SHARE' if keyshare else 'UPDATE'
                            try:
                                probe.execute(select(table.c.id).where(table.c.id==identity)
                                    .with_for_update(nowait=True,read=keyshare,key_share=keyshare)).one()
                                result='acquired'
                            except DBAPIError as error:
                                result=getattr(error.orig,'sqlstate',None)
                            diagnostics[name+':'+mode]={'pid':pid,'result':result}
                            assert result==('acquired' if allowed else '55P03')
                    assert state(db,path)==before  # No preliminary business/audit/receipt write.
                finally:release.set()
                response=pending.result(timeout=10)
        finally:event.remove(app.state.db.engine,'after_cursor_execute',acquired)
        after=state(db,path)
        evidence('savepoint',{'schema':env['settings'].schema,'winner':winner,'diagnostics':diagnostics,
            'http':response.status_code,'before':before,'after':after})
        assert response.status_code==200,response.text
        assert after['row']['version']==before['row']['version']+1
        assert len(after['audit'])==len(after['receipts'])==1
        assert after['invariants']==before['invariants']


@pytest.mark.parametrize('kind',['battery','alert'])
def test_sibling_resource_wait_logout_wins_without_assignment_change(race_environment,kind):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');path,body=target(db,kind);before=state(db,path)
        with db.sessions() as blocker,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            table=db.table('batteries' if kind=='battery' else 'alerts')
            blocker.execute(select(table.c.id).where(table.c.id==before['row']['id']).with_for_update()).one()
            holder=blocker.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(http.post,path,headers=headers(tech),json=body)
                try:
                    waits=waiters(observer,holder,1)
                    revoked=http.post('/v1/auth/logout',headers=headers(tech));assert revoked.status_code==200
                    assert http.get('/v1/me',headers=tech).status_code==401
                    assignments=db.table('user_station_assignments')
                    with db.sessions() as read:
                        assert read.scalar(select(assignments.c.user_id).where(assignments.c.user_id==demo_id('technician'),assignments.c.station_id==demo_id('S01')))
                finally:blocker.rollback()
                response=pending.result(timeout=10)
        after=state(db,path)
        evidence('sibling_session',{'kind':kind,'schema':env['settings'].schema,'holder':holder,'waiters':waits,
            'http':response.status_code,'code':response.json().get('code'),'before':before,'after':after})
        assert (response.status_code,response.json()['code'])==(401,'SESSION_REVOKED')
        assert after==before
