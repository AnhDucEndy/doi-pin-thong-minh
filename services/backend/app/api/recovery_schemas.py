"""P8-REC-0.1 input contracts; never accept client-selected custody/state."""
from typing import Annotated, Literal, Any
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.api.schemas import Strict

Purpose = Literal['VERIFY_OLD_POSSESSION', 'RETURN_OLD_TO_CUSTOMER',
                  'VERIFY_NEW_DELIVERY', 'RETURN_FOREIGN_OBJECT', 'RESUME_SWAP']
ContextHash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Serial = Annotated[str, Field(min_length=1, max_length=200)]


class BeginOperation(Strict):
    kind: Literal['BEGIN_OPERATION']
    purpose: Purpose


class ReinspectOperation(Strict):
    kind: Literal['REINSPECT_OPERATION']
    operation_id: UUID
    context_hash: ContextHash


class CloseNoEffect(Strict):
    kind: Literal['CLOSE_NO_EFFECT']
    operation_id: UUID
    context_hash: ContextHash


class StageReference(Strict):
    stage: Literal['PRE_ACTION_INSPECTION', 'POST_ACTION_RECEIPT', 'RECONCILIATION_INSPECTION'] | None = None
    receipt_id: UUID | None = None
    receipt_hash: ContextHash | None = None

    @model_validator(mode='after')
    def complete_reference(self):
        values = (self.stage, self.receipt_id, self.receipt_hash)
        if any(v is not None for v in values) and not all(v is not None for v in values):
            raise ValueError('Stage and exact receipt ID/hash must be supplied together')
        return self


class TechnicianAttest(StageReference):
    kind: Literal['TECHNICIAN_ATTEST']
    operation_id: UUID
    context_hash: ContextHash
    actual_serial: Serial
    observation: Literal['CONFIRM', 'REJECT']


class AuthorizeAction(Strict):
    kind: Literal['AUTHORIZE_ACTION']
    operation_id: UUID
    context_hash: ContextHash
    phase: Literal['INTENT', 'ACTIVATE'] = 'INTENT'
    authorization_id: UUID | None = None
    acknowledgment_id: UUID | None = None

    @model_validator(mode='after')
    def activation_references(self):
        if self.phase == 'ACTIVATE':
            if self.authorization_id is None or self.acknowledgment_id is None:
                raise ValueError('Activation requires exact intent and acknowledgment')
        elif self.authorization_id is not None or self.acknowledgment_id is not None:
            raise ValueError('Intent cannot reference an existing activation')
        return self


class AttachOperation(Strict):
    kind: Literal['ATTACH_OPERATION']
    operation_id: UUID


class LegacyEvidence(Strict):
    expected_version: int = Field(ge=1)
    evidence_event_id: UUID
    note: str = Field(min_length=1)


class StructuredEvidence(Strict):
    expected_version: int = Field(ge=1)
    statement: Annotated[BeginOperation | TechnicianAttest | AttachOperation | AuthorizeAction | ReinspectOperation | CloseNoEffect,
                         Field(discriminator='kind')]
    note: str = Field(min_length=1)


class LegacySettlement(Strict):
    expected_version: int = Field(ge=1)
    evidence_event_id: UUID
    resolution_note: str = Field(min_length=1)


class StructuredSettlement(Strict):
    expected_version: int = Field(ge=1)
    operation_id: UUID
    resolution_note: str = Field(min_length=1)


class CustomerConfirmation(StageReference):
    operation_id: UUID
    context_hash: ContextHash
    confirm: bool = Field(strict=True)


class ServiceObservation(Strict):
    """Observed model facts, not a desired holder or destination override.

    Subject/source/destination are derived from the immutable operation. A null
    actual serial is a missing observation, never proof of possession.
    """
    result: Literal['OBSERVED', 'UNKNOWN', 'REJECTED']
    actual_serial: Serial | None
    supporting_event_ids: list[UUID] = Field(max_length=32)
    simulation_only: Literal[True]


class DeviceObservation(Strict):
    event_id: UUID
    operation_id: UUID
    context_hash: ContextHash
    boot_id: UUID
    seq: int = Field(ge=1, strict=True)
    observed_at: AwareDatetime
    observation: ServiceObservation


class RecoveryConfirmationContext(Strict):
    protocol_version: Literal['0.2'] | None = None
    stage: Literal['LEGACY', 'PRE_ACTION_INSPECTION', 'POST_ACTION_RECEIPT', 'RECONCILIATION_INSPECTION'] = 'LEGACY'
    receipt_id: UUID | None = None
    receipt_hash: ContextHash | None = None
    receipt_observed_at: AwareDatetime | None = None
    case_version: int | None = Field(default=None, ge=1)
    confirmation_status: Literal['AVAILABLE', 'WAITING_RECEIPT', 'UNAVAILABLE', 'CONFIRMED', 'REJECTED',
                                 'EXPIRED', 'CONSUMED', 'CANCELLED', 'REVOKED'] = 'UNAVAILABLE'
    operation_id: UUID
    context_hash: ContextHash
    purpose: Purpose
    expected_serial: Serial
    station_id: UUID
    customer_id: UUID
    expires_at: AwareDatetime
    simulation_only: Literal[True]


