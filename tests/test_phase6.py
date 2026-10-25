"""TC14/TC15 and CT03/10/11: PostgreSQL settlement, not physical exchange."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import secrets
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import func, insert, select, update

from app.application import payments, reservations
from app.application.identity import DomainError, utcnow
from app.api.payments import ProviderChargeRequest
from app.config import ROOT, approved_policy
from app.main import create_app
from app.workers import payment as worker
from simulators.payment.main import Ledger, create_app as mock_app
from test_phase1 import headers, validate
from test_phase2 import owner
from test_phase4 import row
from test_phase5 import prepare, verified, reserve, cancel, login, race_environment


@pytest.fixture(autouse=True)
def private_keys(monkeypatch):
    monkeypatch.setenv('PAYMENT_SERVICE_KEY', secrets.token_urlsafe(32))
    monkeypatch.setenv('PAYMENT_CALLBACK_KEY', secrets.token_urlsafe(32))


def book(http, env, actor, db=None):
    prepare(http, env, db)
    response = reserve(http, actor, verified(http, env, actor))
    assert response.status_code == 200 and response.json()['state'] == 'RESERVED'
    return response.json()


def consent(http, actor, swap, key=None, **changes):
    return http.post('/v1/swaps/' + swap['id'] + '/consent', headers=headers(actor, key), json={
        'expected_version':swap['version'], 'quoted_amount_minor':swap['amount_minor'], 'currency':swap['currency'],
        'accept':True, **changes})


def payment(http, actor, swap):
    response = http.get('/v1/swaps/' + swap['id'] + '/payment', headers=actor)
    assert response.status_code == 200
    validate('Payments', response.json())
    return response.json()


def counts(db, identity=None):
    with db.sessions() as s:
        result = {n:s.scalar(select(func.count()).select_from(db.table(n))) for n in
            ('payments','outbox_messages','payment_events','device_commands')}
        holds=db.table('resource_reservations')
        result['holds']=s.scalar(select(func.count()).select_from(holds).where(holds.c.released_at.is_(None)))
        return result


def outcome(payload, query=False, state='SUCCEEDED'):
    return {'provider_key':payload['provider_key'],'provider_reference':'mock-fixed-'+payload['payment_id'],
            'result':state,'amount_minor':payload['amount_minor'],'currency':payload['currency']}


def callback(http, p, **changes):
    import os
    return http.post('/v1/payment-events', headers={'X-Payment-Key':os.environ['PAYMENT_CALLBACK_KEY']},json={
        'provider_event_id':uuid4().hex, 'payment_id':p['id'],'provider_key':p['provider_key'],
        'provider_reference':p['provider_reference'] or 'mock-fixed-'+p['id'], 'result':'SUCCEEDED',
        'amount_minor':p['amount_minor'],'currency':p['currency'], **changes})


def test_TC14_consent_intent_quote_and_outbox_atomic(client, environment, auth):
    actor=auth('customer'); swap=book(client,environment,actor); key=uuid4()
    response=consent(client,actor,swap,key); assert response.status_code==202
    validate('SwapTransactions',response.json()); assert response.json()['state']=='AWAITING_PAYMENT'
    assert consent(client,actor,swap,key).json()==response.json()
    p=payment(client,actor,swap)
    assert p['state']=='CREATED' and p['amount_minor']==approved_policy()['fee_minor'] and p['currency']=='VND'
    assert counts(client.app.state.db)=={'payments':1,'outbox_messages':1,'payment_events':0,'device_commands':0,'holds':3}
    assert consent(client,actor,swap).status_code==409
    assert consent(client,actor,swap,key,quoted_amount_minor=1).json()['code']=='IDEMPOTENCY_CONFLICT'
    assert cancel(client,actor,response.json()).json()['code']=='RECONCILIATION_REQUIRED'


@pytest.mark.parametrize('change',[{'quoted_amount_minor':1},{'quoted_amount_minor':'9000'},{'expected_version':True},
    {'currency':'USD'},{'accept':False},{'accept':1},{'expected_version':1},{'amount_minor':1}])
def test_quote_state_and_strict_fields(client,environment,auth,change):
    actor=auth('customer');swap=book(client,environment,actor)
    response=consent(client,actor,swap,**change)
    assert response.status_code in (409,422)
    if isinstance(change.get('quoted_amount_minor'), str) or change.get('expected_version') is True:
        assert response.status_code==422
    assert counts(client.app.state.db)['payments']==0
    assert row(client,'swap_transactions',UUID(swap['id']))['state']=='RESERVED'


@pytest.mark.parametrize('boundary',[-1,0,1])
def test_consent_exact_reservation_boundary(client,environment,auth,monkeypatch,boundary):
    actor=auth('customer');swap=book(client,environment,actor)
    current=utcnow()
    with owner(client) as (s,db):
        t=db.table('swap_transactions');s.execute(update(t).where(t.c.id==UUID(swap['id'])).values(reservation_expires_at=current))
    # Only the clock moves; eligibility remains genuine fresh accepted device evidence.
    monkeypatch.setattr(payments,'utcnow',lambda:current+timedelta(microseconds=boundary))
    response=consent(client,actor,swap)
    assert response.status_code==(202 if boundary<0 else 409)
    assert counts(client.app.state.db)['payments']==int(boundary<0)


@pytest.mark.parametrize('damage',['door','bms','hold','service','legacy'])
def test_consent_cannot_use_invalid_resources(client,environment,auth,damage):
    actor=auth('customer');swap=book(client,environment,actor)
    with owner(client) as (s,db):
        if damage=='bms':
            t=db.table('batteries');s.execute(update(t).where(t.c.id==UUID(swap['new_battery_id'])).values(lifecycle='QUARANTINED'))
        elif damage=='hold':
            t=db.table('resource_reservations');s.execute(update(t).where(t.c.swap_id==UUID(swap['id'])).values(released_at=utcnow()))
        else:
            t=db.table('compartments');s.execute(update(t).where(t.c.id==UUID(swap['return_compartment_id'])).values(
                **({'service_state':'MAINTENANCE'} if damage=='service' else {'observed_at':utcnow()} if damage=='legacy' else {'door_state':'OPEN'})))
    assert consent(client,actor,swap).json()['code']=='RESOURCE_UNAVAILABLE'
    assert counts(client.app.state.db)['payments']==0


@pytest.mark.parametrize('state',['SUCCEEDED','FAILED','PENDING'])
def test_verified_mock_outcomes_no_physical_effect(client,environment,auth,state):
    actor=auth('customer');swap=book(client,environment,actor);assert consent(client,actor,swap).status_code==202
    worker.tick(client.app.state.db,transport=lambda p,query=False:outcome(p,query,state))
    p=payment(client,actor,swap);assert p['state']==state
    current=row(client,'swap_transactions',UUID(swap['id']))
    assert current['state']=={'SUCCEEDED':'AWAITING_RETURN','FAILED':'CANCELLED','PENDING':'AWAITING_PAYMENT'}[state]
    assert counts(client.app.state.db)['holds']==(0 if state=='FAILED' else 3)
    assert counts(client.app.state.db)['device_commands']==0
    assert not current['return_observed_at'] and not current['pickup_observed_at']
    reservations.expire(client.app.state.db,current['reservation_expires_at']+timedelta(seconds=1))
    assert row(client,'swap_transactions',current['id'])['state']==current['state']


@pytest.mark.parametrize('field',['provider_key','provider_reference','amount_minor','currency','fake_source','unknown_payment','refund','null_refund'])
def test_TC14_callback_identity_money_and_source(client,environment,auth,field):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap);p=payment(client,actor,swap)
    if field=='fake_source':
        response=client.post('/v1/payment-events',headers=actor,json={'provider_event_id':'fake','payment_id':p['id'],
            'provider_key':p['provider_key'],'provider_reference':'mock','result':'SUCCEEDED','amount_minor':9000,'currency':'VND'})
    else:
        changes={'provider_key':str(uuid4())} if field=='provider_key' else {'amount_minor':1} if field=='amount_minor' else {
            'currency':'USD'} if field=='currency' else {'payment_id':str(uuid4())} if field=='unknown_payment' else {
            'refund_id':str(uuid4())} if field=='refund' else {'refund_id':None} if field=='null_refund' else {'provider_reference':'wrong'}
        if field=='provider_reference':
            with owner(client) as (s,db):
                t=db.table('payments');s.execute(update(t).where(t.c.id==UUID(p['id'])).values(provider_reference='known'))
        response=callback(client,p,**changes)
    assert response.status_code in (401,404,409,422)
    assert counts(client.app.state.db)['payment_events']==0
    assert payment(client,actor,swap)['state']=='CREATED'


def test_TC15_timeout_query_lost_response_and_ten_duplicates(client,environment,auth):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    calls=[]
    def lost(payload,query=False):
        calls.append(query)
        if not query:raise httpx.ReadTimeout('simulated response loss')
        return outcome(payload)
    db=client.app.state.db;start=utcnow();worker.tick(db,now=start,transport=lost)
    p=payment(client,actor,swap);assert p['state']=='UNKNOWN'
    assert row(client,'swap_transactions',UUID(swap['id']))['state']=='REVIEW_REQUIRED'
    worker.tick(db,now=start+timedelta(seconds=31),transport=lost)
    p=payment(client,actor,swap);assert p['state']=='SUCCEEDED' and calls==[False,True]
    identity=uuid4().hex
    responses=[callback(client,p,provider_event_id=identity) for _ in range(10)]
    assert all(r.status_code==202 for r in responses)
    assert [r.json()['duplicate'] for r in responses]==[False]+[True]*9
    assert callback(client,p,provider_event_id=identity,result='FAILED').status_code==409
    worker.process_events(db)
    assert counts(db)['payments']==1 and counts(db)['payment_events']==1
    assert payment(client,actor,swap)['state']=='SUCCEEDED'


@pytest.mark.parametrize('result',['NOT_FOUND','PENDING','UNKNOWN'])
def test_uncertain_query_never_recharges_or_releases(client,environment,auth,result):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    calls=[]
    def unknown(p,query=False):
        calls.append(query)
        return {**outcome(p), 'result':result} if query else {**outcome(p),'result':'UNKNOWN'}
    start=utcnow();db=client.app.state.db;worker.tick(db,now=start,transport=unknown)
    worker.tick(db,now=start+timedelta(seconds=31),transport=unknown)
    assert calls==[False,True] and payment(client,actor,swap)['state']=='UNKNOWN'
    assert counts(db)['holds']==3 and counts(db)['payments']==1


def test_late_conflicting_result_preserves_success_and_requires_review(client,environment,auth):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    worker.tick(client.app.state.db,transport=outcome);p=payment(client,actor,swap)
    for state in ('PENDING','FAILED'):
        assert callback(client,p,result=state).status_code==202
        worker.process_events(client.app.state.db)
        assert payment(client,actor,swap)['state']=='SUCCEEDED'
    assert row(client,'swap_transactions',UUID(swap['id']))['state']=='REVIEW_REQUIRED'
    assert counts(client.app.state.db)['holds']==3
    with client.app.state.db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(client.app.state.db.table('recovery_cases')))==1


def test_success_with_changed_door_requires_review_keeps_money_and_holds(client,environment,auth):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    def changed(payload,query=False):
        with owner(client) as (s,db):
            t=db.table('compartments');s.execute(update(t).where(t.c.id==UUID(swap['return_compartment_id'])).values(door_state='OPEN'))
        return outcome(payload)
    worker.tick(client.app.state.db,transport=changed)
    assert payment(client,actor,swap)['state']=='SUCCEEDED'
    assert row(client,'swap_transactions',UUID(swap['id']))['state']=='REVIEW_REQUIRED'
    assert counts(client.app.state.db)['holds']==3


@pytest.mark.parametrize('stage',['consent','settle'])
def test_payment_and_swap_audit_rollback(client,environment,auth,monkeypatch,stage):
    actor=auth('customer');swap=book(client,environment,actor)
    def fail(*a,**k):raise DomainError(422,'TEST_AUDIT_FAILURE')
    if stage=='consent':
        monkeypatch.setattr(payments,'record',fail)
        assert consent(client,actor,swap).status_code==422
        assert counts(client.app.state.db)['payments']==0 and counts(client.app.state.db)['outbox_messages']==0
        assert row(client,'swap_transactions',UUID(swap['id']))['state']=='RESERVED'
    else:
        consent(client,actor,swap);p=payment(client,actor,swap)
        assert callback(client,p).status_code==202
        monkeypatch.setattr(payments,'record',fail)
        with pytest.raises(DomainError):worker.process_events(client.app.state.db)
        assert payment(client,actor,swap)['state']=='CREATED'
        assert row(client,'swap_transactions',UUID(swap['id']))['state']=='AWAITING_PAYMENT'
        with client.app.state.db.sessions() as s:
            assert s.scalar(select(client.app.state.db.table('payment_events').c.processed_at)) is None


def test_rbac_ownership_revoked_session_and_reconcile(client,environment,auth):
    actor=auth('customer');swap=book(client,environment,actor)
    assert client.get('/v1/swaps/'+swap['id']+'/payment',headers=actor).status_code==404
    for role in ('admin','technician'):
        assert consent(client,auth(role),swap).status_code==403
    consent(client,actor,swap);p=payment(client,actor,swap)
    assert client.get('/v1/swaps/'+swap['id']+'/payment',headers=auth('technician')).status_code==403
    assert client.get('/v1/swaps/'+str(uuid4())+'/payment',headers=actor).status_code==404
    assert client.post('/v1/payments/'+p['id']+'/reconcile',headers=headers(actor),json={'expected_version':1,'reason':'test'}).status_code==403
    worker.tick(client.app.state.db,transport=lambda p,query=False:{**outcome(p),'result':'UNKNOWN'})
    p=payment(client,actor,swap)
    response=client.post('/v1/payments/'+p['id']+'/reconcile',headers=headers(auth()),json={'expected_version':p['version'],'reason':'test'})
    assert response.status_code==202
    assert client.post('/v1/auth/logout',headers=headers(actor)).status_code==200
    assert consent(client,actor,swap).status_code==401


@pytest.mark.parametrize('same_key',[False,True])
def test_concurrent_payment_intents_one_charge(race_environment,same_key):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        actor=login(http,env);swap=book(http,env,actor,env['seed_db']);key=uuid4()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda i:consent(http,actor,swap,key if same_key else uuid4()),range(2)))
        assert sorted(r.status_code for r in responses)==([202,202] if same_key else [202,409])
        assert counts(env['seed_db'])['payments']==1 and counts(env['seed_db'])['outbox_messages']==1
        ledger=Ledger(ROOT/'.cache'/('p6-ledger-'+uuid4().hex)/'ledger.sqlite3')
        def provider(p,query=False):return ledger.query(p['provider_key']) if query else ledger.charge(ProviderChargeRequest(**p))
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:worker.tick(env['seed_db'],transport=provider),range(2)))
        assert payment(http,actor,swap)['state']=='SUCCEEDED'


@pytest.mark.parametrize('competitor',['cancel','expire'])
def test_consent_competes_with_cancel_or_expiry(race_environment,competitor):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        actor=login(http,env);swap=book(http,env,actor,env['seed_db'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(consent,http,actor,swap)
            b=pool.submit(cancel,http,actor,swap) if competitor=='cancel' else pool.submit(reservations.expire,env['seed_db'],utcnow()+timedelta(seconds=121))
            response=a.result();b.result()
        current=row(http,'swap_transactions',UUID(swap['id']));c=counts(env['seed_db'])
        assert (current['state'],c['payments'],c['holds']) in [('AWAITING_PAYMENT',1,3),('CANCELLED',0,0)]


@pytest.mark.parametrize('scenario',['success','failure','timeout','lost-response','delayed'])
def test_private_provider_durable_idempotency_and_restart(monkeypatch,scenario):
    import os
    path=ROOT/'.cache'/('p6-provider-'+uuid4().hex)/'ledger.sqlite3'
    body=ProviderChargeRequest(payment_id=uuid4(),swap_id=uuid4(),provider_key=uuid4(),amount_minor=9000,currency='VND')
    app=mock_app(path,scenario,delay=0)
    with TestClient(app) as http:
        header={'X-Service-Key':os.environ['PAYMENT_SERVICE_KEY'],'Idempotency-Key':str(body.provider_key)}
        assert http.post('/mock/v1/charges',headers={},json=body.model_dump(mode='json')).status_code==401
        for _ in range(2):
            assert http.post('/mock/v1/charges',headers=header,json=body.model_dump(mode='json')).status_code==(503 if scenario=='lost-response' else 202)
        assert http.post('/mock/v1/charges',headers=header,json={**body.model_dump(mode='json'),'amount_minor':1}).status_code==409
    restarted=Ledger(path,'failure')
    result=restarted.query(body.provider_key);validate('ProviderResult',result)
    assert result['result']==('FAILED' if scenario=='failure' else 'PENDING' if scenario=='timeout' else 'SUCCEEDED')
    with restarted.connect() as conn:assert conn.execute('SELECT COUNT(*) FROM charges').fetchone()[0]==1


@pytest.mark.parametrize('damage',['provider_key','amount_minor','currency','result'])
def test_worker_does_not_trust_malformed_provider_result(client,environment,auth,damage):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    def bad(p,query=False):
        return {**outcome(p),damage: str(uuid4()) if damage=='provider_key' else 1 if damage=='amount_minor' else 'USD' if damage=='currency' else 'invented'}
    worker.tick(client.app.state.db,transport=bad)
    assert payment(client,actor,swap)['state']=='UNKNOWN'
    assert counts(client.app.state.db)['holds']==3


def test_cross_customer_payment_hidden_and_terminal_reconcile_rejected(client,environment,auth):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    with owner(client) as (s,db):
        user=uuid4();s.execute(insert(db.table('users')).values(id=user,username='other-'+user.hex,password_hash='not-login',role='CUSTOMER'))
        t=db.table('swap_transactions');s.execute(update(t).where(t.c.id==UUID(swap['id'])).values(customer_id=user))
    assert client.get('/v1/swaps/'+swap['id']+'/payment',headers=actor).status_code==404
    assert consent(client,actor,swap).status_code==404
    with client.app.state.db.sessions() as s:p=dict(payments.get(s,client.app.state.db,UUID(swap['id'])))
    response=client.post('/v1/payments/'+str(p['id'])+'/reconcile',headers=headers(auth()),json={'expected_version':p['version'],'reason':'test'})
    assert response.status_code==409


def test_payment_result_rollback_then_retry_applies_once(client,environment,auth,monkeypatch):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    db=client.app.state.db;p=payment(client,actor,swap);callback(client,p)
    original=payments.change_swap
    def fail(*a,**k):raise DomainError(422,'TEST_SWAP_FAILURE')
    monkeypatch.setattr(payments,'change_swap',fail)
    with pytest.raises(DomainError):worker.process_events(db)
    assert payment(client,actor,swap)['state']=='CREATED'
    assert row(client,'swap_transactions',UUID(swap['id']))['state']=='AWAITING_PAYMENT'
    monkeypatch.setattr(payments,'change_swap',original);worker.process_events(db);worker.process_events(db)
    assert payment(client,actor,swap)['state']=='SUCCEEDED' and counts(db)['payments']==1


def test_pending_timeout_reconcile_version_and_query_only(client,environment,auth):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    db=client.app.state.db;start=utcnow()
    worker.tick(db,now=start,transport=lambda p,query=False:outcome(p,query,'PENDING'))
    p=payment(client,actor,swap)
    route='/v1/payments/'+p['id']+'/reconcile';key=uuid4()
    assert client.post(route,headers=headers(auth()),json={'expected_version':1,'reason':'test'}).json()['code']=='VERSION_CONFLICT'
    admin=auth();body={'expected_version':p['version'],'reason':'test'}
    result=client.post(route,headers=headers(admin,key),json=body);assert result.status_code==202
    assert client.post(route,headers=headers(admin,key),json=body).json()==result.json()
    calls=[]
    def query(p,query=False):calls.append(query);return outcome(p,query)
    worker.tick(db,now=start+timedelta(seconds=31),transport=query)
    assert calls==[True] and payment(client,actor,swap)['state']=='SUCCEEDED'


@pytest.mark.parametrize('kind',['cancel','expire'])
def test_settlement_competes_with_cancel_or_expiration(race_environment,kind):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        actor=login(http,env);swap=book(http,env,actor,env['seed_db']);accepted=consent(http,actor,swap).json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(worker.tick,env['seed_db'],transport=outcome)
            b=pool.submit(cancel,http,actor,accepted) if kind=='cancel' else pool.submit(reservations.expire,env['seed_db'],utcnow()+timedelta(seconds=121))
            a.result();b.result()
        assert payment(http,actor,swap)['state']=='SUCCEEDED'
        assert row(http,'swap_transactions',UUID(swap['id']))['state']=='AWAITING_RETURN'
        assert counts(env['seed_db'])['holds']==3


@pytest.mark.parametrize('kind',['callback','provider'])
def test_non_ascii_private_key_is_rejected_not_server_error(client,kind):
    if kind=='callback':
        response=client.post('/v1/payment-events',headers=[(b'X-Payment-Key',b'\xff')],json={
            'provider_event_id':uuid4().hex,'payment_id':str(uuid4()),'provider_key':str(uuid4()),
            'provider_reference':'mock-test','result':'SUCCEEDED','amount_minor':9000,'currency':'VND'})
    else:
        path=ROOT/'.cache'/('p6-key-test-'+uuid4().hex)/'ledger.sqlite3'
        with TestClient(mock_app(path)) as provider:
            response=provider.get('/mock/v1/charges/'+str(uuid4()),headers=[(b'X-Service-Key',b'\xff')])
    assert response.status_code==401


def test_callback_delivery_response_loss_retries_same_event_and_survives_restart(client,environment,auth):
    from simulators.payment.callbacks import deliver
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap);p=payment(client,actor,swap)
    path=ROOT/'.cache'/('p6-callback-'+uuid4().hex)/'ledger.sqlite3'
    ledger=Ledger(path);ledger.charge(ProviderChargeRequest(payment_id=p['id'],swap_id=p['swap_id'],
        provider_key=p['provider_key'],amount_minor=p['amount_minor'],currency=p['currency']))
    url='http://127.0.0.1/v1/payment-events'
    class LostResponse:
        def post(self,*args,**kwargs):
            assert client.post(*args,**kwargs).status_code==202
            raise httpx.ReadTimeout('Only callback response was lost')
    assert deliver(ledger,url,LostResponse())==0
    assert counts(client.app.state.db)['payment_events']==1
    assert deliver(Ledger(path),url,client)==1
    assert deliver(Ledger(path),url,client)==0
    worker.process_events(client.app.state.db)
    assert payment(client,actor,swap)['state']=='SUCCEEDED'
    assert counts(client.app.state.db)['payment_events']==1 and counts(client.app.state.db)['device_commands']==0
    with ledger.connect() as s:
        assert s.execute('SELECT COUNT(*) FROM charges').fetchone()[0]==1
        assert s.execute('SELECT COUNT(*) FROM callback_deliveries').fetchone()[0]==1


@pytest.mark.parametrize('url',['https://example.com/v1/payment-events','http://127.0.0.1/other','http://user:password@localhost/v1/payment-events'])
def test_callback_delivery_stays_private(url):
    from simulators.payment.callbacks import deliver
    from app.config import ConfigNotReady
    ledger=Ledger(ROOT/'.cache'/('p6-callback-url-'+uuid4().hex)/'ledger.sqlite3')
    with pytest.raises(ConfigNotReady):deliver(ledger,url)


def test_terminal_failure_conflict_keeps_durable_review_evidence(client,environment,auth):
    actor=auth('customer');swap=book(client,environment,actor);consent(client,actor,swap)
    worker.tick(client.app.state.db,transport=lambda p,query=False:outcome(p,query,'FAILED'))
    p=payment(client,actor,swap);assert p['state']=='FAILED'
    assert callback(client,p,result='SUCCEEDED').status_code==202
    worker.process_events(client.app.state.db)
    assert payment(client,actor,swap)['state']=='FAILED'
    assert row(client,'swap_transactions',UUID(swap['id']))['state']=='CANCELLED'
    with client.app.state.db.sessions() as s:
        case=s.execute(select(client.app.state.db.table('recovery_cases'))).mappings().one()
        assert case['state']=='OPEN' and case['new_pin_delivered']=='UNKNOWN'
