"""Native PG/API + real Simulator model; same OS, not real-process E2E.

Operational preparation uses authenticated APIs, real source events and the
existing verified charge mock. No SQL constructs custody or positive proof.
"""
import json
from uuid import UUID, uuid4
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select

from app.application import no_delivery
from app.config import approved_policy
from app.seed import demo_id
from app.workers.device import process_one
from app.workers import payment as payment_worker
from simulators.device.main import Simulator
from simulators.device import no_delivery as local
from test_phase1 import headers
from test_phase4 import row
from test_phase5 import verified, reserve
from test_phase6 import consent, outcome


def physical_review(client,environment,auth,tmp_path):
    customer,tech=auth('customer'),auth('technician')
    db=client.app.state.db
    def transport(request):
        params={'headers':{'X-Device-Key':environment['keys']['S01']}}
        # Explicit legacy service calls carry their real Technician session;
        # ordinary Device ingress remains authenticated by its own Device-Key.
        if request.headers.get('Authorization'):
            params['headers']['Authorization']=request.headers['Authorization']
        if request.content:params['json']=json.loads(request.content)
        response=getattr(client,request.method.lower())(request.url.path,**params)
        if request.url.path=='/v1/device/events' and response.status_code==202:
            with db.sessions.begin() as s:
                process_one(s,db,UUID(response.json()['event_id']),approved_policy())
            response=client.post(request.url.path,**params)
        return httpx.Response(response.status_code,json=response.json())
    sim=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'no_delivery.sqlite3',
                  transport=httpx.MockTransport(transport),scenario='nack')
    sim.cycle()
    supply=demo_id('S01:battery:2')
    evidence=json.loads(sim.conn.execute("SELECT body FROM events WHERE json_extract(body,'$.kind')='SNAPSHOT' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
    response=client.post('/v1/batteries/'+str(supply)+'/actions',headers=headers(tech),json={
        'expected_version':row(client,'batteries',supply)['version'],'action':'ACTIVATE',
        'reason':'Activate with actual Simulator evidence','evidence_event_id':evidence['event_id']})
    assert response.status_code==200,response.text
    for number in (1,2):
        slot=demo_id('S01:slot:'+str(number))
        response=client.post('/v1/compartments/'+str(slot)+'/actions',headers=headers(tech),json={
            'expected_version':row(client,'compartments',slot)['version'],'action':'RESTORE',
            'reason':'Restore from real current Simulator snapshot','evidence_event_id':evidence['event_id']})
        assert response.status_code==200,response.json().get('code')
    swap=verified(client,environment,customer)
    response=reserve(client,customer,swap)
    assert response.status_code==200,response.text
    swap=response.json()
    assert swap['state']=='RESERVED',swap['state']
    response=consent(client,customer,swap)
    assert response.status_code==202,response.json().get('code')
    payment_worker.tick(db,transport=outcome)
    from app.application.swaps import tick as advance_swaps
    advance_swaps(db)
    # The device honestly refuses OPEN_RETURN. A terminal NACK is not a
    # statement about delivery; independent current proof must still follow.
    sim.cycle()
    swap=row(client,'swap_transactions',UUID(swap['id']))
    assert swap['state']=='REVIEW_REQUIRED'
    return swap,sim,customer,tech


def facts(client,swap):
    db=client.app.state.db
    with db.sessions() as s:
        result={}
        for name,column,ids in (
            ('batteries','id',[swap['old_battery_id'],swap['new_battery_id']]),
            ('payments','swap_id',[swap['id']]),('resource_reservations','swap_id',[swap['id']]),
            ('refunds','payment_id',list(s.scalars(select(db.table('payments').c.id).where(db.table('payments').c.swap_id==swap['id']))))):
            table=db.table(name)
            result[name]=[dict(r) for r in s.execute(select(table).where(table.c[column].in_(ids)).order_by(table.c.id)).mappings()]
        return result


def begin(client,swap,tech,key=None):
    url='/v1/swaps/'+str(swap['id'])+'/recovery'
    case=client.get(url,headers=tech).json()
    body={'protocol_version':'0.3','expected_version':case['version'],'note':'Readonly no-delivery inspection',
          'statement':{'kind':'BEGIN_OPERATION','purpose':'VERIFY_NO_DELIVERY'}}
    response=client.post(url+'/evidence',headers=headers(tech,key),json=body)
    assert response.status_code==200,response.text
    return response.json()


def inspect(client,environment,sim):
    tasks=client.get('/v1/device/recovery-tasks',headers={'X-Device-Key':environment['keys']['S01']})
    assert tasks.status_code==200,tasks.text
    task=tasks.json()['items'][0]
    assert task['task_kind']=='VERIFY_NO_DELIVERY_INSPECT' and task['effect_allowed'] is False
    packet=local.inspect(sim,task)
    response=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json=packet)
    assert response.status_code==202,response.text
    return task,packet,response.json()


def reference(case,receipt):
    return dict(protocol_version='0.3',operation_id=case['operation']['operation_id'],
        context_hash=case['operation']['context_hash'],stage='NO_DELIVERY_INSPECTION',
        receipt_id=receipt['id'],receipt_hash=case['proofs'][0]['payload_hash'])


def test_current_three_source_transport_and_replay_do_not_change_protected_facts(client,environment,auth,tmp_path):
    swap,sim,customer,tech=physical_review(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap);initial_slots=sim.slots()
        key=uuid4();case=begin(client,swap,tech,key)
        task,packet,receipt=inspect(client,environment,sim)
        url='/v1/swaps/'+str(swap['id'])+'/recovery'
        case=client.get(url,headers=tech).json()
        ref=reference(case,receipt)
        tech_body=dict(protocol_version='0.3',expected_version=case['version'],note='Current model witnessed',
            statement={**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':packet['actual_serial'],'observation':'CONFIRM'})
        key=uuid4();first=client.post(url+'/evidence',headers=headers(tech,key),json=tech_body)
        assert first.status_code==200,first.text
        assert client.post(url+'/evidence',headers=headers(tech,key),json=tech_body).json()==first.json()
        key=uuid4();body={**ref,'confirm':True}
        first=client.post(url+'/confirmations',headers=headers(customer,key),json=body)
        assert first.status_code==201,first.text
        assert client.post(url+'/confirmations',headers=headers(customer,key),json=body).json()==first.json()
        case=client.get(url,headers=tech).json()
        assert {p['source_kind'] for p in case['proofs']}=={'SIMULATOR','TECHNICIAN','CUSTOMER'}
        assert case['new_pin_delivered']=='UNKNOWN' and case['old_pin_settled'] is False
        projection=client.get('/v1/swaps/'+str(swap['id']),headers=customer).json()['recovery_confirmation']
        assert projection['confirmation_status']=='CONFIRMED' and projection['receipt_id']==receipt['id']
        assert facts(client,swap)==before and sim.slots()==initial_slots
        assert sum(r[0] for r in sim.conn.execute('SELECT effects FROM commands'))==0
        with client.app.state.db.sessions() as s:
            audit=client.app.state.db.table('audit_events')
            actions=list(s.scalars(select(audit.c.action).where(audit.c.aggregate_id==UUID(case['case_id']))))
            assert actions.count('ND_OPERATION_CREATED')==1 and actions.count('ND_INSPECTION_ACCEPTED')==1
            assert actions.count('ND_HUMAN_ATTESTED')==2
    finally:sim.close()


def test_wrong_boot_receipt_refusal_is_durable_and_has_no_case_audit_write(client,environment,auth,tmp_path):
    swap,sim,customer,tech=physical_review(client,environment,auth,tmp_path)
    try:
        case=begin(client,swap,tech)
        task=client.get('/v1/device/recovery-tasks',headers={'X-Device-Key':environment['keys']['S01']}).json()['items'][0]
        packet=local.inspect(sim,task);packet['boot_id']=str(uuid4())
        before=facts(client,swap)
        url='/v1/swaps/'+str(swap['id'])+'/recovery';case=client.get(url,headers=tech).json()
        responses=[client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S01']},json=packet) for _ in range(2)]
        assert [r.status_code for r in responses]==[422,422]
        assert responses[0].json()==responses[1].json()
        assert client.get(url,headers=tech).json()==case and facts(client,swap)==before
    finally:sim.close()


def test_issuer_packet_tampering_cannot_create_or_rehabilitate_proof(client,environment,auth,tmp_path):
    from copy import deepcopy
    swap,sim,customer,tech=physical_review(client,environment,auth,tmp_path)
    try:
        case=begin(client,swap,tech)
        task=client.get('/v1/device/recovery-tasks',headers={'X-Device-Key':environment['keys']['S01']}).json()['items'][0]
        original=local.inspect(sim,task);url='/v1/swaps/'+str(swap['id'])+'/recovery'
        before=client.get(url,headers=tech).json();protected=facts(client,swap)
        changes=[{'boot_id':str(uuid4())},{'context_hash':'f'*64},{'actual_serial':'NOT-THE-MODEL'},
                 {'device_id':str(uuid4())},{'snapshot_hash':'f'*64},{'seq':1},
                 {'delivery_history':{**original['delivery_history'],'event_ids':[str(uuid4())]}},
                 {'command_entries':[]},
                 {'quiescence':{**original['quiescence'],'command_digest':'f'*64}}]
        dev={'X-Device-Key':environment['keys']['S01']}
        cross=client.post('/v1/device/recovery-observations',headers={'X-Device-Key':environment['keys']['S02']},json=original)
        assert (cross.status_code,cross.json()['code'])==(403,'DEVICE_STATION_FORBIDDEN')
        for change in changes:
            packet={**deepcopy(original),'event_id':str(uuid4()),**change}
            result=client.post('/v1/device/recovery-observations',headers=dev,json=packet)
            assert result.status_code in (409,422) and result.json()['code']!='VALIDATION_ERROR'
            replay=client.post('/v1/device/recovery-observations',headers=dev,json=packet)
            assert replay.status_code==result.status_code and replay.json()==result.json()
            fixed={**original,'event_id':packet['event_id']}
            conflict=client.post('/v1/device/recovery-observations',headers=dev,json=fixed)
            assert (conflict.status_code,conflict.json()['code'])==(409,'IDEMPOTENCY_CONFLICT')
            assert client.get(url,headers=tech).json()==before and facts(client,swap)==protected
        valid=client.post('/v1/device/recovery-observations',headers=dev,json=original)
        assert valid.status_code==202
    finally:sim.close()


def test_human_context_ownership_append_only_and_conflicting_replay(client,environment,auth,tmp_path):
    from test_phase1 import create_customer
    admin=auth('admin');other,password=create_customer(client,admin)
    other_auth=client.post('/v1/auth/login',json={'username':other['username'],'password':password})
    assert other_auth.status_code==200
    outsider={'Authorization':'Bearer '+other_auth.json()['access_token']}
    swap,sim,customer,tech=physical_review(client,environment,auth,tmp_path)
    try:
        begin(client,swap,tech);task,packet,receipt=inspect(client,environment,sim)
        url='/v1/swaps/'+str(swap['id'])+'/recovery';case=client.get(url,headers=tech).json();ref=reference(case,receipt)
        before=facts(client,swap)
        for actor in (tech,admin,outsider):
            response=client.post(url+'/confirmations',headers=headers(actor),json={**ref,'confirm':True})
            assert response.status_code==403
        assert client.get('/v1/swaps/'+str(swap['id']),headers=outsider).status_code==404
        for change in ({'context_hash':'f'*64},{'receipt_hash':'f'*64},{'operation_id':str(uuid4())}):
            response=client.post(url+'/confirmations',headers=headers(customer),json={**ref,**change,'confirm':True})
            assert response.status_code in (404,409,422)
        response=client.post(url+'/confirmations',headers=headers(customer),json={**ref,'stage':'PRE_ACTION_INSPECTION','confirm':True})
        assert response.status_code==422
        assert client.get(url,headers=tech).json()==case and facts(client,swap)==before
        key=uuid4();body={**ref,'confirm':False};hs=headers(customer,key)
        result=client.post(url+'/confirmations',headers=hs,json=body)
        assert result.status_code==201 and result.json()['confirmed'] is False
        assert client.post(url+'/confirmations',headers=hs,json=body).json()==result.json()
        conflict=client.post(url+'/confirmations',headers=hs,json={**body,'confirm':True})
        assert (conflict.status_code,conflict.json()['code'])==(409,'IDEMPOTENCY_CONFLICT')
        assert client.post(url+'/confirmations',headers=headers(customer),json={**ref,'confirm':True}).status_code==409
        after=client.get(url,headers=tech).json()
        assert len(after['proofs'])==2 and after['version']==case['version']+1 and after['certificate'] is None
    finally:sim.close()


def test_human_audit_failure_rolls_back_proof_version_and_success_replay(client,environment,auth,tmp_path):
    swap,sim,customer,tech=physical_review(client,environment,auth,tmp_path)
    try:
        begin(client,swap,tech);task,packet,receipt=inspect(client,environment,sim)
        url='/v1/swaps/'+str(swap['id'])+'/recovery';case=client.get(url,headers=tech).json();ref=reference(case,receipt)
        body={**ref,'confirm':True};hs=headers(customer,uuid4());before=facts(client,swap)
        with patch('app.application.no_delivery.audit',side_effect=RuntimeError('HUMAN_AUDIT_ROLLBACK')):
            with pytest.raises(RuntimeError,match='HUMAN_AUDIT_ROLLBACK'):
                client.post(url+'/confirmations',headers=hs,json=body)
        assert client.get(url,headers=tech).json()==case and facts(client,swap)==before
        result=client.post(url+'/confirmations',headers=hs,json=body)
        assert result.status_code==201
        assert client.post(url+'/confirmations',headers=hs,json=body).json()==result.json()
    finally:sim.close()


@pytest.mark.parametrize('terminal_column',['consumed_at','cancelled_at'])
def test_terminal_metadata_alone_does_not_release_backend_station_fence(client,environment,auth,tmp_path,terminal_column):
    """Adversarial metadata fixture, NOT physical proof or a legal release."""
    from sqlalchemy import update
    from app.application.identity import utcnow
    swap,sim,customer,tech=physical_review(client,environment,auth,tmp_path)
    try:
        case=begin(client,swap,tech);inspect(client,environment,sim)
        db=client.app.state.db;identity=UUID(case['operation']['operation_id']);before=facts(client,swap)
        # Only the untrusted closure marker is varied. No SQL changes a proof,
        # custody, NO, Payment, holds, device observation or historical clock.
        with db.sessions.begin() as session:
            table=db.table('recovery_operations')
            session.execute(update(table).where(table.c.id==identity).values(**{terminal_column:utcnow()}))
        assert sim.conn.execute("SELECT state FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()
        with db.sessions() as session:
            fence=no_delivery.station_fence(session,db,swap['station_id'])
            assert fence is not None and fence['id']==identity
        url='/v1/swaps/'+str(swap['id'])+'/recovery';current=client.get(url,headers=tech).json()
        response=client.post(url+'/evidence',headers=headers(tech),json={'expected_version':current['version'],
            'note':'Terminal metadata is not a release receipt','statement':{'kind':'BEGIN_OPERATION','purpose':'RESUME_SWAP'}})
        assert (response.status_code,response.json()['code'])==(409,'QUIESCENCE_REQUIRED')
        assert client.get(url,headers=tech).json()==current and facts(client,swap)==before
    finally:sim.close()
