"""P8-REC-0.1 evidence endpoints; source authentication remains distinct."""
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.recovery_schemas import (CustomerConfirmation, LegacyEvidence, StructuredEvidence,
    LegacySettlement, StructuredSettlement, DeviceObservation, RecoveryTasks,
    RecoveryConfirmationReceipt, RecoveryObservationReceipt, PreActionInspection, AuthorizationAcknowledgment, PostActionReceipt)
from app.application import recovery as service
from app.application.device import device_actor
from app.api.recovery_schemas import ReconciliationInspection, NoEffectClosure


def build_router(session, principal, mutation):
    router = APIRouter(tags=['FR12'])

    def device(request: Request, key: str | None = Header(default=None, alias='X-Device-Key'),
               current=Depends(session, scope='function')):
        return device_actor(current, request.app.state.db, key)

    @router.get('/v1/device/recovery-tasks', operation_id='pollRecoveryTasks', response_model=RecoveryTasks, response_model_exclude_unset=True)
    def tasks(request: Request, actor=Depends(device, scope='function'), current=Depends(session, scope='function')):
        return service.tasks(current, request.app.state.db, actor)

    @router.post('/v1/device/recovery-observations', status_code=202, operation_id='receiveRecoveryObservation', response_model=RecoveryObservationReceipt)
    def observation(body: ReconciliationInspection | NoEffectClosure | PostActionReceipt | AuthorizationAcknowledgment | PreActionInspection | DeviceObservation, request: Request, actor=Depends(device, scope='function'),
                    current=Depends(session, scope='function')):
        if isinstance(body, (PreActionInspection, AuthorizationAcknowledgment, PostActionReceipt, NoEffectClosure)):
            from app.application.recovery_inspection import receive
            return receive(current, request.app.state.db, actor, body)
        return service.observe(current, request.app.state.db, actor, body)

    @router.get('/v1/swaps/{swap_id}/recovery', operation_id='getRecovery')
    def get(swap_id: UUID, request: Request, actor=Depends(principal, scope='function'),
            current=Depends(session, scope='function')):
        return service.get(current, request.app.state.db, actor, swap_id)

    @router.post('/v1/swaps/{swap_id}/recovery/evidence', operation_id='recordRecoveryEvidence')
    def record(swap_id: UUID, body: LegacyEvidence | StructuredEvidence, request: Request,
            key: UUID = Header(alias='Idempotency-Key'), actor=Depends(principal, scope='function'),
            current=Depends(session, scope='function')):
        db = request.app.state.db
        swap = service.assets.get_row(current, db, 'swap_transactions', swap_id)
        service.authorize(current, db, actor, swap, write=True)
        return mutation(request, current, actor, key, body.model_dump(), 200,
            lambda: service.record(current, db, actor, swap_id, body,
                request.app.state.settings.recovery_operation_ttl_seconds))

    @router.post('/v1/swaps/{swap_id}/recovery/confirmations', status_code=201,
                 operation_id='confirmRecovery', response_model=RecoveryConfirmationReceipt)
    def confirm(swap_id: UUID, body: CustomerConfirmation, request: Request,
            key: UUID = Header(alias='Idempotency-Key'), actor=Depends(principal, scope='function'),
            current=Depends(session, scope='function')):
        db = request.app.state.db
        swap = service.assets.get_row(current, db, 'swap_transactions', swap_id)
        if actor['user']['role'] != 'CUSTOMER' or swap['customer_id'] != actor['user']['id']:
            raise service.DomainError(403, 'FORBIDDEN')
        return mutation(request, current, actor, key, body.model_dump(), 201,
            lambda: service.confirmation(current, db, actor, swap_id, body))

    @router.post('/v1/swaps/{swap_id}/recovery/settle', operation_id='settleRecovery')
    def settle(swap_id: UUID, body: LegacySettlement | StructuredSettlement, request: Request,
            key: UUID = Header(alias='Idempotency-Key'), actor=Depends(principal, scope='function'),
            current=Depends(session, scope='function')):
        db = request.app.state.db
        swap = service.assets.get_row(current, db, 'swap_transactions', swap_id)
        service.authorize(current, db, actor, swap, write=True)
        return mutation(request, current, actor, key, body.model_dump(), 200,
            lambda: service.settle(current, db, actor, swap_id, body))

    return router
