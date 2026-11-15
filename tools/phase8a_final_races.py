"""Fixture-only scheduling of existing HTTP transactions; no business writes via SQL."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

from sqlalchemy import select, text
from tools.smoke_phase4 import wait, fingerprints


def marker(directory, session):
    tmp = directory/'pg.tmp'
    tmp.write_text(str(session.scalar(text('select pg_backend_pid()'))))
    tmp.replace(directory/'paused')
    wait(lambda:(directory/'release').exists(), 'Release test transaction', 10)


def app():
    from app import main
    from app.application import recovery
    if not os.environ['DATABASE_SCHEMA'].startswith('phase5_test_'):
        raise RuntimeError('Isolated fixture required')
    directory = Path(os.environ['P8_RACE_DIR'])
    def pause(action, session):
        if (directory/action).exists():
            marker(directory,session)

    identity_audit, recovery_audit = main.audit, recovery.audit
    def identity(session, db, actor, action, *args, **kwargs):
        identity_audit(session,db,actor,action,*args,**kwargs)
        pause(action,session)
    def record(session, db, actor, case, action, after):
        recovery_audit(session,db,actor,case,action,after)
        pause(action,session)
    main.audit, recovery.audit = identity, record
    original = recovery.lock_context
    def before_lock(session, *args, **kwargs):
        pause('before-lock',session)
        return original(session,*args,**kwargs)
    recovery.lock_context = before_lock
    return main.create_app()


def verify(gate, first, second, fixture, base, op, tech, customer, directory, ledgers, demo, fingerprint, processes):
    from test_phase5 import login
    db = fixture['seed_db']
    swap_id = UUID(base.split('/')[3])
    def facts():
        with db.sessions() as s:
            def rows(name, **keys):
                return s.execute(select(db.table(name)).filter_by(**keys)).mappings().all()
            case, = rows('recovery_cases',swap_id=swap_id)
            operation, = rows('recovery_operations',id=UUID(op['id']))
            swap, = rows('swap_transactions',id=swap_id)
            pins = [rows('batteries',id=swap[k])[0] for k in ('old_battery_id','new_battery_id')]
            with sqlite3.connect((ledgers/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as ledger:
                effects = ledger.execute('select coalesce(sum(effects),0) from service_operations').fetchone()[0]
            return dict(version=case['version'],consumed=bool(operation['consumed_at']),old_settled=case['old_pin_settled'],
                case=case['state'],swap=swap['state'],custody=[[p[k] for k in ('location_kind','holder_user_id','compartment_id')] for p in pins],
                payment=rows('payments',swap_id=swap_id)[0]['state'],holds=len(rows('resource_reservations',swap_id=swap_id,released_at=None)),
                success=len(rows('audit_events',aggregate_id=case['id'],action='MANUAL_RECOVERY_SETTLED')),effects=effects)
    def call(http, method, path, auth, body):
        return http.request(method,path,headers={**auth,'Idempotency-Key':str(uuid4())},json=body)
    def confirm(http, decision):
        return call(http,'POST',base+'/confirmations',customer,
                    dict(operation_id=op['id'],context_hash=op['context_hash'],confirm=decision))
    admin = login(second,fixture,'admin')
    user = first.get('/v1/me',headers=tech).json()
    user_path = '/v1/users/'+user['id']
    def assignment(http):
        return call(http,'PUT',user_path+'/station-assignments',admin,{'station_ids':[]})
    def update(http):
        return call(http,'PATCH',user_path,admin,{'expected_version':user['version'],'role':'ADMIN'})
    witness = first.get('/v1/me', headers=customer).json()
    def revoke_witness(http):
        return call(http, 'PATCH', '/v1/users/'+witness['id'], admin,
                    {'expected_version':witness['version'], 'state':'LOCKED'})

    testimony = gate in ('reject-first','confirm-first')
    if not testimony:
        assert confirm(first,True).status_code==201
    before = facts()
    def settle(http, version):
        return call(http,'POST',base+'/settle',tech,dict(expected_version=version,operation_id=op['id'],
                                                        resolution_note='Observed final ordering'))
    report = dict(gate=gate,schema=fixture['settings'].schema,backend_os_pids=[p.pid for p in processes[:2]],
                  before=before, waits=[], http={})
    def result(label, future):
        response = future.result()
        report['http'][label]=[response.status_code,response.json().get('code')]
        return response.status_code
    def observe_wait(holder, port):
        with db.sessions() as s:
            def blocked():
                s.execute(text('select pg_stat_clear_snapshot()'))
                return s.scalar(text('select pid from pg_stat_activity where application_name=:app '
                    'and :holder=any(pg_blocking_pids(pid)) limit 1'),dict(app=f'{directory.name}-{port}',holder=holder))
            wait(blocked,'Independent backend waiting for selected holder',3)
            report['waits'].append(dict(holder=holder,waiter=blocked()))
    try:
        if gate in ('legacy-freshness','fresh-before-expiry','operation-expiry'):
            from datetime import datetime, timedelta
            from app.application.identity import digest
            from app.application import recovery as r
            if gate=='operation-expiry':
                boundary=datetime.fromisoformat(op['expires_at'])
            else:
                processes[3].terminate()
                processes[3].wait(10)
                with db.sessions() as s:
                    swap=r.assets.get_row(s,db,'swap_transactions',swap_id)
                    device=r.assets.available_device(s,db,swap['station_id'])
                    events=db.table('device_events')
                    def drained():
                        return not s.scalar(select(events.c.id).where(events.c.device_id==device['id'],
                            events.c.processed_at.is_(None),events.c.processing_error.is_(None)).limit(1))
                    wait(drained,'All events sent before S01 stopped have committed',8)
                    _, snap, _, times=r.current_snapshot(s,db,swap)
                    boundary=min(times)+timedelta(seconds=swap['policy_snapshot']['telemetry_stale_seconds'])
                    report['final_snapshot']={'id':str(snap['id']),'observed_at':str(snap['observed_at'])}
            sessions=db.table('auth_sessions')
            with ThreadPoolExecutor(1) as pool:
                with db.sessions.begin() as s:
                    def now():return s.scalar(text('select clock_timestamp()'))
                    wait(lambda:now()>=boundary-timedelta(seconds=2.8),'Approach actual deadline',130)
                    s.execute(select(sessions.c.id).where(sessions.c.token_hash==
                        digest(tech['Authorization'].removeprefix('Bearer '))).with_for_update())
                    holder=s.scalar(text('select pg_backend_pid()'))
                    future=pool.submit(settle,first,before['version'])
                    observe_wait(holder,8030)
                    start=now()
                    assert start<boundary
                    if gate!='fresh-before-expiry':
                        wait(lambda:now()>boundary,'Actual snapshot staleness',4)
                    report['time_window']=[str(t) for t in (start,boundary,now())]
                if gate=='fresh-before-expiry':
                    assert result('settlement',future)==200
                    op_table=db.table('recovery_operations')
                    with db.sessions() as s:
                        assert s.scalar(select(op_table.c.consumed_at).where(op_table.c.id==UUID(op['id'])))<boundary
                        committed=s.scalar(text('select clock_timestamp()'))
                        assert committed<boundary
                        report['commit_visible_by']=str(committed)
                    assert facts()=={**before,'consumed':True,'old_settled':True,'version':before['version']+1,'success':1}
                else:
                    assert result('settlement',future)==422
                    assert facts()==before
            assert fingerprints(demo)==fingerprint
            return
        if gate in ('snapshot-first','settle-before-snapshot'):
            verify_snapshot(gate,first,second,fixture,directory,ledgers,processes,settle,
                            before,op,observe_wait,report)
            accepted = gate=='settle-before-snapshot'
            after=facts()
            assert after['consumed']==after['old_settled']==accepted and after['success']==int(accepted)
            assert all(before[k]==after[k] for k in ('custody','payment','holds','effects'))
            assert fingerprints(demo)==fingerprint
            return
        with ThreadPoolExecutor(3) as pool:
            try:
                if testimony:
                    (directory/'RECOVERY_ATTESTATION_RECORDED').touch()
                    leader=pool.submit(confirm,first,gate=='confirm-first')
                elif gate=='assignment-first':
                    (directory/'ASSIGN_STATIONS').touch()
                    leader=pool.submit(assignment,first)
                elif gate=='witness-first':
                    (directory/'UPDATE_USER').touch()
                    leader=pool.submit(revoke_witness,first)
                elif gate=='role-first':
                    (directory/'before-lock').touch()
                    leader=pool.submit(settle,first,before['version'])
                elif gate in ('settle-first','settle-before-role','settle-before-witness'):
                    (directory/'MANUAL_RECOVERY_SETTLED').touch()
                    leader=pool.submit(settle,first,before['version'])
                else:
                    raise ValueError(gate)
                wait(lambda:(directory/'paused').is_file(),'Uncommitted first transaction',6)
                holder=int((directory/'paused').read_text())
                if testimony:
                    opposing=pool.submit(confirm,second,gate!='confirm-first')
                    observe_wait(holder,8031)
                    follower=pool.submit(settle,first,before['version']+1)
                    observe_wait(holder,8030)
                elif gate in ('assignment-first','witness-first'):
                    follower=pool.submit(settle,second,before['version'])
                    observe_wait(holder,8031)
                elif gate=='role-first':
                    assert assignment(second).status_code==200
                    user['version']+=1
                    follower=pool.submit(update,second)
                    assert follower.result().status_code==200
                    assert second.get('/v1/me',headers=tech).status_code==401
                else:
                    change={'settle-before-role':update,'settle-before-witness':revoke_witness,
                            'settle-first':assignment}[gate]
                    follower=pool.submit(change,second)
                    observe_wait(holder,8031)
            finally:
                (directory/'release').touch()
            leader_status=result('first',leader)
            follower_status=result('second',follower)
            if testimony:
                assert result('opposing',opposing)==409
                assert leader_status==201 and follower_status==(200 if gate=='confirm-first' else 422)
            elif gate=='assignment-first':
                assert leader_status==200 and report['http']['second']==[403,'STATION_FORBIDDEN']
            elif gate=='role-first':
                assert leader_status==401 and follower_status==200
            elif gate=='witness-first':
                assert leader_status==200 and report['http']['second']==[403,'RECOVERY_ACTOR_UNAVAILABLE']
            elif gate=='settle-before-role':
                assert leader_status==200 and report['http']['second']==[409,'USER_REFERENCED']
            else:
                assert leader_status==follower_status==200
        if gate in ('witness-first','settle-before-witness'):
            assert second.get('/v1/me', headers=customer).status_code == 401
        accepted = gate not in ('reject-first','assignment-first','role-first','witness-first')
        after=facts()
        assert after['version']==before['version']+int(testimony)+int(accepted)
        assert after['consumed']==after['old_settled']==accepted and after['success']==int(accepted)
        assert all(before[k]==after[k] for k in ('case','swap','custody','payment','holds','effects'))
        assert before['payment']=='SUCCEEDED' and before['holds']==3 and before['effects']==0
    finally:
        report.update(after=facts(),demo_fingerprint_unchanged=fingerprints(demo)==fingerprint)
        print(json.dumps(report,default=str,indent=2))
        (directory/'gate.json').write_text(json.dumps(report,default=str,indent=2))
    assert report['demo_fingerprint_unchanged']


def verify_snapshot(gate, first, second, fixture, directory, ledgers, processes,
                    settle, before, op, observe_wait, report):
    from simulators.device.main import Simulator
    # Reboot the S01 test simulator on its original durable ledger. The new
    # snapshot observes an opened model door. Keep the original proof intact.
    processes[3].terminate()
    processes[3].wait(10)
    db=fixture['seed_db']
    sim=Simulator('S01',fixture['keys']['S01'],ledger=ledgers/'S01.sqlite3')
    try:
        slot=next(s for s in sim.slots() if s['compartment_id']==op['context']['return_compartment_id'])
        sim.save_slot({**slot,'door_state':'OPEN','lock_released':True})
        packet=sim.snapshot()
    finally:
        sim.close()
    def event():
        t=db.table('device_events')
        with db.sessions() as s:
            e=s.execute(select(t).where(t.c.id==UUID(packet['event_id']))).mappings().first()
            return None if e is None else dict(accepted=e['accepted'],processed=bool(e['processed_at']),boot=str(e['boot_id']))
    def send():
        return second.post('/v1/device/events',headers={'X-Device-Key':fixture['keys']['S01']},json=packet)
    with ThreadPoolExecutor(2) as pool:
        try:
            if gate=='snapshot-first':
                (directory/'watch-event').write_text(packet['event_id'])
                response=send()
                assert response.status_code==202 and response.json()['processing_state']=='QUEUED'
                wait(lambda:(directory/'paused').exists(),'Worker processed event before commit',6)
                report['inbox_before_worker_commit']=event()
                assert report['inbox_before_worker_commit']['processed'] is False
                future=pool.submit(settle,first,before['version'])
                observe_wait(int((directory/'paused').read_text()),8030)
            else:
                (directory/'MANUAL_RECOVERY_SETTLED').touch()
                future=pool.submit(settle,first,before['version'])
                wait(lambda:(directory/'paused').exists(),'Settlement holds station',6)
                receiver=pool.submit(send)
                observe_wait(int((directory/'paused').read_text()),8031)
                assert event() is None
        finally:
            (directory/'release').touch()
        decision=future.result()
        if gate=='settle-before-snapshot':
            response=receiver.result()
        report['http']={'settlement':[decision.status_code,decision.json().get('code')],'inbox':[response.status_code,response.json()['processing_state']]}
        wait(lambda:event() and event()['processed'],'Worker completed projection')
        report['committed_event']=event()
        assert event()['accepted'] and response.status_code==202
        assert decision.status_code==(200 if gate=='settle-before-snapshot' else 422)


def cross_expiry(branch,first,second,case,op,base,tech,db,directory,report,pids):
    from datetime import datetime, timezone
    wait(lambda:datetime.now(timezone.utc)>=datetime.fromisoformat(op['expires_at']),'Contract expiry',130)
    initial=case()
    body={'expected_version':initial['version'],'note':'Expiry concurrency',
          'statement':dict(operation_id=op['id'],context_hash=op['context_hash'])}
    successor=branch=='K'
    action='RECOVERY_REINSPECTION_REQUESTED' if successor else 'RECOVERY_NO_EFFECT_CLOSURE_REQUESTED'
    leading='REINSPECT_OPERATION' if successor else 'CLOSE_NO_EFFECT'
    trailing='CLOSE_NO_EFFECT' if successor else 'REINSPECT_OPERATION'
    def issue(http,kind):
        return http.post(base+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},
                         json={**body,'statement':{**body['statement'],'kind':kind}})
    (directory/action).touch()
    with ThreadPoolExecutor(2) as pool:
        winner=pool.submit(issue,first,leading)
        try:
            wait(lambda:(directory/'paused').exists(),'Intent audit before commit',8)
            holder=int((directory/'paused').read_text())
            loser=pool.submit(issue,second,trailing)
            with db.sessions() as s:
                def waiter():
                    return s.scalar(text('select pid from pg_stat_activity where application_name=:name '
                        'and :holder=any(pg_blocking_pids(pid)) limit 1'),{'name':f'{directory.name}-8031','holder':holder})
                wait(waiter,'Other intent waits on station',3)
                blocked=waiter()
        finally:
            (directory/'release').touch()
        a,b=winner.result(),loser.result()
    final=case()
    report['cross_expiry']=dict(backend_os_pids=pids,pg_holder=holder,pg_waiter=blocked,leader=leading,
        first_http=a.status_code,second_http=b.status_code,second_code=b.json().get('code'),before_version=initial['version'],
        after_version=final['version'],old_settled=final['old_pin_settled'],consumed=bool(final['active_operation']['consumed_at']))
    assert a.status_code==200 and b.status_code==409 and b.json()['code']=='VERSION_CONFLICT'
    assert final['version']==initial['version']+1 and not final['old_pin_settled']
    assert not final['active_operation']['consumed_at']
    with db.sessions() as s:
        actions=s.scalars(select(db.table('audit_events').c.action)).all()
        assert actions.count(action)==1 and 'FOREIGN_OBJECT_RETURN_SETTLED' not in actions
    return final['active_operation']


def staged_freshness(first,case,post,db,tech,base,op,report,directory,pids):
    from datetime import datetime, timedelta
    from app.config import approved_policy
    proof=next(row for row in post if row['source_kind']=='SIMULATOR')
    boundary=datetime.fromisoformat(proof['observed_at'])+timedelta(seconds=approved_policy()['telemetry_stale_seconds'])
    request=dict(expected_version=case()['version'],operation_id=op['id'],resolution_note='Freshness at decision')
    sessions=db.table('auth_sessions')
    # Read the witness session from the persisted attestation (the API view may redact it).
    attest=db.table('recovery_attestations')
    with db.sessions() as s:
        witness=s.scalar(select(attest.c.payload).where(attest.c.operation_id==UUID(op['id']),
            attest.c.stage=='POST_ACTION_RECEIPT',attest.c.source_kind=='CUSTOMER'))
    with ThreadPoolExecutor(1) as pool:
        with db.sessions.begin() as s:
            def now(): return s.scalar(text('select clock_timestamp()'))
            wait(lambda:now()>=boundary-timedelta(seconds=2.7),'Approach immutable receipt freshness boundary',18)
            s.execute(select(sessions.c.id).where(sessions.c.id==UUID(witness['auth_session_id'])).with_for_update())
            holder=s.scalar(text('select pg_backend_pid()'))
            future=pool.submit(first.post,base+'/settle',headers={**tech,'Idempotency-Key':str(uuid4())},json=request)
            def waiter():
                return s.scalar(text('select pid from pg_stat_activity where application_name=:name '
                    'and :holder=any(pg_blocking_pids(pid))'),dict(holder=holder,name=f'{directory.name}-8030'))
            wait(waiter,'Settlement waiting while receipt is still current',2)
            pid=waiter()
            start=now()
            assert start<boundary
            wait(lambda:now()>boundary,'Cross actual freshness deadline',4)
            release=now()
        response=future.result()
    report['freshness_wait']=dict(os_pids=pids,pg_holder=holder,pg_waiter=pid,wait_seen=start,deadline=boundary,
        release=release,status=response.status_code,code=response.json().get('code'))
    assert response.status_code==422 and response.json()['code']=='EVENT_STALE', response.text


if __name__=='__main__':
    from app.workers import device
    if not os.environ['DATABASE_SCHEMA'].startswith('phase5_test_'):
        raise RuntimeError('Expected fixture')
    directory=Path(os.environ['P8_RACE_DIR'])
    process_one=device.process_one
    def processed(session,db,event_id,*args,**kwargs):
        done=process_one(session,db,event_id,*args,**kwargs)
        watch=directory/'watch-event'
        if done and watch.exists() and watch.read_text()==str(event_id):
            marker(directory,session)
        return done
    device.process_one=processed
    device.main()
