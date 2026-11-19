"""Admin durable intent only. Never sends a provider Refund command."""
from uuid import UUID,uuid4
from unittest.mock import patch

import pytest
from sqlalchemy import select

from test_phase1 import headers
from test_phase8b_b1b_certificate import three_sources,decide
from test_phase8b_b1b_no_delivery import facts


def eligible(client,environment,auth,tmp_path):
    admin=auth('admin')  # Warm Admin before the short-lived proof window.
    swap,sim,customer,tech,ref=three_sources(client,environment,auth,tmp_path)
    response,_,_=decide(client,swap,tech,ref)
    assert response.status_code==200,response.json().get('code')
    return admin,swap,sim,customer,tech,response.json()['certificate']


def financial_rows(client):
    db=client.app.state.db
    with db.sessions() as s:
        return {name:[dict(v) for v in s.execute(select(db.table(name))).mappings()] for name in
            ('refunds','refund_attempts','refund_certificate_redemptions','refund_retry_permissions')}


def test_first_intent_rollback_replay_and_no_provider_dispatch(client,environment,auth,tmp_path):
    admin,swap,sim,customer,tech,cert=eligible(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap);db=client.app.state.db;p=before['payments'][0]
        url='/v1/payments/'+str(p['id'])+'/refund';key=uuid4()
        body={'expected_version':p['version'],'reason':'Approved full mock refund intent'}
        hs=headers(admin,key);before_rows=financial_rows(client)
        with patch('app.application.refund_audit.request_record',side_effect=RuntimeError('REFUND_AUDIT_FAILURE')):
            with pytest.raises(RuntimeError,match='REFUND_AUDIT_FAILURE'):
                client.post(url,headers=hs,json=body)
        assert facts(client,swap)==before and financial_rows(client)==before_rows
        response=client.post(url,headers=hs,json=body)
        assert response.status_code==202,response.text
        refund=response.json()
        assert refund['state']=='REQUESTED' and refund['amount_minor']==p['amount_minor']
        from app.workers import payment as charge_worker
        calls=[]
        def forbid_financial_dispatch(request):
            calls.append(request.url.path)
            raise AssertionError('Refund must not be dispatched by the charge worker')
        charge_worker.tick(db,transport=forbid_financial_dispatch)
        assert calls==[]
        assert client.post(url,headers=hs,json=body).json()==refund
        response=client.post(url,headers=headers(admin),json=body)
        assert response.status_code==409
        # A post-commit witness logout does not undo or renew historical intent.
        response=client.post('/v1/auth/logout',headers=headers(tech))
        assert response.status_code==200
        response=client.post(url,headers=hs,json=body)
        assert response.status_code==202 and response.json()==refund
        after=facts(client,swap)
        for name in ('batteries','payments','resource_reservations'):assert after[name]==before[name]
        with db.sessions() as s:
            rows=financial_rows(client)
            assert len(rows['refunds'])==len(rows['refund_attempts'])==len(rows['refund_certificate_redemptions'])==1
            assert rows['refund_attempts'][0]['generation']==0 and rows['refund_attempts'][0]['permit_id'] is None
            assert rows['refund_certificate_redemptions'][0]['certificate_id']==UUID(cert['certificate_id'])
            boxes=db.table('outbox_messages')
            out=s.execute(select(boxes).where(boxes.c.kind=='REFUND')).mappings().one()
            assert out['attempts']==0 and out['delivered_at'] is None
            assert out['payload']['command']['attempt_id']==str(rows['refund_attempts'][0]['id'])
            assert out['payload']['command']['generation']==0
            audit=db.table('audit_events')
            for action in ('REFUND_REQUEST_CREATED','ND_CERTIFICATE_REDEEMED'):
                assert len(list(s.scalars(select(audit.c.id).where(audit.c.action==action))))==1
            transactions=db.table('swap_transactions')
            current=s.execute(select(transactions).where(transactions.c.id==swap['id'])).mappings().one()
            assert current['state']=='COMPENSATING' and current['version']==swap['version']+1
            case=s.execute(select(db.table('recovery_cases'))).mappings().one()
            assert case['old_pin_settled'] is False and case['new_pin_delivered']=='NO'
        assert sim.conn.execute('SELECT sum(effects) FROM commands').fetchone()[0]==0
    finally:sim.close()


def test_new_boot_revokes_certificate_without_refund_or_protected_mutation(client,environment,auth,tmp_path):
    from simulators.device.main import Simulator
    admin,swap,sim,customer,tech,cert=eligible(client,environment,auth,tmp_path)
    try:
        before=facts(client,swap);path=tmp_path/'no_delivery.sqlite3';transport=sim.http._transport
        sim.close()
        sim=Simulator('S01',environment['keys']['S01'],ledger=path,transport=transport,scenario='nack')
        sim.cycle()
        p=before['payments'][0]
        response=client.post('/v1/payments/'+str(p['id'])+'/refund',headers=headers(admin),json={
            'expected_version':p['version'],'reason':'Old boot must not authorize refund'})
        assert response.status_code in (409,422)
        assert facts(client,swap)==before
        db=client.app.state.db
        with db.sessions() as s:
            rev=s.execute(select(db.table('refund_certificate_revocations'))).mappings().one()
            assert rev['certificate_id']==UUID(cert['certificate_id'])
            case=s.execute(select(db.table('recovery_cases'))).mappings().one()
            assert case['new_pin_delivered']=='UNKNOWN' and case['old_pin_settled'] is False
            assert not financial_rows(client)['refunds']
            audit=db.table('audit_events')
            assert len(list(s.scalars(select(audit.c.id).where(audit.c.action=='ND_CERTIFICATE_REVOKED'))))==1
        assert sim.conn.execute("SELECT state FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()
    finally:sim.close()
