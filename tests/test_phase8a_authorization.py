"""Authorization uses real PostgreSQL and actual simulator observations.

Positive flow waits the real physical deadline. No custody/timestamp SQL edits.
HTTP adapter is in-process: this file is NOT real-process E2E evidence.
"""
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func
from test_phase8a_inspection_transport import setup_inspection, facts
from simulators.device.recovery_fence import transport_inspection, flush, acknowledge_authorization
from test_phase5 import race_environment


def proofs(client, environment, auth, task, tech):
    url=f"/v1/swaps/{task['swap_id']}/recovery"
    case=client.get(url,headers=tech).json()
    receipt=case['active_operation']['attestations'][0]
    binding={'operation_id':task['operation_id'],'context_hash':task['context_hash'],
             'stage':'PRE_ACTION_INSPECTION','receipt_id':receipt['id'],'receipt_hash':receipt['payload_hash']}
    result=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json={
        'expected_version':case['version'],'note':'Pre-action witnessed serial and presenter',
        'statement':{**binding,'kind':'TECHNICIAN_ATTEST','actual_serial':receipt['payload']['actual_serial'],'observation':'CONFIRM'}})
    assert result.status_code==200,result.text
    result=client.post(url+'/confirmations',headers={**auth('customer'),'Idempotency-Key':str(uuid4())},
        json={**binding,'confirm':True})
    assert result.status_code==201,result.text
    return client.get(url,headers=tech).json()


def issue(client, task, tech, case, key=None):
    return client.post(f"/v1/swaps/{task['swap_id']}/recovery/evidence",
        headers={**tech,'Idempotency-Key':key or str(uuid4())},json={
        'expected_version':case['version'],'note':'Authorize transport only, no effect',
        'statement':{'kind':'AUTHORIZE_ACTION','operation_id':task['operation_id'],'context_hash':task['context_hash']}})


