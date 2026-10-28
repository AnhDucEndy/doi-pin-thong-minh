"""Durable inbox and command adapter. No public command creation or custody transitions."""
from datetime import timedelta
from uuid import UUID, uuid4
import hmac
import json

from sqlalchemy import insert, select, update, or_
from app.application import assets
from app.application.identity import DomainError, utcnow
from app.domain.device import validate_event
from app.domain.identity import digest
from app.infrastructure.db import advisory_lock

TERMINAL = ['OBSERVED','REJECTED','EXPIRED']


def device_actor(session, db, key):
    if not key or len(key) < 24:
        raise DomainError(401,'DEVICE_AUTH_REQUIRED')
    table = db.table('devices')
    rows = session.execute(select(table).where(table.c.key_hash == digest(key))).mappings().all()
    if len(rows) != 1 or not hmac.compare_digest(rows[0]['key_hash'],digest(key)):
        raise DomainError(401,'DEVICE_KEY_INVALID')
    if not rows[0]['enabled']:
        raise DomainError(403,'DEVICE_DISABLED')
    return rows[0]


def audit(session, db, actor, action, identity, after, actor_type='DEVICE'):
    kind='device_command' if action.startswith('COMMAND_') else 'device_event' if action=='DEVICE_EVENT_PROCESSED' else 'alert' if action=='DEVICE_ALERT' else 'device'
    session.execute(insert(db.table('audit_events')).values(id=uuid4(),actor_type=actor_type,
        actor_id=str(actor['id']) if actor_type=='DEVICE' else 'device-worker',
        aggregate_type=kind,aggregate_id=identity,action=action,after_data=after,correlation_id=uuid4()))


def check_scope(session, db, device, body):
    slot_id = body.get('compartment_id')
    if slot_id:
        slot = assets.get_row(session,db,'compartments',UUID(slot_id))
        if slot['station_id'] != device['station_id']:
            raise DomainError(403,'DEVICE_STATION_FORBIDDEN')
    if body['kind'] == 'SNAPSHOT':
        slots = body['payload']['slots']
        ids = [s['compartment_id'] for s in slots]
        if len(ids) != len(set(ids)):
            raise DomainError(422,'SNAPSHOT_DUPLICATE_SLOT')
        command_ids=[entry['command_id'] for entry in body['payload']['command_ledger']]
        if len(command_ids)!=len(set(command_ids)):
            raise DomainError(422,'SNAPSHOT_DUPLICATE_COMMAND')
        for slot in slots:
            if assets.get_row(session,db,'compartments',UUID(slot['compartment_id']))['station_id'] != device['station_id']:
                raise DomainError(403,'DEVICE_STATION_FORBIDDEN')
        for entry in body['payload']['command_ledger']:
            command = assets.get_row(session,db,'device_commands',UUID(entry['command_id']))
            if command['device_id'] != device['id']:
                raise DomainError(403,'COMMAND_SCOPE_INVALID')
    if body.get('command_id'):
        command = assets.get_row(session,db,'device_commands',UUID(body['command_id']))
        if (command['device_id'] != device['id'] or str(command['swap_id']) != body['swap_id']
            or str(command['compartment_id']) != slot_id):
            raise DomainError(403,'COMMAND_SCOPE_INVALID')
    elif body.get('swap_id'):
        raise DomainError(422,'COMMAND_REQUIRED')
    if body['kind'] == 'TELEMETRY':
        pin = assets.get_row(session,db,'batteries',UUID(body['payload']['battery_id']))
        if str(pin['compartment_id']) != slot_id or pin['location_kind'] != 'COMPARTMENT':
            raise DomainError(403,'BATTERY_SCOPE_INVALID')
    if body['kind'] == 'FAULT' and body['payload'].get('battery_id'):
        pin = assets.get_row(session,db,'batteries',UUID(body['payload']['battery_id']))
        if str(pin['compartment_id']) != slot_id:
            raise DomainError(403,'BATTERY_SCOPE_INVALID')


def receipt(row, duplicate=False):
    return {'event_id':row['id'],'duplicate':duplicate,'processing_state':
        ('QUEUED' if row['processed_at'] is None else 'PROCESSED' if row['accepted'] else 'REJECTED')}


