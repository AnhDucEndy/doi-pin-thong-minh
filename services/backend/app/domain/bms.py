"""Payload validation reusable by the future inbox; no device endpoint or worker here."""
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class BMSPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    battery_id: UUID
    soc: float | None = Field(ge=0, le=100, allow_inf_nan=False, strict=True)
    soh: float | None = Field(ge=0, le=100, allow_inf_nan=False, strict=True)
    temperature_c: float | None = Field(allow_inf_nan=False, strict=True)
    fault_codes: list[str]
