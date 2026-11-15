from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4,UUID
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import create_app
from test_phase5 import race_environment,login
from test_phase8a_inspection_transport import setup_inspection,facts
from simulators.device.recovery_fence import transport_inspection,flush

def request(case,task,observation='CONFIRM'):
    p=case['active_operation']['attestations'][0]
    return {'expected_version':case['version'],'note':'IA01 regression',
        'statement':{'kind':'TECHNICIAN_ATTEST','operation_id':task['operation_id'],
            'context_hash':task['context_hash'],'stage':'PRE_ACTION_INSPECTION',
            'receipt_id':p['id'],'receipt_hash':p['payload_hash'],
            'actual_serial':p['payload']['actual_serial'],'observation':observation}}

@pytest.mark.parametrize('observation',['CONFIRM','REJECT'])
def test_same_boot_replay_and_audit_rollback(client,environment,auth,tmp_path,observation):
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
    try:
        transport_inspection(sim,task);flush(sim)
        url=f"/v1/swaps/{swap['id']}/recovery"
        before=client.get(url,headers=tech).json(); body=request(before,task,observation)
        protected=facts(client,swap);key=str(uuid4())
        with patch('app.application.recovery.audit',side_effect=RuntimeError('IA01_AUDIT_ROLLBACK')):
            with pytest.raises(RuntimeError,match='IA01_AUDIT_ROLLBACK'):
                client.post(url+'/evidence',headers={**tech,'Idempotency-Key':key},json=body)
        assert client.get(url,headers=tech).json()==before
        result=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':key},json=body)
        assert result.status_code==200,result.text
        assert client.post(url+'/evidence',headers={**tech,'Idempotency-Key':key},json=body).json()==result.json()
        assert result.json()['version']==before['version']+1
        assert facts(client,swap)==protected
    finally:sim.close()

def test_two_backends_store_one_same_boot_technician_proof(race_environment,tmp_path):
    env=race_environment
    with TestClient(create_app(env['settings'])) as first,TestClient(create_app(env['settings'])) as second:
        swap,sim,task,tech=setup_inspection(first,env,lambda role:login(first,env,role),tmp_path,committed=True)
        try:
            transport_inspection(sim,task);flush(sim)
            url=f"/v1/swaps/{swap['id']}/recovery"
            before=first.get(url,headers=tech).json();body=request(before,task)
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses=list(pool.map(lambda http:http.post(url+'/evidence',
                    headers={**tech,'Idempotency-Key':str(uuid4())},json=body),[first,second]))
            assert sorted(r.status_code for r in responses)==[200,409]
            after=first.get(url,headers=tech).json()
            assert after['version']==before['version']+1
            assert [p['source_kind'] for p in after['active_operation']['attestations']].count('TECHNICIAN')==1
        finally:sim.close()

@pytest.mark.parametrize('delay,code',[(16,'EVENT_STALE'),(121,'RECOVERY_OPERATION_EXPIRED')])
def test_pre_rechecks_decision_time_after_provenance_reads(client,environment,auth,tmp_path,delay,code):
    from datetime import timedelta
    from app.application import recovery
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
    try:
        transport_inspection(sim,task);flush(sim)
        url=f"/v1/swaps/{swap['id']}/recovery"
        before=client.get(url,headers=tech).json();protected=facts(client,swap)
        original=recovery.assets.get_row; clock=recovery.utcnow
        def read(session,db,name,identity,**kwargs):
            value=original(session,db,name,identity,**kwargs)
            if name=='device_events':
                recovery.utcnow=lambda:clock()+timedelta(seconds=delay)
            return value
        # Simulate elapsed decision time only, never alter persisted observation
        # timestamps. Actual lock/OS-process ordering is covered separately.
        with patch('app.application.recovery.utcnow',clock),patch('app.application.recovery.assets.get_row',side_effect=read):
            result=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json=request(before,task))
        assert result.status_code in (409,422) and result.json()['code']==code,result.text
        assert client.get(url,headers=tech).json()==before
        assert facts(client,swap)==protected
    finally:sim.close()
