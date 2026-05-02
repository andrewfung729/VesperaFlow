"""API schemas for executor profiles."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator
from vesperaflow_core import ExecutorName
from vesperaflow_store.models import ExecutorProfile

_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ExecutorProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    executor: ExecutorName
    is_enabled: bool = True
    is_default: bool = False
    default_model: str | None = Field(default=None, max_length=160)
    env: dict[str, str] = Field(default_factory=dict)
    secret_env: dict[str, str] = Field(default_factory=dict)

    @field_validator("default_model", mode="before")
    @classmethod
    def _normalize_default_model(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def _validate_maps(self) -> "ExecutorProfileCreateRequest":
        _validate_env(self.env)
        _validate_env(self.secret_env)
        return self


class ExecutorProfileUpdateRequest(BaseModel):
    version: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_enabled: bool | None = None
    is_default: bool | None = None
    default_model: str | None = Field(default=None, max_length=160)
    env: dict[str, str] | None = None
    secret_env: dict[str, str | None] | None = None

    @field_validator("default_model", mode="before")
    @classmethod
    def _normalize_default_model(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def _validate_maps(self) -> "ExecutorProfileUpdateRequest":
        if self.env is not None:
            _validate_env(self.env)
        if self.secret_env is not None:
            _validate_env_patch(self.secret_env)
        return self


class ExecutorProfileResponse(BaseModel):
    profile_id: str
    name: str
    executor: ExecutorName
    is_enabled: bool
    is_default: bool
    default_model: str | None
    env: dict[str, str]
    secret_env_keys: list[str]
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @classmethod
    def from_model(cls, profile: ExecutorProfile) -> "ExecutorProfileResponse":
        return cls(
            profile_id=profile.profile_id,
            name=profile.name,
            executor=profile.executor,
            is_enabled=profile.is_enabled,
            is_default=profile.is_default,
            default_model=profile.default_model,
            env=dict(profile.env or {}),
            secret_env_keys=sorted((profile.secret_env or {}).keys()),
            version=profile.version,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            archived_at=profile.archived_at,
        )

def _validate_env(value: dict[str, str]) -> None:
    for key in value:
        if not _ENV_KEY_RE.match(key):
            raise ValueError("env keys must match [A-Z_][A-Z0-9_]*")


def _validate_env_patch(value: dict[str, str | None]) -> None:
    for key in value:
        if not _ENV_KEY_RE.match(key):
            raise ValueError("env keys must match [A-Z_][A-Z0-9_]*")
