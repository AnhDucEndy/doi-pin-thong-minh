from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import Field
from sqlalchemy import select

from app.api.schemas import Strict
from app.application import assets, reservations as service
from app.application.device import device_actor
from app.application.identity import DomainError, idempotent
from app.config import approved_policy
from app.domain.identity import digest


class CredentialRequest(Strict):
    rfid_value: str = Field(min_length=1, max_length=200)


class QrRequest(Strict):
    station_id: UUID


class VerificationRequest(Strict):
    method: Literal['QR', 'RFID']
    credential: str = Field(min_length=1, max_length=512)


class VersionAction(Strict):
    expected_version: int = Field(ge=1)


class ReasonAction(VersionAction):
    reason: str = Field(min_length=1)


def build_router(session, principal, admin, mutation):
    router = APIRouter()

    def customer(actor=Depends(principal, scope='function')):
        if actor['user']['role'] != 'CUSTOMER':
            raise DomainError(403, 'FORBIDDEN')
        return actor

    def reader(actor=Depends(principal, scope='function')):
        if actor['user']['role'] not in ('ADMIN', 'CUSTOMER'):
            raise DomainError(403, 'FORBIDDEN')
        return actor

    def device(request: Request, key: str | None = Header(default=None, alias='X-Device-Key'),
               current=Depends(session, scope='function')):
        return device_actor(current, request.app.state.db, key)

    @router.post('/v1/users/{user_id}/credentials', status_code=201, operation_id='createCredential', tags=['FR09'])
    def create_credential(user_id: UUID, body: CredentialRequest, request: Request,
            key: UUID = Header(alias='Idempotency-Key'), actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        return mutation(request, current, actor, key, body.model_dump(), 201,
            lambda: service.create_credential(current, request.app.state.db, actor['user'], user_id, body.rfid_value))

    @router.post('/v1/credentials/{credential_id}/revoke', operation_id='revokeCredential', tags=['FR09'])
    def revoke(credential_id: UUID, request: Request, key: UUID = Header(alias='Idempotency-Key'),
            actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        return mutation(request, current, actor, key, {}, 200,
            lambda: service.revoke_credential(current, request.app.state.db, actor['user'], credential_id))

    @router.post('/v1/qr-challenges', status_code=201, operation_id='createQr', tags=['FR09'])
    def create_qr(body: QrRequest, request: Request, key: UUID = Header(alias='Idempotency-Key'),
            actor=Depends(customer, scope='function'), current=Depends(session, scope='function')):
        db = request.app.state.db
        token = service.qr_token(actor['user']['id'], key)
        result = mutation(request, current, actor, key, body.model_dump(), 201,
            lambda: service.create_qr(current, db, actor['user'], body.station_id, token,
                approved_policy(request.app.state.settings.policy_path)))
        row = assets.get_row(current, db, 'qr_challenges', UUID(str(result['challenge_id'])))
        if row['token_hash'] != digest(token):
            raise DomainError(409, 'QR_DELIVERY_UNAVAILABLE')
        return {**result, 'qr_token': token}

    @router.post('/v1/device/verifications', status_code=201, operation_id='verifyAtDevice', tags=['FR09'])
    def verify(body: VerificationRequest, request: Request, key: UUID = Header(alias='Idempotency-Key'),
            actor=Depends(device, scope='function'), current=Depends(session, scope='function')):
        return idempotent(current, request.app.state.db, 'device:' + str(actor['id']),
            'POST /v1/device/verifications', key, body.model_dump(), 201,
            lambda: service.verify(current, request.app.state.db, actor, body.method, body.credential,
                approved_policy(request.app.state.settings.policy_path)))

    @router.get('/v1/swaps', operation_id='listSwaps', tags=['FR13'])
    def list_swaps(request: Request, active: bool | None = None, cursor: UUID | None = None,
            limit: int = Query(20, ge=1, le=100), actor=Depends(reader, scope='function'), current=Depends(session, scope='function')):
        table = request.app.state.db.table('swap_transactions')
        query = select(table).order_by(table.c.id).limit(limit + 1)
        if actor['user']['role'] == 'CUSTOMER':
            query = query.where(table.c.customer_id == actor['user']['id'])
        if active is not None:
            query = query.where(table.c.state.not_in(assets.CLOSED_SWAPS) if active else table.c.state.in_(assets.CLOSED_SWAPS))
        if cursor:
            query = query.where(table.c.id > cursor)
        rows = current.execute(query).mappings().all()
        return {'items': [service.public_swap(r) for r in rows[:limit]],
            'next_cursor': str(rows[limit - 1]['id']) if len(rows) > limit else None}

    @router.get('/v1/swaps/{swap_id}', operation_id='getSwap', tags=['FR13'])
    def get_swap(swap_id: UUID, request: Request, actor=Depends(reader, scope='function'), current=Depends(session, scope='function')):
        return service.public_swap(service.owned_swap(current, request.app.state.db, actor['user'], swap_id))

    @router.post('/v1/swaps/{swap_id}/reserve', operation_id='reserveSwap', tags=['FR10'])
    def reserve(swap_id: UUID, body: VersionAction, request: Request, key: UUID = Header(alias='Idempotency-Key'),
            actor=Depends(customer, scope='function'), current=Depends(session, scope='function')):
        approved_policy(request.app.state.settings.policy_path)
        service.owned_swap(current, request.app.state.db, actor['user'], swap_id)
        return mutation(request, current, actor, key, body.model_dump(), 200,
            lambda: service.reserve(current, request.app.state.db, actor['user'], swap_id, body.expected_version))

    @router.post('/v1/swaps/{swap_id}/cancel', operation_id='cancelSwap', tags=['FR12'])
    def cancel(swap_id: UUID, body: ReasonAction, request: Request, key: UUID = Header(alias='Idempotency-Key'),
            actor=Depends(customer, scope='function'), current=Depends(session, scope='function')):
        service.owned_swap(current, request.app.state.db, actor['user'], swap_id)
        return mutation(request, current, actor, key, body.model_dump(), 200,
            lambda: service.cancel(current, request.app.state.db, actor['user'], swap_id, body.expected_version, body.reason))

    return router
