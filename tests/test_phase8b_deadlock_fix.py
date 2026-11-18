"""Deterministic PG lock graph and full HTTP races; no provider/certificate effects.

Test middleware/event barriers are never installed by production. Time waits
below target real expiry/freshness boundaries, not speculative race sleeps.
"""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import timedelta
import json
from pathlib import Path
import secrets
from threading import Event
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, event, insert, select, text, update

from app.application import assets, payments, recovery
from app.application.identity import utcnow
from app.config import ROOT
from app.domain.identity import digest
from app.domain.recovery import canonical_hash
from app.main import create_app
from app.seed import demo_id
from app.workers import device as device_worker, payment as payment_worker
from test_phase1 import headers
from test_phase5 import race_environment, login
from test_phase6 import book, consent, outcome, payment
from test_phase8b_b1a import post, protected
from test_phase8b_b1a_transactions import waiters


def history(db,swap):
    now=utcnow();case_id=uuid4();op_id=uuid4()
    with db.sessions.begin() as s:
        s.execute(insert(db.table('recovery_cases')).values(id=case_id,swap_id=UUID(swap['id'])))
        s.execute(insert(db.table('recovery_operations')).values(id=op_id,case_id=case_id,
            swap_id=UUID(swap['id']),station_id=UUID(swap['station_id']),customer_id=demo_id('customer'),
            pin_id=UUID(swap['old_battery_id']),expected_serial='storage-only-not-proof',purpose='VERIFY_OLD_POSSESSION',
            context={},context_hash=canonical_hash({}),created_by=demo_id('technician'),
            created_at=now,expires_at=now+timedelta(seconds=120),consumed_at=now,
            base_case_version=1,base_swap_version=1))
    return case_id,op_id


def setup(http,env):
    customer=login(http,env);admin=login(http,env,'admin')
    swap=book(http,env,customer,env['seed_db']);assert consent(http,customer,swap).status_code==202
    payment_worker.tick(env['seed_db'],transport=outcome)
    return admin,swap,payment(http,customer,swap)


def evidence(label,data):
    (ROOT/'docs/PHASE8B_TESTS'/f'{label}_{uuid4().hex}.json').write_text(json.dumps(data,indent=2,default=str),encoding='utf8')


def test_station_row_remains_exclusive_but_fk_reference_can_complete(race_environment):
    env=race_environment;db=env['seed_db'];station=demo_id('S01');tech=demo_id('technician')
    with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
        assets.station_lock(held,db,station);holder=held.scalar(text('select pg_backend_pid()'))
        # Native FK reference must finish WHILE the station writer lock is held.
        with db.sessions.begin() as reference:
            reference.execute(delete(db.table('user_station_assignments')).where(db.table('user_station_assignments').c.user_id==tech))
            reference.execute(insert(db.table('user_station_assignments')).values(user_id=tech,station_id=station))
        waits=[]
        def row_writer(kind):
            with db.sessions.begin() as s:
                if kind=='mutex':assets.station_lock(s,db,station)
                elif kind=='update':s.execute(update(db.table('stations')).where(db.table('stations').c.id==station).values(name='locked target'))
                elif kind=='keyshare':s.execute(select(db.table('stations').c.id).where(db.table('stations').c.id==station).with_for_update(read=True,key_share=True))
                else:s.execute(select(db.table('stations').c.id).where(db.table('stations').c.id==station).with_for_update())
                return s.scalar(text('select pg_backend_pid()'))
        with ThreadPoolExecutor(max_workers=4) as pool:
            # KEY SHARE succeeds, but mutex, non-key UPDATE and FOR UPDATE wait.
            keyshare=pool.submit(row_writer,'keyshare').result(timeout=2)
            futures=[pool.submit(row_writer,k) for k in ('mutex','update','strong')]
            try:waits=waiters(observer,holder,3)
            finally:held.rollback()
            assert len({f.result(timeout=5) for f in futures})==3
        evidence('station_compatibility',{'station_holder':holder,'key_share_pid':keyshare,'blocked_writers':waits})


