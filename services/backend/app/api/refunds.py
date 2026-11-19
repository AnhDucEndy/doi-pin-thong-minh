"""Original FR16 public paths; all positive money processing is gated on B1b/B3."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import Field

from app.api.payments import PaymentNumbers
from app.api.schemas import Strict
from app.application import refunds


class ReasonAction(PaymentNumbers):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1)


class RefundView(Strict):
    id: UUID
    payment_id: UUID
    requested_by: UUID
    provider_key: UUID
    provider_reference: str | None
    state: Literal['REQUESTED', 'PENDING', 'UNKNOWN', 'FAILED', 'SUCCEEDED']
    amount_minor: int
    verified_at: datetime | None
    reason: str
    version: int
    created_at: datetime


def build_router(session, principal, admin, mutation):
    router = APIRouter()

    @router.post('/v1/payments/{payment_id}/refund', status_code=202, response_model=RefundView,
                 operation_id='requestRefund', tags=['FR16'])
    def request_refund(payment_id: UUID, body: ReasonAction, request: Request,
                       key: UUID = Header(alias='Idempotency-Key'),
                       actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        return refunds.protected_request(request,current,actor,key,payment_id,body)

    @router.get('/v1/payments/{payment_id}/refund', response_model=RefundView,
                operation_id='getRefund', tags=['FR16'])
    def get_refund(payment_id: UUID, request: Request, actor=Depends(principal, scope='function'),
                   current=Depends(session, scope='function')):
        return refunds.get(current, request.app.state.db, actor, payment_id)

    @router.post('/v1/refunds/{refund_id}/reconcile', status_code=202, response_model=RefundView,
                 operation_id='reconcileRefund', tags=['FR16'])
    def reconcile_refund(refund_id: UUID, body: ReasonAction, request: Request,
                         key: UUID = Header(alias='Idempotency-Key'),
                         actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        return mutation(request, current, actor, key, body.model_dump(), 202,
            lambda: refunds.reconcile(current, request.app.state.db, actor, refund_id, body))

    return router
