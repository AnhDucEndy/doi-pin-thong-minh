"""B1a PostgreSQL foundation, NOT positive refund eligibility or TC16/CT13 E2E.

Rows inserted directly below are storage/constraint fixtures only. They are
never used as a no-delivery certificate or as proof of physical custody.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Event
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import DBAPIError

from app.api.refunds import ReasonAction
from app.application import refund_audit, refunds
from app.application.identity import DomainError, idempotent, utcnow
from app.domain.refunds import transition, reconcile_mode
from app.main import create_app
from app.seed import demo_id
from test_phase1 import headers, validate, create_customer
from test_phase5 import race_environment, login
from test_phase6 import book, consent, outcome, payment
from app.workers import payment as payment_worker


TABLES = ('refunds','refund_attempts','refund_retry_permissions','refund_permit_redemptions',
          'refund_eligibility_certificates','refund_certificate_redemptions')


def charge(client, environment, auth):
    customer = auth('customer')
    swap = book(client, environment, customer)
    assert consent(client, customer, swap).status_code == 202
    payment_worker.tick(client.app.state.db, transport=outcome)
    return customer, swap, payment(client, customer, swap)


def protected(db):
    names = TABLES + ('payments','batteries','swap_transactions','resource_reservations',
        'device_commands','audit_events','outbox_messages','idempotency_records')
    with db.sessions() as s:
        return {n: sorted([dict(r) for r in s.execute(select(db.table(n))).mappings()], key=str) for n in names}


def store(session, db, p, state='REQUESTED', **changes):
    """Storage-only record. Never called by a successful public refund request."""
    values = dict(id=uuid4(), payment_id=UUID(p['id']), requested_by=demo_id('admin'),
        provider_key=uuid4(), amount_minor=p['amount_minor'], reason='storage fixture', state=state)
    values.update(changes)
    return dict(session.execute(insert(db.table('refunds')).values(**values).returning(db.table('refunds'))).mappings().one())


def post(client, actor, p, key=None, **changes):
    return client.post('/v1/payments/'+p['id']+'/refund', headers=headers(actor,key),
        json={'expected_version':p['version'], 'reason':'mock refund review', **changes})


def test_migration_grants_clean_and_upgrade(environment):
    # environment executes 0001, persists a user, upgrades to head twice and
    # verifies the historical marker; a clean schema is retained, never dropped.
    with environment['owner'].connect() as c:
        assert c.scalar(text('select version_num from alembic_version')) == '0010_no_delivery_eligibility'
        for name in TABLES:
            target = environment['settings'].schema+'.'+name
            assert c.scalar(text('select to_regclass(:n)'), {'n':target})
            assert c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,'SELECT')"), {'n':target})
            assert not c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,'DELETE')"), {'n':target})
            assert c.scalar(text('select count(*) from '+name)) == 0
        for col in ('provider_key','payment_id','requested_by','reason','amount_minor'):
            assert not c.scalar(text("select has_column_privilege('doi_pin_runtime',:n,:col,'UPDATE')"),
                {'n':environment['settings'].schema+'.refunds','col':col})
        for name in TABLES[1:]:
            assert not c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,'UPDATE')"),
                {'n':environment['settings'].schema+'.'+name})
        # 0010 grants append-only certificate writes; explicit 0009 storage
        # remains SELECT-only and is checked in test_phase8b_b1b_migration.
        for name in TABLES[-2:]:
            assert c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,'INSERT')"),
                {'n':environment['settings'].schema+'.'+name})


@pytest.mark.parametrize('changes',[{'amount_minor':1},{'currency':'USD'},{'custody':'CUSTOMER'},
    {'state':'SUCCEEDED'},{'actor_id':str(uuid4())},{'reason':''},{'reason':None},
    {'expected_version':True},{'expected_version':'1'},{'expected_version':0}])
def test_strict_request_schema(client,auth,changes):
    response = post(client,auth(),{'id':str(uuid4()),'version':1},**changes)
    assert response.status_code == 422 and response.json()['code']=='VALIDATION_ERROR'


@pytest.mark.parametrize('role',['customer','technician'])
def test_mutation_rbac_before_lookup(client,auth,role):
    actor=auth(role)
    assert post(client,actor,{'id':str(uuid4()),'version':1}).status_code==403
    assert client.post('/v1/refunds/'+str(uuid4())+'/reconcile',headers=headers(actor),
        json={'expected_version':1,'reason':'review'}).status_code==403


def test_missing_certificate_refuses_before_all_writes(client,environment,auth):
    _,swap,p=charge(client,environment,auth)
    admin=auth(); before=protected(client.app.state.db); key=uuid4()
    for current_key, changes in ((key,{}),(key,{}),(uuid4(),{}),(key,{'reason':'other body'})):
        response=post(client,admin,p,current_key,**changes)
        assert (response.status_code,response.json()['code'])==(422,'REFUND_EVIDENCE_REQUIRED')
        assert protected(client.app.state.db)==before
    # Failed attempts are not cached as success or as successful idempotency receipts.
    assert len(before['resource_reservations'])==3
    assert before['payments'][0]['state']=='SUCCEEDED'


def test_expected_payment_version_and_unverified_charge(client,environment,auth):
    actor=auth('customer'); swap=book(client,environment,actor)
    assert consent(client,actor,swap).status_code==202
    p=payment(client,actor,swap); admin=auth(); before=protected(client.app.state.db)
    assert post(client,admin,p,expected_version=p['version']+1).json()['code']=='VERSION_CONFLICT'
    assert post(client,admin,p).json()['code']=='STATE_CONFLICT'
    assert protected(client.app.state.db)==before


def test_get_refund_owner_admin_and_cross_customer(client,environment,auth):
    customer,_,p=charge(client,environment,auth); admin=auth()
    other,password=create_customer(client,admin)
    other_login=client.post('/v1/auth/login',json={'username':other['username'],'password':password})
    stranger={'Authorization':'Bearer '+other_login.json()['access_token']}
    path='/v1/payments/'+p['id']+'/refund'
    assert client.get(path,headers=customer).status_code==404
    assert client.get(path,headers=stranger).status_code==403
    with client.app.state.db.sessions.begin() as s: r=store(s,client.app.state.db,p)
    for actor in (admin,customer):
        response=client.get(path,headers=actor)
        assert response.status_code==200
        validate('Refunds',response.json())
        assert response.json()['id']==str(r['id'])
        assert 'currency' not in response.json()
    assert client.get(path,headers=stranger).status_code==403
    assert client.get(path,headers=auth('technician')).status_code==403


@pytest.mark.parametrize('state,code',[('FAILED','REFUND_RETRY_NOT_AUTHORIZED'),
    ('UNKNOWN','REFUND_EVIDENCE_REQUIRED'),('SUCCEEDED','STATE_CONFLICT'),('PENDING','STATE_CONFLICT')])
def test_reconcile_version_state_and_no_dispatch(client,environment,auth,state,code):
    _,_,p=charge(client,environment,auth);db=client.app.state.db
    with db.sessions.begin() as s:r=store(s,db,p,state)
    actor=auth(); before=protected(db); path='/v1/refunds/'+str(r['id'])+'/reconcile'
    assert client.post(path,headers=headers(actor),json={'expected_version':2,'reason':'review'}).json()['code']=='VERSION_CONFLICT'
    key=uuid4()
    for _ in range(2):
        response=client.post(path,headers=headers(actor,key),json={'expected_version':1,'reason':'review'})
        assert response.json()['code']==code and response.status_code in (409,422)
    assert protected(db)==before


def test_audit_insert_failure_rolls_back_state(client,environment,auth):
    _,_,p=charge(client,environment,auth);db=client.app.state.db
    with db.sessions.begin() as s:r=store(s,db,p)
    before=protected(db)
    with pytest.raises(DBAPIError),db.sessions.begin() as s:
        old=refund_audit.snapshot(s,db,r['id'])
        s.execute(update(db.table('refunds')).where(db.table('refunds').c.id==r['id']).values(state='UNKNOWN',version=2))
        # Actual NOT NULL audit failure, not a simulated successful audit.
        refund_audit.record(s,db,demo_id('admin'),'REFUND_UNKNOWN',r['id'],before=old,correlation_id=None)
    assert protected(db)==before


@pytest.mark.parametrize('damage',['amount','duplicate_payment','duplicate_key','missing_payment','immutable','downgrade','unknown_post','failed_retry'])
def test_refund_storage_constraints(client,environment,auth,damage):
    _,_,p=charge(client,environment,auth); db=client.app.state.db
    with db.sessions.begin() as s:
        r=store(s,db,p,state='SUCCEEDED' if damage=='downgrade' else 'UNKNOWN' if damage=='unknown_post' else 'FAILED' if damage=='failed_retry' else 'REQUESTED')
    with pytest.raises(DBAPIError),db.sessions.begin() as s:
        if damage=='amount':store(s,db,p,amount_minor=1)
        elif damage=='duplicate_payment':store(s,db,p)
        elif damage=='duplicate_key':store(s,db,p,provider_key=r['provider_key'])
        elif damage=='missing_payment':store(s,db,{**p,'id':str(uuid4())})
        else:
            changes={'amount_minor':2} if damage=='immutable' else {'state':'FAILED' if damage=='downgrade' else 'PENDING','version':2}
            s.execute(update(db.table('refunds')).where(db.table('refunds').c.id==r['id']).values(**changes))


def test_attempt_permission_constraints_and_append_only(client,environment,auth):
    _,_,p=charge(client,environment,auth);db=client.app.state.db; initial=uuid4();permit=uuid4();next_id=uuid4();now=utcnow()
    with db.sessions.begin() as s:
        r=store(s,db,p)
        s.execute(insert(db.table('refund_attempts')).values(id=initial,refund_id=r['id'],generation=0))
        s.execute(insert(db.table('refund_retry_permissions')).values(id=permit,refund_id=r['id'],prior_attempt_id=initial,
            prior_generation=0,attempt_id=next_id,generation=1,issued_at=now,expires_at=now+timedelta(seconds=15),
            payload={'storage_only':True},payload_hash='a'*64))
    invalid = [lambda s:s.execute(insert(db.table('refund_attempts')).values(id=uuid4(),refund_id=r['id'],generation=0)),
        lambda s:s.execute(insert(db.table('refund_attempts')).values(id=uuid4(),refund_id=r['id'],generation=1,permit_id=permit)),
        lambda s:s.execute(update(db.table('refund_retry_permissions')).where(db.table('refund_retry_permissions').c.id==permit).values(payload_hash='b'*64))]
    for execute in invalid:
        with pytest.raises(DBAPIError),db.sessions.begin() as s:execute(s)
    with db.sessions.begin() as s:
        s.execute(insert(db.table('refund_attempts')).values(id=next_id,refund_id=r['id'],generation=1,permit_id=permit))
    for identity,at in ((initial,now),(next_id,now+timedelta(seconds=16))):
        with pytest.raises(DBAPIError),db.sessions.begin() as s:
            s.execute(insert(db.table('refund_permit_redemptions')).values(permit_id=permit,attempt_id=identity,redeemed_at=at))
    with db.sessions.begin() as s:
        s.execute(insert(db.table('refund_permit_redemptions')).values(permit_id=permit,attempt_id=next_id,redeemed_at=now))
    with pytest.raises(DBAPIError),db.sessions.begin() as s:
        s.execute(insert(db.table('refund_permit_redemptions')).values(permit_id=permit,attempt_id=next_id,redeemed_at=now))


def test_immutable_trigger_also_protects_owner_role(client,environment,auth):
    from test_phase2 import owner
    _,_,p=charge(client,environment,auth);db=client.app.state.db
    with db.sessions.begin() as s:r=store(s,db,p)
    with owner(client) as (connection,_):
        for changes in ({'provider_key':uuid4(),'version':2},{'reason':'rewrite','version':2},
                        {'amount_minor':1,'version':2},{'state':'PENDING','version':1}):
            with pytest.raises(DBAPIError),connection.begin_nested():
                connection.execute(update(db.table('refunds')).where(db.table('refunds').c.id==r['id']).values(**changes))
    assert protected(db)['refunds'][0]==r


def test_audit_actual_before_after_redaction_replay_and_rollback(client,environment,auth):
    _,_,p=charge(client,environment,auth);db=client.app.state.db;identity=uuid4();key=uuid4();actor=demo_id('admin')
    def create(s):
        before=refund_audit.snapshot(s,db,identity);assert before is None
        r=store(s,db,p,id=identity,reason='never copy free text to audit')
        refund_audit.record(s,db,actor,'REFUND_REQUEST_CREATED',identity,before=before,
            correlation_id=UUID(p['swap_id']),references={'attempt_id':str(key),'password':'not-an-actual-credential'})
        return {'id':str(r['id'])}
    with db.sessions.begin() as s:
        first=idempotent(s,db,actor,'storage-test',key,{},202,lambda:create(s))
        assert idempotent(s,db,actor,'storage-test',key,{},202,lambda:pytest.fail('replayed mutation'))==first
        before=refund_audit.snapshot(s,db,identity)
        s.execute(update(db.table('refunds')).where(db.table('refunds').c.id==identity).values(state='UNKNOWN',version=2))
        refund_audit.record(s,db,actor,'REFUND_UNKNOWN',identity,before=before,correlation_id=UUID(p['swap_id']))
    with db.sessions() as s:
        t=db.table('audit_events');rows=s.execute(select(t).where(t.c.aggregate_id==identity).order_by(t.c.created_at,t.c.action)).mappings().all()
        assert len(rows)==2
        creation=next(a for a in rows if a['action']=='REFUND_REQUEST_CREATED')
        changed=next(a for a in rows if a['action']=='REFUND_UNKNOWN')
        assert creation['before_data'] is None and creation['after_data']['refund']['state']=='REQUESTED'
        assert changed['before_data']['refund']['state']=='REQUESTED'
        assert changed['after_data']['refund']['state']=='UNKNOWN'
        assert (changed['before_data']['refund']['version'],changed['after_data']['refund']['version'])==(1,2)
        assert changed['after_data']['refund']['charge_state']=='SUCCEEDED'
        assert all(word not in json.dumps([dict(r) for r in rows],default=str) for word in ('password','never copy','not-an-actual-credential'))
    before=protected(db)
    with pytest.raises(RuntimeError),db.sessions.begin() as s:
        old=refund_audit.snapshot(s,db,identity)
        s.execute(update(db.table('refunds')).where(db.table('refunds').c.id==identity).values(state='SUCCEEDED',version=3))
        refund_audit.record(s,db,actor,'REFUND_RESULT_VERIFIED',identity,before=old,correlation_id=UUID(p['swap_id']))
        raise RuntimeError('fault after audit insert before commit')
    assert protected(db)==before


@pytest.mark.parametrize('start,end,allowed',[('REQUESTED','PENDING',True),('REQUESTED','UNKNOWN',True),
    ('PENDING','SUCCEEDED',True),('UNKNOWN','FAILED',True),('UNKNOWN','PENDING',False),
    ('FAILED','PENDING',False),('SUCCEEDED','FAILED',False),('REQUESTED','SUCCEEDED',False)])
def test_state_policy(start,end,allowed):
    if allowed:assert transition(start,end)==end
    else:
        with pytest.raises(DomainError):transition(start,end)
    assert reconcile_mode('UNKNOWN')=='QUERY_ONLY'


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_missing_certificate_no_partial_intent(race_environment,same_key):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        customer=login(http,env);admin=login(http,env,'admin')
        swap=book(http,env,customer,db);assert consent(http,customer,swap).status_code==202
        payment_worker.tick(db,transport=outcome);p=payment(http,customer,swap)
        before=protected(db);key=uuid4()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:post(http,admin,p,key if same_key else uuid4()),range(2)))
        assert [(r.status_code,r.json()['code']) for r in responses]==[(422,'REFUND_EVIDENCE_REQUIRED')]*2
        assert protected(db)==before


def test_runtime_openapi_matches_original_refund_contract(client):
    from openapi_spec_validator import validate_spec
    from test_phase1 import SPEC
    spec=client.app.openapi();validate_spec(spec)
    for path in ('/v1/payments/{payment_id}/refund','/v1/refunds/{refund_id}/reconcile'):
        for method,op in spec['paths'][path].items():
            assert op==SPEC['paths'][path][method]
    assert not any(path.startswith('/mock/') for path in spec['paths'])