@pytest.mark.parametrize('winner',['assignment','refund'])
def test_full_http_assignment_refund_both_orders(race_environment,winner):
    env=race_environment;db=env['seed_db'];pathvar=ContextVar('test_route',default='')
    app=create_app(env['settings']);held=Event();release=Event();pids={};errors=[]
    @app.middleware('http')
    async def route_marker(request,call_next):
        token=pathvar.set(request.url.path)
        try:return await call_next(request)
        finally:pathvar.reset(token)
    with TestClient(app) as http:
        admin,swap,p=setup(http,env);history(db,swap);before=protected(db)
        assignment_path=f'/v1/users/{demo_id("technician")}/station-assignments'
        refund_path=f'/v1/payments/{p["id"]}/refund'
        def acquired(conn,cursor,statement,parameters,context,many):
            path=pathvar.get()
            target=(path==assignment_path and 'FROM users' in statement and 'FOR UPDATE' in statement)
            target=target if winner=='assignment' else (path==refund_path and 'FROM auth_sessions' in statement and 'FOR UPDATE' in statement)
            if target and not held.is_set():
                pids['winner']=conn.connection.driver_connection.info.backend_pid
                held.set();assert release.wait(4),'Test barrier not released'
        def failed(context):errors.append(getattr(context.original_exception,'sqlstate',None))
        event.listen(app.state.db.engine,'after_cursor_execute',acquired)
        event.listen(app.state.db.engine,'handle_error',failed)
        def assign():return http.put(assignment_path,headers=headers(admin),json={'station_ids':[]})
        try:
            with env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer,ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(assign if winner=='assignment' else lambda:post(http,admin,p))
                assert held.wait(4),'Winner did not reach row-lock barrier'
                second=pool.submit((lambda:post(http,admin,p)) if winner=='assignment' else assign)
                try:diagnostic=waiters(observer,pids['winner'],1)
                finally:release.set()
                a,b=first.result(timeout=10),second.result(timeout=10)
            assignment,refund=(a,b) if winner=='assignment' else (b,a)
            assert assignment.status_code==200,assignment.text
            assert (refund.status_code,refund.json()['code'])==(422,'REFUND_EVIDENCE_REQUIRED')
            assert not errors
            after=protected(db)
            for name in before:
                if name not in ('audit_events','idempotency_records'):assert after[name]==before[name]
            assert len(after['audit_events'])==len(before['audit_events'])+1
            assert len(after['idempotency_records'])==len(before['idempotency_records'])+1
            # Revoke is effective, not just a hidden menu. No technician proof may follow it.
            technician=login(http,env,'technician')
            assert http.get(f'/v1/swaps/{swap["id"]}/recovery',headers=technician).status_code==403
            evidence('http_assignment_'+winner,{'winner':winner,'winner_pid':pids['winner'],'waiters':diagnostic,
                'http':[assignment.status_code,refund.status_code],'sqlstates':errors,'refund_writes':0,
                'two_os_processes':False,'assignment_audit_delta':1})
        finally:
            release.set();event.remove(app.state.db.engine,'after_cursor_execute',acquired)
            event.remove(app.state.db.engine,'handle_error',failed)


@pytest.mark.parametrize('competitor',['payment','device','recovery'])
def test_shared_callers_serialize_refund_without_partial_writes(race_environment,competitor):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        admin,swap,p=setup(http,env);history(db,swap);before=protected(db)
        with db.sessions() as other,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            if competitor=='payment':payments.lock(other,db,UUID(p['id']))
            elif competitor=='device':device_worker.station_locks(other,db,UUID(swap['station_id']))
            else:recovery.lock_context(other,db,UUID(swap['id']),demo_id('technician'))
            holder=other.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                request=pool.submit(post,http,admin,p)
                try:diagnostic=waiters(observer,holder,1)
                finally:other.commit()
                response=request.result(timeout=10)
        assert (response.status_code,response.json()['code'])==(422,'REFUND_EVIDENCE_REQUIRED')
        assert protected(db)==before
        evidence('shared_'+competitor,{'holder_pid':holder,'waiters':diagnostic,'http':response.status_code,
            'scope':'real shared lock entry point; no provider/effect execution'})


