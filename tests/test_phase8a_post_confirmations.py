"""Human statements reference real model receipts on isolated PostgreSQL."""
import json
from uuid import UUID, uuid4
from unittest.mock import patch
from datetime import timedelta
import pytest
from sqlalchemy import select,update,func
from test_phase8a_handover import prepared_action
from test_phase8a_inspection_transport import facts
from test_phase4 import send
from simulators.device.service import perform


@pytest.mark.parametrize('extra',[{'actor_id':str(uuid4())},{'role':'TECHNICIAN'},
    {'recipient_id':str(uuid4())},{'actual_serial':'CLIENT-OVERRIDE'}])
def test_customer_post_cannot_choose_principal_or_receipt_facts(extra):
    from pydantic import ValidationError
    from app.api.recovery_schemas import CustomerConfirmation
    with pytest.raises(ValidationError):
        CustomerConfirmation.model_validate({'operation_id':str(uuid4()),'context_hash':'a'*64,
            'stage':'POST_ACTION_RECEIPT','receipt_id':str(uuid4()),'receipt_hash':'b'*64,'confirm':True,**extra})


@pytest.mark.parametrize('confirmed',[True,False])
def test_post_statements_provenance_refusals_replay_and_rollback(client,environment,auth,tmp_path,confirmed):
    swap,sim,task,tech,device=prepared_action(client,environment,auth,tmp_path)
    url=f"/v1/swaps/{swap['id']}/recovery"
    customer=auth('customer');admin=auth('admin')
    def case():return client.get(url,headers=tech).json()
    known_version=case()['version']
    def submit(source,binding,headers=None,key=None):
        if source=='CUSTOMER':
            return client.post(url+'/confirmations',headers={**(headers or customer),'Idempotency-Key':key or str(uuid4())},json={**binding,'confirm':confirmed})
        return client.post(url+'/evidence',headers={**(headers or tech),'Idempotency-Key':key or str(uuid4())},json={
            'expected_version':case().get('version',known_version),'note':'Witness post-action receipt',
            'statement':{**binding,'kind':'TECHNICIAN_ATTEST','actual_serial':'SIMULATED-WRONG-BATTERY','observation':'CONFIRM' if confirmed else 'REJECT'}})
    try:
        before=facts(client,swap)
        pre=case()['active_operation']['attestations'][0]
        binding={'operation_id':task['operation_id'],'context_hash':task['context_hash'],
            'stage':'POST_ACTION_RECEIPT','receipt_id':pre['id'],'receipt_hash':pre['payload_hash']}
        assert submit('CUSTOMER',binding).status_code==409 # pre receipt is not post proof
        assert submit('TECHNICIAN',binding).status_code==409
        perform(sim,task,technician_token=tech['Authorization'].split(' ',1)[1])
        packet=json.loads(sim.conn.execute('SELECT observation FROM service_operations').fetchone()[0])
        snapshot=json.loads(sim.conn.execute('SELECT body FROM events WHERE id=?',(packet['snapshot_event_id'],)).fetchone()[0])
        assert send(client,environment,snapshot).status_code==202
        receipt=client.post('/v1/device/recovery-observations',headers=device,json=packet)
        assert receipt.status_code==202,receipt.text
        assert send(client,environment,sim.snapshot()).status_code==202
        post=next(a for a in case()['active_operation']['attestations'] if a['stage']=='POST_ACTION_RECEIPT')
        binding.update(receipt_id=post['id'],receipt_hash=post['payload_hash'])
        for source in ('CUSTOMER','TECHNICIAN'):
            assert submit(source,{**binding,'context_hash':'f'*64}).status_code==409
            assert submit(source,{**binding,'receipt_hash':'e'*64}).status_code==409
            assert submit(source,binding,admin).status_code==403
        assert submit('CUSTOMER',{**binding,'recipient_id':str(uuid4())}).status_code==422
        assert submit('CUSTOMER',binding,tech).status_code==403
        assert submit('TECHNICIAN',binding,customer).status_code==403
        bad_serial=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json={
            'expected_version':case()['version'],'note':'Wrong witnessed serial',
            'statement':{**binding,'kind':'TECHNICIAN_ATTEST','actual_serial':'OTHER-SERIAL','observation':'CONFIRM'}})
        assert bad_serial.status_code==422,bad_serial.text
        from app.application import recovery
        clock=recovery.utcnow
        for seconds in (16,121):
            with patch('app.application.recovery.utcnow',lambda:clock()+timedelta(seconds=seconds)):
                refused=submit('CUSTOMER',binding)
                assert refused.status_code in (409,422),refused.text
        db=client.app.state.db
        displaced=client.app.state.test_connection.begin_nested()
        try:
            # Simulate a displaced active-operation pointer, not a successful
            # supersession workflow. No receipt, physical model or custody edits.
            with db.sessions.begin() as s:
                t=db.table('recovery_cases')
                s.execute(update(t).where(t.c.swap_id==UUID(swap['id'])).values(operation_id=None))
            assert submit('CUSTOMER',binding).status_code==409
        finally:displaced.rollback()
        # Actual revocation/assignment changes inside an enclosing test savepoint.
        # Rollback restores test setup; no observation/receipt timestamps rewritten.
        for fault in ('session','assignment','role'):
            save=client.app.state.test_connection.begin_nested()
            try:
                with db.sessions.begin() as s:
                    if fault=='session':
                        # Customer post request uses a different current session;
                        # revoke all Customer sessions to cover the actual bearer.
                        t=db.table('auth_sessions');s.execute(update(t).where(t.c.user_id==UUID(task['customer_id'])).values(revoked_at=clock()))
                    elif fault=='assignment':
                        t=db.table('user_station_assignments');s.execute(t.delete().where(t.c.user_id==UUID(task['created_by'])))
                    else:
                        t=db.table('users');s.execute(update(t).where(t.c.id==UUID(task['created_by'])).values(role='ADMIN'))
                refused=submit('CUSTOMER' if fault=='session' else 'TECHNICIAN',binding)
                assert refused.status_code in (401,403),refused.text
            finally:save.rollback()
        with patch('app.application.recovery.audit',side_effect=RuntimeError('POST_AUDIT_ROLLBACK')):
            with pytest.raises(RuntimeError,match='POST_AUDIT_ROLLBACK'):submit('CUSTOMER',binding)
        key=str(uuid4())
        accepted=submit('CUSTOMER',binding,key=key)
        assert accepted.status_code==201,accepted.text
        assert accepted.json()['confirmed'] is confirmed
        assert submit('CUSTOMER',binding,key=key).json()==accepted.json()
        assert submit('CUSTOMER',{**binding,'context_hash':'a'*64},key=key).status_code==409
        assert submit('CUSTOMER',binding).status_code==409
        accepted=submit('TECHNICIAN',binding)
        assert accepted.status_code==200,accepted.text
        rows=[a for a in case()['active_operation']['attestations'] if a['stage']=='POST_ACTION_RECEIPT']
        assert {a['source_kind'] for a in rows}=={'SIMULATOR','TECHNICIAN','CUSTOMER'}
        assert all(a['payload']['confirm'] is confirmed for a in rows if a['source_kind']!='SIMULATOR')
        assert facts(client,swap)==before and not case()['old_pin_settled']
        assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
    finally:sim.close()


