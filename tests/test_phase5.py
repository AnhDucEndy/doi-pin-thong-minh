"""TC09/TC10, pre-payment TC12 and scoped TC13; real PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import secrets
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update

from app.application import reservations as service
from app.application.identity import DomainError, utcnow
from app.config import ROOT, approved_policy
from app.main import create_app
from app.seed import demo_id
from test_phase1 import headers, validate
from test_phase2 import owner
from test_phase4 import connected, row, send, snapshot_packet, telemetry, process

PIN = demo_id('S01:battery:2')
SLOT = demo_id('S01:slot:1')


def login(http, env, name='customer'):
    result = http.post('/v1/auth/login', json={'username': name, 'password': env['passwords'][name]})
    assert result.status_code == 200
    return {'Authorization': 'Bearer ' + result.json()['access_token']}


def prepare(http, env, owner_db=None):
    boot = connected(http, env)
    assert send(http, env, telemetry(boot, soc=80, soh=80, temperature_c=40)).status_code == 202
    def update_rows(connection, db):
        slots, pins = db.table('compartments'), db.table('batteries')
        connection.execute(update(slots).where(slots.c.id.in_([SLOT, demo_id('S01:slot:2')])).values(service_state='ACTIVE'))
        connection.execute(update(pins).where(pins.c.id == PIN).values(lifecycle='IN_SERVICE'))
    if owner_db:
        with owner_db.sessions.begin() as connection:
            update_rows(connection, owner_db)
    else:
        with owner(http) as (connection, db):
            update_rows(connection, db)
    return boot


def qr(http, auth, key=None, station='S01'):
    result = http.post('/v1/qr-challenges', headers=headers(auth, key), json={'station_id': str(demo_id(station))})
    assert result.status_code == 201
    validate('QrResponse', result.json())
    return result.json()


def verify(http, env, value, method='QR', key=None, station='S01'):
    return http.post('/v1/device/verifications', headers={'X-Device-Key': env['keys'][station],
        'Idempotency-Key': str(key or uuid4())}, json={'method': method, 'credential': value})


def verified(http, env, auth):
    code = qr(http, auth)
    result = verify(http, env, code['qr_token'])
    assert result.status_code == 201, result.json().get('code')
    validate('SwapTransactions', result.json())
    return result.json()


def reserve(http, auth, swap, key=None):
    return http.post(f'/v1/swaps/{swap["id"]}/reserve', headers=headers(auth, key),
                     json={'expected_version': swap['version']})


def cancel(http, auth, swap, key=None):
    return http.post(f'/v1/swaps/{swap["id"]}/cancel', headers=headers(auth, key),
                     json={'expected_version': swap['version'], 'reason': 'Test cancellation before payment'})


def test_TC09_qr_delivery_idempotency_and_no_plaintext_cache(client, environment, auth):
    customer = auth(); customer = auth('customer')
    key = uuid4()
    first = qr(client, customer, key)
    assert qr(client, customer, key) == first
    assert len(first['qr_token']) >= 40
    assert qr(client, customer)['qr_token'] != first['qr_token']
    changed = client.post('/v1/qr-challenges', headers=headers(customer, key), json={'station_id': str(demo_id('S02'))})
    assert changed.status_code == 409 and changed.json()['code'] == 'IDEMPOTENCY_CONFLICT'
    db = client.app.state.db
    with db.sessions() as session:
        for name in ('idempotency_records', 'audit_events', 'qr_challenges'):
            values = [dict(r) for r in session.execute(select(db.table(name))).mappings()]
            assert first['qr_token'] not in json.dumps(values, default=str)


@pytest.mark.parametrize('role', ['admin', 'technician'])
def test_TC09_qr_customer_role_only(client, auth, role):
    result = client.post('/v1/qr-challenges', headers=headers(auth(role)), json={'station_id': str(demo_id('S01'))})
    assert result.status_code == 403


@pytest.mark.parametrize('problem,expected', [('expired',409),('unknown',401),('tampered',401),('used',409),
    ('wrong_station',403),('locked',403),('wrong_role',403),('disabled',403)])
def test_TC09_qr_rejections(client, environment, auth, problem, expected):
    prepare(client, environment)
    customer = auth('customer'); code = qr(client, customer)
    value = code['qr_token']
    if problem == 'used':
        assert verify(client, environment, value).status_code == 201
    if problem in ('expired', 'locked', 'wrong_role', 'disabled'):
        with owner(client) as (connection, db):
            if problem == 'expired':
                table = db.table('qr_challenges'); connection.execute(update(table).where(table.c.id == UUID(code['challenge_id'])).values(expires_at=utcnow()))
            elif problem == 'disabled':
                table=db.table('devices');connection.execute(update(table).where(table.c.id==demo_id('device:S01')).values(enabled=False))
            else:
                table=db.table('users');connection.execute(update(table).where(table.c.id==demo_id('customer')).values(**({'state':'LOCKED'} if problem=='locked' else {'role':'ADMIN'})))
    if problem == 'unknown': value = secrets.token_urlsafe(32)
    if problem == 'tampered': value = value + 'x'
    result = verify(client, environment, value, station='S02' if problem == 'wrong_station' else 'S01')
    assert result.status_code == expected
    if problem != 'used':
        assert row(client,'qr_challenges',UUID(code['challenge_id']))['consumed_at'] is None


def test_TC09_verified_retry_and_replay_only_one_consumption(client, environment, auth):
    prepare(client,environment);customer=auth('customer');code=qr(client,customer);key=uuid4()
    first=verify(client,environment,code['qr_token'],key=key)
    assert first.status_code==201
    assert verify(client,environment,code['qr_token'],key=key).json()==first.json()
    assert verify(client,environment,code['qr_token']).json()['code']=='QR_ALREADY_USED'
    changed=verify(client,environment,code['qr_token']+'x',key=key)
    assert changed.status_code==409 and changed.json()['code']=='IDEMPOTENCY_CONFLICT'
    assert client.get('/v1/swaps/'+first.json()['id'],headers=customer).json()['state']=='VERIFIED'
    db=client.app.state.db
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(db.table('resource_reservations')))==0
        assert s.scalar(select(func.count()).select_from(db.table('device_commands')))==0


def test_TC09_rfid_reusable_revocation_and_reads_do_not_reserve(client,environment,auth):
    prepare(client,environment);admin,customer=auth(),auth('customer');value=secrets.token_urlsafe(24)
    uri=f'/v1/users/{demo_id("customer")}/credentials';key=uuid4()
    credential=client.post(uri,headers=headers(admin,key),json={'rfid_value':value})
    assert credential.status_code==201;validate('CredentialView',credential.json())
    assert client.post(uri,headers=headers(admin,key),json={'rfid_value':value}).json()==credential.json()
    assert client.post(uri,headers=headers(admin),json={'rfid_value':value}).status_code==409
    first=verify(client,environment,value,'RFID');assert first.status_code==201
    assert verify(client,environment,value,'RFID').json()['code']=='ACTIVE_TRANSACTION'
    assert cancel(client,customer,first.json()).status_code==200
    second=verify(client,environment,value,'RFID');assert second.status_code==201 and second.json()['id']!=first.json()['id']
    assert cancel(client,customer,second.json()).status_code==200
    result=client.post(f'/v1/credentials/{credential.json()["id"]}/revoke',headers=headers(admin))
    assert result.status_code==200 and result.json()['revoked'] is True
    assert verify(client,environment,value,'RFID').status_code==401
    assert verify(client,environment,'missing-value','RFID').status_code==401


def test_TC10_reserve_quote_atomic_resources_retry_and_cancel(client,environment,auth):
    prepare(client,environment);customer=auth('customer');swap=verified(client,environment,customer);key=uuid4()
    result=reserve(client,customer,swap,key);assert result.status_code==200;booked=result.json()
    validate('SwapTransactions',booked);assert booked['state']=='RESERVED' and booked['amount_minor']==9000
    assert booked['old_battery_id']!=booked['new_battery_id'] and booked['return_compartment_id']!=booked['supply_compartment_id']
    assert reserve(client,customer,swap,key).json()==booked
    assert reserve(client,customer,swap).status_code==409
    db=client.app.state.db
    with db.sessions() as s:
        holds=db.table('resource_reservations');rows=s.execute(select(holds).where(holds.c.swap_id==UUID(swap['id']))).mappings().all()
        assert len(rows)==3 and all(r['released_at'] is None for r in rows)
        for name in ('payments','outbox_messages','device_commands'):
            assert s.scalar(select(func.count()).select_from(db.table(name)))==0
    key=uuid4();cancelled=cancel(client,customer,booked,key)
    assert cancelled.status_code==200 and cancelled.json()['state']=='CANCELLED'
    assert cancel(client,customer,booked,key).json()==cancelled.json()
    assert cancel(client,customer,cancelled.json()).status_code==409
    with db.sessions() as s:
        assert all(s.scalars(select(holds.c.released_at).where(holds.c.swap_id==UUID(swap['id']))))


@pytest.mark.parametrize('problem', ['soc','soh','hot','stale','unverified','quarantine','door','maintenance','no_return'])
def test_TC10_eligibility_rejections_no_partial_holds(client,environment,auth,problem):
    boot=prepare(client,environment);customer=auth('customer');swap=verified(client,environment,customer)
    if problem in ('soc','soh','hot'):
        send(client,environment,telemetry(boot,2,**{'soc':{'soc':79},'soh':{'soh':79},'hot':{'temperature_c':41}}[problem]))
    else:
        with owner(client) as (c,db):
            if problem in ('stale','unverified'):
                t=db.table('device_events' if problem=='unverified' else 'battery_telemetry')
                c.execute(update(t).values(**({'accepted':False} if problem=='unverified' else {'measured_at':utcnow()-timedelta(seconds=30)})))
            elif problem=='quarantine':
                t=db.table('batteries');c.execute(update(t).where(t.c.id==PIN).values(lifecycle='QUARANTINED'))
            else:
                t=db.table('compartments');identity=SLOT if problem=='no_return' else demo_id('S01:slot:2')
                c.execute(update(t).where(t.c.id==identity).values(**({'door_state':'OPEN'} if problem=='door' else {'service_state':'MAINTENANCE'})))
    result=reserve(client,customer,swap)
    if problem=='unverified':assert result.status_code==503  # No accepted snapshot -> offline.
    else:assert result.status_code==200 and result.json()['state']=='CANCELLED'
    db=client.app.state.db
    with db.sessions() as s:assert s.scalar(select(func.count()).select_from(db.table('resource_reservations')))==0


@pytest.mark.parametrize('delta_us', [-1,0,1])
def test_verification_ttl_boundary(client,environment,auth,monkeypatch,delta_us):
    prepare(client,environment);customer=auth('customer');swap=verified(client,environment,customer)
    stored=row(client,'swap_transactions',UUID(swap['id']))
    instant=stored['created_at']+timedelta(seconds=approved_policy()['verification_ttl_seconds'],microseconds=delta_us)
    monkeypatch.setattr(service,'utcnow',lambda:instant)
    if delta_us<0:
        # Eligibility is stale at +120s even though verification has not expired.
        assert reserve(client,customer,swap).status_code==503
    else:assert reserve(client,customer,swap).json()['state']=='CANCELLED'


@pytest.mark.parametrize('delta_us', [-1,0,1])
def test_reservation_expiry_boundary_and_retry_does_not_resurrect(client,environment,auth,delta_us):
    prepare(client,environment);customer=auth('customer');swap=verified(client,environment,customer);key=uuid4()
    booked=reserve(client,customer,swap,key).json();db=client.app.state.db
    stored=row(client,'swap_transactions',UUID(swap['id']));deadline=stored['reservation_expires_at']
    service.expire(db,deadline+timedelta(microseconds=delta_us))
    current=client.get('/v1/swaps/'+swap['id'],headers=customer).json()
    assert current['state']==('RESERVED' if delta_us<0 else 'CANCELLED')
    # Contractual idempotency receipt is historical; re-read current state after a retry.
    assert reserve(client,customer,swap,key).json()==booked
    assert client.get('/v1/swaps/'+swap['id'],headers=customer).json()['state']==current['state']


@pytest.mark.parametrize('effect', ['payment','outbox','command'])
def test_expiration_and_cancel_never_release_uncertain_resources(client,environment,auth,effect):
    prepare(client,environment);customer=auth('customer');swap=verified(client,environment,customer)
    booked=reserve(client,customer,swap).json();identity=UUID(swap['id'])
    with owner(client) as (c,db):
        if effect=='payment':c.execute(insert(db.table('payments')).values(id=uuid4(),swap_id=identity,provider_key=uuid4(),amount_minor=9000))
        elif effect=='outbox':c.execute(insert(db.table('outbox_messages')).values(id=uuid4(),aggregate_type='swap',aggregate_id=identity,kind='CHARGE',dedup_key=uuid4().hex,payload={}))
        else:c.execute(insert(db.table('device_commands')).values(id=uuid4(),swap_id=identity,device_id=demo_id('device:S01'),compartment_id=SLOT,kind='OPEN_RETURN',expires_at=utcnow()+timedelta(seconds=15),payload_hash='fixture',payload={}))
    assert cancel(client,customer,booked).json()['code']=='RECONCILIATION_REQUIRED'
    service.expire(client.app.state.db,row(client,'swap_transactions',identity)['reservation_expires_at']+timedelta(seconds=1))
    assert row(client,'swap_transactions',identity)['state']=='RESERVED'


def test_TC13_roles_ownership_and_no_device_key_in_user_api(client,environment,auth):
    prepare(client,environment);customer=auth('customer');swap=verified(client,environment,customer)
    for role in ('admin','technician'):
        assert reserve(client,auth(role),swap).status_code==403
    assert client.get('/v1/swaps',headers=auth('technician')).status_code==403
    assert any(item['id']==swap['id'] for item in client.get('/v1/swaps',headers=auth()).json()['items'])
    assert client.get('/v1/swaps?active=true',headers=customer).json()['items'][0]['id']==swap['id']
    with owner(client) as (c,db):
        user=uuid4();c.execute(insert(db.table('users')).values(id=user,username='other-'+user.hex,password_hash='not-a-login-account',role='CUSTOMER'))
        c.execute(update(db.table('swap_transactions')).where(db.table('swap_transactions').c.id==UUID(swap['id'])).values(customer_id=user))
    assert client.get('/v1/swaps/'+swap['id'],headers=customer).status_code==404
    assert reserve(client,customer,swap).status_code==404
    assert client.post('/v1/device/verifications',headers=headers(customer),json={'method':'QR','credential':'test'}).status_code==401


def test_verification_transaction_rollback_keeps_qr_unused(client,environment,auth,monkeypatch):
    prepare(client,environment);customer=auth('customer');code=qr(client,customer)
    before=client.get('/v1/swaps',headers=customer).json()['items']
    def fail(*args,**kwargs):raise DomainError(422,'TEST_AUDIT_FAILURE')
    monkeypatch.setattr(service,'swap_audit',fail)
    assert verify(client,environment,code['qr_token']).status_code==422
    assert row(client,'qr_challenges',UUID(code['challenge_id']))['consumed_at'] is None
    assert client.get('/v1/swaps',headers=customer).json()['items']==before


def test_reservation_transaction_rollback_keeps_no_orphan_holds(client,environment,auth,monkeypatch):
    prepare(client,environment);customer=auth('customer');swap=verified(client,environment,customer)
    def fail(*args,**kwargs):raise DomainError(422,'TEST_AUDIT_FAILURE')
    monkeypatch.setattr(service,'swap_audit',fail)
    assert reserve(client,customer,swap).status_code==422
    assert row(client,'swap_transactions',UUID(swap['id']))['state']=='VERIFIED'
    with client.app.state.db.sessions() as s:assert s.scalar(select(func.count()).select_from(client.app.state.db.table('resource_reservations')))==0


@pytest.fixture
def race_environment(environment):
    # Each real-connection race has a separate schema; no commits contaminate rollback tests.
    from conftest import environment as factory
    generator=factory.__wrapped__();isolated=next(generator)
    try:yield isolated
    finally:
        try:next(generator)
        except StopIteration:pass


@pytest.mark.parametrize('same_key', [False,True])
def test_CT01_concurrent_qr_exactly_one_consumption(race_environment,same_key):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        prepare(http,env,env['seed_db']);customer=login(http,env);code=qr(http,customer);key=uuid4()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda i:verify(http,env,code['qr_token'],key=key if same_key else uuid4()),range(2)))
        assert sorted(r.status_code for r in responses)==([201,201] if same_key else [201,409])
        if same_key:assert responses[0].json()==responses[1].json()
        with env['seed_db'].sessions() as s:
            t=env['seed_db'].table('swap_transactions');assert s.scalar(select(func.count()).select_from(t))==1


def second_customer(http,env):
    user=uuid4();password=secrets.token_urlsafe(24)
    admin=login(http,env,'admin');name='race-'+user.hex
    result=http.post('/v1/users',headers=headers(admin),json={'username':name,'password':password,'role':'CUSTOMER'})
    identity=UUID(result.json()['id'])
    with env['seed_db'].sessions.begin() as s:
        s.execute(insert(env['seed_db'].table('batteries')).values(id=uuid4(),serial='race-'+user.hex,
            family=approved_policy()['battery_family'],location_kind='CUSTOMER',holder_user_id=identity))
    response=http.post('/v1/auth/login',json={'username':name,'password':password})
    return {'Authorization':'Bearer '+response.json()['access_token']}


def test_CT02_two_customers_cannot_double_book(race_environment):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        prepare(http,env,env['seed_db']);a=login(http,env);b=second_customer(http,env)
        swaps=[verified(http,env,x) for x in (a,b)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda pair:reserve(http,pair[0],pair[1]),zip((a,b),swaps)))
        assert all(r.status_code==200 for r in results)
        assert sorted(r.json()['state'] for r in results)==['CANCELLED','RESERVED']
        with env['seed_db'].sessions() as s:
            holds=env['seed_db'].table('resource_reservations')
            assert s.scalar(select(func.count()).select_from(holds).where(holds.c.released_at.is_(None)))==3


@pytest.mark.parametrize('opponent', ['maintenance','quarantine','telemetry'])
def test_reservation_race_with_asset_changes(race_environment,opponent):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        boot=prepare(http,env,env['seed_db']);customer=login(http,env);tech=login(http,env,'technician');swap=verified(http,env,customer)
        if opponent=='telemetry':
            def other():return send(http,env,telemetry(boot,2,temperature_c=41))
        else:
            table='compartments' if opponent=='maintenance' else 'batteries';identity=SLOT if opponent=='maintenance' else PIN
            version=row(http,table,identity)['version']
            def other():return http.post(f'/v1/{table}/{identity}/actions',headers=headers(tech),json={
                'expected_version':version,'action':'SET_MAINTENANCE' if opponent=='maintenance' else 'QUARANTINE','reason':'Concurrent safety test'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(reserve,http,customer,swap);second=pool.submit(other)
            result,changed=first.result(),second.result()
        assert result.status_code==200
        final=row(http,'swap_transactions',UUID(swap['id']))
        if opponent=='telemetry':
            assert changed.status_code==202 and final['state'] in ('CANCELLED','REVIEW_REQUIRED')
        else:assert not (result.json()['state']=='RESERVED' and changed.status_code==200)


def test_cancel_and_expire_release_once(race_environment):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        prepare(http,env,env['seed_db']);customer=login(http,env);swap=verified(http,env,customer);booked=reserve(http,customer,swap).json()
        deadline=row(http,'swap_transactions',UUID(swap['id']))['reservation_expires_at']
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(cancel,http,customer,booked);second=pool.submit(service.expire,http.app.state.db,deadline)
            assert first.result().status_code in (200,409);second.result()
        assert row(http,'swap_transactions',UUID(swap['id']))['state']=='CANCELLED'
        with env['seed_db'].sessions() as s:
            t=env['seed_db'].table('audit_events');assert s.scalar(select(func.count()).select_from(t).where(t.c.action=='CANCEL_RESERVATION'))==1


@pytest.mark.parametrize('delta_us', [-1,0,1])
def test_TC09_qr_exact_expiration_boundary(client,environment,auth,monkeypatch,delta_us):
    prepare(client,environment);code=qr(client,auth('customer'));instant=utcnow()
    with owner(client) as (c,db):
        t=db.table('qr_challenges');c.execute(update(t).where(t.c.id==UUID(code['challenge_id'])).values(expires_at=instant))
    monkeypatch.setattr(service,'utcnow',lambda:instant+timedelta(microseconds=delta_us))
    response=verify(client,environment,code['qr_token'])
    assert response.status_code==(201 if delta_us<0 else 409)
    if delta_us>=0:assert response.json()['code']=='QR_EXPIRED'


@pytest.mark.parametrize('body', [{'method':'QR','credential':'x','station_id':str(demo_id('S02'))},
    {'method':'OTHER','credential':'x'}, {'method':'RFID'}, {'method':'RFID','credential':''}])
def test_TC09_verification_strict_schema(client,environment,body):
    result=client.post('/v1/device/verifications',headers={'X-Device-Key':environment['keys']['S01'],
        'Idempotency-Key':str(uuid4())},json=body)
    assert result.status_code==422


def test_old_expiry_job_cannot_release_a_new_booking(client,environment,auth):
    prepare(client,environment);customer=auth('customer');first=verified(client,environment,customer)
    booked=reserve(client,customer,first).json();old_deadline=row(client,'swap_transactions',UUID(first['id']))['reservation_expires_at']
    assert cancel(client,customer,booked).status_code==200
    second=verified(client,environment,customer);new=reserve(client,customer,second).json()
    service.expire(client.app.state.db,old_deadline)
    assert row(client,'swap_transactions',UUID(second['id']))['state']=='RESERVED'
    with client.app.state.db.sessions() as s:
        t=client.app.state.db.table('resource_reservations')
        assert s.scalar(select(func.count()).select_from(t).where(t.c.swap_id==UUID(new['id']),t.c.released_at.is_(None)))==3


def test_reservation_preserves_phase4_measurement_order_guard(client,environment,auth):
    boot=prepare(client,environment);customer=auth('customer')
    latest=telemetry(boot,2,soc=10);send(client,environment,latest)
    old=telemetry(boot,3,soc=90);old['observed_at']=latest['observed_at']
    send(client,environment,old)
    assert row(client,'device_events',UUID(old['event_id']))['processing_error']=='EVENT_OUT_OF_ORDER'
    response=reserve(client,customer,verified(client,environment,customer))
    assert response.status_code==200 and response.json()['state']=='CANCELLED'


def test_CT02_double_booking_across_two_backend_processes(race_environment):
    import os,socket,subprocess,sys,time
    import httpx
    env=race_environment;processes=[];logs=[]
    directory=ROOT/'.cache'/('phase5-two-api-'+uuid4().hex[:8]);directory.mkdir(parents=True)
    child=dict(os.environ,DATABASE_SCHEMA=env['settings'].schema,PYTHONPATH=str(ROOT/'services/backend'),PYTHONIOENCODING='utf-8')
    try:
        for port in (8005,8006):
            with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',port))!=0,'Isolated test port is occupied'
            log=(directory/f'api-{port}.log').open('w',encoding='utf-8');logs.append(log)
            p=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1',
                '--port',str(port),'--no-access-log','--no-proxy-headers'],cwd=ROOT,env=child,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            processes.append(p)
            deadline=utcnow()+timedelta(seconds=15)
            while True:
                try:
                    if httpx.get(f'http://127.0.0.1:{port}/health',timeout=1).status_code==200:break
                except httpx.HTTPError:pass
                assert utcnow()<deadline,'Backend subprocess did not start'
                time.sleep(.1)
        with TestClient(create_app(env['settings'])) as setup:
            prepare(setup,env,env['seed_db']);a=login(setup,env);b=second_customer(setup,env)
            codes=[qr(setup,x) for x in (a,b)]
            with httpx.Client(base_url='http://127.0.0.1:8005',timeout=15) as left,httpx.Client(base_url='http://127.0.0.1:8006',timeout=15) as right:
                swaps=[verify(h,env,c['qr_token']).json() for h,c in zip((left,right),codes)]
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results=list(pool.map(lambda x:reserve(*x),zip((left,right),(a,b),swaps)))
                assert all(r.status_code==200 for r in results)
                assert sorted(r.json()['state'] for r in results)==['CANCELLED','RESERVED']
                with env['seed_db'].sessions() as s:
                    t=env['seed_db'].table('resource_reservations')
                    assert s.scalar(select(func.count()).select_from(t).where(t.c.released_at.is_(None)))==3
    finally:
        for p in reversed(processes):
            if p.poll() is None:p.terminate();p.wait(timeout=10)
        for log in logs:log.close()
