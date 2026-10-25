"""Persistent inbox/timeout worker. Run independently from the HTTP server."""
import argparse
from datetime import timedelta
import time
from uuid import UUID, uuid4

from sqlalchemy import and_, insert, or_, select, update
from app.application import assets
from app.application.device import audit, check_scope, TERMINAL
from app.application.identity import DomainError, utcnow
from app.config import Settings, approved_policy
from app.infrastructure.db import Database


def review(session,db,station_id,reason):
    swaps=db.table('swap_transactions')
    for row in assets.active_swaps(session,db,station_id):
        if row['state']=='COMPENSATING' or any(row[k] is None for k in
            ('old_battery_id','new_battery_id','return_compartment_id','supply_compartment_id','amount_minor')):
            continue
        if row['state']=='REVIEW_REQUIRED' and row['review_reason']==reason:continue
        session.execute(update(swaps).where(swaps.c.id==row['id']).values(state='REVIEW_REQUIRED',review_reason=reason,version=row['version']+1))


def alert(session,db,device,code,event=None,slot=None,pin=None):
    table=db.table('alerts');dedup=f'{code}:{slot or "station"}:{pin or "none"}'
    old=session.execute(select(table).where(table.c.station_id==device['station_id'],table.c.dedup_key==dedup,
        table.c.state!='RESOLVED').with_for_update()).mappings().first()
    values={'last_event_id':event} if event else {}
    if old:
        session.execute(update(table).where(table.c.id==old['id']).values(**values,occurrences=old['occurrences']+1,version=old['version']+1))
    else:
        identity=uuid4()
        session.execute(insert(table).values(id=identity,station_id=device['station_id'],compartment_id=slot,battery_id=pin,
            dedup_key=dedup,code=code,**values))
        audit(session,db,device,'DEVICE_ALERT',identity,{'code':code,'event_id':str(event) if event else None},actor_type='DEVICE' if event else 'SYSTEM')


def block(session,db,device,code,event=None,slot=None,pin=None):
    alert(session,db,device,code,event,slot,pin)
    if slot:
        table=db.table('compartments');row=assets.get_row(session,db,'compartments',slot)
        if row['service_state']=='ACTIVE':
            session.execute(update(table).where(table.c.id==slot).values(service_state='BLOCKED',version=row['version']+1))
    if pin:
        table=db.table('batteries');row=assets.get_row(session,db,'batteries',pin)
        if row['lifecycle'] in ('REGISTERED','IN_SERVICE'):
            session.execute(update(table).where(table.c.id==pin).values(lifecycle='QUARANTINED',version=row['version']+1))
    review(session,db,device['station_id'],code)


def station_locks(session,db,station_id):
    assets.station_lock(session,db,station_id)
    users,swaps,slots,pins=[db.table(n) for n in ('users','swap_transactions','compartments','batteries')]
    active=assets.active_swaps(session,db,station_id)
    for user in sorted({s['customer_id'] for s in active}):
        session.execute(select(users.c.id).where(users.c.id==user).with_for_update())
    session.execute(select(swaps.c.id).where(swaps.c.station_id==station_id).order_by(swaps.c.id).with_for_update()).all()
    slot_ids=list(session.scalars(select(slots.c.id).where(slots.c.station_id==station_id).order_by(slots.c.id).with_for_update()))
    session.execute(select(pins.c.id).where(pins.c.compartment_id.in_(slot_ids)).order_by(pins.c.id).with_for_update()).all()


def observation(session,db,device,event,slot_id,payload,expected_command=False):
    # The station/resource locks are already held. A higher transport sequence
    # (including a fresh boot) cannot supersede newer physical evidence.
    latest=assets.latest_observation(session,db,device['id'],slot_id)
    if latest and event['observed_at']<=latest['observed_at']:
        raise DomainError(422,'EVENT_OUT_OF_ORDER')
    slot=assets.get_row(session,db,'compartments',slot_id)
    table=db.table('compartments')
    session.execute(update(table).where(table.c.id==slot_id).values(door_state=payload['door_state'],
        observed_present=payload['present'],observed_serial=payload['observed_serial'],
        observed_at=event['received_at'],version=slot['version']+1))
    known=assets.pin_at(session,db,slot)
    consistent=(payload['present'] is False and payload['observed_serial'] is None and known is None) or (
        payload['present'] is True and known and known['serial']==payload['observed_serial'])
    if not consistent and not expected_command:
        block(session,db,device,'PRESENCE_MISMATCH',event['id'],slot_id,known['id'] if known else None)