class RecoveryCommandContext(Strict):
    id: UUID
    state: Literal['QUEUED', 'DISPATCHED', 'ACKNOWLEDGED', 'OBSERVED', 'REJECTED', 'EXPIRED', 'UNKNOWN']


class RecoveryContext(Strict):
    predecessor_id: UUID | None = None
    predecessor_context_hash: ContextHash | None = None
    reconciliation_only: Literal[True] | None = None
    predecessor_authorization_id: UUID | None = None
    predecessor_authorization_hash: ContextHash | None = None
    operation_id: UUID
    case_id: UUID
    swap_id: UUID
    station_id: UUID
    customer_id: UUID
    purpose: Purpose
    expected_serial: Serial
    return_compartment_id: UUID
    supply_compartment_id: UUID
    created_by: UUID
    base_case_version: int = Field(ge=1)
    base_swap_version: int = Field(ge=1)
    commands: list[RecoveryCommandContext]


class RecoveryTask(RecoveryContext):
    context_hash: ContextHash
    expires_at: AwareDatetime
    simulation_only: Literal[True]


class RecoveryTasks(Strict):
    items: list['ClosureTask | ReconciliationTask | ActionTask | AuthorizationIntentTask | InspectionTask | RecoveryTask']


class RecoveryConfirmationReceipt(Strict):
    id: UUID
    operation_id: UUID
    accepted: Literal[True]
    confirmed: bool


class RecoveryObservationReceipt(Strict):
    id: UUID
    accepted: Literal[True]
    duplicate: bool


class RecoveryAttestationView(Strict):
    stage: Literal['LEGACY', 'PRE_ACTION_INSPECTION', 'POST_ACTION_RECEIPT', 'RECONCILIATION_INSPECTION'] = 'LEGACY'
    reference_receipt_id: UUID | None = None
    id: UUID
    event_id: UUID
    operation_id: UUID
    source_kind: Literal['SIMULATOR', 'TECHNICIAN', 'CUSTOMER']
    actor_user_id: UUID | None
    device_id: UUID | None
    observed_at: AwareDatetime
    received_at: AwareDatetime
    # Read-only accepted evidence; write schemas remain strictly tagged above.
    payload: dict[str, Any]
    payload_hash: ContextHash
    source_boot: UUID | None
    source_seq: int | None
    source_event_id: UUID | None


class RecoveryOperationView(Strict):
    authorization: dict[str, Any] | None = None
    protocol_version: Literal['0.2'] | None = None
    id: UUID
    case_id: UUID
    swap_id: UUID
    station_id: UUID
    customer_id: UUID
    pin_id: UUID | None
    expected_serial: Serial
    purpose: Purpose
    context: RecoveryContext
    context_hash: ContextHash
    created_by: UUID
    created_at: AwareDatetime
    expires_at: AwareDatetime
    base_case_version: int = Field(ge=1)
    base_swap_version: int = Field(ge=1)
    supersedes_id: UUID | None
    consumed_at: AwareDatetime | None
    cancelled_at: AwareDatetime | None
    attestations: list[RecoveryAttestationView]
    simulation_only: Literal[True]


class InspectionTask(RecoveryTask):
    protocol_version: Literal['0.2']
    task_kind: Literal['INSPECT']


class InspectionSlot(Strict):
    compartment_id: UUID
    door_state: Literal['OPEN', 'CLOSED', 'UNKNOWN']
    present: bool
    observed_serial: Serial | None
    battery_id: UUID | None
    lock_released: bool


class InspectionPresenter(Strict):
    serial: Serial
    customer_id: UUID
    swap_id: UUID


class InspectionCommand(Strict):
    id: UUID
    hash: ContextHash
    status: Literal['UNKNOWN', 'NOT_EXECUTED', 'EXECUTED']
    effects: int = Field(ge=0, le=1, strict=True)
    body: str


class InspectionService(Strict):
    id: UUID
    context_hash: ContextHash
    state: Literal['UNKNOWN', 'OBSERVED', 'REJECTED']
    effects: int = Field(ge=0, le=1, strict=True)
    observation: str | None
    sent: int = Field(ge=0, le=1, strict=True)