def test_post_statement_cannot_promote_old_boot_receipt_to_current_proof(client,environment,auth,tmp_path):
    from simulators.device.main import Simulator
    swap,sim,task,tech,device=prepared_action(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap)
        perform(sim,task,technician_token=tech['Authorization'].split(' ',1)[1])
        packet=json.loads(sim.conn.execute('SELECT observation FROM service_operations').fetchone()[0])
        snapshot=json.loads(sim.conn.execute('SELECT body FROM events WHERE id=?',(packet['snapshot_event_id'],)).fetchone()[0])
        assert send(client,environment,snapshot).status_code==202
        accepted=client.post('/v1/device/recovery-observations',headers=device,json=packet)
        assert accepted.status_code==202,accepted.text
        transport=sim.http._transport;sim.close()
        sim=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'inspection.sqlite3',transport=transport)
        assert sim.boot!=packet['boot_id']
        assert send(client,environment,sim.snapshot()).status_code==202
        case=client.get(f"/v1/swaps/{swap['id']}/recovery",headers=tech).json()
        receipt=next(a for a in case['active_operation']['attestations'] if a['stage']=='POST_ACTION_RECEIPT')
        response=client.post(f"/v1/swaps/{swap['id']}/recovery/confirmations",
            headers={**auth('customer'),'Idempotency-Key':str(uuid4())},json={
                'operation_id':task['operation_id'],'context_hash':task['context_hash'],
                'stage':'POST_ACTION_RECEIPT','receipt_id':receipt['id'],'receipt_hash':receipt['payload_hash'],'confirm':True})
        assert response.status_code==409 and response.json()['code']=='RECONCILIATION_REQUIRED',response.text
        assert facts(client,swap)==before
        assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
    finally:sim.close()
