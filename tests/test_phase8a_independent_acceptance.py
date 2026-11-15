"""Independent targeted probe: real PG and simulator boot, no custody/time edits."""
import json
from uuid import uuid4
from test_phase8a_inspection_transport import setup_inspection, facts
from simulators.device.recovery_fence import transport_inspection, flush
from simulators.device.main import Simulator
from test_phase4 import send


def test_technician_pre_confirmation_rejects_old_boot_receipt(client,environment,auth,tmp_path):
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
    url=f"/v1/swaps/{swap['id']}/recovery"
    try:
        transport_inspection(sim,task);flush(sim)
        case=client.get(url,headers=tech).json()
        receipt=case['active_operation']['attestations'][0]
        old_boot=sim.boot
        transport=sim.http._transport
        sim.close()
        sim=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'inspection.sqlite3',
                      scenario='wrong-return',transport=transport)
        assert sim.boot!=old_boot
        assert send(client,environment,sim.snapshot()).status_code==202
        projection=client.get('/v1/swaps/'+swap['id'],headers=auth('customer')).json()['recovery_confirmation']
        assert projection['confirmation_status']=='UNAVAILABLE'
        before=facts(client,swap)
        binding={'operation_id':task['operation_id'],'context_hash':task['context_hash'],
                'stage':'PRE_ACTION_INSPECTION','receipt_id':receipt['id'],'receipt_hash':receipt['payload_hash']}
        customer=client.post(url+'/confirmations',headers={**auth('customer'),'Idempotency-Key':str(uuid4())},
                            json={**binding,'confirm':True})
        assert customer.status_code==409
        key=str(uuid4())
        body={
            'expected_version':case['version'],'note':'Independent old boot refusal',
            'statement':{'kind':'TECHNICIAN_ATTEST','operation_id':task['operation_id'],
                'context_hash':task['context_hash'],'stage':'PRE_ACTION_INSPECTION',
                'receipt_id':receipt['id'],'receipt_hash':receipt['payload_hash'],
                'actual_serial':receipt['payload']['actual_serial'],'observation':'CONFIRM'}}
        result=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':key},json=body)
        replay=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':key},json=body)
        assert replay.status_code==result.status_code
        assert {k:v for k,v in replay.json().items() if k!='correlation_id'} == {k:v for k,v in result.json().items() if k!='correlation_id'}
        after=client.get(url,headers=tech).json()
        print(json.dumps({'http':result.status_code,'code':result.json().get('code'),
            'old_boot':old_boot,'new_boot':sim.boot,'projection':projection['confirmation_status'],
            'before_version':case['version'],'after_version':after['version'],
            'sources':[p['source_kind'] for p in after['active_operation']['attestations']],
            'customer_status':customer.status_code,'customer_code':customer.json().get('code'),
            'replay_status':replay.status_code,
            'protected_facts_unchanged':facts(client,swap)==before}))
        assert result.status_code in (409,422), 'Old-boot PRE receipt must not become accepted current Technician proof'
        assert after['version']==case['version']
        assert after['active_operation']['attestations']==case['active_operation']['attestations']
        assert facts(client,swap)==before
    finally:
        sim.close()