def receive(session, db, actor, body):
    observed, payload_hash = validate_event(body)
    if body['seq']>9223372036854775807 or (body['kind']=='TELEMETRY' and body['payload']['temperature_c'] is not None
        and abs(body['payload']['temperature_c'])>=10000):
        raise DomainError(422,'DEVICE_EVENT_INVALID')  # PostgreSQL storage domains, never overflow into a 5xx.
    assets.station_lock(session,db,actor['station_id'])
    device = assets.get_row(session,db,'devices',actor['id'],lock=True)
    if not device['enabled']:
        raise DomainError(403,'DEVICE_DISABLED')
    events = db.table('device_events')
    advisory_lock(session,'device-event:'+body['event_id'])
    existing = session.execute(select(events).where(events.c.id == UUID(body['event_id']))).mappings().first()
    if existing:
        if existing['device_id'] != actor['id'] or existing['payload_hash'] != payload_hash:
            raise DomainError(409,'EVENT_ID_CONFLICT')
        return receipt(existing,True)
    check_scope(session,db,device,body)
    collision = session.execute(select(events.c.id).where(events.c.device_id == actor['id'],
        events.c.boot_id == UUID(body['boot_id']),events.c.seq == body['seq'])).first()
    if collision:
        raise DomainError(409,'EVENT_SEQUENCE_CONFLICT')
    row = session.execute(insert(events).values(id=UUID(body['event_id']),device_id=actor['id'],
        boot_id=UUID(body['boot_id']),seq=body['seq'],kind=body['kind'],observed_at=observed,received_at=utcnow(),
        payload_hash=payload_hash,payload=body['payload'],
        **{k:UUID(body[k]) for k in ('compartment_id','swap_id','command_id') if body.get(k)}).returning(events)).mappings().one()
    # This transaction commits via the Phase 1 session dependency before HTTP 202 is sent.
    return receipt(row)


def command_allowed(session,db,command,policy,now):
    swap = assets.get_row(session,db,'swap_transactions',command['swap_id'])
    slot = assets.get_row(session,db,'compartments',command['compartment_id'])
    device = assets.get_row(session,db,'devices',command['device_id'])
    station = assets.get_row(session,db,'stations',device['station_id'])
    if (not device['enabled'] or station['state'] != 'ACTIVE' or slot['station_id'] != device['station_id']
        or swap['station_id'] != device['station_id'] or command['expires_at'] <= now
        or slot['service_state'] != 'ACTIVE' or slot['door_state'] != 'CLOSED'
        or not assets.online(session,db,device,now,policy) or not assets.fresh(slot['observed_at'],now,policy)):
        return False
    reservations = db.table('resource_reservations')
    def reserved(**values):
        return session.execute(select(reservations.c.id).where(reservations.c.swap_id == swap['id'],
            reservations.c.released_at.is_(None),*[getattr(reservations.c,k)==v for k,v in values.items()])).first() is not None
    payments = db.table('payments')
    paid = session.execute(select(payments.c.id).where(payments.c.swap_id == swap['id'],payments.c.state=='SUCCEEDED',
        payments.c.amount_minor==swap['amount_minor'],payments.c.currency==swap['currency'])).first()
    if not paid or not swap['consented_at'] or not reserved(compartment_id=slot['id']):
        return False
    relevant_pin=swap['old_battery_id'] if command['kind']=='OPEN_RETURN' else swap['new_battery_id']
    if assets.has_alert(session,db,station['id'],slot['id'],relevant_pin):return False
    if 'payload' in command:
        pin=assets.get_row(session,db,'batteries',relevant_pin) if relevant_pin else None
        if (not isinstance(command['payload'],dict) or not pin or command['payload'].get('expected_serial')!=pin['serial']
            or command['payload'].get('simulation_only') is not True
            or digest(json.dumps(command['payload'],sort_keys=True))!=command['payload_hash']):return False
    def final_fresh(extra_slots=(), pin=None):
        timestamps=[device['last_received_at']]
        for observed in (slot,*extra_slots):
            if not assets.current_observation(session,db,device,observed):return False
            evidence=assets.latest_observation(session,db,device['id'],observed['id'])
            timestamps.extend([observed['observed_at'],evidence['observed_at']])
        if pin:
            readings=db.table('battery_telemetry')
            reading=session.execute(select(readings).where(readings.c.battery_id==pin['id'])
                .order_by(readings.c.received_at.desc(),readings.c.id.desc()).limit(1)).mappings().first()
            if not reading:return False
            timestamps.extend([reading['received_at'],reading['measured_at']])
        decision_at=utcnow()
        return command['expires_at']>decision_at and all(assets.fresh(t,decision_at,policy) for t in timestamps)
    if command['kind'] == 'OPEN_RETURN':
        old = assets.get_row(session,db,'batteries',swap['old_battery_id']) if swap['old_battery_id'] else None
        return bool(swap['state']=='AWAITING_RETURN' and slot['id']==swap['return_compartment_id']
            and slot['observed_present'] is False and slot['observed_serial'] is None and not assets.pin_at(session,db,slot)
            and old and old['holder_user_id']==swap['customer_id'] and old['family']==policy['battery_family']
            and final_fresh())
    new = assets.get_row(session,db,'batteries',swap['new_battery_id']) if swap['new_battery_id'] else None
    old = assets.get_row(session,db,'batteries',swap['old_battery_id']) if swap['old_battery_id'] else None
    receiving = assets.get_row(session,db,'compartments',swap['return_compartment_id']) if swap['return_compartment_id'] else None
    return bool(swap['state'] in ('RETURN_ACCEPTED','AWAITING_PICKUP') and swap['return_observed_at']
        and receiving and old and old['compartment_id']==receiving['id'] and old['holder_user_id'] is None
        and receiving['service_state']=='ACTIVE' and receiving['door_state']=='CLOSED'
        and receiving['observed_present'] is True and receiving['observed_serial']==old['serial']
        and reserved(compartment_id=receiving['id'])
        and not assets.has_alert(session,db,station['id'],receiving['id'],old['id'])
        and slot['id']==swap['supply_compartment_id'] and new and new['compartment_id']==slot['id']
        and reserved(battery_id=new['id']) and slot['observed_present'] is True and slot['observed_serial']==new['serial']
        and not assets.has_alert(session,db,station['id'],slot['id'],new['id'])
        and assets.quality(session,db,new,device,now,policy) and final_fresh((receiving,),new))


