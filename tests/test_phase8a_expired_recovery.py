"""ER-01/02 through authenticated APIs, PostgreSQL fixture, and the real model.

Use the actual operation expiry and original receipt times. Each scenario uses
a fresh simulator ledger. No updates to custody, projections or proofs.
"""
import json
import time
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from simulators.device import recovery_reconciliation as local
from simulators.device.service import perform
from test_phase4 import send
from test_phase8a_handover import prepared_action
from test_phase8a_inspection_transport import facts


@pytest.mark.parametrize('mode',['closure','successor','successor_rejected'])
def test_expired_recovery(client,environment,auth,tmp_path,mode):
    swap,sim,action,tech,device=prepared_action(client,environment,auth,tmp_path)
    url=f"/v1/swaps/{swap['id']}/recovery"
    def case():
        return client.get(url,headers=tech).json()
    def request(statement):
        return {'note':'Reconcile expired operation','statement':statement,'expected_version':case()['version']}
    def post(path,body,actor=tech,key=None):
        return client.post(url+path,headers={**actor,'Idempotency-Key':key or str(uuid4())},json=body)
    def submit(packet):
        return client.post('/v1/device/recovery-observations',headers=device,json=packet)
    def tasks():
        return client.get('/v1/device/recovery-tasks',headers=device).json()['items']
    def refresh():
        assert send(client,environment,sim.snapshot()).status_code==202
    def count(name,action_name=None):
        db=client.app.state.db
        with db.sessions() as s:
            t=db.table(name)
            query=select(t.c.id)
            if action_name: query=query.where(t.c.action==action_name)
            return len(s.execute(query).all())
    def verify_revocation(decide, actor_id):
        db = client.app.state.db
        for fault in ('session', 'station-assignment'):
            savepoint = client.app.state.test_connection.begin_nested()
            try:
                with db.sessions.begin() as session:
                    if fault == 'session':
                        tokens = db.table('auth_sessions')
                        session.execute(tokens.update().where(tokens.c.user_id == actor_id)
                                        .values(revoked_at=datetime.now(timezone.utc)))
                    else:
                        assignments = db.table('user_station_assignments')
                        session.execute(assignments.delete().where(assignments.c.user_id == actor_id))
                refused = decide()
                assert refused.status_code in (401, 403), refused.text
            finally:
                savepoint.rollback()
    try:
        before=facts(client,swap)
        old=action['operation_id']
        kind='CLOSE_NO_EFFECT' if mode=='closure' else 'REINSPECT_OPERATION'
        stmt={'kind':kind,'operation_id':old,'context_hash':action['context_hash']}
        assert post('/evidence',request(stmt)).status_code==409
        if mode!='closure':
            assert perform(sim,action,technician_token=tech['Authorization'].split()[1])=='OBSERVED'
            original=json.loads(sim.conn.execute('SELECT observation FROM service_operations').fetchone()[0])
            source=json.loads(sim.conn.execute('SELECT body FROM events WHERE id=?',(original['snapshot_event_id'],)).fetchone()[0])
            assert send(client,environment,source).status_code==202
        deadline=datetime.fromisoformat(action['expires_at'].replace('Z','+00:00')).timestamp()
        while time.time()<deadline:
            refresh()
            time.sleep(min(4,max(0,deadline-time.time())))
        refresh()
        if mode!='closure':
            # Response loss until after expiry: replay original durable history.
            assert submit(original).status_code==202
            assert submit(original).json()['duplicate']
            assert post('/evidence',request({**stmt,'kind':'CLOSE_NO_EFFECT'})).status_code==409
        key=str(uuid4()); body=request(stmt)
        result=post('/evidence',body,key=key)
        assert result.status_code==200,result.text
        assert post('/evidence',body,key=key).json()==result.json()
        assert post('/evidence',body).status_code==409
        task=tasks()[0]
        if mode=='closure':
            assert task['task_kind']=='CLOSE_NO_EFFECT'
            packet=local.close_no_effect(sim,task)
            assert local.close_no_effect(sim,task)==packet
            verify_revocation(lambda: submit(packet), UUID(action['created_by']))
            assert count('recovery_closure_receipts') == 0
            assert sim.conn.execute('SELECT state FROM recovery_station_fence').fetchone()[0]=='ACTIVE'
            with pytest.raises(RuntimeError,match='PERMANENTLY_DISABLED'):
                local.deny_guard(sim.conn,'OPERATION',old)
            with patch('app.application.recovery.audit',side_effect=RuntimeError('ROLLBACK_CLOSURE')):
                with pytest.raises(RuntimeError,match='ROLLBACK_CLOSURE'):
                    submit(packet)
            assert count('recovery_closure_receipts')==0 and not case()['active_operation']['cancelled_at']
            assert submit(packet).status_code==202
            assert submit(packet).json()['duplicate']
            assert count('audit_events','RECOVERY_NO_EFFECT_CLOSED')==1
            assert case()['active_operation']['cancelled_at']
            local.acknowledge_closure(sim,tasks()[0])
            assert sim.conn.execute('SELECT state FROM recovery_station_fence').fetchone()[0]=='CLOSED'
            assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
        else:
            assert task['task_kind']=='RECONCILE_INSPECT' and task['predecessor_id']==old
            assert post('/evidence',request({'kind':'AUTHORIZE_ACTION','operation_id':task['operation_id'],
                'context_hash':task['context_hash']})).status_code==409
            packet=local.reinspect(sim,task)
            wrong=submit({**packet,'event_id':str(uuid4()),'recipient_id':str(uuid4())})
            assert wrong.status_code in (409,422)
            boot_mismatch = submit({**packet, 'event_id':str(uuid4()), 'boot_id':str(uuid4())})
            assert boot_mismatch.status_code in (409,422)
            accepted=submit(packet)
            assert accepted.status_code==202,accepted.text
            assert submit(packet).json()['duplicate']
            op=case()['active_operation']; receipt=op['attestations'][0]
            ref={'operation_id':op['id'],'context_hash':op['context_hash'],'stage':receipt['stage'],
                 'receipt_id':receipt['id'],'receipt_hash':receipt['payload_hash']}
            assert post('/evidence',request({**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':packet['actual_serial'],
                                             'observation':'CONFIRM'})).status_code==200
            customer = auth('customer')
            projected = client.get('/v1/swaps/'+swap['id'],headers=customer).json()['recovery_confirmation']
            assert projected['stage']=='RECONCILIATION_INSPECTION'
            assert projected['receipt_id']==ref['receipt_id'] and projected['receipt_hash']==ref['receipt_hash']
            customer_ref = {k:projected[k] for k in ('operation_id','context_hash','stage','receipt_id','receipt_hash')}
            assert post('/confirmations',{**customer_ref,'confirm':mode!='successor_rejected'},customer).status_code==201
            body={'expected_version':case()['version'],'operation_id':op['id'],'resolution_note':'Foreign object only'}
            if mode=='successor_rejected':
                assert post('/settle',body).status_code == 422
                assert post('/confirmations',{**ref,'confirm':True},customer).status_code == 409
                assert not case()['active_operation']['consumed_at']
                assert count('audit_events','FOREIGN_OBJECT_RETURN_SETTLED') == 0
                assert facts(client,swap) == before and not case()['old_pin_settled']
                assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0] == 1
                return
            key=str(uuid4())
            verify_revocation(lambda: post('/settle',body), UUID(action['created_by']))
            assert count('audit_events','FOREIGN_OBJECT_RETURN_SETTLED') == 0
            with patch('app.application.recovery.audit',side_effect=RuntimeError('ROLLBACK_CHAIN')):
                with pytest.raises(RuntimeError,match='ROLLBACK_CHAIN'):
                    post('/settle',body,key=key)
            assert not case()['active_operation']['consumed_at'] and count('audit_events','FOREIGN_OBJECT_RETURN_SETTLED')==0
            result=post('/settle',body,key=key)
            assert result.status_code==200,result.text
            assert post('/settle',body,key=key).json()==result.json()
            assert count('audit_events','FOREIGN_OBJECT_RETURN_SETTLED')==1
            assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
        assert facts(client,swap)==before and not case()['old_pin_settled']
    finally:
        sim.close()
