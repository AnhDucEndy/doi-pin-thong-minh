from uuid import UUID, uuid4
import hmac

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import insert, select

from app.api.asset_schemas import (AvailabilityPage, CompartmentAction, CompartmentCreate,
    CompartmentsPage, CompartmentView, DeviceCreate, DeviceCreated, DevicesPage, DeviceUpdate,
    DeviceView, StationCreate, StationUpdate, StationView)
from app.application import assets
from app.application.identity import DomainError, utcnow
from app.config import approved_policy
from app.domain.identity import digest


def build_router(session, principal, admin, mutation):
    """Reuse Phase 1 dependency instances so auth and mutations share one transaction."""
    router = APIRouter()

    def operator(actor=Depends(principal, scope='function')):
        if actor['user']['role'] not in ('ADMIN', 'TECHNICIAN'):
            raise DomainError(403, 'FORBIDDEN')
        return actor

    def page(current, table, cursor, limit, clauses=(), project=dict):
        query = select(table).where(*clauses).order_by(table.c.id).limit(limit + 1)
        if cursor:
            query = query.where(table.c.id > cursor)
        rows = current.execute(query).mappings().all()
        return {'items': [project(row) for row in rows[:limit]],
                'next_cursor': str(rows[limit - 1]['id']) if len(rows) > limit else None}

    @router.get('/v1/stations', response_model=AvailabilityPage, operation_id='listStations', tags=['FR05'])
    def list_stations(request: Request, cursor: UUID | None = None, limit: int = Query(20, ge=1, le=100),
                      actor=Depends(principal, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        policy = approved_policy(request.app.state.settings.policy_path)
        now = utcnow()
        return page(current, db.table('stations'), cursor, limit,
                    project=lambda row: assets.availability(current, db, row, policy, now))

    @router.post('/v1/stations', response_model=StationView, status_code=201, operation_id='createStation', tags=['FR03'])
    def create_station(body: StationCreate, request: Request, key: UUID = Header(alias='Idempotency-Key'),
                       actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        def execute():
            db = request.app.state.db
            table = db.table('stations')
            result = current.execute(insert(table).values(id=uuid4(), **body.model_dump()).returning(table)).mappings().one()
            assets.asset_audit(current, db, actor['user'], 'station', 'CREATE_STATION', result['id'], after=dict(result))
            return dict(result)
        return mutation(request, current, actor, key, body.model_dump(), 201, execute)

    @router.get('/v1/stations/{station_id}', response_model=StationView, operation_id='getStation', tags=['FR03'])
    def get_station(station_id: UUID, request: Request, actor=Depends(operator, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        assets.scope(current, db, actor['user'], station_id)
        return dict(assets.get_row(current, db, 'stations', station_id))

    @router.patch('/v1/stations/{station_id}', response_model=StationView, operation_id='updateStation', tags=['FR03'])
    def update_station(station_id: UUID, body: StationUpdate, request: Request,
                       key: UUID = Header(alias='Idempotency-Key'), actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        return mutation(request, current, actor, key, body.model_dump(exclude_unset=True), 200,
                        lambda: assets.update_station(current, request.app.state.db, actor['user'], station_id, body))

    @router.post('/v1/devices', response_model=DeviceCreated, status_code=201, operation_id='createDevice', tags=['FR03'])
    def create_device(body: DeviceCreate, request: Request, key: UUID = Header(alias='Idempotency-Key'),
                      actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        secret = assets.device_key(actor['user']['id'], key)
        def execute():
            db = request.app.state.db
            assets.station_lock(current, db, body.station_id)
            table = db.table('devices')
            result = current.execute(insert(table).values(id=uuid4(), station_id=body.station_id,
                serial=body.serial, key_hash=digest(secret)).returning(table)).mappings().one()
            public = assets.public_device(result)
            assets.asset_audit(current, db, actor['user'], 'device', 'CREATE_DEVICE', result['id'], after=public)
            return public
        # Cache only the public device projection, reconstruct the identical one-time delivery on retry.
        device = mutation(request, current, actor, key, body.model_dump(), 201, execute)
        stored = assets.get_row(current, request.app.state.db, 'devices', UUID(str(device['id'])))
        if not hmac.compare_digest(stored['key_hash'], digest(secret)):
            raise DomainError(409, 'DEVICE_KEY_UNAVAILABLE')
        return {'device': device, 'device_key_once': secret}

    @router.get('/v1/devices', response_model=DevicesPage, operation_id='listDevices', tags=['FR03'])
    def list_devices(request: Request, response: Response, cursor: UUID | None = None, limit: int = Query(20, ge=1, le=100),
                     actor=Depends(operator, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        table = db.table('devices')
        response.headers['X-Dashboard-Poll-Seconds'] = str(approved_policy(request.app.state.settings.policy_path)['dashboard_poll_seconds'])
        clauses = []
        if actor['user']['role'] == 'TECHNICIAN':
            assignments = db.table('user_station_assignments')
            clauses.append(table.c.station_id.in_(select(assignments.c.station_id).where(assignments.c.user_id == actor['user']['id'])))
        return page(current, table, cursor, limit, clauses, assets.public_device)

    @router.patch('/v1/devices/{device_id}', response_model=DeviceView, operation_id='updateDevice', tags=['FR03'])
    def update_device(device_id: UUID, body: DeviceUpdate, request: Request,
                      key: UUID = Header(alias='Idempotency-Key'), actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        return mutation(request, current, actor, key, body.model_dump(), 200,
                        lambda: assets.disable_device(current, request.app.state.db, actor['user'], device_id, body))

    @router.get('/v1/stations/{station_id}/compartments', response_model=CompartmentsPage, operation_id='listCompartments', tags=['FR04'])
    def list_compartments(station_id: UUID, request: Request, cursor: UUID | None = None, limit: int = Query(20, ge=1, le=100),
                          actor=Depends(operator, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        assets.scope(current, db, actor['user'], station_id)
        assets.get_row(current, db, 'stations', station_id)
        table = db.table('compartments')
        return page(current, table, cursor, limit, [table.c.station_id == station_id])

    @router.post('/v1/stations/{station_id}/compartments', response_model=CompartmentView, status_code=201, operation_id='createCompartment', tags=['FR04'])
    def create_compartment(station_id: UUID, body: CompartmentCreate, request: Request,
                           key: UUID = Header(alias='Idempotency-Key'), actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        def execute():
            db = request.app.state.db
            assets.station_lock(current, db, station_id)
            table = db.table('compartments')
            result = current.execute(insert(table).values(id=uuid4(), station_id=station_id, slot_no=body.slot_no).returning(table)).mappings().one()
            assets.asset_audit(current, db, actor['user'], 'compartment', 'CREATE_COMPARTMENT', result['id'], after=dict(result))
            return dict(result)
        return mutation(request, current, actor, key, body.model_dump(), 201, execute)

    @router.post('/v1/compartments/{compartment_id}/actions', response_model=CompartmentView, operation_id='changeCompartment', tags=['FR04'])
    def compartment_action(compartment_id: UUID, body: CompartmentAction, request: Request,
                           key: UUID = Header(alias='Idempotency-Key'), actor=Depends(operator, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        # Recheck scope even for a cached idempotency result after an assignment is revoked.
        initial = assets.get_row(current, db, 'compartments', compartment_id)
        assets.scope(current, db, actor['user'], initial['station_id'])
        policy = approved_policy(request.app.state.settings.policy_path)
        return mutation(request, current, actor, key, body.model_dump(exclude_unset=True), 200,
                        lambda: assets.change_compartment(current, db, actor['user'], compartment_id, body, policy))

    return router
