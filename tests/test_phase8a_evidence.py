"""Independent evidence cases. Passing these is not settlement acceptance."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.config import Settings
from app.domain.recovery import canonical_hash, proof_errors


def evidence():
    now = datetime.now(timezone.utc)
    customer, technician, boot = uuid4(), uuid4(), uuid4()
    op = {'id': uuid4(), 'purpose': 'VERIFY_OLD_POSSESSION', 'created_at': now - timedelta(seconds=30),
        'expires_at': now + timedelta(seconds=90), 'context_hash': 'c' * 64,
        'expected_serial': 'ACTUAL-OLD', 'created_by': technician, 'customer_id': customer}
    records = []
    for source, actor in [('SIMULATOR', None), ('TECHNICIAN', technician), ('CUSTOMER', customer)]:
        observed = now - timedelta(seconds=20 if source == 'SIMULATOR' else 10)
        payload = {'context_hash': op['context_hash'], 'simulation_only': True,
            'actual_serial': 'ACTUAL-OLD', 'confirm': True, 'result': 'OBSERVED'}
        records.append({'operation_id': op['id'], 'source_kind': source, 'actor_user_id': actor,
            'device_id': uuid4() if source == 'SIMULATOR' else None,
            'source_boot': boot if source == 'SIMULATOR' else None,
            'observed_at': observed, 'received_at': observed + timedelta(seconds=1),
            'payload': payload, 'payload_hash': canonical_hash(payload)})
    return op, records, now, boot


def test_agreeing_sources_with_historical_observation():
    op, records, now, boot = evidence()
    assert proof_errors(op, records, now, boot) == []
    # The 15-second CURRENT SNAPSHOT guard belongs at the DB decision. Stored
    # service evidence does not become false simply because >15 seconds old.


@pytest.mark.parametrize('source', ['SIMULATOR', 'TECHNICIAN', 'CUSTOMER'])
def test_each_source_is_required(source):
    op, records, now, boot = evidence()
    assert 'SOURCES_INCOMPLETE' in proof_errors(op,
        [r for r in records if r['source_kind'] != source], now, boot)


@pytest.mark.parametrize('index', [1, 2])
def test_rejection_cannot_be_outvoted(index):
    op, records, now, boot = evidence()
    records[index]['payload']['confirm'] = False
    records[index]['payload_hash'] = canonical_hash(records[index]['payload'])
    assert 'ATTESTATION_REJECTED' in proof_errors(op, records, now, boot)


@pytest.mark.parametrize('index', [0, 1])
@pytest.mark.parametrize('serial', [None, 'FOREIGN'])
def test_missing_or_wrong_serial_not_possession(index, serial):
    op, records, now, boot = evidence()
    records[index]['payload']['actual_serial'] = serial
    records[index]['payload_hash'] = canonical_hash(records[index]['payload'])
    assert 'SERIAL_MISMATCH' in proof_errors(op, records, now, boot)


@pytest.mark.parametrize('index', [1, 2])
def test_confirmation_must_follow_observation_receipt(index):
    op, records, now, boot = evidence()
    records[index]['observed_at'] = records[0]['observed_at']
    assert 'CONFIRMATION_PRECEDES_OBSERVATION' in proof_errors(op, records, now, boot)


def test_equality_at_operation_expiry_is_expired():
    op, records, _, boot = evidence()
    assert 'OPERATION_EXPIRED' in proof_errors(op, records, op['expires_at'], boot)


def test_duplicate_source_is_not_bilateral_proof():
    op, records, now, boot = evidence()
    records.append(deepcopy(records[-1]))
    assert 'DUPLICATE_SOURCE' in proof_errors(op, records, now, boot)


def test_boot_change_requires_revalidation():
    op, records, now, _ = evidence()
    assert 'DEVICE_PROVENANCE_INVALID' in proof_errors(op, records, now, uuid4())


def test_role_change_cannot_allow_one_principal_to_attest_twice():
    op, records, now, boot = evidence()
    records[1]['actor_user_id'] = records[2]['actor_user_id']
    assert 'ACTOR_MISMATCH' in proof_errors(op, records, now, boot)


@pytest.mark.parametrize('field', ['context_hash', 'actual_serial'])
def test_payload_tampering_is_detected(field):
    op, records, now, boot = evidence()
    records[0]['payload'][field] = 'modified'
    assert 'PAYLOAD_INTEGRITY' in proof_errors(op, records, now, boot)


def test_ttl_configuration_does_not_modify_approved_policy():
    assert Settings('postgresql+psycopg://unused').recovery_operation_ttl_seconds == 120
    assert Settings('postgresql+psycopg://unused', recovery_operation_ttl_seconds=90).recovery_operation_ttl_seconds == 90
    with pytest.raises(ValueError):
        Settings('postgresql+psycopg://unused', recovery_operation_ttl_seconds=0)
