from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select, update, func
from pydantic import Field

from app.api.schemas import Strict
from app.application import assets
from app.application import device as service
from app.application.identity import DomainError, utcnow
from app.config import approved_policy


class VersionAction(Strict):
    expected_version:int=Field(ge=1)


class AlertResolve(VersionAction):
    evidence_event_id:UUID
    resolution_note:str=Field(min_length=1)


def build_router(session,principal,mutation):
    router=APIRouter()
    def device(request:Request,key:str|None=Header(default=None,alias='X-Device-Key'),current=Depends(session,scope='function')):
        return service.device_actor(current,request.app.state.db,key)
    def operator(actor=Depends(principal,scope='function')):
        if actor['user']['role'] not in ('ADMIN','TECHNICIAN'):raise DomainError(403,'FORBIDDEN')
        return actor
    @router.post('/v1/device/events',status_code=202,operation_id='receiveDeviceEvent',tags=['FR07','FR17','FR19'])
    def receive(body:dict,request:Request,actor=Depends(device,scope='function'),current=Depends(session,scope='function')):
        return service.receive(current,request.app.state.db,actor,body)
    @router.get('/v1/device/commands',operation_id='pollCommands',tags=['FR17'])
    def poll(request:Request,cursor:UUID|None=None,limit:int=Query(20,ge=1,le=100),actor=Depends(device,scope='function'),current=Depends(session,scope='function')):
        return service.poll(current,request.app.state.db,actor,approved_policy(request.app.state.settings.policy_path),cursor,limit)
    @router.get('/v1/alerts',operation_id='listAlerts',tags=['FR19'])
    def list_alerts(request:Request,cursor:UUID|None=None,limit:int=Query(20,ge=1,le=100),actor=Depends(operator,scope='function'),current=Depends(session,scope='function')):
        db=request.app.state.db;table=db.table('alerts');query=select(table).order_by(table.c.id).limit(limit+1)
        if actor['user']['role']=='TECHNICIAN':
            assignments=db.table('user_station_assignments')
            query=query.where(table.c.station_id.in_(select(assignments.c.station_id).where(assignments.c.user_id==actor['user']['id'])))
        if cursor:query=query.where(table.c.id>cursor)
        rows=current.execute(query).mappings().all()
        return {'items':[dict(row) for row in rows[:limit]],'next_cursor':str(rows[limit-1]['id']) if len(rows)>limit else None}
    @router.get('/v1/dashboard',operation_id='dashboard',tags=['FR18'])
    def dashboard(request:Request,actor=Depends(operator,scope='function'),current=Depends(session,scope='function')):
        db=request.app.state.db;stations=db.table('stations');query=select(stations)
        if actor['user']['role']=='TECHNICIAN':
            assignments=db.table('user_station_assignments')
            query=query.where(stations.c.id.in_(select(assignments.c.station_id).where(assignments.c.user_id==actor['user']['id'])))
        rows=current.execute(query).mappings().all();ids=[r['id'] for r in rows];now=utcnow()
        policy=approved_policy(request.app.state.settings.policy_path)
        states=[assets.availability(current,db,row,policy,now)['operational_state'] for row in rows]
        alerts,swaps=db.table('alerts'),db.table('swap_transactions')
        return {'online_stations':states.count('ONLINE'),'offline_stations':states.count('OFFLINE'),
            'open_alerts':current.scalar(select(func.count()).select_from(alerts).where(alerts.c.station_id.in_(ids),alerts.c.state!='RESOLVED')),
            'review_swaps':current.scalar(select(func.count()).select_from(swaps).where(swaps.c.station_id.in_(ids),swaps.c.state=='REVIEW_REQUIRED')),'as_of':now}
    def transition(identity,body,request,actor,current,resolve):
        db=request.app.state.db;table=db.table('alerts');initial=assets.get_row(current,db,'alerts',identity)
        assets.scope(current,db,actor['user'],initial['station_id'])
        if actor['user']['role']!='TECHNICIAN':raise DomainError(403,'FORBIDDEN')
        assets.station_lock(current,db,initial['station_id']);row=assets.get_row(current,db,'alerts',identity,lock=True)
        assets.version(row,body.expected_version)
        if row['state']=='RESOLVED':raise DomainError(409,'STATE_CONFLICT')
        values={'version':row['version']+1}
        if not resolve:values.update(state='ACKNOWLEDGED',acknowledged_by=actor['user']['id'])
        else:
            policy=approved_policy(request.app.state.settings.policy_path);now=utcnow()
            device=assets.available_device(current,db,row['station_id'])
            event=assets.snapshot(current,db,device,now,body.evidence_event_id)
            if not event or not assets.fresh(event['received_at'],now,policy) or not assets.online(current,db,device,now,policy):
                raise DomainError(422,'EVIDENCE_REQUIRED')
            if row['last_event_id']:
                last=assets.get_row(current,db,'device_events',row['last_event_id'])
                if event['received_at'] < last['received_at']:raise DomainError(422,'EVIDENCE_REQUIRED')
            if row['code']=='DEVICE_HEALTH_FAULT':
                events=db.table('device_events')
                health=current.execute(select(events).where(events.c.device_id==device['id'],events.c.boot_id==device['boot_id'],
                    events.c.kind=='HEARTBEAT',events.c.accepted.is_(True),events.c.processed_at.is_not(None))
                    .order_by(events.c.received_at.desc()).limit(1)).mappings().first()
                if not health or health['payload'].get('health')!='OK' or not assets.fresh(health['received_at'],now,policy):
                    raise DomainError(422,'EVIDENCE_REQUIRED')
            commands=db.table('device_commands')
            pending=select(commands.c.id).where(commands.c.device_id==device['id'],commands.c.state.in_(['QUEUED','DISPATCHED','ACKNOWLEDGED','UNKNOWN']))
            if row['compartment_id']:pending=pending.where(commands.c.compartment_id==row['compartment_id'])
            if current.execute(pending).first():raise DomainError(409,'RECONCILIATION_REQUIRED')
            if row['code'] in ('COMMAND_TIMEOUT','COMMAND_OBSERVATION_MISMATCH'):
                raise DomainError(409,'RECONCILIATION_REQUIRED')
            slots=db.table('compartments');query=select(slots).where(slots.c.station_id==row['station_id'])
            if row['compartment_id']:query=query.where(slots.c.id==row['compartment_id'])
            observations={s['compartment_id']:s for s in event['payload']['slots']}
            for slot in current.execute(query).mappings().all():
                pin=assets.pin_at(current,db,slot);observed=observations.get(str(slot['id']))
                if (not observed or slot['door_state']!='CLOSED' or not assets.fresh(slot['observed_at'],now,policy)
                    or event['received_at']<slot['observed_at'] or observed['door_state']!='CLOSED'
                    or observed['present']!=slot['observed_present'] or observed['observed_serial']!=slot['observed_serial']):
                    raise DomainError(422,'EVIDENCE_REQUIRED')
                if pin:
                    if (slot['observed_present'] is not True or slot['observed_serial']!=pin['serial']
                        or not assets.quality(current,db,pin,device,now,policy,issue=False,require_service=False)):
                        raise DomainError(422,'EVIDENCE_REQUIRED')
                elif slot['observed_present'] is not False or slot['observed_serial'] is not None:
                    raise DomainError(422,'EVIDENCE_REQUIRED')
            values.update(state='RESOLVED',resolved_by=actor['user']['id'],resolution_note=body.resolution_note,last_event_id=event['id'])
        result=current.execute(update(table).where(table.c.id==identity).values(**values).returning(table)).mappings().one()
        assets.asset_audit(current,db,actor['user'],'alert','RESOLVE_ALERT' if resolve else 'ACK_ALERT',identity,dict(row),dict(result))
        return dict(result)
    @router.post('/v1/alerts/{alert_id}/acknowledge',operation_id='ackAlert',tags=['FR19'])
    def ack(alert_id:UUID,body:VersionAction,request:Request,key:UUID=Header(alias='Idempotency-Key'),actor=Depends(operator,scope='function'),current=Depends(session,scope='function')):
        row=assets.get_row(current,request.app.state.db,'alerts',alert_id);assets.scope(current,request.app.state.db,actor['user'],row['station_id'])
        if actor['user']['role']!='TECHNICIAN':raise DomainError(403,'FORBIDDEN')
        return mutation(request,current,actor,key,body.model_dump(),200,lambda:transition(alert_id,body,request,actor,current,False))
    @router.post('/v1/alerts/{alert_id}/resolve',operation_id='resolveAlert',tags=['FR19'])
    def resolve(alert_id:UUID,body:AlertResolve,request:Request,key:UUID=Header(alias='Idempotency-Key'),actor=Depends(operator,scope='function'),current=Depends(session,scope='function')):
        row=assets.get_row(current,request.app.state.db,'alerts',alert_id);assets.scope(current,request.app.state.db,actor['user'],row['station_id'])
        if actor['user']['role']!='TECHNICIAN':raise DomainError(403,'FORBIDDEN')
        return mutation(request,current,actor,key,body.model_dump(),200,lambda:transition(alert_id,body,request,actor,current,True))
    return router
