"""Authority serialization regression: actual routes, isolated native PG sessions.

Barriers observe database locks, never change proof/custody or business clocks.
These are same-OS ASGI clients, not two OS API servers.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
import secrets
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, insert, select, text

from app.application import assets
from app.application.identity import utcnow
from app.domain.identity import digest
from app.main import create_app
from app.infrastructure.db import advisory_lock
from app.seed import demo_id
from test_phase1 import headers
from test_phase5 import race_environment, login
from test_phase8b_b1a_transactions import waiters
from test_phase8b_independent_review import facts
from test_phase8b_deadlock_fix import evidence


def target(db, kind):
    if kind == 'compartment':
        return f'/v1/compartments/{demo_id("S01:slot:1")}/actions', dict(expected_version=1,action='SET_MAINTENANCE',reason='IA01')
    if kind == 'battery':
        return f'/v1/batteries/{demo_id("S01:battery:2")}/actions', dict(expected_version=1,action='QUARANTINE',reason='IA01')
    identity=uuid4()
    with db.sessions.begin() as s:
        s.execute(insert(db.table('alerts')).values(id=identity,station_id=demo_id('S01'),dedup_key=str(identity),code='SIMULATED_FAULT'))
    return f'/v1/alerts/{identity}/acknowledge',dict(expected_version=1)


def state(db, path):
    name='compartments' if '/compartments/' in path else 'batteries' if '/batteries/' in path else 'alerts'
    identity=UUID(path.split('/')[3])
    with db.sessions() as s:
        row=dict(assets.get_row(s,db,name,identity))
        a=db.table('audit_events');i=db.table('idempotency_records')
        pins=db.table('batteries')
        invariant={'custody':[dict(v) for v in s.execute(select(pins.c.id,pins.c.location_kind,pins.c.holder_user_id,pins.c.compartment_id).order_by(pins.c.id)).mappings()]}
        for table in ('payments','refunds','resource_reservations','device_commands','outbox_messages'):
            t=db.table(table);invariant[table]=[dict(v) for v in s.execute(select(t).order_by(t.c.id)).mappings()]
        return {'row':row,'audit':[dict(v) for v in s.execute(select(a).where(a.c.aggregate_id==identity)).mappings()],
            'receipts':[dict(v) for v in s.execute(select(i).where(i.c.route=='POST '+path)).mappings()],
            'protected':facts(db),'invariants':invariant}


@pytest.mark.parametrize('kind',['battery','alert'])
def test_sibling_assignment_revoke_during_station_wait(race_environment,kind):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin');path,body=target(db,kind);before=state(db,path)
        with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            assets.station_lock(held,db,demo_id('S01'));holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(http.post,path,headers=headers(tech),json=body)
                try:
                    diagnostic=waiters(observer,holder,1)
                    revoke=http.put(f'/v1/users/{demo_id("technician")}/station-assignments',headers=headers(admin),json={'station_ids':[]})
                    assert revoke.status_code==200,revoke.text
                finally:held.rollback()
                response=pending.result(timeout=10)
        after=state(db,path)
        evidence('ia01_sibling',{'kind':kind,'holder':holder,'waits':diagnostic,'http':response.status_code,'body':response.json(),'before':before,'after':after})
        assert (response.status_code,response.json().get('code'))==(403,'STATION_FORBIDDEN')
        assert after==before


@pytest.mark.parametrize('kind',['compartment','battery','alert'])
@pytest.mark.parametrize('revocation',['logout','role','state'])
def test_current_authority_revoked_before_decision(race_environment,kind,revocation):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin');path,body=target(db,kind);before=state(db,path)
        with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            assets.station_lock(held,db,demo_id('S01'));holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(http.post,path,headers=headers(tech),json=body)
                try:
                    diagnostic=waiters(observer,holder,1)
                    if revocation=='logout':
                        revoked=http.post('/v1/auth/logout',headers=headers(tech))
                    else:
                        version=1
                        if revocation=='role':
                            removed=http.put(f'/v1/users/{demo_id("technician")}/station-assignments',headers=headers(admin),json={'station_ids':[]})
                            assert removed.status_code==200;version=removed.json()['version']
                        revoked=http.patch(f'/v1/users/{demo_id("technician")}',headers=headers(admin),
                            json={'expected_version':version,**({'role':'CUSTOMER'} if revocation=='role' else {'state':'LOCKED'})})
                    assert revoked.status_code==200,revoked.text
                    assert http.get('/v1/me',headers=tech).status_code==401
                finally:held.rollback()
                response=pending.result(timeout=10)
        assert (response.status_code,response.json()['code'])==(401,'SESSION_REVOKED')
        assert state(db,path)==before
        evidence('ia01_authority',{'kind':kind,'revocation':revocation,'holder':holder,'waits':diagnostic,'revoke':200,'mutation':401,'unchanged':True})


@pytest.mark.parametrize('kind',['compartment','battery','alert'])
@pytest.mark.parametrize('revocation',['assignment','logout','state'])
def test_mutation_authority_first_revocation_waits(race_environment,monkeypatch,kind,revocation):
    env=race_environment;db=env['seed_db'];ready=Event();release=Event();winner={};audit=assets.asset_audit
    def barrier(s,d,actor,*args,**kwargs):
        result=audit(s,d,actor,*args,**kwargs)
        if actor['id']==demo_id('technician'):
            winner['pid']=s.scalar(text('select pg_backend_pid()'));ready.set()
            assert release.wait(4),'Mutation barrier not released'
        return result
    monkeypatch.setattr(assets,'asset_audit',barrier)
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin');path,body=target(db,kind);before=state(db,path)
        def revoke():
            if revocation=='assignment':return http.put(f'/v1/users/{demo_id("technician")}/station-assignments',headers=headers(admin),json={'station_ids':[]})
            if revocation=='logout':return http.post('/v1/auth/logout',headers=headers(tech))
            return http.patch(f'/v1/users/{demo_id("technician")}',headers=headers(admin),json={'expected_version':1,'state':'LOCKED'})
        with env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer,ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(http.post,path,headers=headers(tech),json=body)
            assert ready.wait(4),'Mutation did not reach audit'
            second=pool.submit(revoke)
            try:
                diagnostic=waiters(observer,winner['pid'],1)
                assert not second.done()
                # Mutation/audit/receipt are not externally visible until commit.
                assert state(db,path)==before
            finally:release.set()
            response=first.result(timeout=10);revoked=second.result(timeout=10)
        assert response.status_code==200,response.text
        assert revoked.status_code==200,revoked.text
        after=state(db,path)
        assert after['row']['version']==before['row']['version']+1
        assert len(after['audit'])==len(before['audit'])+1
        assert len(after['receipts'])==len(before['receipts'])+1
        assert after['invariants']==before['invariants']
        assert http.post(path,headers=headers(tech),json=body).status_code==(403 if revocation=='assignment' else 401)
        evidence('ia01_mutation_first',{'kind':kind,'revocation':revocation,'winner':winner,'waits':diagnostic,'mutation':200,'revoke':200,'before':before,'after':after})


@pytest.mark.parametrize('kind',['compartment','battery','alert'])
def test_atomic_audit_rollback_replay_and_revoked_replay(race_environment,monkeypatch,kind):
    env=race_environment;db=env['seed_db'];original=assets.asset_audit
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin');path,body=target(db,kind);before=state(db,path);key=uuid4();auth=headers(tech,key)
        def fail(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('IA01 injected audit failure')
        with monkeypatch.context() as patch:
            patch.setattr(assets,'asset_audit',fail)
            with pytest.raises(RuntimeError,match='IA01 injected audit failure'):http.post(path,headers=auth,json=body)
        assert state(db,path)==before
        response=http.post(path,headers=auth,json=body);assert response.status_code==200,response.text
        committed=state(db,path)
        assert http.post(path,headers=auth,json=body).json()==response.json()
        assert state(db,path)==committed
        conflict=http.post(path,headers=auth,json={**body,'expected_version':2})
        assert (conflict.status_code,conflict.json()['code'])==(409,'IDEMPOTENCY_CONFLICT')
        removed=http.put(f'/v1/users/{demo_id("technician")}/station-assignments',headers=headers(admin),json={'station_ids':[]})
        assert removed.status_code==200
        assert http.post(path,headers=auth,json=body).status_code==403
        assert state(db,path)==committed


def test_exact_session_other_session_logout_and_native_expiry(race_environment):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        other=login(http,env,'technician');valid=login(http,env,'technician')
        assert http.post('/v1/auth/logout',headers=headers(other)).status_code==200
        path,body=target(db,'compartment')
        ok=http.post(path,headers=headers(valid),json=body);assert ok.status_code==200
        # A newly inserted short-lived authentication fixture, not a changed TTL
        # or timestamp on historical proof. It is valid before the actual wait.
        secret=secrets.token_urlsafe(48);expires=utcnow()+timedelta(seconds=3)
        with db.sessions.begin() as s:
            s.execute(insert(db.table('auth_sessions')).values(id=uuid4(),user_id=demo_id('technician'),token_hash=digest(secret),expires_at=expires))
        short={'Authorization':'Bearer '+secret}
        assert http.get('/v1/me',headers=short).status_code==200
        path,body=target(db,'battery');before=state(db,path)
        with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            assets.station_lock(held,db,demo_id('S01'));holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(http.post,path,headers=headers(short),json=body)
                try:
                    diagnostic=waiters(observer,holder,1)
                    Event().wait(max(0,(expires-utcnow()).total_seconds())+.05)
                finally:held.rollback()
                response=pending.result(timeout=10)
        assert (response.status_code,response.json()['code'])==(401,'SESSION_REVOKED')
        assert state(db,path)==before
        evidence('ia01_exact_session',{'other_logged_out':True,'valid_session_mutation':200,'short_session_http':401,'waits':diagnostic})


@pytest.mark.parametrize('kind',['compartment','battery','alert'])
def test_role_and_station_contract_unchanged(race_environment,kind):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin');customer=login(http,env,'customer')
        path,body=target(db,kind);before=state(db,path)
        assert http.post(path,headers=headers(customer),json=body).status_code==403
        if kind!='compartment':assert http.post(path,headers=headers(admin),json=body).status_code==403
        denied=http.post(f'/v1/compartments/{demo_id("S02:slot:1")}/actions',headers=headers(tech),
            json={'expected_version':1,'action':'SET_MAINTENANCE','reason':'wrong station'})
        assert (denied.status_code,denied.json()['code'])==(403,'STATION_FORBIDDEN')
        assert state(db,path)==before


@pytest.mark.parametrize('kind',['compartment','battery','alert'])
@pytest.mark.parametrize('same_key',[True,False])
def test_two_technician_mutations_single_success(race_environment,monkeypatch,kind,same_key):
    env=race_environment;db=env['seed_db'];ready=Event();release=Event();winner={};audit=assets.asset_audit
    def barrier(s,d,*args,**kwargs):
        result=audit(s,d,*args,**kwargs)
        if not ready.is_set():
            winner['pid']=s.scalar(text('select pg_backend_pid()'));ready.set();assert release.wait(4)
        return result
    monkeypatch.setattr(assets,'asset_audit',barrier)
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');path,body=target(db,kind);before=state(db,path);key=uuid4()
        with env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer,ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(http.post,path,headers=headers(tech,key),json=body);assert ready.wait(4)
            second=pool.submit(http.post,path,headers=headers(tech,key if same_key else uuid4()),json=body)
            try:diagnostic=waiters(observer,winner['pid'],1)
            finally:release.set()
            a,b=first.result(timeout=10),second.result(timeout=10)
        assert a.status_code==200,a.text
        assert b.status_code==(200 if same_key else 409),b.text
        if same_key:assert a.json()==b.json()
        else:assert b.json()['code']=='VERSION_CONFLICT'
        after=state(db,path)
        assert after['row']['version']==before['row']['version']+1
        assert len(after['audit'])==len(before['audit'])+1
        assert len(after['receipts'])==len(before['receipts'])+1
        assert after['invariants']==before['invariants']
        evidence('ia01_concurrent',{'kind':kind,'same_key':same_key,'winner':winner,'waits':diagnostic,'http':[a.status_code,b.status_code],'before':before,'after':after})


def test_cached_replay_revalidates_after_idempotency_wait(race_environment):
    env=race_environment;db=env['seed_db'];key=uuid4()
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin');path,body=target(db,'compartment')
        assert http.post(path,headers=headers(tech,key),json=body).status_code==200
        before=state(db,path)
        with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            advisory_lock(held,f'idem:{demo_id("technician")}:POST {path}:{key}');holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(http.post,path,headers=headers(tech,key),json=body)
                try:
                    diagnostic=waiters(observer,holder,1)
                    revoke=http.put(f'/v1/users/{demo_id("technician")}/station-assignments',headers=headers(admin),json={'station_ids':[]})
                    assert revoke.status_code==200
                finally:held.rollback()
                response=pending.result(timeout=10)
        assert (response.status_code,response.json()['code'])==(403,'STATION_FORBIDDEN')
        assert state(db,path)==before
        evidence('ia01_cached_authority',{'holder':holder,'waits':diagnostic,'http':403,'cached_success_not_reused':True})
