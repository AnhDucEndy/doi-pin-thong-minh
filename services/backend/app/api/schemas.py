from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.domain.identity import Role, AccountState


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class LoginRequest(Strict):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class UserView(Strict):
    id: UUID
    username: str
    role: Role
    state: AccountState
    version: int
    created_at: datetime


class LoginResponse(Strict):
    access_token: str
    token_type: Literal['Bearer'] = 'Bearer'
    expires_in: int = Field(ge=1)
    user: UserView


class UsersPage(Strict):
    items: list[UserView]
    next_cursor: str | None


class UserCreate(Strict):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=12, max_length=256)
    role: Role

    @field_validator('username')
    @classmethod
    def normalize(cls, value):
        value = value.strip().lower()
        if len(value) < 3:
            raise ValueError('Username must contain at least 3 characters')
        return value


class UserUpdate(Strict):
    expected_version: int = Field(ge=1)
    role: Role | None = None
    state: AccountState | None = None


class AssignmentRequest(Strict):
    station_ids: list[UUID]


class CallbackReceipt(Strict):
    accepted: bool
    duplicate: bool
