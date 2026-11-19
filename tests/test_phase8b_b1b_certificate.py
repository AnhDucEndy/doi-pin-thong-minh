"""Current independent proof -> Backend certificate. No SQL positive facts."""
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest
from sqlalchemy import select

from test_phase1 import headers
from test_phase8b_b1b_no_delivery import physical_review,begin,inspect,reference,facts


def three_sources(client,environment,auth,tmp_path,*,confirmed=True):
    swap,sim,customer,tech=physical_review(client,environment,auth,tmp_path)
    try:
        case=begin(client,swap,tech)
        task,packet,receipt=inspect(client,environment,sim)
        url='/v1/swaps/'+str(swap['id'])+'/recovery'
        case=client.get(url,headers=tech).json();ref=reference(case,receipt)
        body={'protocol_version':'0.3','expected_version':case['version'],'note':'Independent Technician statement',
            'statement':{**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':packet['actual_serial'],'observation':'CONFIRM'}}
        response=client.post(url+'/evidence',headers=headers(tech),json=body)
        assert response.status_code==200,response.json().get('code')
        response=client.post(url+'/confirmations',headers=headers(customer),json={**ref,'confirm':confirmed})
        assert response.status_code==201,response.json().get('code')
        return swap,sim,customer,tech,ref
    except BaseException:
        sim.close();raise


def decide(client,swap,tech,ref,key=None):
    url='/v1/swaps/'+str(swap['id'])+'/recovery'
    case=client.get(url,headers=tech).json()
    body={'protocol_version':'0.3','expected_version':case['version'],'note':'Evaluate independent proof',
          'statement':{**ref,'kind':'VERIFY_NO_DELIVERY_DECIDE'}}
    request_headers=headers(tech,key)
    return client.post(url+'/evidence',headers=request_headers,json=body),request_headers,body


def test_backend_certificate_is_bound_fresh_atomic_and_does_not_settle_old_pin(client,environment,auth,tmp_path):
    swap,sim,customer,tech,ref=three_sources(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap);url='/v1/swaps/'+str(swap['id'])+'/recovery'
        case_before=client.get(url,headers=tech).json();key=uuid4()
        with patch('app.application.no_delivery.audit',side_effect=RuntimeError('ND_AUDIT_FAILURE')):
            with pytest.raises(RuntimeError,match='ND_AUDIT_FAILURE'):
                decide(client,swap,tech,ref,key)
        assert client.get(url,headers=tech).json()==case_before and facts(client,swap)==before
        response,hs,body=decide(client,swap,tech,ref,key)
        assert response.status_code==200,response.text
        result=response.json();cert=result['certificate']
        assert result['new_pin_delivered']=='NO' and result['old_pin_settled'] is False
        assert result['version']==case_before['version']+1 and cert['case_version']==result['version']
        assert cert['operation_id']==ref['operation_id'] and cert['receipt_id']==ref['receipt_id']
        assert cert['receipt_hash']==ref['receipt_hash'] and cert['effect_count_delta']==0
        replay=client.post(url+'/evidence',headers=hs,json=body)
        assert replay.status_code==200 and replay.json()==result
        assert facts(client,swap)==before
        db=client.app.state.db
        with db.sessions() as s:
            table=db.table('refund_eligibility_certificates');audit=db.table('audit_events')
            stored=s.execute(select(table)).mappings().one()
            assert stored['issuer_session_id'] is not None and stored['issued_by']==UUID(case_before['operation']['created_by'])
            assert stored['valid_until']>stored['validated_at']
            assert list(s.scalars(select(audit.c.action).where(audit.c.aggregate_id==UUID(result['case_id'])))).count('ND_CERTIFICATE_ISSUED')==1
    finally:sim.close()


def test_rejected_customer_proof_cannot_issue_certificate(client,environment,auth,tmp_path):
    swap,sim,customer,tech,ref=three_sources(client,environment,auth,tmp_path,confirmed=False)
    try:
        url='/v1/swaps/'+str(swap['id'])+'/recovery';before=client.get(url,headers=tech).json()
        response,_,_=decide(client,swap,tech,ref)
        assert (response.status_code,response.json()['code'])==(422,'EVIDENCE_REQUIRED')
        assert client.get(url,headers=tech).json()==before
        assert before['certificate'] is None and before['new_pin_delivered']=='UNKNOWN'
    finally:sim.close()


def test_revoked_witness_session_is_not_replaced_by_sibling_caller_session(client,environment,auth,tmp_path):
    swap,sim,customer,tech,ref=three_sources(client,environment,auth,tmp_path)
    try:
        sibling=auth('technician')
        response=client.post('/v1/auth/logout',headers=headers(tech))
        assert response.status_code==200
        url='/v1/swaps/'+str(swap['id'])+'/recovery';before=client.get(url,headers=sibling).json()
        response,_,_=decide(client,swap,sibling,ref)
        assert (response.status_code,response.json()['code'])==(401,'SESSION_REVOKED')
        assert client.get(url,headers=sibling).json()==before
        assert before['certificate'] is None and before['new_pin_delivered']=='UNKNOWN'
    finally:sim.close()


def test_no_delivery_preserves_old_obligation_already_settled_by_legacy_proof(client,environment,auth,tmp_path):
    from simulators.device.service import perform,flush
    swap,sim,customer,tech=physical_review(client,environment,auth,tmp_path)
    try:
        url='/v1/swaps/'+str(swap['id'])+'/recovery';case=client.get(url,headers=tech).json()
        response=client.post(url+'/evidence',headers=headers(tech),json={'expected_version':case['version'],
            'note':'Verify actual possession of the old battery independently',
            'statement':{'kind':'BEGIN_OPERATION','purpose':'VERIFY_OLD_POSSESSION'}})
        assert response.status_code==200,response.json().get('code')
        old_op=response.json()['active_operation']
        task=client.get('/v1/device/recovery-tasks',headers={'X-Device-Key':environment['keys']['S01']}).json()['items'][0]
        assert perform(sim,task,technician_token=tech['Authorization'].removeprefix('Bearer '))=='OBSERVED'
        flush(sim)
        case=client.get(url,headers=tech).json();receipt=case['active_operation']['attestations'][0]
        response=client.post(url+'/evidence',headers=headers(tech),json={'expected_version':case['version'],
            'note':'Witness actual old-battery model possession','statement':{'kind':'TECHNICIAN_ATTEST',
            'operation_id':old_op['id'],'context_hash':old_op['context_hash'],
            'actual_serial':receipt['payload']['actual_serial'],'observation':'CONFIRM'}})
        assert response.status_code==200,response.json().get('code')
        response=client.post(url+'/confirmations',headers=headers(customer),json={
            'operation_id':old_op['id'],'context_hash':old_op['context_hash'],'confirm':True})
        assert response.status_code==201,response.json().get('code')
        case=client.get(url,headers=tech).json()
        response=client.post(url+'/settle',headers=headers(tech),json={'expected_version':case['version'],
            'operation_id':old_op['id'],'resolution_note':'Old obligation settled through actual legacy independent proof'})
        assert response.status_code==200,response.json().get('code')
        assert response.json()['old_pin_settled'] is True
        before=facts(client,swap)
        begin(client,swap,tech);_,packet,accepted=inspect(client,environment,sim)
        case=client.get(url,headers=tech).json();ref=reference(case,accepted)
        response=client.post(url+'/evidence',headers=headers(tech),json={'protocol_version':'0.3',
            'expected_version':case['version'],'note':'Fresh independent no-new-battery proof',
            'statement':{**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':packet['actual_serial'],'observation':'CONFIRM'}})
        assert response.status_code==200,response.json().get('code')
        assert client.post(url+'/confirmations',headers=headers(customer),json={**ref,'confirm':True}).status_code==201
        response,_,_=decide(client,swap,tech,ref)
        assert response.status_code==200,response.json().get('code')
        assert response.json()['new_pin_delivered']=='NO' and response.json()['old_pin_settled'] is True
        assert facts(client,swap)==before
        assert sim.conn.execute('SELECT sum(effects) FROM commands').fetchone()[0]==0
        assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==0
    finally:sim.close()