def test_authorization_and_ack_are_durable_idempotent_without_physical_effect(client,environment,auth,tmp_path,monkeypatch):
    from app.application import recovery_authorization
    original_refuse=recovery_authorization.refuse
    def diagnostic_refuse(*args,**kwargs):
        import traceback
        traceback.print_stack(limit=5)
        return original_refuse(*args,**kwargs)
    monkeypatch.setattr(recovery_authorization,'refuse',diagnostic_refuse)
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path,wait_for_physical_deadline=True)
    try:
        transport_inspection(sim,task); flush(sim)
        case=proofs(client,environment,auth,task,tech)
        before=facts(client,swap); slots=sim.slots()
        key=str(uuid4())
        from unittest.mock import patch
        from datetime import timedelta
        from app.application import recovery
        # Let current snapshot/actors pass, then expire evidence during the
        # later historical-command reads. Check the final decision, not input.
        read_row=recovery.assets.get_row
        for seconds,code in ((16,'EVENT_STALE'),(121,'RECOVERY_OPERATION_EXPIRED')):
            real_clock=recovery.utcnow
            def slow_history(session,db,name,identity,**kwargs):
                value=read_row(session,db,name,identity,**kwargs)
                if name=='device_events':
                    recovery.utcnow=lambda:real_clock()+timedelta(seconds=seconds)
                return value
            with patch('app.application.recovery.utcnow',real_clock), patch('app.application.recovery.assets.get_row',side_effect=slow_history):
                refused=issue(client,task,tech,case)
                assert refused.status_code in (409,422) and refused.json()['code']==code,refused.text
            assert facts(client,swap)==before
        with patch('app.application.recovery.audit',side_effect=RuntimeError('TEST_AUTHORIZATION_AUDIT_ROLLBACK')):
            with pytest.raises(RuntimeError,match='TEST_AUTHORIZATION_AUDIT_ROLLBACK'):
                issue(client,task,tech,case,key)
        assert facts(client,swap)==before
        db=client.app.state.db
        with db.sessions() as s:
            assert s.scalar(select(func.count()).select_from(db.table('recovery_action_authorizations')))==0
        result=issue(client,task,tech,case,key)
        assert result.status_code==200,result.text
        permit=result.json()['active_operation']['authorization']
        assert permit and permit['effect_allowed'] is False and not permit['transport_acknowledged']
        assert issue(client,task,tech,case,key).json()==result.json()
        assert issue(client,task,tech,case).status_code==409
        tasks=client.get('/v1/device/recovery-tasks',headers={'X-Device-Key':environment['keys']['S01']})
        assert tasks.status_code==200,tasks.text
        intent=tasks.json()['items'][0]
        assert intent['task_kind']=='AUTHORIZATION_INTENT' and intent['effect_allowed'] is False
        packet=acknowledge_authorization(sim,intent)
        assert acknowledge_authorization(sim,intent)==packet
        wrong={**packet,'event_id':str(uuid4()),'authorization_hash':'e'*64}
        refused=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json=wrong)
        assert refused.status_code==409
        corrected={**packet,'event_id':wrong['event_id']}
        assert client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json=corrected).status_code==409
        # DB commits receipt but local outbox never sees/records its response.
        accepted=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json=packet)
        assert accepted.status_code==202 and not accepted.json()['duplicate'],accepted.text
        assert sim.conn.execute('SELECT sent FROM recovery_authorization_outbox').fetchone()[0]==0
        sim.close()
        import json, httpx
        from simulators.device.main import Simulator
        def respond(request):
            args={'headers':{'X-Device-Key':environment['keys']['S01']}}
            if request.content:args['json']=json.loads(request.content)
            result=getattr(client,request.method.lower())(request.url.path,**args)
            return httpx.Response(result.status_code,json=result.json())
        sim=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'inspection.sqlite3',transport=httpx.MockTransport(respond))
        assert sim.boot!=packet['boot_id']
        assert acknowledge_authorization(sim,intent)==packet # Same durable history, not a new permit.
        flush(sim)
        ack=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json=packet)
        assert ack.status_code==202 and ack.json()['duplicate'],ack.text
        changed=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},
            json={**packet,'authorization_hash':'f'*64})
        assert changed.status_code==409
        current=client.get(f"/v1/swaps/{swap['id']}/recovery",headers=tech).json()
        assert current['active_operation']['authorization']['transport_acknowledged']
        assert facts(client,swap)==before and sim.slots()==slots
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
        assert sim.conn.execute('SELECT count(*) FROM recovery_authorization_outbox').fetchone()[0]==1
        assert sim.conn.execute('SELECT sum(effects) FROM commands').fetchone()[0]==1 # Original wrong return only.
        db=client.app.state.db
        with db.sessions() as s:
            for name in ('recovery_action_authorizations','recovery_authorization_acks'):
                assert s.scalar(select(func.count()).select_from(db.table(name)))==1
        from test_phase4 import send
        snapshot=sim.snapshot()
        assert send(client,environment,snapshot).status_code==202
        tasks=client.get('/v1/device/recovery-tasks',headers={'X-Device-Key':environment['keys']['S01']})
        assert tasks.status_code==200 and tasks.json()['items']==[]
        assert sim.conn.execute('SELECT state FROM recovery_station_fence').fetchone()[0]=='ACTIVE'
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
    finally:sim.close()


def test_two_backend_apps_authorize_once_on_distinct_pg_connections(race_environment,tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from app.main import create_app
    env=race_environment
    with TestClient(create_app(env['settings'])) as first, TestClient(create_app(env['settings'])) as second:
        def auth(name):
            result=first.post('/v1/auth/login',json={'username':name,'password':env['passwords'][name]})
            assert result.status_code==200
            return {'Authorization':'Bearer '+result.json()['access_token']}
        swap,sim,task,tech=setup_inspection(first,env,auth,tmp_path,wait_for_physical_deadline=True,committed=True)
        try:
            transport_inspection(sim,task);flush(sim)
            case=proofs(first,env,auth,task,tech);before=facts(first,swap)
            with first.app.state.db.sessions() as a, second.app.state.db.sessions() as b:
                assert a.scalar(text('select pg_backend_pid()'))!=b.scalar(text('select pg_backend_pid()'))
            gate=Barrier(2)
            def submit(http):
                gate.wait(timeout=10)
                return issue(http,task,tech,case)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(submit,[first,second]))
            assert sorted(r.status_code for r in results)==[200,409],[r.text for r in results]
            assert facts(first,swap)==before
            db=first.app.state.db
            with db.sessions() as s:
                p=db.table('recovery_action_authorizations'); a=db.table('audit_events')
                assert s.scalar(select(func.count()).select_from(p).where(p.c.operation_id==UUID(task['operation_id'])))==1
                assert s.scalar(select(func.count()).select_from(a).where(a.c.action=='RECOVERY_AUTHORIZATION_INTENT_CREATED'))==1
        finally:sim.close()


