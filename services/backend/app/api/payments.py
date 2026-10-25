import hmac
import os
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import Field, field_validator
from app.api.schemas import Strict
from app.application import payments, reservations
from app.application.identity import DomainError
from app.config import ConfigNotReady, approved_policy


def secret(name):
    value = os.getenv(name, '')
    if len(value) < 32 or value.startswith('REPLACE_'):
        raise ConfigNotReady('CONFIG_NOT_READY')
    return value


class PaymentNumbers(Strict):
    @field_validator('expected_version', 'quoted_amount_minor', 'amount_minor', mode='before', check_fields=False)
    @classmethod
    def json_number(cls, value):
        # JSON Schema integer does not accept strings/bools. Integral JSON
        # numbers remain valid; Pydantic checks their range/integrality below.
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError('JSON number required')
        return value


class ConsentRequest(PaymentNumbers):
    expected_version: int = Field(ge=1)
    quoted_amount_minor: int = Field(ge=1)
    currency: Literal['VND']
    accept: Literal[True]

    @field_validator('accept', mode='before')
    @classmethod
    def explicit_accept(cls, value):
        if value is not True:
            raise ValueError('Explicit boolean consent required')
        return value


class ReconcileRequest(PaymentNumbers):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1)


class PaymentCallback(PaymentNumbers):
    provider_event_id: str
    payment_id: UUID
    refund_id: UUID | None = None
    provider_key: UUID
    provider_reference: str
    result: Literal['PENDING', 'SUCCEEDED', 'FAILED']
    amount_minor: int = Field(ge=1)
    currency: Literal['VND']

    @field_validator('refund_id', mode='before')
    @classmethod
    def optional_uuid_not_null(cls, value):
        if value is None:
            raise ValueError('Omit refund_id for a charge event')
        return value


class ProviderChargeRequest(PaymentNumbers):
    payment_id: UUID
    swap_id: UUID
    provider_key: UUID
    amount_minor: int = Field(ge=1)
    currency: Literal['VND']


class ProviderResult(PaymentNumbers):
    provider_key: UUID
    provider_reference: str | None
    result: Literal['NOT_FOUND', 'PENDING', 'SUCCEEDED', 'FAILED', 'UNKNOWN']
    amount_minor: int | None = Field(ge=1)
    currency: Literal['VND'] | None


def build_router(session, principal, admin, mutation):
    router = APIRouter()

    def customer(actor=Depends(principal, scope='function')):
        if actor['user']['role'] != 'CUSTOMER':
            raise DomainError(403, 'FORBIDDEN')
        return actor

    @router.post('/v1/swaps/{swap_id}/consent', status_code=202, operation_id='consentSwap', tags=['FR14'])
    def consent(swap_id: UUID, body: ConsentRequest, request: Request, key: UUID = Header(alias='Idempotency-Key'),
                actor=Depends(customer, scope='function'), current=Depends(session, scope='function')):
        approved_policy(request.app.state.settings.policy_path)
        reservations.owned_swap(current, request.app.state.db, actor['user'], swap_id)
        return mutation(request, current, actor, key, body.model_dump(), 202,
            lambda: payments.consent(current, request.app.state.db, actor['user'], swap_id, body))

    @router.get('/v1/swaps/{swap_id}/payment', operation_id='getPayment', tags=['FR14'])
    def get(swap_id: UUID, request: Request, actor=Depends(principal, scope='function'), current=Depends(session, scope='function')):
        reservations.owned_swap(current, request.app.state.db, actor['user'], swap_id)
        return dict(payments.get(current, request.app.state.db, swap_id))

    @router.post('/v1/payments/{payment_id}/reconcile', status_code=202, operation_id='reconcilePayment', tags=['FR15'])
    def reconcile(payment_id: UUID, body: ReconcileRequest, request: Request, key: UUID = Header(alias='Idempotency-Key'),
                  actor=Depends(admin, scope='function'), current=Depends(session, scope='function')):
        return mutation(request, current, actor, key, body.model_dump(), 202,
            lambda: payments.reconcile(current, request.app.state.db, payment_id, body.expected_version, body.reason))

    @router.post('/v1/payment-events', status_code=202, operation_id='receivePaymentEvent', tags=['FR14'])
    def receive(body: PaymentCallback, request: Request, key: str | None = Header(None, alias='X-Payment-Key'),
                current=Depends(session, scope='function')):
        if not key or not hmac.compare_digest(key.encode(), secret('PAYMENT_CALLBACK_KEY').encode()):
            raise DomainError(401, 'AUTH_REQUIRED')
        return payments.receive(current, request.app.state.db, body)

    return router