def command_event(session,db,device,event):
    table=db.table('device_commands');command=assets.get_row(session,db,'device_commands',event['command_id'],lock=True)
    now=utcnow()
    if command['state'] in TERMINAL:
        return  # late duplicate ACKs cannot regress a terminal result
    if command['state']=='UNKNOWN' or event['received_at']>command['expires_at'] or now>command['expires_at']:
        raise DomainError(422,'COMMAND_LATE_OR_UNKNOWN')
    if command['state'] not in ('DISPATCHED','ACKNOWLEDGED'):
        raise DomainError(422,'COMMAND_NOT_DISPATCHED')
    payload=event['payload']
    if event['kind']=='COMMAND_ACK':
        state={'ACCEPTED':'ACKNOWLEDGED','REJECTED':'REJECTED','UNKNOWN':'UNKNOWN'}[payload['result']]
        if state!=command['state']:
            session.execute(update(table).where(table.c.id==command['id']).values(state=state,version=command['version']+1))
            audit(session,db,device,'COMMAND_ACK',command['id'],{'state':state,'event_id':str(event['id'])})
        if state in ('REJECTED','UNKNOWN'):review(session,db,device['station_id'],'COMMAND_'+state)
        return
    swap=assets.get_row(session,db,'swap_transactions',command['swap_id'])
    expected_present=command['kind']=='OPEN_RETURN'
    serial=assets.get_row(session,db,'batteries',swap['old_battery_id'])['serial'] if expected_present else None
    expected=payload['present']==expected_present and payload['observed_serial']==serial
    # Opening observation may retain the original pin. Only final presence/closed evidence is compared.
    observation(session,db,device,event,command['compartment_id'],payload,expected_command=True)
    if not expected and payload['door_state']=='CLOSED':
        block(session,db,device,'COMMAND_OBSERVATION_MISMATCH',event['id'],command['compartment_id'])
        return
    if event['kind']!='DOOR' or payload['door_state']!='CLOSED' or not expected:return
    events=db.table('device_events')
    previous=session.execute(select(events).where(events.c.command_id==command['id'],events.c.boot_id==event['boot_id'],
        events.c.accepted.is_(True),events.c.processed_at.is_not(None),events.c.seq<event['seq']).order_by(events.c.seq)).mappings().all()
    opens=[e['seq'] for e in previous if e['kind']=='DOOR' and e['payload'].get('door_state')=='OPEN']
    presence=[e['seq'] for e in previous if e['kind']=='PRESENCE' and e['payload'].get('present')==expected_present
        and e['payload'].get('observed_serial')==serial]
    if not any(o<p<event['seq'] for o in opens for p in presence):return
    session.execute(update(table).where(table.c.id==command['id']).values(state='OBSERVED',evidence_event_id=event['id'],version=command['version']+1))
    audit(session,db,device,'COMMAND_OBSERVED',command['id'],{'event_id':str(event['id'])})
    # No custody, payment or swap-completion updates in this phase.


