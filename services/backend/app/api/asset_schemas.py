from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field
from app.api.schemas import Strict

StationState = Literal['ACTIVE', 'MAINTENANCE', 'INACTIVE']


class StationCreate(Strict):
    code: str
    name: str
    address: str


class StationUpdate(Strict):
    expected_version: int = Field(ge=1)
    name: str | None = None
    address: str | None = None
    state: StationState | None = None


class StationView(StationCreate):
    id: UUID
    state: StationState
    version: int
    created_at: datetime


class Availability(Strict):
    station_id: UUID
    name: str
    address: str
    operational_state: Literal['ONLINE', 'OFFLINE', 'MAINTENANCE', 'INACTIVE']
    available_count: int = Field(ge=0)
    as_of: datetime


class AvailabilityPage(Strict):
    items: list[Availability]
    next_cursor: str | None


class DeviceCreate(Strict):
    station_id: UUID
    serial: str


class DeviceUpdate(Strict):
    expected_version: int = Field(ge=1)
    enabled: bool


class DeviceView(Strict):
    id: UUID
    station_id: UUID
    serial: str
    enabled: bool
    last_received_at: datetime | None
    boot_id: UUID | None
    last_seq: int
    version: int
    created_at: datetime


class DeviceCreated(Strict):
    device: DeviceView
    device_key_once: str


class DevicesPage(Strict):
    items: list[DeviceView]
    next_cursor: str | None


class CompartmentCreate(Strict):
    slot_no: int = Field(ge=1)


class CompartmentAction(Strict):
    expected_version: int = Field(ge=1)
    action: Literal['SET_MAINTENANCE', 'RESTORE', 'RETIRE']
    reason: str = Field(min_length=1)
    evidence_event_id: UUID | None = None


class CompartmentView(Strict):
    id: UUID
    station_id: UUID
    slot_no: int
    service_state: Literal['ACTIVE', 'BLOCKED', 'MAINTENANCE', 'RETIRED']
    door_state: Literal['OPEN', 'CLOSED', 'UNKNOWN']
    observed_present: bool | None
    observed_serial: str | None
    observed_at: datetime | None
    version: int
    created_at: datetime


class CompartmentsPage(Strict):
    items: list[CompartmentView]
    next_cursor: str | None
