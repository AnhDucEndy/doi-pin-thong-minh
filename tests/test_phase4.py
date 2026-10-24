"""TC17/TC19, related TC07/TC18 and CT04/06/09/10/11. PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from uuid import UUID,uuid4

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import insert,select,update

from app.application import device as commands
from app.application.identity import utcnow
from app.config import approved_policy
from app.main import create_app
from app.seed import demo_id
from app.workers.device import process_one,expire_station,tick
from simulators.device.main import Simulator
from test_phase1 import headers,validate
from test_phase2 import owner,swap_fixture

DEVICE=demo_id('device:S01');SLOT=demo_id('S01:slot:1');PIN=demo_id('S01:battery:2')


def packet(kind='HEARTBEAT',boot=None,seq=1,payload=None,**refs):
    return {'event_id':str(uuid4()),'boot_id':str(boot or uuid4()),'seq':seq,'kind':kind,
        'observed_at':utcnow().isoformat(),'payload':payload if payload is not None else {'health':'OK'},**refs}


def snapshot_packet(boot=None,seq=0):
    return packet('SNAPSHOT',boot,seq,{'slots':[{'compartment_id':str(demo_id(f'S01:slot:{slot}')),
        'door_state':'CLOSED','present':slot>1,'observed_serial':f'S01-B{slot:03}' if slot>1 else None} for slot in range(1,7)],'command_ledger':[]})


def process(client,identity,now=None):
    with client.app.state.db.sessions.begin() as s:
        process_one(s,client.app.state.db,UUID(str(identity)),approved_policy(),now)


def send(client,environment,body,process_it=True,code='S01'):
    response=client.post('/v1/device/events',headers={'X-Device-Key':environment['keys'][code]},json=body)
    if response.status_code==202 and process_it:process(client,body['event_id'])
    return response


def connected(client,environment):
    body=snapshot_packet();response=send(client,environment,body)
    assert response.status_code==202,response.text
    assert row(client,'device_events',UUID(body['event_id']))['accepted'] is True,row(client,'device_events',UUID(body['event_id']))['processing_error']
    return body['boot_id']


def row(client,name,identity):
    table=client.app.state.db.table(name)
    with client.app.state.db.sessions() as s:return dict(s.execute(select(table).where(table.c.id==identity)).mappings().one())


def telemetry(boot,seq=1,**changes):
    return packet('TELEMETRY',boot,seq,{'battery_id':str(PIN),'soc':90,'soh':95,'temperature_c':25,'fault_codes':[],**changes},compartment_id=str(demo_id('S01:slot:2')))


def command_fixture(client,environment):
    boot=connected(client,environment);swap=swap_fixture(client)
    with owner(client) as (c,db):
        c.execute(update(db.table('swap_transactions')).where(db.table('swap_transactions').c.id==swap).values(state='AWAITING_RETURN',consented_at=utcnow()))
        c.execute(update(db.table('compartments')).where(db.table('compartments').c.id==SLOT).values(service_state='ACTIVE'))
        c.execute(insert(db.table('payments')).values(id=uuid4(),swap_id=swap,provider_key=uuid4(),state='SUCCEEDED',amount_minor=9000,verified_at=utcnow()))
    with client.app.state.db.sessions.begin() as s:
        command=commands.enqueue_command(s,client.app.state.db,swap,SLOT,'OPEN_RETURN',approved_policy())
    return boot,swap,command


def poll(client,environment):return client.get('/v1/device/commands',headers={'X-Device-Key':environment['keys']['S01']})


def command_packet(boot,swap,command,seq=1,result='ACCEPTED'):
    return packet('COMMAND_ACK',boot,seq,{'result':result,'reason':'Simulation test'},
        compartment_id=str(SLOT),swap_id=str(swap),command_id=str(command['id']))


def test_TC17_inbox_commits_before_worker_and_duplicate_receipts(client,environment):
    body=snapshot_packet();response=send(client,environment,body,False)
    assert response.status_code==202 and response.json()['processing_state']=='QUEUED'
    validate('EventReceipt',response.json());assert row(client,'devices',DEVICE)['boot_id'] is None
    duplicate=send(client,environment,body,False);assert duplicate.json()['duplicate'] is True
    process(client,body['event_id']);duplicate=send(client,environment,body,False)
    assert duplicate.json()['processing_state']=='PROCESSED'
    changed={**body,'payload':{'slots':[],'command_ledger':[]}}
    assert send(client,environment,changed,False).json()['code']=='EVENT_ID_CONFLICT'
    assert send(client,environment,{**body,'event_id':str(uuid4())},False).json()['code']=='EVENT_SEQUENCE_CONFLICT'


def test_TC17_device_authentication_and_scope(client,environment,auth):
    body=snapshot_packet()
    assert client.post('/v1/device/events',json=body).status_code==401
    assert client.post('/v1/device/events',json=body,headers=auth()).status_code==401
    assert client.get('/v1/device/commands',headers=auth()).status_code==401
    assert client.post('/v1/device/events',json=body,headers={'X-Device-Key':'invalid-secret-value-at-least-24'}).status_code==401
    assert send(client,environment,body,False,code='S02').status_code==403
    with owner(client) as (c,db):c.execute(update(db.table('devices')).where(db.table('devices').c.id==DEVICE).values(enabled=False))
    assert send(client,environment,body,False).json()['code']=='DEVICE_DISABLED'


@pytest.mark.parametrize('change',[{'kind':'INVALID'},{'seq':-1},{'seq':True},{'observed_at':'invalid'},
    {'station_id':str(uuid4())},{'payload':{}},{'payload':{'health':'BAD'}}])
def test_TC17_invalid_envelope(client,environment,change):
    response=send(client,environment,{**packet(),**change},False)
    assert response.status_code==422 and response.json()['code']=='DEVICE_EVENT_INVALID'


@pytest.mark.parametrize('change',[{'soc':101},{'soh':-1},{'soc':'90'},{'fault_codes':'FAULT'}])
def test_TC07_telemetry_validation(client,environment,change):
    boot=connected(client,environment);response=send(client,environment,telemetry(boot,**change),False)
    assert response.status_code==422


def test_TC07_missing_field_vs_null(client,environment):
    boot=connected(client,environment);body=telemetry(boot);del body['payload']['soc']
    assert send(client,environment,body,False).status_code==422
    body=telemetry(boot,soc=None);assert send(client,environment,body).status_code==202
    assert row(client,'batteries',PIN)['lifecycle']=='QUARANTINED'


@pytest.mark.parametrize('problem',['old','future','order','boot','old_boot'])
def test_CT09_stale_and_reordered_events_cannot_refresh(client,environment,problem):
    boot=connected(client,environment)
    baseline=row(client,'devices',DEVICE)
    if problem=='old_boot':
        connected(client,environment);body=snapshot_packet(boot,2)
    else:
        body=packet(boot=boot,seq=0 if problem=='order' else 1)
        if problem=='order':body['event_id']=str(uuid4());body['seq']=2;send(client,environment,body);body=packet(boot=boot,seq=1)
        if problem=='old':body['observed_at']=(utcnow()-timedelta(seconds=30)).isoformat()
        if problem=='future':body['observed_at']=(utcnow()+timedelta(seconds=30)).isoformat()
        if problem=='boot':body['boot_id']=str(uuid4())
    before=row(client,'devices',DEVICE);response=send(client,environment,body)
    assert response.status_code==202
    event=row(client,'device_events',UUID(body['event_id']))
    assert event['accepted'] is False and event['processing_error']
    assert row(client,'devices',DEVICE)==before
    duplicate=send(client,environment,body,False);assert duplicate.json()['processing_state']=='REJECTED'


def test_TC18_offline_reconnect_requires_snapshot_and_does_not_restore(client,environment):
    boot=connected(client,environment)
    with owner(client) as (c,db):
        c.execute(update(db.table('devices')).where(db.table('devices').c.id==DEVICE).values(last_received_at=utcnow()-timedelta(seconds=30)))
    body=packet(boot=boot);send(client,environment,body)
    assert row(client,'device_events',UUID(body['event_id']))['processing_error']=='SNAPSHOT_REQUIRED'
    last_contact=row(client,'devices',DEVICE)['last_received_at']
    with client.app.state.db.sessions.begin() as s:expire_station(s,client.app.state.db,row(client,'devices',DEVICE),approved_policy(),utcnow())
    assert row(client,'devices',DEVICE)['last_received_at']==last_contact
    body=snapshot_packet(boot,2);send(client,environment,body)
    assert row(client,'devices',DEVICE)['last_received_at']
    assert row(client,'compartments',SLOT)['service_state']=='BLOCKED'


def test_TC07_valid_telemetry_is_not_lifecycle_activation(client,environment,auth):
    boot=connected(client,environment);body=telemetry(boot)
    assert send(client,environment,body).status_code==202
    assert row(client,'device_events',UUID(body['event_id']))['accepted'] is True
    assert row(client,'batteries',PIN)['lifecycle']=='REGISTERED'
    response=client.get(f'/v1/batteries/{PIN}/telemetry',headers=auth())
    assert response.json()['items'][0]['quality_ok'] is True
    assert response.headers['X-Battery-Available']=='false'


@pytest.mark.parametrize('payload',[{'temperature_c':41},{'fault_codes':['FAULT']},{'soc':None}])
def test_TC19_fault_quarantines_and_good_data_never_restores(client,environment,auth,payload):
    boot=connected(client,environment);send(client,environment,telemetry(boot,**payload))
    assert row(client,'batteries',PIN)['lifecycle']=='QUARANTINED'
    assert row(client,'compartments',demo_id('S01:slot:2'))['service_state']=='BLOCKED'
    tech=auth('technician');alerts=client.get('/v1/alerts',headers=tech);validate('AlertsPage',alerts.json())
    alert=alerts.json()['items'][0]
    response=client.post(f'/v1/alerts/{alert["id"]}/acknowledge',headers=headers(tech),json={'expected_version':alert['version']})
    assert response.status_code==200 and response.json()['state']=='ACKNOWLEDGED'
    send(client,environment,telemetry(boot,seq=2))
    assert row(client,'batteries',PIN)['lifecycle']=='QUARANTINED'
    assert client.get(f'/v1/batteries/{PIN}/telemetry',headers=tech).headers['X-Battery-Available']=='false'


def test_TC17_wrong_pin_or_command_and_duplicate_snapshot_slot(client,environment):
    boot=connected(client,environment)
    response=send(client,environment,telemetry(boot,battery_id=str(demo_id('S02:battery:2'))),False)
    assert response.status_code==403
    body=command_packet(boot,uuid4(),{'id':uuid4()});assert send(client,environment,body,False).status_code==404
    body=snapshot_packet(boot,3);body['payload']['slots'].append(body['payload']['slots'][0]);assert send(client,environment,body,False).status_code==422


def test_CT04_ack_is_not_door_or_delivery_and_duplicate_ack(client,environment):
    boot,swap,command=command_fixture(client,environment);response=poll(client,environment);assert response.status_code==200,response.text
    validate('DeviceCommandsPage',response.json());assert len(response.json()['items'])==1
    with client.app.state.db.sessions() as s:
        audits=client.app.state.db.table('audit_events')
        created=s.execute(select(audits).where(audits.c.action=='COMMAND_CREATED',audits.c.aggregate_id==command['id'])).mappings().one()
        assert created['actor_type']=='SYSTEM' and created['aggregate_type']=='device_command'
    before=row(client,'compartments',SLOT);pin_before=row(client,'batteries',demo_id('customer:initial-battery'))
    body=command_packet(boot,swap,command);send(client,environment,body)
    assert row(client,'device_commands',command['id'])['state']=='ACKNOWLEDGED'
    assert row(client,'compartments',SLOT)==before
    assert row(client,'batteries',demo_id('customer:initial-battery'))==pin_before
    state=row(client,'device_commands',command['id']);send(client,environment,command_packet(boot,swap,command,seq=2))
    assert row(client,'device_commands',command['id'])==state
    with client.app.state.db.sessions.begin() as s:
        replay=commands.enqueue_command(s,client.app.state.db,swap,SLOT,'OPEN_RETURN',approved_policy())
    assert replay['id']==command['id']


@pytest.mark.parametrize('result,state',[('REJECTED','REJECTED'),('UNKNOWN','UNKNOWN')])
def test_command_nack_unknown_preserves_reservations(client,environment,result,state):
    boot,swap,command=command_fixture(client,environment);poll(client,environment)
    send(client,environment,command_packet(boot,swap,command,result=result))
    assert row(client,'device_commands',command['id'])['state']==state
    assert row(client,'swap_transactions',swap)['state']=='REVIEW_REQUIRED'
    with client.app.state.db.sessions() as s:
        reservations=client.app.state.db.table('resource_reservations');assert s.scalar(select(reservations.c.released_at).where(reservations.c.swap_id==swap)) is None


@pytest.mark.parametrize('dispatched',[False,True])
def test_command_timeout_and_late_ack(client,environment,dispatched):
    boot,swap,command=command_fixture(client,environment)
    if dispatched:poll(client,environment)
    with client.app.state.db.sessions.begin() as s:expire_station(s,client.app.state.db,row(client,'devices',DEVICE),approved_policy(),command['expires_at']+timedelta(seconds=1))
    expected='UNKNOWN' if dispatched else 'EXPIRED'
    assert row(client,'device_commands',command['id'])['state']==expected
    # Reconnect then late ACK: no terminal regression or new effects.
    send(client,environment,snapshot_packet(boot,1));send(client,environment,command_packet(boot,swap,command,seq=2))
    assert row(client,'device_commands',command['id'])['state']==expected


def test_command_physical_chain_observed_without_custody(client,environment):
    boot,swap,command=command_fixture(client,environment);poll(client,environment)
    old=row(client,'batteries',demo_id('customer:initial-battery'))
    for seq,kind,door,present,serial in [(1,'DOOR','OPEN',False,None),(2,'PRESENCE','OPEN',True,old['serial']),(3,'DOOR','CLOSED',True,old['serial'])]:
        body=packet(kind,boot,seq,{'door_state':door,'present':present,'observed_serial':serial},compartment_id=str(SLOT),swap_id=str(swap),command_id=str(command['id']))
        assert send(client,environment,body).status_code==202
    result=row(client,'device_commands',command['id']);assert result['state']=='OBSERVED' and result['evidence_event_id']
    assert row(client,'batteries',old['id'])==old
    send(client,environment,command_packet(boot,swap,command,seq=4,result='REJECTED'))
    assert row(client,'device_commands',command['id'])==result


def test_simulator_restart_no_second_actuator_effect(tmp_path):
    path=tmp_path/'simulator.sqlite3'
    simulator=Simulator('S01','not-a-real-key-for-local-unit-test',ledger=path,scenario='physical')
    command={'id':str(uuid4()),'device_id':str(DEVICE),'swap_id':str(uuid4()),'compartment_id':str(SLOT),'kind':'OPEN_RETURN',
        'expires_at':(utcnow()+timedelta(seconds=15)).isoformat(),'payload':{'expected_serial':'CUSTOMER-B001','simulation_only':True}}
    assert simulator.handle(command)=='EXECUTED';simulator.close()
    restarted=Simulator('S01','not-a-real-key-for-local-unit-test',ledger=path,scenario='physical')
    assert restarted.handle(command)=='ACCEPTED'
    assert restarted.conn.execute('SELECT effects FROM commands').fetchone()[0]==1
    state=next(s for s in restarted.slots() if s['compartment_id']==str(SLOT))
    assert state['door_state']=='CLOSED' and state['present'] is True and state['lock_released'] is False
    restarted.close()


def test_simulator_crash_after_ledger_returns_unknown(tmp_path):
    path=tmp_path/'crash.sqlite3';sim=Simulator('S01','not-a-real-key-for-local-unit-test',ledger=path,scenario='crash-after-ledger')
    command={'id':str(uuid4()),'device_id':str(DEVICE),'swap_id':str(uuid4()),'compartment_id':str(SLOT),'kind':'OPEN_RETURN',
        'expires_at':(utcnow()+timedelta(seconds=15)).isoformat(),'payload':{'expected_serial':'CUSTOMER-B001','simulation_only':True}}
    with pytest.raises(RuntimeError):sim.handle(command)
    sim.close();sim=Simulator('S01','not-a-real-key-for-local-unit-test',ledger=path,scenario='physical')
    assert sim.handle(command)=='UNKNOWN'
    assert sim.conn.execute('SELECT effects FROM commands').fetchone()[0]==0;sim.close()


def test_simulator_http_adapter_inbox_and_worker(client,environment,tmp_path):
    def transport(request):
        response=client.request(request.method,request.url.path,headers=dict(request.headers),content=request.content)
        if request.method=='POST' and response.status_code==202:process(client,response.json()['event_id'])
        return httpx.Response(response.status_code,json=response.json())
    sim=Simulator('S01',environment['keys']['S01'],ledger=tmp_path/'http.sqlite3',transport=httpx.MockTransport(transport))
    receipts=sim.cycle();assert len(receipts)==7
    assert row(client,'devices',DEVICE)['boot_id']==UUID(sim.boot)
    assert row(client,'compartments',SLOT)['door_state']=='CLOSED'
    assert row(client,'compartments',SLOT)['service_state']=='BLOCKED'
    sim.close()


def test_TC19_fault_cannot_be_cleared_by_old_bms(client,environment,auth):
    boot=connected(client,environment);send(client,environment,telemetry(boot))
    fault=packet('FAULT',boot,2,{'code':'BMS_HARDWARE_FAULT','battery_id':str(PIN),'details':'Simulation'},compartment_id=str(demo_id('S01:slot:2')))
    send(client,environment,fault);tech=auth('technician')
    alerts=client.get('/v1/alerts',headers=tech).json()['items'];alert=alerts[0]
    snapshot=snapshot_packet(boot,3);send(client,environment,snapshot)
    body={'expected_version':row(client,'batteries',PIN)['version'],'action':'RESTORE','reason':'Inspection',
        'evidence_event_id':snapshot['event_id'],'resolve_alert_ids':[alert['id']]}
    response=client.post(f'/v1/batteries/{PIN}/actions',headers=headers(tech),json=body)
    assert response.status_code==422 and row(client,'alerts',UUID(alert['id']))['state']=='OPEN'
    send(client,environment,telemetry(boot,4))
    response=client.post(f'/v1/batteries/{PIN}/actions',headers=headers(tech),json=body)
    assert response.status_code==200,response.text
    assert row(client,'alerts',UUID(alert['id']))['state']=='RESOLVED'
    assert row(client,'compartments',demo_id('S01:slot:2'))['service_state']=='BLOCKED'


def test_inbox_projection_rollback_is_atomic(client,environment,monkeypatch):
    from app.workers import device as worker
    body=snapshot_packet();send(client,environment,body,False)
    before=row(client,'compartments',SLOT)
    original=worker.observation
    def fail(*args,**kwargs):
        original(*args,**kwargs)
        from app.application.identity import DomainError
        raise DomainError(422,'INJECTED_ROLLBACK')
    monkeypatch.setattr(worker,'observation',fail);process(client,body['event_id'])
    assert row(client,'compartments',SLOT)==before
    assert row(client,'devices',DEVICE)['boot_id'] is None
    event=row(client,'device_events',UUID(body['event_id']))
    assert event['accepted'] is False and event['processing_error']=='INJECTED_ROLLBACK'


def test_snapshot_reboot_unknown_ledger_keeps_command_unknown(client,environment):
    boot,swap,command=command_fixture(client,environment);poll(client,environment)
    body=snapshot_packet();body['payload']['command_ledger']=[{'command_id':str(command['id']),'status':'EXECUTED'}]
    send(client,environment,body)
    assert row(client,'device_commands',command['id'])['state']=='UNKNOWN'
    assert row(client,'swap_transactions',swap)['state']=='REVIEW_REQUIRED'
    assert poll(client,environment).json()['items']==[]


def test_TC19_alert_scope_resolve_does_not_restore_lifecycle(client,environment,auth):
    boot=connected(client,environment);send(client,environment,telemetry(boot,temperature_c=41))
    tech=auth('technician');alert=client.get('/v1/alerts',headers=tech).json()['items'][0]
    assert client.get('/v1/alerts',headers=auth('customer')).status_code==403
    with owner(client) as (c,db):
        c.execute(insert(db.table('alerts')).values(id=uuid4(),station_id=demo_id('S02'),dedup_key='foreign',code='FAULT'))
    assert len(client.get('/v1/alerts',headers=tech).json()['items'])==1
    send(client,environment,telemetry(boot,2));snapshot=snapshot_packet(boot,3);send(client,environment,snapshot)
    response=client.post(f'/v1/alerts/{alert["id"]}/resolve',headers=headers(tech),json={
        'expected_version':alert['version'],'evidence_event_id':snapshot['event_id'],'resolution_note':'Fresh simulation evidence'})
    assert response.status_code==200,response.text
    assert row(client,'batteries',PIN)['lifecycle']=='QUARANTINED'
    assert row(client,'compartments',demo_id('S01:slot:2'))['service_state']=='BLOCKED'


def test_CT11_concurrent_duplicate_event_once(environment):
    body=snapshot_packet()
    with TestClient(create_app(environment['settings'])) as http:
        def submit(_):return http.post('/v1/device/events',headers={'X-Device-Key':environment['keys']['S01']},json=body)
        with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(submit,range(2)))
        assert all(r.status_code==202 for r in responses)
        assert sorted(r.json()['duplicate'] for r in responses)==[False,True]
    with environment['seed_db'].sessions() as s:
        events=environment['seed_db'].table('device_events')
        assert len(s.execute(select(events).where(events.c.id==UUID(body['event_id']))).all())==1


@pytest.mark.parametrize('scenario,result',[('ack-only','ACCEPTED'),('nack','REJECTED')])
def test_simulator_duplicate_command_replays_original_ack(tmp_path,scenario,result):
    path=tmp_path/'replay.sqlite3';sim=Simulator('S01','not-a-real-key-for-local-unit-test',ledger=path,scenario=scenario)
    command={'id':str(uuid4()),'device_id':str(DEVICE),'swap_id':str(uuid4()),'compartment_id':str(SLOT),'kind':'OPEN_RETURN',
        'expires_at':(utcnow()+timedelta(seconds=15)).isoformat(),'payload':{'expected_serial':'CUSTOMER-B001','simulation_only':True}}
    sim.handle(command);first=json.loads(sim.conn.execute('SELECT body FROM events ORDER BY rowid DESC LIMIT 1').fetchone()[0])['payload']
    sim.close();sim=Simulator('S01','not-a-real-key-for-local-unit-test',ledger=path,scenario='physical')
    assert sim.handle(command)==result
    second=json.loads(sim.conn.execute('SELECT body FROM events ORDER BY rowid DESC LIMIT 1').fetchone()[0])['payload']
    assert first==second and sim.conn.execute('SELECT effects FROM commands').fetchone()[0]==0;sim.close()


@pytest.mark.parametrize('values',[{'soc':79},{'soh':79}])
def test_low_soc_soh_is_supply_filter_not_new_lifecycle_rule(client,environment,auth,values):
    boot=connected(client,environment);send(client,environment,telemetry(boot,**values))
    assert row(client,'batteries',PIN)['lifecycle']=='REGISTERED'
    response=client.get(f'/v1/batteries/{PIN}/telemetry',headers=auth())
    assert response.json()['items'][0]['quality_ok'] is True and response.headers['X-Battery-Available']=='false'


def test_TC18_dashboard_scopes_online_offline_maintenance_and_review(client,environment,auth):
    boot=connected(client,environment);swap=swap_fixture(client);admin,tech=auth(),auth('technician')
    with owner(client) as (c,db):
        c.execute(update(db.table('swap_transactions')).where(db.table('swap_transactions').c.id==swap).values(state='REVIEW_REQUIRED',review_reason='Fixture'))
        for code in ('S01','S02'):
            c.execute(insert(db.table('alerts')).values(id=uuid4(),station_id=demo_id(code),dedup_key='dashboard',code='SIMULATED_FAULT'))
    response=client.get('/v1/dashboard',headers=admin);assert response.status_code==200;validate('Dashboard',response.json())
    assert {k:response.json()[k] for k in ('online_stations','offline_stations','open_alerts','review_swaps')}=={
        'online_stations':1,'offline_stations':1,'open_alerts':2,'review_swaps':1}
    summary=client.get('/v1/dashboard',headers=tech).json()
    assert summary['online_stations']==1 and summary['offline_stations']==0 and summary['open_alerts']==1 and summary['review_swaps']==1
    with owner(client) as (c,db):c.execute(update(db.table('stations')).where(db.table('stations').c.id==demo_id('S02')).values(state='MAINTENANCE'))
    assert client.get('/v1/dashboard',headers=admin).json()['offline_stations']==0
    assert client.get('/v1/dashboard',headers=auth('customer')).status_code==403
