"""Activated handover: actual simulator model and isolated PostgreSQL, no custody SQL."""
import json
from uuid import uuid4
from unittest.mock import patch
import httpx
import pytest
from test_phase8a_inspection_transport import setup_inspection, facts
from test_phase8a_authorization import proofs, issue
from test_phase4 import send
from simulators.device.recovery_fence import transport_inspection, flush as flush_fence, acknowledge_authorization
from simulators.device.service import perform, flush


def prepared_action(client, environment, auth, tmp_path):
    swap, sim, task, tech = setup_inspection(client,environment,auth,tmp_path,wait_for_physical_deadline=True)
    transport_inspection(sim,task); flush_fence(sim)
    case = proofs(client,environment,auth,task,tech)
    result = issue(client,task,tech,case)
    assert result.status_code == 200, result.text
    device = {'X-Device-Key':environment['keys']['S01']}
    intent = client.get('/v1/device/recovery-tasks',headers=device).json()['items'][0]
    packet = acknowledge_authorization(sim,intent)
    ack = client.post('/v1/device/recovery-observations',headers=device,json=packet)
    assert ack.status_code == 202, ack.text
    case = client.get(f"/v1/swaps/{swap['id']}/recovery",headers=tech).json()
    body = {'expected_version':case['version'],'note':'Explicit activated foreign return',
        'statement':{'kind':'AUTHORIZE_ACTION','phase':'ACTIVATE','operation_id':task['operation_id'],
            'context_hash':task['context_hash'],'authorization_id':intent['authorization_id'],
            'acknowledgment_id':ack.json()['id']}}
    url = f"/v1/swaps/{swap['id']}/recovery/evidence"
    headers = {**tech,'Idempotency-Key':str(uuid4())}
    before = facts(client,swap)
    with patch('app.application.recovery.audit',side_effect=RuntimeError('ACTIVATION_AUDIT_ROLLBACK')):
        with pytest.raises(RuntimeError,match='ACTIVATION_AUDIT_ROLLBACK'):
            client.post(url,headers=headers,json=body)
    assert facts(client,swap)==before
    result = client.post(url,headers=headers,json=body)
    assert result.status_code == 200,result.text
    assert client.post(url,headers=headers,json=body).json()==result.json()
    assert client.post(url,headers={**tech,'Idempotency-Key':str(uuid4())},json=body).status_code==409
    action = client.get('/v1/device/recovery-tasks',headers=device).json()['items'][0]
    assert action['task_kind']=='ACTION' and action['effect_allowed'] is True
    assert result.json()['active_operation']['authorization']['effect_allowed'] is False
    # The adapter passes the real human bearer separately from Device-Key.
    def respond(request):
        args={'headers':{'X-Device-Key':environment['keys']['S01']}}
        if request.headers.get('Authorization'):
            args['headers']['Authorization']=request.headers['Authorization']
        if request.content: args['json']=json.loads(request.content)
        response=getattr(client,request.method.lower())(request.url.path,**args)
        return httpx.Response(response.status_code,json=response.json())
    sim.http.close()
    sim.http=httpx.Client(base_url='http://localhost',transport=httpx.MockTransport(respond))
    return swap,sim,action,tech,device


