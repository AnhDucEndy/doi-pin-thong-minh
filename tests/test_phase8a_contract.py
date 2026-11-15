"""Input-boundary checks for the approved recovery appendix (no DB mutation)."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.api.recovery_schemas import (
    CustomerConfirmation, DeviceObservation, LegacyEvidence, LegacySettlement,
    StructuredEvidence, StructuredSettlement,
)


@pytest.mark.parametrize('references', [{}, {'authorization_id':str(uuid4())}, {'acknowledgment_id':str(uuid4())}])
def test_activation_requires_both_durable_references(references):
    from app.api.recovery_schemas import AuthorizeAction
    with pytest.raises(ValidationError):
        AuthorizeAction.model_validate({'kind':'AUTHORIZE_ACTION','phase':'ACTIVATE',
            'operation_id':str(uuid4()),'context_hash':'a'*64,**references})


def test_intent_cannot_implicitly_activate_and_activation_is_explicit():
    from app.api.recovery_schemas import AuthorizeAction
    body={'kind':'AUTHORIZE_ACTION','operation_id':str(uuid4()),'context_hash':'a'*64}
    assert AuthorizeAction.model_validate(body).phase=='INTENT'
    refs={'authorization_id':str(uuid4()),'acknowledgment_id':str(uuid4())}
    with pytest.raises(ValidationError):
        AuthorizeAction.model_validate({**body,**refs})
    assert AuthorizeAction.model_validate({**body,**refs,'phase':'ACTIVATE'}).phase=='ACTIVATE'


@pytest.mark.parametrize('purpose', [
    'VERIFY_OLD_POSSESSION', 'RETURN_OLD_TO_CUSTOMER', 'VERIFY_NEW_DELIVERY',
    'RETURN_FOREIGN_OBJECT', 'RESUME_SWAP',
])
def test_approved_purposes(purpose):
    parsed = StructuredEvidence.model_validate({'expected_version': 1,
        'statement': {'kind': 'BEGIN_OPERATION', 'purpose': purpose}, 'note': 'inspection'})
    assert parsed.statement.purpose == purpose


@pytest.mark.parametrize('field,value', [
    ('desired_state', 'COMPLETED'), ('holder_user_id', str(uuid4())),
    ('old_pin_settled', True), ('new_pin_delivered', 'YES'), ('actor_id', str(uuid4())),
])
def test_client_cannot_select_settlement_result(field, value):
    with pytest.raises(ValidationError):
        StructuredSettlement.model_validate({'expected_version': 1,
            'operation_id': str(uuid4()), 'resolution_note': 'inspection', field: value})


def test_legacy_contracts_are_distinct_from_structured_requests():
    evidence = {'expected_version': 1, 'evidence_event_id': str(uuid4()), 'note': 'inspection'}
    assert isinstance(TypeAdapter(LegacyEvidence | StructuredEvidence).validate_python(evidence), LegacyEvidence)
    settle = {'expected_version': 1, 'evidence_event_id': str(uuid4()), 'resolution_note': 'inspection'}
    assert isinstance(TypeAdapter(LegacySettlement | StructuredSettlement).validate_python(settle), LegacySettlement)
    with pytest.raises(ValidationError):
        TypeAdapter(LegacyEvidence | StructuredEvidence).validate_python({**evidence,
            'statement': {'kind': 'BEGIN_OPERATION', 'purpose': 'RESUME_SWAP'}})


@pytest.mark.parametrize('value', ['true', 'false', 0, 1, None])
def test_confirmation_requires_explicit_boolean(value):
    with pytest.raises(ValidationError):
        CustomerConfirmation.model_validate({'operation_id': str(uuid4()),
            'context_hash': 'a' * 64, 'confirm': value})


def observation():
    return {'event_id': str(uuid4()), 'operation_id': str(uuid4()), 'context_hash': 'a' * 64,
        'boot_id': str(uuid4()), 'seq': 1, 'observed_at': datetime.now(timezone.utc).isoformat(),
        'observation': {'result': 'OBSERVED', 'actual_serial': 'observed-model-serial',
            'supporting_event_ids': [], 'simulation_only': True}}


@pytest.mark.parametrize('timestamp', [None, 'invalid', '2026-10-29T10:00:00'])
def test_observation_requires_timezone(timestamp):
    with pytest.raises(ValidationError):
        DeviceObservation.model_validate({**observation(), 'observed_at': timestamp})


@pytest.mark.parametrize('seq', [0, -1, True, '2'])
def test_service_sequence_is_positive_integer(seq):
    with pytest.raises(ValidationError):
        DeviceObservation.model_validate({**observation(), 'seq': seq})


def test_missing_serial_remains_missing_not_expected_serial():
    body = observation()
    body['observation'].update(result='UNKNOWN', actual_serial=None)
    assert DeviceObservation.model_validate(body).observation.actual_serial is None


def test_customer_rejection_is_preserved():
    parsed = CustomerConfirmation.model_validate({'operation_id': str(uuid4()),
        'context_hash': 'a' * 64, 'confirm': False})
    assert parsed.confirm is False
