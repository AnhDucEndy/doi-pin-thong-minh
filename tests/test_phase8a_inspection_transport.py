"""PostgreSQL/API + actual simulator model transport; not OS-process E2E."""
from copy import deepcopy
import json
from uuid import UUID, uuid4
import httpx
import pytest
from sqlalchemy import select
from app.seed import demo_id
from simulators.device.main import Simulator
from simulators.device.service import perform
from simulators.device.recovery_fence import transport_inspection, flush
from test_phase7 import paid, drive
from test_phase4 import send, row


def setup_inspection(client, environment, auth, tmp_path, *, wait_for_physical_deadline=False, committed=False):
    if committed:
        from test_phase6 import book, consent, outcome
        from app.workers import payment
        actor = auth('customer')
        swap = book(client, environment, actor, environment['seed_db'])
        assert consent(client, actor, swap).status_code == 202
        payment.tick(client.app.state.db, transport=outcome)
    else:
        swap = paid(client, environment, auth)
    if not wait_for_physical_deadline:
        drive(client, swap['id'])
    def respond(request):
        method = getattr(client, request.method.lower())
        args = {'headers': {'X-Device-Key': environment['keys']['S01']}}
        if request.content:
            args['json'] = json.loads(request.content)
        result = method(request.url.path, **args)
        return httpx.Response(result.status_code, json=result.json())
    sim = Simulator('S01', environment['keys']['S01'], ledger=tmp_path/'inspection.sqlite3',
                    scenario='wrong-return', transport=httpx.MockTransport(respond))
    def ingest():
        for record in sim.conn.execute('SELECT body FROM events WHERE sent=0 ORDER BY rowid').fetchall():
            packet = json.loads(record['body'])
            response = send(client, environment, packet)
            assert response.status_code==202, response.text
            sim.conn.execute('UPDATE events SET sent=1 WHERE id=?',(packet['event_id'],))
        sim.conn.commit()
    if wait_for_physical_deadline:
        # Positive authorization needs authentic accepted wrong-return history,
        # not commands dispatched to the previous boot before the simulator joins.
        sim.snapshot(); ingest()
        for slot in sim.slots():
            if slot['battery_id']:
                sim.emit('TELEMETRY', {'battery_id':slot['battery_id'],'soc':90,'soh':95,
                    'temperature_c':25,'fault_codes':[]}, compartment_id=slot['compartment_id'])
        ingest()
        drive(client, swap['id'])
    commands = client.get('/v1/device/commands',headers={'X-Device-Key':environment['keys']['S01']}).json()['items']
    assert len(commands)==1
    sim.snapshot(); ingest()
    sim.handle(commands[0]); ingest()
    if wait_for_physical_deadline:
        import time
        from datetime import datetime, timezone
        command = row(client, 'device_commands', UUID(commands[0]['id']))
        deadline = command['created_at'].timestamp() + 60
        while datetime.now(timezone.utc).timestamp() <= deadline:
            sim.snapshot(); ingest()
            time.sleep(min(5, max(0.05, deadline-datetime.now(timezone.utc).timestamp())))
        from app.workers.device import tick
        from app.config import approved_policy
        tick(client.app.state.db, approved_policy())
    sim.snapshot(); ingest()
    tech=auth('technician')
    url=f"/v1/swaps/{swap['id']}/recovery"
    case=client.get(url,headers=tech).json()
    response=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json={
        'expected_version':case['version'],'note':'Read actual foreign model',
        'statement':{'kind':'BEGIN_OPERATION','purpose':'RETURN_FOREIGN_OBJECT'}})
    assert response.status_code==200,response.text
    tasks=client.get('/v1/device/recovery-tasks',headers={'X-Device-Key':environment['keys']['S01']})
    assert tasks.status_code==200,tasks.text
    task=tasks.json()['items'][0]
    assert task['task_kind']=='INSPECT' and task['protocol_version']=='0.2'
    return swap,sim,task,tech


def facts(client,swap):
    db=client.app.state.db
    with db.sessions() as s:
        holds=db.table('resource_reservations');payments=db.table('payments')
        return (row(client,'batteries',UUID(swap['old_battery_id'])),
            row(client,'batteries',UUID(swap['new_battery_id'])),
            list(s.execute(select(holds).where(holds.c.swap_id==UUID(swap['id'])))),
            list(s.execute(select(payments).where(payments.c.swap_id==UUID(swap['id'])))))


def test_real_model_inspection_transport_is_readonly_idempotent_and_stage_bound(client,environment,auth,tmp_path):
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap);slots=sim.slots()
        assert perform(sim,task,technician_token='not-used-for-readonly-inspection')=='INSPECTED'
        packet=transport_inspection(sim,task)
        assert packet['actual_serial']=='SIMULATED-WRONG-BATTERY'
        flush(sim)
        assert sim.conn.execute('SELECT sent FROM recovery_inspection_outbox').fetchone()[0]==1
        result=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json=packet)
        assert result.status_code==202 and result.json()['duplicate']
        changed=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json={**packet,'actual_serial':'CHANGED'})
        assert changed.status_code==409 and changed.json()['code']=='IDEMPOTENCY_CONFLICT'
        out_of_order=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json={**packet,'event_id':str(uuid4())})
        assert out_of_order.status_code==422 and out_of_order.json()['code']=='EVENT_OUT_OF_ORDER'
        assert facts(client,swap)==before and sim.slots()==slots
        case=client.get(f"/v1/swaps/{swap['id']}/recovery",headers=tech).json()
        attest=case['active_operation']['attestations']
        assert len(attest)==1 and attest[0]['stage']=='PRE_ACTION_INSPECTION'
        assert attest[0]['payload']['effect_count_delta']==0
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
        for path,body in [('settle',{'expected_version':case['version'],'operation_id':task['operation_id'],'resolution_note':'must not hand over'})]:
            refused=client.post(f"/v1/swaps/{swap['id']}/recovery/{path}",headers={**tech,'Idempotency-Key':str(uuid4())},json=body)
            assert refused.status_code==409
    finally:
        sim.close()


@pytest.mark.parametrize('fault',['context','serial','boot','seq','station','key','stage'])
def test_invalid_inspection_cannot_become_accepted_by_replay(client,environment,auth,tmp_path,fault):
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
    try:
        original=transport_inspection(sim,task); packet=deepcopy(original)
        key=environment['keys']['S01']
        if fault=='context':packet['context_hash']='f'*64
        if fault=='serial':packet['actual_serial']='WRONG'
        if fault=='boot':packet['boot_id']=str(uuid4())
        if fault=='seq':packet['seq']=0
        if fault=='station':key=environment['keys']['S02']
        if fault=='key':key='not-a-valid-device-key'
        if fault=='stage':packet['stage']='POST_ACTION_RECEIPT'
        before=facts(client,swap)
        result=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':key},json=packet)
        assert result.status_code in (401,403,409,422),result.text
        again=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':key},json=packet)
        assert again.status_code==result.status_code
        if fault in ('context','serial','boot'):
            changed=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':key},json=original)
            assert changed.status_code==409
        assert facts(client,swap)==before
    finally:sim.close()


def test_restart_retains_fence_and_original_receipt(client,environment,auth,tmp_path):
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
    packet=transport_inspection(sim,task)
    sim.close()
    restarted=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'inspection.sqlite3')
    try:
        assert restarted.boot!=packet['boot_id']
        assert transport_inspection(restarted,task)==packet
        assert restarted.conn.execute("SELECT state FROM recovery_station_fence").fetchone()[0]=='ACTIVE'
        result=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json=packet)
        assert result.status_code==202,result.text
    finally:restarted.close()
