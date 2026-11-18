"""Refund state policy; B1a never trusts a client boolean as provider authority."""
from enum import Enum

from app.application.identity import DomainError


class RefundState(str, Enum):
    REQUESTED = 'REQUESTED'
    PENDING = 'PENDING'
    UNKNOWN = 'UNKNOWN'
    FAILED = 'FAILED'
    SUCCEEDED = 'SUCCEEDED'


def transition(current, target):
    """Ordinary transitions only. FAILED retry needs the future permit consumer.

    This pure policy is NOT provider verification or permission to dispatch.
    """
    current, target = RefundState(current), RefundState(target)
    if current == target:
        return current
    if current == RefundState.FAILED:
        raise DomainError(409, 'REFUND_RETRY_NOT_AUTHORIZED')
    allowed = {
        RefundState.REQUESTED: {RefundState.PENDING, RefundState.UNKNOWN},
        RefundState.PENDING: {RefundState.UNKNOWN, RefundState.FAILED, RefundState.SUCCEEDED},
        RefundState.UNKNOWN: {RefundState.FAILED, RefundState.SUCCEEDED},
        RefundState.SUCCEEDED: set(),
    }
    if target not in allowed[current]:
        raise DomainError(409, 'STATE_CONFLICT')
    return target


def reconcile_mode(state):
    if state == RefundState.UNKNOWN:
        return 'QUERY_ONLY'
    if state == RefundState.FAILED:
        raise DomainError(409, 'REFUND_RETRY_NOT_AUTHORIZED')
    raise DomainError(409, 'STATE_CONFLICT')