def apply(session,db,device,event,policy,now):
    from app.application.device import check_scope
    body={k:str(event[k]) for k in ('compartment_id','swap_id','command_id') if event[k]}
    body.update(kind=event['kind'],payload=event['payload'])
    check_scope(session,db,device,body)
    if not device['enabled']:raise DomainError(403,'DEVICE_DISABLED')
    if not assets.fresh(event['observed_at'],now,policy) or event['observed_at']>event['received_at']:
        raise DomainError(422,'EVENT_STALE_OR_FUTURE')
    kind=event['kind'];new_boot=event['boot_id']!=device['boot_id']
    events=db.table('device_events')
    if new_boot:
        if kind!='SNAPSHOT':raise DomainError(422,'SNAPSHOT_REQUIRED')
        previous=session.execute(select(events.c.id).where(events.c.device_id==device['id'],events.c.boot_id==event['boot_id'],
            events.c.accepted.is_(True),events.c.processed_at.is_not(None))).first()
        if previous:raise DomainError(422,'BOOT_REPLAY')
    elif event['seq']<=device['last_seq']:raise DomainError(422,'EVENT_OUT_OF_ORDER')
    reconnect=not assets.fresh(device['last_received_at'],now,policy)
    if reconnect and kind!='SNAPSHOT':raise DomainError(422,'SNAPSHOT_REQUIRED')
    payload=event['payload']
    if kind=='SNAPSHOT':
        slots=db.table('compartments')
        expected=set(session.scalars(select(slots.c.id).where(slots.c.station_id==device['station_id'])))
        if {UUID(s['compartment_id']) for s in payload['slots']}!=expected:
            raise DomainError(422,'SNAPSHOT_INCOMPLETE')
        for slot in payload['slots']:observation(session,db,device,event,UUID(slot['compartment_id']),slot)
        if new_boot or reconnect:
            commands=db.table('device_commands');ledger={e['command_id']:e['status'] for e in payload['command_ledger']}
            for command in session.execute(select(commands).where(commands.c.device_id==device['id'],commands.c.state.in_(['QUEUED','DISPATCHED','ACKNOWLEDGED']))).mappings().all():
                if command['state']=='QUEUED' and str(command['id']) not in ledger and command['expires_at']>now:
                    continue  # Never dispatched: absence from the device ledger cannot imply an actuator effect.
                state='QUEUED' if ledger.get(str(command['id']))=='NOT_EXECUTED' and command['expires_at']>now else 'UNKNOWN'
                session.execute(update(commands).where(commands.c.id==command['id']).values(state=state,version=command['version']+1))
                if state=='UNKNOWN':review(session,db,device['station_id'],'REBOOT_COMMAND_UNKNOWN')
    elif kind=='TELEMETRY':
        pin=assets.get_row(session,db,'batteries',UUID(payload['battery_id']))
        # Sequence orders transport events within a boot, not BMS measurements.
        # The station/pin locks held by process_one serialize this check + insert.
        measured_at=assets.latest_accepted_measurement(session,db,pin['id'])
        if measured_at is not None and event['observed_at']<=measured_at:
            raise DomainError(422,'EVENT_OUT_OF_ORDER')
        slot=assets.get_row(session,db,'compartments',event['compartment_id'])
        complete=all(payload[k] is not None for k in ('soc','soh','temperature_c'))
        matches=slot['observed_present'] is True and slot['observed_serial']==pin['serial']
        good=complete and matches and not payload['fault_codes']
        session.execute(insert(db.table('battery_telemetry')).values(id=uuid4(),event_id=event['id'],battery_id=pin['id'],
            soc=payload['soc'],soh=payload['soh'],temperature_c=payload['temperature_c'],fault_codes=payload['fault_codes'],
            measured_at=event['observed_at'],received_at=event['received_at'],quality_ok=bool(good)))
        if not good or payload['temperature_c']>policy['temperature_max_c']:
            block(session,db,device,'BMS_UNSAFE',event['id'],slot['id'],pin['id'])
    elif kind in ('COMMAND_ACK','DOOR','PRESENCE'):command_event(session,db,device,event)
    elif kind=='FAULT':
        block(session,db,device,payload['code'],event['id'],event['compartment_id'],UUID(payload['battery_id']) if payload.get('battery_id') else None)
    elif kind=='HEARTBEAT' and payload['health']=='FAULT':
        block(session,db,device,'DEVICE_HEALTH_FAULT',event['id'])
    values={'boot_id':event['boot_id'],'last_seq':event['seq'],'version':device['version']+1}
    if kind in ('HEARTBEAT','SNAPSHOT'):values['last_received_at']=event['received_at']
    session.execute(update(db.table('devices')).where(db.table('devices').c.id==device['id']).values(**values))


