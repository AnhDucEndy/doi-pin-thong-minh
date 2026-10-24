from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import select

from app.api.battery_schemas import BatteryAction, BatteryCreate, BatteriesPage, BatteryView, TelemetryPage
from app.application import assets, batteries
from app.application.identity import DomainError, utcnow
from app.config import approved_policy


def build_router(session, principal, admin, mutation):
    router = APIRouter()

    def operator(actor=Depends(principal, scope='function')):
        if actor['user']['role'] not in ('ADMIN', 'TECHNICIAN'):
            raise DomainError(403, 'FORBIDDEN')
        return actor

    @router.get('/v1/batteries', response_model=BatteriesPage, operation_id='listBatteries', tags=['FR06'])
    def list_batteries(request: Request, cursor: UUID | None = None, limit: int = Query(20, ge=1, le=100),
                       actor=Depends(operator, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        pins = db.table('batteries')
        query = select(pins).order_by(pins.c.id).limit(limit + 1)
        if actor['user']['role'] == 'TECHNICIAN':
            slots, assignments = db.table('compartments'), db.table('user_station_assignments')
            query = query.where(pins.c.compartment_id.in_(select(slots.c.id).where(slots.c.station_id.in_(
                select(assignments.c.station_id).where(assignments.c.user_id == actor['user']['id'])))))
        if cursor:
            query = query.where(pins.c.id > cursor)
        rows = current.execute(query).mappings().all()
        return {'items': [dict(row) for row in rows[:limit]], 'next_cursor': str(rows[limit-1]['id']) if len(rows) > limit else None}

    @router.post('/v1/batteries', response_model=BatteryView, status_code=201, operation_id='createBattery', tags=['FR06'])
    def create_battery(body: BatteryCreate, request: Request, key: UUID = Header(alias='Idempotency-Key'),
                       actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        policy = approved_policy(request.app.state.settings.policy_path)
        return mutation(request, current, actor, key, body.model_dump(exclude_unset=True), 201,
            lambda: batteries.create(current, request.app.state.db, actor['user'], body, policy))

    @router.post('/v1/batteries/{battery_id}/actions', response_model=BatteryView, operation_id='changeBattery', tags=['FR06', 'FR08'])
    def change_battery(battery_id: UUID, body: BatteryAction, request: Request, key: UUID = Header(alias='Idempotency-Key'),
                       actor=Depends(operator, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        batteries.scope(current, db, actor['user'], assets.get_row(current, db, 'batteries', battery_id))
        if (actor['user']['role'] == 'ADMIN') != (body.action == 'RETIRE'):
            raise DomainError(403, 'FORBIDDEN')
        policy = approved_policy(request.app.state.settings.policy_path)
        return mutation(request, current, actor, key, body.model_dump(exclude_unset=True), 200,
            lambda: batteries.change(current, db, actor['user'], battery_id, body, policy))

    @router.get('/v1/batteries/{battery_id}/telemetry', response_model=TelemetryPage, operation_id='listTelemetry', tags=['FR07'])
    def list_telemetry(battery_id: UUID, request: Request, response: Response, cursor: UUID | None = None, limit: int = Query(20, ge=1, le=100),
                       actor=Depends(operator, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        pin = assets.get_row(current, db, 'batteries', battery_id)
        batteries.scope(current, db, actor['user'], pin)
        policy, now = approved_policy(request.app.state.settings.policy_path), utcnow()
        # Additive response metadata; the approved JSON response body stays exactly unchanged.
        response.headers['X-Battery-Available'] = str(assets.eligible(current, db, pin, policy, now)).lower()
        response.headers['X-Battery-Assessed-At'] = now.isoformat()
        response.headers['X-BMS-Limits'] = ','.join(str(policy[k]) for k in
            ('soc_min_pct', 'soh_min_pct', 'temperature_max_c', 'telemetry_stale_seconds'))
        readings = db.table('battery_telemetry')
        query = select(readings).where(readings.c.battery_id == battery_id)
        # Opaque cursor is the previous row id, sorted by server receive time (never random UUID alone).
        if cursor:
            anchor = current.execute(select(readings).where(readings.c.id == cursor, readings.c.battery_id == battery_id)).mappings().first()
            if not anchor:
                raise DomainError(422, 'INVALID_CURSOR')
            from sqlalchemy import or_, and_
            query = query.where(or_(readings.c.received_at < anchor['received_at'],
                and_(readings.c.received_at == anchor['received_at'], readings.c.id < cursor)))
        rows = current.execute(query.order_by(readings.c.received_at.desc(), readings.c.id.desc()).limit(limit+1)).mappings().all()
        return {'items': [dict(row) for row in rows[:limit]], 'next_cursor': str(rows[limit-1]['id']) if len(rows) > limit else None}

    return router