def enqueue_command(session,db,swap_id,slot_id,kind,policy):
    """Internal swap adapter; there is deliberately no user HTTP control route."""
    swap = assets.get_row(session,db,'swap_transactions',swap_id)
    assets.station_lock(session,db,swap['station_id'])
    assets.get_row(session,db,'users',swap['customer_id'],lock=True)
    swap = assets.get_row(session,db,'swap_transactions',swap_id,lock=True)
    assets.get_row(session,db,'compartments',slot_id,lock=True)
    table=db.table('device_commands')
    previous=session.execute(select(table).where(table.c.swap_id==swap_id,table.c.kind==kind)).mappings().first()
    if previous:
        if previous['compartment_id']!=slot_id: raise DomainError(409,'COMMAND_CONFLICT')
        return dict(previous)
    device=assets.available_device(session,db,swap['station_id'])
    if not device or kind not in ('OPEN_RETURN','OPEN_SUPPLY'): raise DomainError(422,'COMMAND_INVALID')
    now=utcnow(); command={'id':uuid4(),'device_id':device['id'],'swap_id':swap_id,'compartment_id':slot_id,
        'kind':kind,'created_at':now,'expires_at':now+timedelta(seconds=policy['command_ttl_seconds'])}
    if not command_allowed(session,db,command,policy,now): raise DomainError(409,'COMMAND_INTERLOCK_FAILED')
    pin_id=swap['old_battery_id'] if kind=='OPEN_RETURN' else swap['new_battery_id']
    pin=assets.get_row(session,db,'batteries',pin_id)
    payload={'expected_serial':pin['serial'],'expected_battery_id':str(pin['id']),'simulation_only':True}
    result=session.execute(insert(table).values(**command,payload=payload,payload_hash=digest(json.dumps(payload,sort_keys=True)))
        .returning(table)).mappings().one()
    audit(session,db,device,'COMMAND_CREATED',command['id'],{'kind':kind,'swap_id':str(swap_id)},actor_type='SYSTEM')
    return dict(result)


def poll(session,db,actor,policy,cursor,limit):
    assets.station_lock(session,db,actor['station_id'])
    device=assets.get_row(session,db,'devices',actor['id'],lock=True)
    if not device['enabled']: raise DomainError(403,'DEVICE_DISABLED')
    table=db.table('device_commands');now=utcnow()
    query=select(table).where(table.c.device_id==device['id'],table.c.state.in_(['QUEUED','DISPATCHED'])).order_by(table.c.id)
    if cursor:query=query.where(table.c.id>cursor)
    result=[]
    for command in session.execute(query.with_for_update()).mappings().all():
        if command['expires_at']<=now: continue  # timeout worker decides EXPIRED vs UNKNOWN
        if not command_allowed(session,db,command,policy,now): continue
        if command['state']=='QUEUED':
            command=session.execute(update(table).where(table.c.id==command['id']).values(state='DISPATCHED',version=command['version']+1).returning(table)).mappings().one()
            audit(session,db,device,'COMMAND_DISPATCHED',command['id'],{'state':'DISPATCHED'})
        result.append({k:v for k,v in command.items() if k!='payload_hash'})
        if len(result)>limit:break
    return {'items':result[:limit],'next_cursor':str(result[limit-1]['id']) if len(result)>limit else None}
