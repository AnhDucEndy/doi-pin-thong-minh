"""B1b checkpoint A: frozen wire/runtime contract, no physical/financial proof."""
from copy import deepcopy
import importlib.util
import json

import pytest
from pydantic import ValidationError
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec
import yaml

from app.api import no_delivery_schemas as dto
from app.api.recovery_schemas import StructuredEvidence, CustomerConfirmation
from app.config import ROOT
from app.main import create_app


ROOT_CONTRACT = ROOT/'docs/implementation-contracts/P8-REC-0.3'
BUNDLE = json.loads((ROOT_CONTRACT/'contract.schema.json').read_text(encoding='utf-8-sig'))
loader = importlib.util.spec_from_file_location('b1b_example_source',
    ROOT/'docs/implementation-contracts/P8-REF-0.1/validate_static.py')
examples = importlib.util.module_from_spec(loader)
loader.loader.exec_module(examples)


def sample(name):
    return examples.example(BUNDLE['$defs'][name], BUNDLE['$defs'])


@pytest.mark.parametrize('name', list(BUNDLE['$defs']))
def test_all_frozen_definitions_round_trip(name):
    model = getattr(dto, 'P8ND'+name)
    value = model.model_validate(sample(name))
    result = value.model_dump(mode='json', exclude_unset=True)
    Draft202012Validator({'$defs': BUNDLE['$defs'], '$ref': '#/$defs/'+name},
                        format_checker=FormatChecker()).validate(result)
    with pytest.raises(ValidationError):
        model.model_validate({**sample(name), 'unexpected_field': 'forbidden'})


@pytest.mark.parametrize('name', ['BeginRequest', 'TechnicianAttestation', 'DecideRequest',
                                  'CustomerConfirmation', 'Observation'])
@pytest.mark.parametrize('field,value', [('actor_id', 'client'), ('custody', 'CUSTOMER'),
                                        ('amount_minor', 1), ('new_pin_delivered', 'NO')])
def test_inputs_cannot_select_authority_or_financial_state(name, field, value):
    with pytest.raises(ValidationError):
        getattr(dto, 'P8ND'+name).model_validate({**sample(name), field: value})


@pytest.mark.parametrize('value', [True, 1.0, '1', 0])
def test_case_version_is_strict_positive_integer(value):
    body = sample('BeginRequest')
    body['expected_version'] = value
    with pytest.raises(ValidationError):
        dto.P8NDBeginRequest.model_validate(body)


@pytest.mark.parametrize('name,field,value', [
    ('InspectionTask', 'effect_allowed', 0),
    ('Observation', 'read_only', 1),
    ('Observation', 'effect_count_delta', False),
    ('CustomerConfirmation', 'confirm', 1),
])
def test_bool_and_numeric_literals_do_not_coerce(name, field, value):
    body = sample(name)
    body[field] = value
    with pytest.raises(ValidationError):
        getattr(dto, 'P8ND'+name).model_validate(body)


def test_old_dtos_cannot_smuggle_no_delivery_purpose_or_stage():
    with pytest.raises(ValidationError):
        StructuredEvidence.model_validate(sample('BeginRequest'))
    with pytest.raises(ValidationError):
        CustomerConfirmation.model_validate(sample('CustomerConfirmation'))
    body = sample('TechnicianAttestation')
    body['statement']['stage'] = 'POST_ACTION_RECEIPT'
    with pytest.raises(ValidationError):
        dto.P8NDTechnicianAttestation.model_validate(body)


def test_runtime_openapi_is_additive_and_keeps_refund_charge_authority():
    spec = create_app().openapi()
    validate_spec(spec)
    original = yaml.safe_load((ROOT/'doi-pin-giai-doan-2/contracts/openapi.yaml')
                              .read_text(encoding='utf-8-sig'))
    assert not any(p.startswith('/mock/') for p in spec['paths'])
    for path in ('/v1/payments/{payment_id}/refund', '/v1/refunds/{refund_id}/reconcile'):
        assert spec['paths'][path] == original['paths'][path]
    assert spec['paths']['/v1/payment-events'] == original['paths']['/v1/payment-events']
    overlay = yaml.safe_load((ROOT_CONTRACT/'openapi.overlay.yaml').read_text(encoding='utf-8-sig'))
    for path, methods in overlay['paths'].items():
        for method, expected in methods.items():
            actual = spec['paths'][path][method]
            assert actual['security'] == expected['security']
            assert actual['operationId'] == expected['operationId']
            assert actual['x-roles'] == expected['x-roles']
    for name, schema in overlay['components']['schemas'].items():
        if name.startswith('P8ND'):
            assert spec['components']['schemas'][name] == schema
    evidence = spec['paths']['/v1/swaps/{swap_id}/recovery/evidence']['post']
    refs = json.dumps(evidence['requestBody'])
    assert all(name in refs for name in ('P8NDBeginRequest', 'P8NDTechnicianAttestation',
                                         'P8NDDecideRequest', 'LegacyEvidence', 'StructuredEvidence'))
    tasks = spec['components']['schemas']['P8NDCompatibleTasks']['properties']['items']['items']
    refs = json.dumps(tasks)
    assert all(name in refs for name in ('RecoveryTask', 'ClosureTask', 'ActionTask', 'P8NDInspectionTask'))
    projection = spec['components']['schemas']['SwapTransactions']['properties']['recovery_confirmation']
    assert 'P8NDCustomerProjection' in json.dumps(projection)
    assert 'RecoveryConfirmationContext' in json.dumps(projection)


def test_checkpoint_a_has_no_action_request_branch():
    body = sample('BeginRequest')
    for kind in ('AUTHORIZE_ACTION', 'ACTIVATE', 'HANDOVER', 'CLOSE_NO_EFFECT'):
        changed = deepcopy(body)
        changed['statement']['kind'] = kind
        with pytest.raises(ValidationError):
            dto.P8NDBeginRequest.model_validate(changed)


@pytest.mark.parametrize('role', ['admin', 'customer'])
def test_api_no_delivery_begin_preserves_technician_authority(client, environment, auth, role):
    from test_phase6 import book
    from test_phase1 import headers
    from sqlalchemy import select
    customer = auth('customer')
    swap = book(client, environment, customer)
    caller = auth(role)  # Login audit belongs to setup, before the refusal snapshot.
    db = client.app.state.db
    with db.sessions() as s:
        before = {name: [dict(v) for v in s.execute(select(db.table(name))).mappings()]
                  for name in ('recovery_cases', 'recovery_operations', 'audit_events',
                               'refund_eligibility_certificates', 'refunds')}
    response = client.post('/v1/swaps/'+swap['id']+'/recovery/evidence',
                           headers=headers(caller), json=sample('BeginRequest'))
    assert response.status_code == 403
    with db.sessions() as s:
        assert before == {name: [dict(v) for v in s.execute(select(db.table(name))).mappings()]
                          for name in before}


def test_api_no_delivery_device_auth_and_closed_input(client, environment):
    response = client.post('/v1/device/recovery-observations',
                           headers={'X-Device-Key': 'invalid-test-key'}, json=sample('Observation'))
    assert response.status_code == 401
    body = sample('Observation')
    body['effect_count_delta'] = 1
    response = client.post('/v1/device/recovery-observations',
        headers={'X-Device-Key': environment['keys']['S01']}, json=body)
    assert response.status_code == 422 and response.json()['code'] == 'VALIDATION_ERROR'