def process_one(session,db,event_id,policy,now=None):
    now=now or utcnow();event=assets.get_row(session,db,'device_events',event_id)
    device=assets.get_row(session,db,'devices',event['device_id'])
    station_locks(session,db,device['station_id'])
    device=assets.get_row(session,db,'devices',device['id'],lock=True)
    event=assets.get_row(session,db,'device_events',event_id,lock=True)
    if event['processed_at'] or event['processing_error']:return False
    try:
        with session.begin_nested():apply(session,db,device,event,policy,now)
        values={'processed_at':now,'accepted':True,'processing_error':None}
    except DomainError as error:
        values={'processed_at':now,'accepted':False,'processing_error':error.code}
    session.execute(update(db.table('device_events')).where(db.table('device_events').c.id==event_id).values(**values))
    audit(session,db,device,'DEVICE_EVENT_PROCESSED',event_id,{'kind':event['kind'],'accepted':values['accepted'],'error':values['processing_error']})
    return True


def expire_station(session,db,device,policy,now):
    station_locks(session,db,device['station_id']);device=assets.get_row(session,db,'devices',device['id'],lock=True)
    commands=db.table('device_commands')
    for command in session.execute(select(commands).where(commands.c.device_id==device['id'],
        commands.c.state.in_(['QUEUED','DISPATCHED','ACKNOWLEDGED']),commands.c.expires_at<=now).with_for_update()).mappings().all():
        state='EXPIRED' if command['state']=='QUEUED' else 'UNKNOWN'
        session.execute(update(commands).where(commands.c.id==command['id']).values(state=state,version=command['version']+1))
        audit(session,db,device,'COMMAND_TIMEOUT',command['id'],{'state':state},actor_type='SYSTEM')
        block(session,db,device,'COMMAND_TIMEOUT',slot=command['compartment_id'])
    if device['last_received_at'] and not assets.fresh(device['last_received_at'],now,policy):
        alerts=db.table('alerts')
        already=session.execute(select(alerts.c.id).where(alerts.c.station_id==device['station_id'],
            alerts.c.code=='DEVICE_OFFLINE',alerts.c.state!='RESOLVED')).first()
        if not already:block(session,db,device,'DEVICE_OFFLINE')
        # Connection is derived from age. Preserve the last contact timestamp for operators.
    # Heartbeat does not refresh BMS. Mark stale pins once while their unresolved alert exists.
    pins,readings=db.table('batteries'),db.table('battery_telemetry')
    slots=db.table('compartments')
    for pin in session.execute(select(pins).where(pins.c.compartment_id.in_(select(slots.c.id).where(slots.c.station_id==device['station_id'])))).mappings().all():
        latest=session.execute(select(readings).where(readings.c.battery_id==pin['id']).order_by(readings.c.received_at.desc(),readings.c.id.desc()).limit(1)).mappings().first()
        if latest and latest['quality_ok'] and not assets.fresh(latest['received_at'],now,policy) and not assets.has_alert(session,db,device['station_id'],pin['compartment_id'],pin['id']):
            block(session,db,device,'BMS_STALE',slot=pin['compartment_id'],pin=pin['id'])


def tick(db,policy,now=None):
    now=now or utcnow()
    with db.sessions() as session:
        events=db.table('device_events')
        ids=list(session.scalars(select(events.c.id).where(events.c.processed_at.is_(None),events.c.processing_error.is_(None)).order_by(events.c.received_at,events.c.seq).limit(100)))
        devices=session.execute(select(db.table('devices'))).mappings().all()
    processed=0
    for identity in ids:
        with db.sessions.begin() as session:processed+=int(process_one(session,db,identity,policy,now))
    for device in devices:
        with db.sessions.begin() as session:expire_station(session,db,device,policy,now)
    from app.application.reservations import expire
    expire(db, now)
    return processed


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    db=Database(Settings.from_env())
    try:
        while True:
            tick(db,approved_policy())
            if args.once:break
            time.sleep(1)
    finally:db.engine.dispose()


if __name__=='__main__':main()
