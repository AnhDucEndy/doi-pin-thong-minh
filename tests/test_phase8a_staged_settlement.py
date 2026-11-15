"""Actual staged foreign effect, then final-decision guards on isolated PG."""
import json
from datetime import timedelta
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest
from sqlalchemy import select, update
from test_phase8a_handover import prepared_action
from test_phase8a_inspection_transport import facts
from test_phase4 import send
from simulators.device.service import perform


@pytest.mark.parametrize('confirm',[True,False,'boot','conflicting-model'])
def test_foreign_settlement_final_guards_atomicity_and_replay(client,environment,auth,tmp_path,confirm):
    from app.application import recovery as r
    swap,sim,task,tech,device=prepared_action(client,environment,auth,tmp_path)
    url=f"/v1/swaps/{swap['id']}/recovery"
    customer=auth('customer'); db=client.app.state.db
    def case():return client.get(url,headers=tech).json()
    def submit(body,key=None):
        return client.post(url+'/settle',headers={**tech,'Idempotency-Key':key or str(uuid4())},json=body)
    def settled_count():
        with db.sessions() as s:
            t=db.table('audit_events')
            return len(s.execute(select(t.c.id).where(t.c.action=='FOREIGN_OBJECT_RETURN_SETTLED')).all())
    try:
        before=facts(client,swap)
        perform(sim,task,technician_token=tech['Authorization'].split(' ',1)[1])
        packet=json.loads(sim.conn.execute('SELECT observation FROM service_operations').fetchone()[0])
        snapshot=json.loads(sim.conn.execute('SELECT body FROM events WHERE id=?',(packet['snapshot_event_id'],)).fetchone()[0])
        assert send(client,environment,snapshot).status_code==202
        receipt=client.post('/v1/device/recovery-observations',headers=device,json=packet)
        assert receipt.status_code==202,receipt.text
        assert send(client,environment,sim.snapshot()).status_code==202
        def body():return {'expected_version':case()['version'],'operation_id':task['operation_id'],'resolution_note':'Foreign object only'}
        rejected=submit(body());assert rejected.status_code==422,rejected.text
        post=next(p for p in case()['active_operation']['attestations'] if p['stage']=='POST_ACTION_RECEIPT')
        binding={'operation_id':task['operation_id'],'context_hash':task['context_hash'],
            'stage':'POST_ACTION_RECEIPT','receipt_id':post['id'],'receipt_hash':post['payload_hash']}
        result=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json={
            'expected_version':case()['version'],'note':'Physical receipt witnessed',
            'statement':{**binding,'kind':'TECHNICIAN_ATTEST','actual_serial':packet['actual_serial'],'observation':'CONFIRM'}})
        assert result.status_code==200,result.text
        result=client.post(url+'/confirmations',headers={**customer,'Idempotency-Key':str(uuid4())},json={**binding,'confirm':confirm is not False})
        assert result.status_code==201,result.text
        request=body()
        legacy=submit({'expected_version':request['expected_version'],'evidence_event_id':str(uuid4()),
            'resolution_note':'Legacy request cannot bind staged proof'})
        assert legacy.status_code==409 and legacy.json()['code']=='RECOVERY_STAGE_CONFLICT',legacy.text
        if confirm in ('boot','conflicting-model'):
            if confirm=='boot':
                from simulators.device.main import Simulator
                transport=sim.http._transport;sim.close()
                sim=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'inspection.sqlite3',transport=transport)
            else:
                # Fault the actual simulator slot model, then let its normal
                # snapshot path observe it. Never forge Backend evidence/custody.
                slot=sim.conn.execute('SELECT body FROM slots WHERE id=?',(task['return_compartment_id'],)).fetchone()
                model=json.loads(slot[0]);model.update(door_state='OPEN',lock_released=True)
                sim.conn.execute('UPDATE slots SET body=? WHERE id=?',(json.dumps(model),task['return_compartment_id']))
                sim.conn.commit()
            assert send(client,environment,sim.snapshot()).status_code==202
            # Exercise current physical-proof guards, not merely a stale case
            # version after the worker processed the contradictory snapshot.
            request['expected_version']=case()['version']
            refused=submit(request);assert refused.status_code in (409,422),refused.text
            assert refused.json()['code']!='VERSION_CONFLICT',refused.text
            assert facts(client,swap)==before and settled_count()==0
            assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
            return
        if not confirm:
            rejected=submit(request);assert rejected.status_code==422,rejected.text
            assert facts(client,swap)==before and settled_count()==0
            return
        assert submit({**request,'expected_version':request['expected_version']-1}).status_code==409
        clock=r.utcnow
        for seconds in (16,121):
            with patch('app.application.recovery.utcnow',lambda:clock()+timedelta(seconds=seconds)):
                response=submit(request);assert response.status_code in (409,422),response.text
        for fault in ('customer-session','tech-role','assignment','displaced'):
            save=client.app.state.test_connection.begin_nested()
            try:
                with db.sessions.begin() as s:
                    if fault=='customer-session':
                        t=db.table('auth_sessions');s.execute(update(t).where(t.c.user_id==UUID(task['customer_id'])).values(revoked_at=clock()))
                    elif fault=='tech-role':
                        t=db.table('users');s.execute(update(t).where(t.c.id==UUID(task['created_by'])).values(role='ADMIN'))
                    elif fault=='assignment':
                        t=db.table('user_station_assignments');s.execute(t.delete().where(t.c.user_id==UUID(task['created_by'])))
                    else:
                        t=db.table('recovery_cases');s.execute(update(t).where(t.c.swap_id==UUID(swap['id'])).values(operation_id=None))
                response=submit(request);assert response.status_code in (401,403,409),response.text
            finally:save.rollback()
        key=str(uuid4())
        with patch('app.application.recovery.audit',side_effect=RuntimeError('SETTLEMENT_ROLLBACK')):
            with pytest.raises(RuntimeError,match='SETTLEMENT_ROLLBACK'):submit(request,key)
        assert case()['active_operation']['consumed_at'] is None
        assert settled_count()==0 and facts(client,swap)==before
        accepted=submit(request,key);assert accepted.status_code==200,accepted.text
        assert accepted.json()['active_operation']['consumed_at']
        assert accepted.json()['state']=='EVIDENCE_RECORDED' and not accepted.json()['old_pin_settled']
        assert accepted.json()['new_pin_delivered']!='YES'
        assert submit(request,key).json()==accepted.json()
        assert submit({**request,'resolution_note':'changed'},key).status_code==409
        assert submit(request).status_code==409
        assert settled_count()==1 and facts(client,swap)==before
        assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
    finally:sim.close()
