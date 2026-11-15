"""Pure proof checks for P8-REC-0.1. No custody or financial side effects.

Authenticated provenance, role/session revocation, current snapshots and locks
must additionally be checked by the application at the decision boundary.
"""
import hashlib
import json

from fastapi.encoders import jsonable_encoder

PURPOSES = frozenset(('VERIFY_OLD_POSSESSION', 'RETURN_OLD_TO_CUSTOMER',
    'VERIFY_NEW_DELIVERY', 'RETURN_FOREIGN_OBJECT', 'RESUME_SWAP'))


def canonical_hash(value):
    return hashlib.sha256(json.dumps(jsonable_encoder(value), sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def proof_errors(operation, attestations, now, boot_id):
    """Return explicit missing/conflicting proof reasons; never infer possession.

    The immutable operation binds the actual serial and customer; a missing,
    rejected, earlier or contradictory source cannot be outweighed by others.
    The simulator timestamp is physical observation time, not receipt time.
    """
    errors = []
    if operation['purpose'] not in PURPOSES:
        errors.append('PURPOSE_INVALID')
    if operation.get('cancelled_at') or operation.get('consumed_at'):
        errors.append('OPERATION_CLOSED')
    if now >= operation['expires_at']:
        errors.append('OPERATION_EXPIRED')
    by_source = {}
    for item in attestations:
        source = item['source_kind']
        if source in by_source:
            errors.append('DUPLICATE_SOURCE')
        by_source[source] = item
        if item['operation_id'] != operation['id']:
            errors.append('OPERATION_MISMATCH')
        payload = item['payload']
        if payload.get('context_hash') != operation['context_hash']:
            errors.append('CONTEXT_MISMATCH')
        if canonical_hash(payload) != item['payload_hash']:
            errors.append('PAYLOAD_INTEGRITY')
        if not (operation['created_at'] <= item['observed_at'] <= item['received_at'] <= now):
            errors.append('ATTESTATION_TIME_INVALID')
        if payload.get('simulation_only') is not True:
            errors.append('SIMULATION_LABEL_REQUIRED')
    if set(by_source) != {'SIMULATOR', 'TECHNICIAN', 'CUSTOMER'}:
        errors.append('SOURCES_INCOMPLETE')
        return sorted(set(errors))
    sim, tech, customer = (by_source[k] for k in ('SIMULATOR', 'TECHNICIAN', 'CUSTOMER'))
    if (sim['source_boot'] != boot_id or not sim.get('device_id')
            or sim.get('actor_user_id') is not None):
        errors.append('DEVICE_PROVENANCE_INVALID')
    if sim['payload'].get('result') != 'OBSERVED':
        errors.append('OBSERVATION_UNKNOWN')
    for item in (sim, tech):
        if item['payload'].get('actual_serial') != operation['expected_serial']:
            errors.append('SERIAL_MISMATCH')
    if (tech.get('actor_user_id') != operation['created_by']
            or customer.get('actor_user_id') != operation['customer_id']
            or tech.get('actor_user_id') == customer.get('actor_user_id')
            or tech.get('device_id') is not None or customer.get('device_id') is not None):
        errors.append('ACTOR_MISMATCH')
    for item in (tech, customer):
        if item['payload'].get('confirm') is not True:
            errors.append('ATTESTATION_REJECTED')
        # The server receipt is the earliest point at which the parties can
        # attest to this accepted observation. Do not trust a client clock.
        if item['observed_at'] < sim['received_at']:
            errors.append('CONFIRMATION_PRECEDES_OBSERVATION')
    return sorted(set(errors))