def test_session_expires_during_observed_station_lock_wait(race_environment):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        _,swap,p=setup(http,env)
        # New isolated authentication fixture, not UPDATE of an existing session,
        # not a production TTL change, and never physical evidence/certificate.
        token=secrets.token_urlsafe(48);expires=utcnow()+timedelta(seconds=3)
        with db.sessions.begin() as s:
            s.execute(insert(db.table('auth_sessions')).values(id=uuid4(),user_id=demo_id('admin'),token_hash=digest(token),expires_at=expires))
        actor={'Authorization':'Bearer '+token}
        assert http.get('/v1/me',headers=actor).status_code==200
        before=protected(db)
        with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            assets.station_lock(held,db,UUID(swap['station_id']));holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                request=pool.submit(post,http,actor,p)
                try:
                    diagnostic=waiters(observer,holder,1)
                    Event().wait(max(0,(expires-utcnow()).total_seconds())+.05)
                finally:held.rollback()
                response=request.result(timeout=10)
        assert (response.status_code,response.json()['code'])==(401,'SESSION_REVOKED')
        assert protected(db)==before
        evidence('expiry_wait',{'holder_pid':holder,'waiters':diagnostic,'http':401,'expiry_crossed':utcnow()>expires})


def test_pre_proof_expires_during_exact_session_lock_wait(race_environment,tmp_path):
    from test_phase8a_inspection_transport import setup_inspection,facts
    from test_phase8a_ia01_fix import request as attest
    from simulators.device.recovery_fence import transport_inspection,flush
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        swap,sim,task,tech=setup_inspection(http,env,lambda role:login(http,env,role),tmp_path,committed=True)
        try:
            transport_inspection(sim,task);flush(sim)
            path=f'/v1/swaps/{swap["id"]}/recovery';case=http.get(path,headers=tech).json()
            with db.sessions() as s:
                t=db.table('recovery_attestations');proof=s.execute(select(t).where(t.c.operation_id==UUID(task['operation_id']))).mappings().one()
                deadline=min(proof['observed_at'],proof['received_at'])+timedelta(seconds=15)
                sessions=db.table('auth_sessions');identity=s.scalar(select(sessions.c.id).where(sessions.c.token_hash==digest(tech['Authorization'].split()[1])))
            Event().wait(max(0,(deadline-utcnow()).total_seconds()-2))
            assert utcnow()<deadline
            before=facts(http,swap)
            with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
                assets.get_row(held,db,'auth_sessions',identity,lock=True);holder=held.scalar(text('select pg_backend_pid()'))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(http.post,path+'/evidence',headers=headers(tech),json=attest(case,task))
                    try:
                        diagnostic=waiters(observer,holder,1)
                        Event().wait(max(0,(deadline-utcnow()).total_seconds())+.05)
                    finally:held.rollback()
                    response=pending.result(timeout=10)
            assert (response.status_code,response.json()['code'])==(422,'EVENT_STALE'),response.text
            assert http.get(path,headers=tech).json()==case
            assert facts(http,swap)==before
            evidence('freshness_wait',{'holder_pid':holder,'waiters':diagnostic,'http':422,'code':'EVENT_STALE','freshness_seconds':15})
        finally:sim.close()


