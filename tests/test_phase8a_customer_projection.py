"""Owner projection and exact receipt consumption, using isolated PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import secrets
from uuid import UUID, uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, update, text

from app.main import create_app
from app.application.identity import utcnow
from app.api.recovery_schemas import RecoveryConfirmationContext
from test_phase5 import race_environment, login
from test_phase8a_inspection_transport import setup_inspection, facts
from test_phase8a_handover import prepared_action
from simulators.device.recovery_fence import transport_inspection, flush
from simulators.device.service import perform
from test_phase4 import send


def projection(http, swap, actor):
    response = http.get('/v1/swaps/'+swap['id'],headers=actor)
    assert response.status_code == 200,response.text
    result = response.json()['recovery_confirmation']
    RecoveryConfirmationContext.model_validate(result)
    return result


def binding(p, confirm=True):
    return {k:p[k] for k in ('operation_id','context_hash','stage','receipt_id','receipt_hash')} | {'confirm':confirm}


@pytest.mark.parametrize('confirm',[True,False])
def test_pre_projection_ownership_lifecycle_and_replay(client,environment,auth,tmp_path,confirm):
    swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
    customer=auth('customer'); url=f"/v1/swaps/{swap['id']}/recovery"
    def submit(body,key=None):
        return client.post(url+'/confirmations',headers={**customer,'Idempotency-Key':key or str(uuid4())},json=body)
    try:
        assert projection(client,swap,customer)['confirmation_status']=='WAITING_RECEIPT'
        transport_inspection(sim,task);flush(sim)
        p=projection(client,swap,customer)
        assert p['protocol_version']=='0.2' and p['stage']=='PRE_ACTION_INSPECTION'
        assert p['confirmation_status']=='AVAILABLE'
        assert not any(k in p for k in ('attestations','authorization','commands','payload','created_by'))
        before=facts(client,swap)
        assert client.get(url,headers=customer).status_code==403
        password=secrets.token_urlsafe(24);username='projection-'+uuid4().hex
        response=client.post('/v1/users',headers={**auth('admin'),'Idempotency-Key':str(uuid4())},
                             json={'username':username,'password':password,'role':'CUSTOMER'})
        assert response.status_code==201,response.text
        response=client.post('/v1/auth/login',json={'username':username,'password':password})
        other={'Authorization':'Bearer '+response.json()['access_token']}
        assert client.get('/v1/swaps/'+swap['id'],headers=other).status_code==404
        assert client.post(url+'/confirmations',headers={**other,'Idempotency-Key':str(uuid4())},json=binding(p)).status_code==403
        for field,value in [('stage','POST_ACTION_RECEIPT'),('receipt_id',str(uuid4())),('receipt_hash','f'*64),('context_hash','e'*64)]:
            assert submit({**binding(p),field:value}).status_code==409
        db=client.app.state.db
        for column,status in [('consumed_at','CONSUMED'),('cancelled_at','CANCELLED')]:
            save=client.app.state.test_connection.begin_nested()
            try:
                with db.sessions.begin() as s:
                    t=db.table('recovery_operations');s.execute(update(t).where(t.c.id==UUID(task['operation_id'])).values(**{column:utcnow()}))
                assert projection(client,swap,customer)['confirmation_status']==status
                assert submit(binding(p)).status_code==409
            finally:save.rollback()
        from app.application import recovery as r
        now=r.utcnow
        with patch.object(r,'utcnow',lambda:now()+timedelta(seconds=121)):
            assert projection(client,swap,customer)['confirmation_status']=='EXPIRED'
            assert submit(binding(p)).status_code==409
        with patch.object(r,'utcnow',lambda:now()+timedelta(seconds=16)):
            assert projection(client,swap,customer)['confirmation_status']=='UNAVAILABLE'
            assert submit(binding(p)).status_code==422
        key=str(uuid4());body=binding(p,confirm)
        result=submit(body,key)
        assert result.status_code==201,result.text
        assert submit(body,key).json()==result.json()
        assert submit(binding(p,not confirm)).status_code==409
        assert projection(client,swap,customer)['confirmation_status']==('CONFIRMED' if confirm else 'REJECTED')
        assert facts(client,swap)==before
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
    finally:sim.close()


def test_post_projection_cannot_reuse_pre_reference_and_rejects_revoked(client,environment,auth,tmp_path):
    swap,sim,task,tech,device=prepared_action(client,environment,auth,tmp_path)
    customer=auth('customer');url=f"/v1/swaps/{swap['id']}/recovery/confirmations"
    def submit(p):
        return client.post(url,headers={**customer,'Idempotency-Key':str(uuid4())},json=binding(p))
    try:
        pre=projection(client,swap,customer)
        before=facts(client,swap)
        perform(sim,task,technician_token=tech['Authorization'].split()[1])
        packet=json.loads(sim.conn.execute('SELECT observation FROM service_operations').fetchone()[0])
        snapshot=json.loads(sim.conn.execute('SELECT body FROM events WHERE id=?',(packet['snapshot_event_id'],)).fetchone()[0])
        assert send(client,environment,snapshot).status_code==202
        assert client.post('/v1/device/recovery-observations',headers=device,json=packet).status_code==202
        assert send(client,environment,sim.snapshot()).status_code==202
        post=projection(client,swap,customer)
        assert post['stage']=='POST_ACTION_RECEIPT' and post['receipt_id']!=pre['receipt_id']
        assert post['confirmation_status']=='AVAILABLE'
        assert submit(pre).status_code==409
        db=client.app.state.db
        save=client.app.state.test_connection.begin_nested()
        try:
            with db.sessions.begin() as s:
                t=db.table('recovery_action_authorizations')
                from app.application.recovery import utcnow
                s.execute(update(t).where(t.c.operation_id==UUID(task['operation_id'])).values(revoked_at=utcnow()))
            assert projection(client,swap,customer)['confirmation_status']=='REVOKED'
            assert submit(post).status_code==409
        finally:save.rollback()
        assert submit(post).status_code==201
        assert facts(client,swap)==before
        assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
    finally:sim.close()


def test_two_apps_consume_projected_pre_receipt_once(race_environment,tmp_path):
    env=race_environment
    with TestClient(create_app(env['settings'])) as first,TestClient(create_app(env['settings'])) as second:
        def auth(name):return login(first,env,name)
        swap,sim,task,tech=setup_inspection(first,env,auth,tmp_path,committed=True)
        try:
            transport_inspection(sim,task);flush(sim)
            customer=auth('customer');p=projection(first,swap,customer)
            before=facts(first,swap)
            with first.app.state.db.sessions() as a,second.app.state.db.sessions() as b:
                assert a.scalar(text('select pg_backend_pid()'))!=b.scalar(text('select pg_backend_pid()'))
            url=f"/v1/swaps/{swap['id']}/recovery/confirmations"
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies=list(pool.map(lambda http:http.post(url,headers={**customer,'Idempotency-Key':str(uuid4())},json=binding(p)),[first,second]))
            assert sorted(r.status_code for r in replies)==[201,409],[r.text for r in replies]
            assert facts(first,swap)==before
        finally:sim.close()
