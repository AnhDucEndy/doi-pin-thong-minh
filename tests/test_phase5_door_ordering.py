"""P5-A01 regression: physical time, transport order, atomicity and PostgreSQL locks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.application import assets, reservations
from app.config import approved_policy
from app.application.identity import utcnow
from app.main import create_app
from app.seed import demo_id
from test_phase2 import owner
from test_phase4 import (DEVICE, command_fixture, packet, poll, process, row, send,
                         snapshot_packet, telemetry)
from test_phase5 import prepare, login, verified, reserve, race_environment, PIN, SLOT


def projections(client):
    db = client.app.state.db
    with db.sessions() as s:
        return {name: [dict(r) for r in s.execute(select(db.table(name)).order_by(db.table(name).c.id)).mappings()]
                for name in ('devices','compartments','batteries','battery_telemetry',
                             'swap_transactions','resource_reservations','device_commands','alerts')}


def assert_rejected(client, env, candidate, before, code='EVENT_OUT_OF_ORDER'):
    result = send(client, env, candidate)
    assert result.status_code == 202
    stored = row(client, 'device_events', UUID(candidate['event_id']))
    assert stored['accepted'] is False and stored['processing_error'] == code
    assert projections(client) == before
    retry = send(client, env, candidate)
    assert retry.json() == {'event_id': candidate['event_id'], 'duplicate': True, 'processing_state':'REJECTED'}
    assert projections(client) == before
    db = client.app.state.db
    with db.sessions() as s:
        t = db.table('audit_events')
        entries = s.execute(select(t).where(t.c.aggregate_id == UUID(candidate['event_id']),
            t.c.action == 'DEVICE_EVENT_PROCESSED')).mappings().all()
        assert len(entries) == 1 and entries[0]['after_data']['error'] == code


@pytest.mark.parametrize('change', ['older','equal_changed','equal_same','lower_sequence','new_boot_old','new_boot_equal'])
def test_physical_and_transport_order_both_required(client, environment, change):
    first = snapshot_packet(seq=5)
    first['observed_at'] = (utcnow()-timedelta(seconds=2)).isoformat()
    first['payload']['slots'][0]['door_state'] = 'OPEN'
    assert send(client, environment, first).status_code == 202
    assert row(client,'device_events',UUID(first['event_id']))['accepted'] is True
    candidate = snapshot_packet(uuid4() if change.startswith('new_boot') else first['boot_id'],
        0 if change.startswith('new_boot') else 4 if change=='lower_sequence' else 6)
    instant = datetime.fromisoformat(first['observed_at'])
    delta = -1 if change in ('older','new_boot_old') else 1 if change=='lower_sequence' else 0
    candidate['observed_at'] = (instant+timedelta(microseconds=delta)).isoformat()
    if change=='equal_same': candidate['payload'] = first['payload']
    assert_rejected(client,environment,candidate,projections(client))


@pytest.mark.parametrize('reboot', [False,True])
def test_new_physical_observation_and_exact_replay(client, environment, reboot):
    first = snapshot_packet(seq=4); first['observed_at']=(utcnow()-timedelta(seconds=2)).isoformat()
    send(client,environment,first)
    candidate = snapshot_packet(uuid4() if reboot else first['boot_id'],0 if reboot else 5)
    candidate['observed_at']=(datetime.fromisoformat(first['observed_at'])+timedelta(microseconds=1)).isoformat()
    candidate['payload']['slots'][0]['door_state']='OPEN'
    send(client,environment,candidate)
    assert row(client,'device_events',UUID(candidate['event_id']))['accepted'] is True
    assert row(client,'compartments',SLOT)['door_state']=='OPEN'
    before=projections(client)
    assert send(client,environment,candidate).json()['duplicate'] is True
    assert projections(client)==before
    if reboot:
        old_boot=snapshot_packet(first['boot_id'],6)
        assert_rejected(client,environment,old_boot,before,'BOOT_REPLAY')


@pytest.mark.parametrize('bad_time', ['missing',None,'invalid','2026-01-01T00:00:00'])
def test_snapshot_invalid_physical_timestamp(client,environment,bad_time):
    candidate=snapshot_packet()
    if bad_time=='missing':candidate.pop('observed_at')
    else:candidate['observed_at']=bad_time
    before=projections(client)
    assert send(client,environment,candidate).status_code==422
    assert projections(client)==before


@pytest.mark.parametrize('seconds', [-16,1])
def test_snapshot_stale_or_future_preserves_projection(client,environment,seconds):
    candidate=snapshot_packet();candidate['observed_at']=(utcnow()+timedelta(seconds=seconds)).isoformat()
    assert_rejected(client,environment,candidate,projections(client),'EVENT_STALE_OR_FUTURE')


def test_snapshot_identity_sequence_collisions_and_wrong_station(client,environment):
    first=snapshot_packet();send(client,environment,first);before=projections(client)
    collision={**first,'event_id':str(uuid4())}
    assert send(client,environment,collision).json()['code']=='EVENT_SEQUENCE_CONFLICT'
    changed={**first,'observed_at':utcnow().isoformat()}
    assert send(client,environment,changed).json()['code']=='EVENT_ID_CONFLICT'
    assert send(client,environment,snapshot_packet(),code='S02').json()['code']=='DEVICE_STATION_FORBIDDEN'
    assert projections(client)==before


def test_snapshot_uuid_letter_case_cannot_bypass_watermark(client,environment):
    first=snapshot_packet()
    first['observed_at']=(utcnow()-timedelta(seconds=1)).isoformat()
    for slot in first['payload']['slots']:
        slot['compartment_id']=slot['compartment_id'].upper()
    first['payload']['slots'][0]['door_state']='OPEN'
    send(client,environment,first)
    assert row(client,'device_events',UUID(first['event_id']))['accepted'] is True
    candidate=snapshot_packet(first['boot_id'],1)
    candidate['observed_at']=(datetime.fromisoformat(first['observed_at'])-timedelta(microseconds=1)).isoformat()
    assert_rejected(client,environment,candidate,projections(client))


@pytest.mark.parametrize('kind', ['DOOR','PRESENCE'])
def test_command_observation_cannot_bypass_snapshot_watermark(client,environment,kind):
    boot,swap,command=command_fixture(client,environment);poll(client,environment)
    with client.app.state.db.sessions() as s:
        latest=assets.latest_observation(s,client.app.state.db,DEVICE,SLOT)
    candidate=packet(kind,boot,1,{'door_state':'OPEN','present':False,'observed_serial':None},
        compartment_id=str(SLOT),swap_id=str(swap),command_id=str(command['id']))
    candidate['observed_at']=(latest['observed_at']-timedelta(microseconds=1)).isoformat()
    assert_rejected(client,environment,candidate,projections(client))


def test_reject_last_slot_rolls_back_earlier_snapshot_updates(client,environment):
    boot,swap,command=command_fixture(client,environment);poll(client,environment)
    with client.app.state.db.sessions() as s:
        first=assets.latest_observation(s,client.app.state.db,DEVICE,SLOT)
    opened=packet('DOOR',boot,1,{'door_state':'OPEN','present':False,'observed_serial':None},
        compartment_id=str(SLOT),swap_id=str(swap),command_id=str(command['id']))
    send(client,environment,opened)
    assert row(client,'device_events',UUID(opened['event_id']))['accepted'] is True
    candidate=snapshot_packet(boot,2)
    start, end=first['observed_at'],datetime.fromisoformat(opened['observed_at'])
    assert end>start
    candidate['observed_at']=(start+(end-start)/2).isoformat()
    # Slot1 has newer individual evidence; put it last to force five updates before rejection.
    candidate['payload']['slots']=candidate['payload']['slots'][1:]+candidate['payload']['slots'][:1]
    assert_rejected(client,environment,candidate,projections(client))


@pytest.mark.parametrize('slot_number', [1,2])
@pytest.mark.parametrize('same_time', [False,True])
def test_legacy_bad_projection_fails_closed_without_rewriting_history(client,environment,auth,slot_number,same_time):
    boot=prepare(client,environment);customer=auth('customer');swap=verified(client,environment,customer)
    newer=snapshot_packet(boot,2);newer['payload']['slots'][slot_number-1]['door_state']='OPEN'
    send(client,environment,newer)
    older=snapshot_packet(boot,3)
    older['observed_at']=(datetime.fromisoformat(newer['observed_at'])-timedelta(seconds=0 if same_time else 1)).isoformat()
    assert send(client,environment,older,process_it=False).status_code==202
    # Explicit historical-version fixture only: model already-corrupt accepted evidence.
    # Never used for ordinary ingestion or the reproduction probes.
    with owner(client) as (s,db):
        events=db.table('device_events');slots=db.table('compartments')
        incoming=s.execute(select(events).where(events.c.id==UUID(older['event_id']))).mappings().one()
        s.execute(update(events).where(events.c.id==incoming['id']).values(accepted=True,processed_at=utcnow()))
        for payload in older['payload']['slots']:
            s.execute(update(slots).where(slots.c.id==UUID(payload['compartment_id'])).values(
                door_state=payload['door_state'],observed_present=payload['present'],observed_serial=payload['observed_serial'],observed_at=incoming['received_at']))
    before=row(client,'compartments',demo_id(f'S01:slot:{slot_number}'))
    result=reserve(client,customer,swap)
    assert result.json()['state']=='CANCELLED' and result.json()['review_reason']=='RESOURCE_UNAVAILABLE'
    assert row(client,'compartments',before['id'])==before  # Read guard does not silently repair old data.


@pytest.mark.parametrize('first_writer', ['door','reservation'])
def test_reservation_serializes_with_open_snapshot(race_environment,monkeypatch,first_writer):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        boot=prepare(http,env,env['seed_db']);customer=login(http,env);swap=verified(http,env,customer)
        incoming=snapshot_packet(boot,2);incoming['payload']['slots'][0]['door_state']='OPEN'
        assert send(http,env,incoming,process_it=False).status_code==202
        entered,release=Event(),Event()
        from app.workers import device as worker
        original_observation,original_audit=worker.observation,reservations.swap_audit
        def observe(*args,**kwargs):
            if first_writer=='door' and args[4]==SLOT:
                entered.set();assert release.wait(3)
            return original_observation(*args,**kwargs)
        def audit(*args,**kwargs):
            if first_writer=='reservation' and args[3]=='RESERVE_RESOURCES':
                entered.set();assert release.wait(3)
            return original_audit(*args,**kwargs)
        monkeypatch.setattr(worker,'observation',observe);monkeypatch.setattr(reservations,'swap_audit',audit)
        with ThreadPoolExecutor(max_workers=2) as pool:
            if first_writer=='door':
                a=pool.submit(process,http,incoming['event_id']);assert entered.wait(3)
                b=pool.submit(reserve,http,customer,swap);release.set();a.result();response=b.result()
            else:
                a=pool.submit(reserve,http,customer,swap);assert entered.wait(3)
                b=pool.submit(process,http,incoming['event_id']);release.set();response=a.result();b.result()
        assert response.json()['state']==('CANCELLED' if first_writer=='door' else 'RESERVED')
        assert row(http,'compartments',SLOT)['door_state']=='OPEN'
        before=projections(http)
        delayed=snapshot_packet(boot,3);delayed['observed_at']=(datetime.fromisoformat(incoming['observed_at'])-timedelta(seconds=1)).isoformat()
        assert_rejected(http,env,delayed,before)
        with env['seed_db'].sessions() as s:
            t=env['seed_db'].table('resource_reservations')
            assert s.scalar(select(func.count()).select_from(t))==(0 if first_writer=='door' else 3)
