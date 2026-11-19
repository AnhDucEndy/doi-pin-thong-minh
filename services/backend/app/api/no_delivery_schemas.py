"""Frozen P8-REC-0.3 wire DTOs. They confer no physical or financial authority."""
from functools import lru_cache
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import AwareDatetime, Field, StrictBool, StrictInt, model_validator

from app.api.schemas import Strict
from app.config import ROOT

Hash = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
Positive = Annotated[StrictInt, Field(ge=1)]
Effect = Annotated[StrictInt, Field(ge=0, le=1)]
Serial = Annotated[str, Field(min_length=1)]


@lru_cache
def frozen_validator(name):
    bundle = json.loads((ROOT / 'docs/implementation-contracts/P8-REC-0.3/contract.schema.json')
                        .read_text(encoding='utf-8-sig'))
    if name not in bundle['$defs']:
        return None
    return Draft202012Validator({'$defs': bundle['$defs'], '$ref': '#/$defs/' + name},
                                format_checker=FormatChecker())


class P8NDModel(Strict):
    @model_validator(mode='before')
    @classmethod
    def frozen_shape(cls, value):
        validator = frozen_validator(cls.__name__.removeprefix('P8ND'))
        if validator is not None and isinstance(value, dict):
            if not validator.is_valid(jsonable_encoder(value)):
                # Do not expose schema diagnostics containing input/proof content.
                raise ValueError('Invalid frozen P8-REC-0.3 shape')
        return value


class P8NDStageReference(P8NDModel):
    protocol_version: Literal['0.3']
    operation_id: UUID
    context_hash: Hash
    stage: Literal['NO_DELIVERY_INSPECTION']
    receipt_id: UUID
    receipt_hash: Hash


class P8NDContext(P8NDModel):
    protocol_version: Literal['0.3']
    purpose: Literal['VERIFY_NO_DELIVERY']
    operation_id: UUID
    case_id: UUID
    swap_id: UUID
    station_id: UUID
    device_id: UUID
    customer_id: UUID
    created_by: UUID
    new_battery_id: UUID
    expected_serial: Serial
    supply_compartment_id: UUID
    return_compartment_id: UUID
    base_case_version: Positive
    base_swap_version: Positive
    created_at: AwareDatetime
    expires_at: AwareDatetime
    context_hash: Hash
    predecessor_id: UUID | None = None
    predecessor_context_hash: Hash | None = None


class P8NDBeginStatement(Strict):
    kind: Literal['BEGIN_OPERATION']
    purpose: Literal['VERIFY_NO_DELIVERY']
    predecessor_id: UUID | None = None


class P8NDBeginRequest(P8NDModel):
    protocol_version: Literal['0.3']
    expected_version: Positive
    note: Annotated[str, Field(min_length=1)]
    statement: P8NDBeginStatement


class P8NDInspectionTask(P8NDModel):
    protocol_version: Literal['0.3']
    task_kind: Literal['VERIFY_NO_DELIVERY_INSPECT']
    context: P8NDContext
    effect_allowed: Literal[False]


class P8NDCommandEntry(P8NDModel):
    id: UUID
    hash: Hash
    status: Literal['UNKNOWN', 'NOT_EXECUTED', 'EXECUTED']
    effects: Effect
    body: str


class P8NDServiceEntry(P8NDModel):
    operation_id: UUID
    context_hash: Hash
    purpose: Annotated[str, Field(min_length=1)]
    state: Literal['PREPARED', 'UNKNOWN', 'OBSERVED', 'REJECTED']
    effects: Effect
    receipt_event_id: UUID | None
    durably_disabled: StrictBool


class P8NDQuiescence(P8NDModel):
    ledger_id: UUID
    fence_generation: Positive
    fence_active: Literal[True]
    cached_commands_denied: Literal[True]
    cached_service_tasks_denied: Literal[True]
    all_issuers_fenced: Literal[True]
    command_digest: Hash
    service_digest: Hash
    denied_command_ids: list[UUID]
    denied_activation_ids: list[UUID]
    watermark_event_id: UUID
    watermark_hash: Hash


class P8NDDeliveryHistory(P8NDModel):
    complete: Literal[True]
    swap_id: UUID
    serial: Serial
    delivery_count: Literal[0]
    journal_hash: Hash
    event_ids: list[UUID]
    boot_ids: list[UUID]