@pytest.mark.parametrize('fault',['missing_proof','too_early','wrong_stage','wrong_receipt','customer_reject',
    'expired','stale','technician_revoked','customer_revoked','assignment_revoked','role_changed'])
def test_authorization_refusal_does_not_change_resources(client,environment,auth,tmp_path,fault,monkeypatch):
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
    try:
        transport_inspection(sim,task);flush(sim)
        url=f"/v1/swaps/{swap['id']}/recovery"
        case=client.get(url,headers=tech).json()
        before=facts(client,swap)
        if fault in ('too_early','expired','stale','technician_revoked','customer_revoked','assignment_revoked','role_changed'):
            case=proofs(client,environment,auth,task,tech)
            if fault in ('expired','stale'):
                from datetime import timedelta
                from app.application import recovery
                clock=recovery.utcnow()+timedelta(seconds=121 if fault=='expired' else 16)
                monkeypatch.setattr(recovery,'utcnow',lambda:clock)
            elif fault in ('assignment_revoked','role_changed'):
                admin=auth('admin')
                changed=client.put(f"/v1/users/{task['created_by']}/station-assignments",
                    headers={**admin,'Idempotency-Key':str(uuid4())},json={'station_ids':[]})
                assert changed.status_code==200,changed.text
                if fault=='role_changed':
                    result=client.patch(f"/v1/users/{task['created_by']}",headers={**admin,'Idempotency-Key':str(uuid4())},
                        json={'expected_version':changed.json()['version'],'role':'ADMIN'})
                    assert result.status_code==200,result.text
            elif fault.endswith('_revoked'):
                from sqlalchemy import update
                from app.application.identity import utcnow
                role=fault.split('_')[0].upper()
                item=next(p for p in case['active_operation']['attestations'] if p['source_kind']==role)
                db=client.app.state.db
                with db.sessions.begin() as s:
                    t=db.table('auth_sessions')
                    s.execute(update(t).where(t.c.id==UUID(item['payload']['auth_session_id'])).values(revoked_at=utcnow()))
        elif fault in ('wrong_stage','wrong_receipt','customer_reject'):
            receipt=case['active_operation']['attestations'][0]
            body={'operation_id':task['operation_id'],'context_hash':task['context_hash'],
                'stage':'POST_ACTION_RECEIPT' if fault=='wrong_stage' else 'PRE_ACTION_INSPECTION',
                'receipt_id':receipt['id'],'receipt_hash':'f'*64 if fault=='wrong_receipt' else receipt['payload_hash'],
                'confirm':fault!='customer_reject'}
            response=client.post(url+'/confirmations',headers={**auth('customer'),'Idempotency-Key':str(uuid4())},json=body)
            # POST is now a supported stage, but a PRE receipt cannot satisfy it.
            assert response.status_code==(201 if fault=='customer_reject' else 409),response.text
            case=client.get(url,headers=tech).json()
        result=issue(client,task,tech,case)
        assert result.status_code in ((401,403) if fault.endswith('_revoked') or fault=='role_changed' else (409,422)),result.text
        assert facts(client,swap)==before
        db=client.app.state.db
        with db.sessions() as s:
            assert s.scalar(select(func.count()).select_from(db.table('recovery_action_authorizations')))==0
    finally:sim.close()