@pytest.mark.parametrize('restart_before_receipt',[False,True])
def test_handover_receipt_single_effect_rollback_and_replay(client,environment,auth,tmp_path,restart_before_receipt):
    swap,sim,task,tech,device=prepared_action(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap)
        token=tech['Authorization'].split(' ',1)[1]
        with pytest.raises((ValueError,httpx.HTTPStatusError)):
            perform(sim,task,technician_token=auth('admin')['Authorization'].split(' ',1)[1])
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
        with patch('simulators.device.recovery_handover.validate',side_effect=RuntimeError('CRASH_BEFORE_PREPARED')):
            with pytest.raises(RuntimeError,match='CRASH_BEFORE_PREPARED'):
                perform(sim,task,technician_token=token)
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
        with patch.object(sim,'boot',str(uuid4())):
            with pytest.raises(ValueError,match='ACTION_NOT_AUTHORIZED'):
                perform(sim,task,technician_token=token)
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
        # Final local expiry interlock is independent of a successful HTTP poll.
        from simulators.device.recovery_handover import validate
        from datetime import datetime, timezone, timedelta
        class ExpiredClock:
            @staticmethod
            def now(zone): return datetime.now(timezone.utc)+timedelta(minutes=3)
            fromisoformat=staticmethod(datetime.fromisoformat)
        sim.conn.execute('BEGIN IMMEDIATE')
        try:
            with patch('simulators.device.recovery_handover.datetime',ExpiredClock):
                with pytest.raises(ValueError,match='ACTION_NOT_AUTHORIZED'):
                    validate(sim,task)
        finally:
            sim.conn.rollback()
        assert perform(sim,task,technician_token=token)=='OBSERVED'
        packet=json.loads(sim.conn.execute('SELECT observation FROM service_operations').fetchone()[0])
        assert packet['actual_serial']=='SIMULATED-WRONG-BATTERY'
        assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
        assert perform(sim,task,technician_token=token)=='OBSERVED'
        snapshot=json.loads(sim.conn.execute('SELECT body FROM events WHERE id=?',(packet['snapshot_event_id'],)).fetchone()[0])
        assert send(client,environment,snapshot).status_code==202
        if restart_before_receipt:
            from simulators.device.main import Simulator
            transport=sim.http._transport
            sim.close()
            sim=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'inspection.sqlite3',transport=transport)
            assert sim.boot!=packet['boot_id']
            assert send(client,environment,sim.snapshot()).status_code==202
            assert perform(sim,task,technician_token='replay-does-not-authorize')=='OBSERVED'
        # A semantic rejection stays rejected. A distinct correct event can be
        # stored, but changing/reusing the rejected event ID is never allowed.
        wrong={**packet,'event_id':str(uuid4()),'recipient_id':str(uuid4())}
        refused=client.post('/v1/device/recovery-observations',headers=device,json=wrong)
        assert refused.status_code==422
        assert client.post('/v1/device/recovery-observations',headers=device,
            json={**packet,'event_id':wrong['event_id']}).status_code==409
        with patch('app.application.recovery.audit',side_effect=RuntimeError('RECEIPT_AUDIT_ROLLBACK')):
            with pytest.raises(RuntimeError,match='RECEIPT_AUDIT_ROLLBACK'):
                client.post('/v1/device/recovery-observations',headers=device,json=packet)
        assert facts(client,swap)==before
        accepted=client.post('/v1/device/recovery-observations',headers=device,json=packet)
        assert accepted.status_code==202,accepted.text
        replay=client.post('/v1/device/recovery-observations',headers=device,json=packet)
        assert replay.status_code==202 and replay.json()['duplicate']
        assert client.post('/v1/device/recovery-observations',headers=device,
            json={**packet,'actual_serial':'OTHER'}).status_code==409
        flush(sim)
        assert sim.conn.execute('SELECT sent FROM service_operations').fetchone()[0]==1
        assert facts(client,swap)==before
        case=client.get(f"/v1/swaps/{swap['id']}/recovery",headers=tech).json()
        assert len([a for a in case['active_operation']['attestations'] if a['stage']=='POST_ACTION_RECEIPT'])==1
        assert not case['old_pin_settled']
        assert sim.conn.execute("SELECT count(*) FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()[0]==1
    finally:
        sim.close()


@pytest.mark.parametrize('boundary',['after_prepared','during_model_transaction'])
def test_prepared_crash_never_reexecutes_effect(client,environment,auth,tmp_path,boundary):
    swap,sim,task,tech,device=prepared_action(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap); slots=sim.slots()
        token=tech['Authorization'].split(' ',1)[1]
        if boundary=='after_prepared':
            with pytest.raises(RuntimeError,match='CRASH_AFTER_PREPARED'):
                perform(sim,task,technician_token=token,crash_after_prepared=True)
        else:
            with patch.object(sim,'snapshot',side_effect=RuntimeError('CRASH_MODEL_BEFORE_COMMIT')):
                with pytest.raises(RuntimeError,match='CRASH_MODEL_BEFORE_COMMIT'):
                    perform(sim,task,technician_token=token)
        assert perform(sim,task,technician_token='unused-replay')=='UNKNOWN'
        assert sim.slots()==slots and facts(client,swap)==before
        assert sim.conn.execute('SELECT state,effects FROM service_operations').fetchone()[:]==('UNKNOWN',0)
        assert sim.conn.execute('SELECT state FROM recovery_action_ledger').fetchone()[0]=='PREPARED'
        from simulators.device.main import Simulator
        sim.close()
        sim=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'inspection.sqlite3')
        assert perform(sim,task,technician_token='unused-replay')=='UNKNOWN'
        assert sim.slots()==slots
    finally:
        sim.close()


def test_activated_permit_revoked_before_prepared_cannot_move_object(client,environment,auth,tmp_path):
    """Legal one-way revocation fixture; no custody, source or clock rewrite."""
    from sqlalchemy import update
    from uuid import UUID
    from app.application.identity import utcnow
    swap,sim,task,tech,device=prepared_action(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap); slots=sim.slots()
        db=client.app.state.db
        with db.sessions.begin() as session:
            table=db.table('recovery_action_authorizations')
            session.execute(update(table).where(table.c.id==UUID(task['authorization_id'])).values(revoked_at=utcnow()))
        assert client.get('/v1/device/recovery-tasks',headers=device).json()['items']==[]
        with pytest.raises(ValueError,match='SERVICE_TASK_NOT_AUTHORIZED'):
            perform(sim,task,technician_token=tech['Authorization'].split(' ',1)[1])
        assert sim.slots()==slots and facts(client,swap)==before
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
        assert sim.conn.execute("SELECT state FROM recovery_station_fence").fetchone()[0]=='ACTIVE'
    finally:
        sim.close()