class P8NDObservation(P8NDModel):
    protocol_version: Literal['0.3']
    stage: Literal['NO_DELIVERY_INSPECTION']
    event_id: UUID
    operation_id: UUID
    context_hash: Hash
    device_id: UUID
    boot_id: UUID
    seq: Positive
    observed_at: AwareDatetime
    snapshot_event_id: UUID
    snapshot_hash: Hash
    actual_serial: Serial
    supply_compartment_id: UUID
    present: Literal[True]
    door_state: Literal['CLOSED']
    read_only: Literal[True]
    effect_count_delta: Literal[0]
    result: Literal['OBSERVED']
    command_entries: list[P8NDCommandEntry]
    service_entries: list[P8NDServiceEntry]
    quiescence: P8NDQuiescence
    delivery_history: P8NDDeliveryHistory


class P8NDTechnicianStatement(P8NDStageReference):
    kind: Literal['TECHNICIAN_ATTEST']
    actual_serial: Serial
    observation: Literal['CONFIRM', 'REJECT']


class P8NDTechnicianAttestation(P8NDModel):
    protocol_version: Literal['0.3']
    expected_version: Positive
    note: Annotated[str, Field(min_length=1)]
    statement: P8NDTechnicianStatement


class P8NDCustomerConfirmation(P8NDStageReference):
    confirm: StrictBool


class P8NDDecideStatement(P8NDStageReference):
    kind: Literal['VERIFY_NO_DELIVERY_DECIDE']


class P8NDDecideRequest(P8NDModel):
    protocol_version: Literal['0.3']
    expected_version: Positive
    note: Annotated[str, Field(min_length=1)]
    statement: P8NDDecideStatement


class P8NDEligibilityCertificate(P8NDModel):
    protocol_version: Literal['0.3']
    certificate_id: UUID
    operation_id: UUID
    context_hash: Hash
    case_id: UUID
    case_version: Positive
    swap_id: UUID
    swap_version: Positive
    payment_id: UUID
    station_id: UUID
    device_id: UUID
    boot_id: UUID
    serial: Serial
    receipt_id: UUID
    receipt_hash: Hash
    technician_attestation_id: UUID
    customer_attestation_id: UUID
    ledger_id: UUID
    fence_generation: Positive
    command_digest: Hash
    service_digest: Hash
    validated_at: AwareDatetime
    valid_until: AwareDatetime
    new_pin_delivered: Literal['NO']
    effect_count_delta: Literal[0]


class P8NDCustomerProjection(P8NDModel):
    protocol_version: Literal['0.3']
    purpose: Literal['VERIFY_NO_DELIVERY']
    operation_id: UUID
    context_hash: Hash
    stage: Literal['NO_DELIVERY_INSPECTION']
    receipt_id: UUID | None
    receipt_hash: Hash | None
    expires_at: AwareDatetime
    expected_serial: Serial
    confirmation_status: Literal['AVAILABLE', 'UNAVAILABLE', 'CONFIRMED', 'REJECTED',
                                 'EXPIRED', 'CONSUMED', 'REVOKED']


class P8NDProofView(P8NDModel):
    id: UUID
    operation_id: UUID
    source_kind: Literal['SIMULATOR', 'TECHNICIAN', 'CUSTOMER']
    stage: Literal['NO_DELIVERY_INSPECTION']
    payload_hash: Hash
    reference_receipt_id: UUID | None
    observed_at: AwareDatetime
    received_at: AwareDatetime
    confirmed: StrictBool | None


class P8NDNoDeliveryResponse(P8NDModel):
    protocol_version: Literal['0.3']
    case_id: UUID
    swap_id: UUID
    version: Positive
    new_pin_delivered: Literal['UNKNOWN', 'NO', 'YES']
    old_pin_settled: StrictBool
    operation: P8NDContext
    proofs: list[P8NDProofView]
    certificate: P8NDEligibilityCertificate | None


class P8NDTaskList(P8NDModel):
    items: list[P8NDInspectionTask]


# Runtime list transport may contain existing tasks and a new readonly task;
# no existing DTO or meaning is changed.
from app.api.recovery_schemas import (RecoveryTask, InspectionTask, AuthorizationIntentTask,
                                      ActionTask, ReconciliationTask, ClosureTask)


class P8NDCompatibleTasks(Strict):
    items: list[ClosureTask | ReconciliationTask | ActionTask | AuthorizationIntentTask
                | InspectionTask | RecoveryTask | P8NDInspectionTask]