class PreActionInspection(Strict):
    protocol_version: Literal['0.2']
    stage: Literal['PRE_ACTION_INSPECTION']
    event_id: UUID
    operation_id: UUID
    context_hash: ContextHash
    boot_id: UUID
    seq: int = Field(ge=1, strict=True)
    observed_at: AwareDatetime
    ledger_id: UUID
    fence_generation: int = Field(ge=1, strict=True)
    actual_serial: Serial | None
    slot: InspectionSlot
    presenter: InspectionPresenter | None
    command_entries: list[InspectionCommand]
    service_entries: list[InspectionService]
    snapshot_event_id: UUID
    wrong_return_event_ids: list[UUID]
    result: Literal['OBSERVED', 'UNKNOWN', 'REJECTED']
    read_only: Literal[True]
    effect_count_delta: Literal[0]
    simulation_only: Literal[True]


class AuthorizationAcknowledgment(Strict):
    protocol_version: Literal['0.2']
    message_kind: Literal['AUTHORIZATION_ACK']
    event_id: UUID
    authorization_id: UUID
    authorization_hash: ContextHash
    operation_id: UUID
    context_hash: ContextHash
    boot_id: UUID
    ledger_id: UUID
    fence_generation: int = Field(ge=1, strict=True)
    seq: int = Field(ge=1, strict=True)
    observed_at: AwareDatetime
    stored: Literal[True]
    effect_count_delta: Literal[0]
    simulation_only: Literal[True]


class AuthorizationIntentTask(RecoveryTask):
    protocol_version: Literal['0.2']
    task_kind: Literal['AUTHORIZATION_INTENT']
    authorization_id: UUID
    authorization_hash: ContextHash
    authorization_payload: dict[str, Any]
    effect_allowed: Literal[False]


class ActionTask(RecoveryTask):
    protocol_version: Literal['0.2']
    task_kind: Literal['ACTION']
    authorization_id: UUID
    authorization_hash: ContextHash
    activation_id: UUID
    activation_hash: ContextHash
    activation_payload: dict[str, Any]
    effect_allowed: Literal[True]


class PostActionReceipt(Strict):
    protocol_version: Literal['0.2']
    stage: Literal['POST_ACTION_RECEIPT']
    event_id: UUID
    operation_id: UUID
    context_hash: ContextHash
    authorization_id: UUID
    authorization_hash: ContextHash
    activation_id: UUID
    activation_hash: ContextHash
    boot_id: UUID
    seq: int = Field(ge=1, strict=True)
    ledger_id: UUID
    fence_generation: int = Field(ge=1, strict=True)
    observed_at: AwareDatetime
    effect_started_at: AwareDatetime
    effect_completed_at: AwareDatetime
    actual_serial: Serial
    source_compartment_id: UUID
    destination: Literal['CUSTOMER']
    recipient_id: UUID
    snapshot_event_id: UUID
    command_digest: ContextHash
    service_entry: dict[str, Any]
    service_entry_hash: ContextHash
    result: Literal['OBSERVED']
    effect_count_delta: Literal[1]
    simulation_only: Literal[True]


class ReconciliationTask(RecoveryTask):
    protocol_version: Literal['0.2']
    task_kind: Literal['RECONCILE_INSPECT']
    effect_allowed: Literal[False]


class ReconciliationInspection(PreActionInspection):
    stage: Literal['RECONCILIATION_INSPECTION']
    predecessor_id: UUID
    predecessor_context_hash: ContextHash
    recipient_id: UUID | None
    historical_receipt: PostActionReceipt | None


class ClosureTask(Strict):
    protocol_version: Literal['0.2']
    task_kind: Literal['CLOSE_NO_EFFECT', 'CLOSURE_COMMITTED']
    closure_id: UUID
    operation_id: UUID
    context_hash: ContextHash
    station_id: UUID
    payload: dict[str, Any]
    payload_hash: ContextHash
    receipt_hash: ContextHash | None = None
    effect_allowed: Literal[False]
    simulation_only: Literal[True]


class NoEffectClosure(Strict):
    inspection_event_id: UUID
    prior_effect_state: Literal['NEVER_PREPARED']
    actual_slot: InspectionSlot
    protocol_version: Literal['0.2']
    message_kind: Literal['NO_EFFECT_CLOSURE']
    event_id: UUID
    closure_id: UUID
    closure_hash: ContextHash
    operation_id: UUID
    context_hash: ContextHash
    boot_id: UUID
    seq: int = Field(ge=1, strict=True)
    observed_at: AwareDatetime
    ledger_id: UUID
    fence_generation: int = Field(ge=1, strict=True)
    snapshot_event_id: UUID
    command_entries: list[InspectionCommand]
    service_entries: list[InspectionService]
    denied_command_ids: list[UUID]
    permit_disabled: Literal[True]
    effect_count_delta: Literal[0]
    simulation_only: Literal[True]


RecoveryTasks.model_rebuild()