@pytest.mark.parametrize('winner',['refund','settlement'])
def test_refund_vs_recovery_settle_both_orders_fail_closed(race_environment,winner):
    from app.application import swaps
    env=race_environment;db=env['seed_db'];route=ContextVar('test_settlement_route',default='')
    app=create_app(env['settings']);held=Event();release=Event();pids={}
    @app.middleware('http')
    async def marker(request,call_next):
        token=route.set(request.url.path)
        try:return await call_next(request)
        finally:route.reset(token)
    with TestClient(app) as http:
        admin,swap,p=setup(http,env);case_id,op=history(db,swap)
        with db.sessions.begin() as s:
            device_worker.station_locks(s,db,UUID(swap['station_id']))
            swaps.review(s,db,assets.get_row(s,db,'swap_transactions',UUID(swap['id'])),'LOCK_GRAPH_TEST_REVIEW')
        tech=login(http,env,'technician');before=protected(db)
        settle_path=f'/v1/swaps/{swap["id"]}/recovery/settle';refund_path=f'/v1/payments/{p["id"]}/refund'
        def acquired(conn,cursor,statement,parameters,context,many):
            target=(route.get()==settle_path and 'FROM recovery_cases' in statement) if winner=='settlement' else (
                route.get()==refund_path and 'FROM auth_sessions' in statement and 'FOR UPDATE' in statement)
            if target and not held.is_set():
                pids['winner']=conn.connection.driver_connection.info.backend_pid
                held.set();assert release.wait(4)
        event.listen(app.state.db.engine,'after_cursor_execute',acquired)
        def settle():return http.post(settle_path,headers=headers(tech),json={
            'expected_version':1,'operation_id':str(op),'resolution_note':'Closed history must not be reused'})
        try:
            with env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer,ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(settle if winner=='settlement' else lambda:post(http,admin,p))
                assert held.wait(4)
                second=pool.submit((lambda:post(http,admin,p)) if winner=='settlement' else settle)
                try:diagnostic=waiters(observer,pids['winner'],1)
                finally:release.set()
                a,b=first.result(timeout=10),second.result(timeout=10)
            settlement,refund=(a,b) if winner=='settlement' else (b,a)
            assert (settlement.status_code,settlement.json()['code'])==(409,'RECOVERY_OPERATION_CLOSED')
            assert (refund.status_code,refund.json()['code'])==(422,'REFUND_EVIDENCE_REQUIRED')
            assert protected(db)==before
            evidence('settle_'+winner,{'winner_pid':pids['winner'],'waiters':diagnostic,
                'http':[settlement.status_code,refund.status_code],
                'scope':'both true HTTP transactions refuse missing eligibility/closed history; no positive certificate'})
        finally:release.set();event.remove(app.state.db.engine,'after_cursor_execute',acquired)


def test_admin_role_revocation_commits_before_refund_decision(race_environment):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        admin,swap,p=setup(http,env)
        name='replacement-'+uuid4().hex;password=secrets.token_urlsafe(24)
        created=http.post('/v1/users',headers=headers(admin),json={'username':name,'password':password,'role':'ADMIN'})
        assert created.status_code==201
        logged=http.post('/v1/auth/login',json={'username':name,'password':password});assert logged.status_code==200
        other={'Authorization':'Bearer '+logged.json()['access_token']}
        with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            assets.station_lock(held,db,UUID(swap['station_id']));holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                request=pool.submit(post,http,admin,p)
                try:
                    diagnostic=waiters(observer,holder,1)
                    changed=http.patch(f'/v1/users/{demo_id("admin")}',headers=headers(other),json={'expected_version':1,'role':'TECHNICIAN'})
                    assert changed.status_code==200,changed.text
                    assert http.get('/v1/me',headers=admin).status_code==401
                    before=protected(db)  # legitimate Identity changes already committed
                finally:held.rollback()
                response=request.result(timeout=10)
        assert (response.status_code,response.json()['code'])==(401,'SESSION_REVOKED')
        assert protected(db)==before
        evidence('role_revoke_wait',{'holder_pid':holder,'waiters':diagnostic,'role_change_http':200,'refund_http':401})
