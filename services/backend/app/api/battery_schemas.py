from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field
from app.api.schemas import Strict


class BatteryCreate(Strict):
    serial: str
    family: str
    location_kind: Literal['COMPARTMENT', 'CUSTOMER', 'UNKNOWN']
    compartment_id: UUID | None = None
    holder_user_id: UUID | None = None


class BatteryView(BatteryCreate):
    id: UUID
    lifecycle: Literal['REGISTERED', 'IN_SERVICE', 'QUARANTINED', 'RETIRED']
    version: int
    created_at: datetime


class BatteriesPage(Strict):
    items: list[BatteryView]
    next_cursor: str | None


class BatteryAction(Strict):
    expected_version: int = Field(ge=1)
    action: Literal['ACTIVATE', 'QUARANTINE', 'RESTORE', 'RETIRE']
    reason: str = Field(min_length=1)
    evidence_event_id: UUID | None = None
    resolve_alert_ids: list[UUID] = Field(default_factory=list)


class TelemetryView(Strict):
    id: UUID
    event_id: UUID
    battery_id: UUID
    soc: float | None
    soh: float | None
    temperature_c: float | None
    fault_codes: list[str]
    measured_at: datetime
    received_at: datetime
    quality_ok: bool


class TelemetryPage(Strict):
    items: list[TelemetryView]
    next_cursor: str | None
