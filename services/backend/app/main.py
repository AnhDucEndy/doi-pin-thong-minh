from contextlib import asynccontextmanager
from copy import deepcopy
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.schemas import (AssignmentRequest, CallbackReceipt, LoginRequest, LoginResponse,
                             UserCreate, UserUpdate, UserView, UsersPage)
from app.application.identity import DomainError, audit, idempotent, login, utcnow
from app.config import ROOT, ConfigNotReady, Settings, approved_policy
from app.domain.identity import digest, hasher, public_user
from app.infrastructure.db import Database, advisory_lock
import yaml

bearer = HTTPBearer(auto_error=False, scheme_name='UserBearer')


def create_app(settings=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.policy = approved_policy(settings.policy_path)
        app.state.db = Database(settings)
        yield
        app.state.db.engine.dispose()

    app = FastAPI(title='Đổi pin · Phase 2 F2', version='0.2.0', lifespan=lifespan)
    app.state.settings = settings

    def error_response(status, code, message):
        return JSONResponse(status_code=status, content={
            'code': code, 'message': message, 'correlation_id': str(uuid4()), 'details': {}})

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return error_response(error.status, error.code, error.message)

    @app.exception_handler(ConfigNotReady)
    async def config_error(request, error):
        return error_response(422, 'CONFIG_NOT_READY', 'Approved simulation configuration is required')

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response(422, 'VALIDATION_ERROR', 'Request fields are invalid')

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, error):
        return error_response(409, 'RESOURCE_CONFLICT', 'A unique or reference constraint was violated')

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return error_response(503, 'DATABASE_UNAVAILABLE', 'Database service is unavailable')

    def session(request: Request):
        with request.app.state.db.sessions() as current:
            try:
                yield current
                current.commit()
            except Exception:
                current.rollback()
                raise

    def principal(request: Request, auth: HTTPAuthorizationCredentials | None = Depends(bearer),
                  current=Depends(session, scope='function')):
        if not auth or auth.scheme.lower() != 'bearer':
            raise DomainError(401, 'AUTH_REQUIRED')
        db = request.app.state.db
        sessions, users = db.table('auth_sessions'), db.table('users')
        token_session = current.execute(select(sessions).where(sessions.c.token_hash == digest(auth.credentials))).mappings().first()
        if not token_session or token_session['expires_at'] <= utcnow():
            raise DomainError(401, 'SESSION_INVALID')
        # Logout may replay its receipt with the same revoked token; no other endpoint may.
        if token_session['revoked_at'] and request.url.path != '/v1/auth/logout':
            raise DomainError(401, 'SESSION_REVOKED')
        user = current.execute(select(users).where(users.c.id == token_session['user_id'])).mappings().first()
        if not user or user['state'] != 'ACTIVE':
            raise DomainError(401, 'SESSION_REVOKED')
        return {'user': user, 'session': token_session}

    def admin(actor=Depends(principal, scope='function')):
        if actor['user']['role'] != 'ADMIN':
            raise DomainError(403, 'FORBIDDEN')
        return actor

    def mutation(request, current, actor, key, body, status, execute):
        return idempotent(current, request.app.state.db, actor['user']['id'],
                          request.method + ' ' + request.url.path, key, body, status, execute)

    @app.get('/health', tags=['Foundation'])
    def health(request: Request, current=Depends(session, scope='function')):
        approved_policy(settings.policy_path)
        version = current.scalar(text('SHOW server_version'))
        return {'status': 'ok', 'phase': 2, 'database': 'connected', 'postgresql_version': version}

    @app.post('/v1/auth/login', response_model=LoginResponse, operation_id='login', tags=['FR01'])
    def authenticate(body: LoginRequest, request: Request, current=Depends(session, scope='function')):
        policy = approved_policy(settings.policy_path)
        token, ttl, user = login(current, request.app.state.db, policy, body.username, body.password,
                                 request.client.host if request.client else 'unknown')
        return {'access_token': token, 'token_type': 'Bearer', 'expires_in': ttl, 'user': public_user(user)}

    @app.post('/v1/auth/logout', response_model=CallbackReceipt, operation_id='logout', tags=['FR01'])
    def logout(request: Request, key: UUID = Header(alias='Idempotency-Key'),
               actor=Depends(principal, scope='function'), current=Depends(session, scope='function')):
        def execute():
            db = request.app.state.db
            sessions = db.table('auth_sessions')
            current.execute(update(sessions).where(sessions.c.id == actor['session']['id']).values(revoked_at=utcnow()))
            audit(current, db, actor['user']['id'], 'LOGOUT', actor['user']['id'])
            return {'accepted': True, 'duplicate': False}
        return mutation(request, current, actor, key, {}, 200, execute)

    @app.get('/v1/me', response_model=UserView, operation_id='me', tags=['FR01'])
    def me(actor=Depends(principal, scope='function')):
        return public_user(actor['user'])

    @app.get('/v1/users', response_model=UsersPage, operation_id='listUsers', tags=['FR02'])
    def list_users(request: Request, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None,
                   actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        table = request.app.state.db.table('users')
        query = select(table).order_by(table.c.id).limit(limit + 1)
        if cursor:
            query = query.where(table.c.id > cursor)
        rows = current.execute(query).mappings().all()
        return {'items': [public_user(row) for row in rows[:limit]],
                'next_cursor': str(rows[limit - 1]['id']) if len(rows) > limit else None}

    @app.post('/v1/users', response_model=UserView, status_code=201, operation_id='createUser', tags=['FR02'])
    def create_user(body: UserCreate, request: Request, key: UUID = Header(alias='Idempotency-Key'),
                    actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        def execute():
            db = request.app.state.db
            row = current.execute(insert(db.table('users')).values(id=uuid4(), username=body.username,
                password_hash=hasher.hash(body.password), role=body.role.value).returning(db.table('users'))).mappings().one()
            view = public_user(row)
            audit(current, db, actor['user']['id'], 'CREATE_USER', row['id'], after=view)
            return view
        return mutation(request, current, actor, key, body.model_dump(), 201, execute)

    @app.patch('/v1/users/{user_id}', response_model=UserView, operation_id='updateUser', tags=['FR02'])
    def update_user(user_id: UUID, body: UserUpdate, request: Request,
                    key: UUID = Header(alias='Idempotency-Key'), actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        def execute():
            db = request.app.state.db
            table = db.table('users')
            # Serialize changes to the admin set, including the last-admin invariant.
            advisory_lock(current, 'identity:account-administration')
            row = current.execute(select(table).where(table.c.id == user_id).with_for_update()).mappings().first()
            if not row:
                raise DomainError(404, 'USER_NOT_FOUND')
            if body.expected_version != row['version']:
                raise DomainError(409, 'VERSION_CONFLICT')
            changes = body.model_dump(exclude={'expected_version'}, exclude_unset=True)
            if not changes or any(value is None for value in changes.values()):
                raise DomainError(422, 'INVALID_ACTION')
            if row['role'] == 'ADMIN' and row['state'] == 'ACTIVE' and (
                changes.get('role', row['role']) != 'ADMIN' or changes.get('state', row['state']) != 'ACTIVE'):
                others = current.execute(select(table.c.id).where(table.c.id != user_id,
                    table.c.role == 'ADMIN', table.c.state == 'ACTIVE')).first()
                if not others:
                    raise DomainError(409, 'LAST_ADMIN')
            if 'role' in changes and changes['role'] != row['role']:
                swaps, pins, assignments = (db.table(n) for n in ('swap_transactions', 'batteries', 'user_station_assignments'))
                if (current.execute(select(swaps.c.id).where(swaps.c.customer_id == user_id,
                       swaps.c.state.not_in(['COMPLETED', 'CANCELLED', 'CLOSED_COMPENSATED']))).first()
                    or current.execute(select(pins.c.id).where(pins.c.holder_user_id == user_id)).first()
                    or current.execute(select(assignments.c.user_id).where(assignments.c.user_id == user_id)).first()):
                    raise DomainError(409, 'USER_REFERENCED', 'Resolve custody, assignments or active swaps before changing role')
            changes['version'] = row['version'] + 1
            result = current.execute(update(table).where(table.c.id == user_id).values(**changes).returning(table)).mappings().one()
            sessions = db.table('auth_sessions')
            current.execute(update(sessions).where(sessions.c.user_id == user_id, sessions.c.revoked_at.is_(None)).values(revoked_at=utcnow()))
            view = public_user(result)
            audit(current, db, actor['user']['id'], 'UPDATE_USER', user_id, public_user(row), view)
            return view
        return mutation(request, current, actor, key, body.model_dump(exclude_unset=True), 200, execute)

    @app.put('/v1/users/{user_id}/station-assignments', response_model=UserView, operation_id='assignStations', tags=['FR02'])
    def assign_stations(user_id: UUID, body: AssignmentRequest, request: Request,
                        key: UUID = Header(alias='Idempotency-Key'), actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        def execute():
            db = request.app.state.db
            users, stations, assignments = (db.table(n) for n in ('users', 'stations', 'user_station_assignments'))
            row = current.execute(select(users).where(users.c.id == user_id).with_for_update()).mappings().first()
            if not row:
                raise DomainError(404, 'USER_NOT_FOUND')
            if row['role'] != 'TECHNICIAN':
                raise DomainError(422, 'TECHNICIAN_REQUIRED')
            ids = set(body.station_ids)
            known = set(current.scalars(select(stations.c.id).where(stations.c.id.in_(ids))).all())
            if ids != known or len(ids) != len(body.station_ids):
                raise DomainError(422, 'INVALID_STATIONS')
            current.execute(delete(assignments).where(assignments.c.user_id == user_id))
            if ids:
                current.execute(insert(assignments), [{'user_id': user_id, 'station_id': station} for station in ids])
            row = current.execute(update(users).where(users.c.id == user_id).values(version=users.c.version + 1).returning(users)).mappings().one()
            audit(current, db, actor['user']['id'], 'ASSIGN_STATIONS', user_id,
                  after={'station_ids': sorted(map(str, ids))})
            return public_user(row)
        return mutation(request, current, actor, key, body.model_dump(), 200, execute)

    from app.api.assets import build_router
    app.include_router(build_router(session, principal, admin, mutation))

    def contract_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        generated = get_openapi(title=app.title, version=app.version, routes=app.routes)
        original = yaml.safe_load((ROOT / 'doi-pin-giai-doan-2/contracts/openapi.yaml').read_text(encoding='utf-8-sig'))
        spec = deepcopy(original)
        spec['info'] = {'title': app.title, 'version': app.version,
                        'description': 'Phase 1 and F2 implemented operations; original GD2 contract applies.'}
        spec['paths'] = {path: {method: original['paths'][path][method] for method in methods}
                         for path, methods in generated['paths'].items() if path.startswith('/v1/')}
        spec['paths']['/health'] = generated['paths']['/health']
        app.openapi_schema = spec
        return spec

    app.openapi = contract_openapi
    return app


def require_station(session, db, user, station_id):
    """Reusable Technician scope guard; does not expose Phase 2 endpoints."""
    assignments = db.table('user_station_assignments')
    if user['role'] != 'TECHNICIAN' or not session.execute(select(assignments.c.user_id).where(
        assignments.c.user_id == user['id'], assignments.c.station_id == station_id)).first():
        raise DomainError(403, 'STATION_FORBIDDEN')
