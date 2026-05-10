"""Dependency-light API request contracts shared by API and clients."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import ExecutionMode, ExecutorName, OccurrenceEditScope, ScheduleType

_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ScheduleCreate(BaseModel):
    schedule_type: ScheduleType
    planned_at: datetime | None = None
    recurrence_rule: str | None = None
    recurrence_timezone: str | None = None


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    instruction_source: str = Field(min_length=1)
    target_working_directory: str | None = Field(default=None, min_length=1)
    execution_mode: ExecutionMode
    template_id: str | None = None
    executor: ExecutorName | None = None
    executor_profile_id: str | None = None
    schedule: ScheduleCreate


class TaskUpdateRequest(BaseModel):
    version: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    instruction_source: str | None = Field(default=None, min_length=1)


class ScheduleUpdateRequest(BaseModel):
    version: int | None = None
    planned_at: datetime | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    instruction_source: str | None = Field(default=None, min_length=1)
    target_working_directory: str | None = Field(default=None, min_length=1)
    executor: ExecutorName | None = None
    executor_profile_id: str | None = None
    recurrence_rule: str | None = None
    recurrence_timezone: str | None = None


class VersionedCommand(BaseModel):
    version: int | None = None


class OccurrenceUpdateRequest(BaseModel):
    version: int | None = None
    original_occurrence_at: datetime
    scope: OccurrenceEditScope
    planned_at: datetime | None = None
    instruction_source: str | None = Field(default=None, min_length=1)
    recurrence_rule: str | None = None
    recurrence_timezone: str | None = None


class OccurrenceCancelRequest(BaseModel):
    version: int | None = None
    original_occurrence_at: datetime
    scope: OccurrenceEditScope


class TemplateScheduleConfig(BaseModel):
    schedule_type: ScheduleType
    planned_at: datetime | None = None
    recurrence_rule: str | None = None
    recurrence_timezone: str | None = None


class TemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str | None = None
    instruction_source: str = Field(min_length=1)
    default_task_title: str | None = Field(default=None, min_length=1, max_length=240)
    default_target_working_directory: str | None = Field(default=None, min_length=1)
    default_execution_mode: ExecutionMode
    default_schedule_config: TemplateScheduleConfig
    default_executor: ExecutorName | None = None
    default_executor_profile_id: str | None = None


class TemplateUpdateRequest(BaseModel):
    version: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    instruction_source: str | None = Field(default=None, min_length=1)
    default_task_title: str | None = Field(default=None, min_length=1, max_length=240)
    default_target_working_directory: str | None = Field(default=None, min_length=1)
    default_execution_mode: ExecutionMode | None = None
    default_schedule_config: TemplateScheduleConfig | None = None
    default_executor: ExecutorName | None = None
    default_executor_profile_id: str | None = None


class TemplateInstantiateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    instruction_source: str | None = Field(default=None, min_length=1)
    target_working_directory: str | None = Field(default=None, min_length=1)
    execution_mode: ExecutionMode | None = None
    executor: ExecutorName | None = None
    executor_profile_id: str | None = None
    schedule: TemplateScheduleConfig | None = None


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
    def _validate_maps(self) -> ExecutorProfileCreateRequest:
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
    def _validate_maps(self) -> ExecutorProfileUpdateRequest:
        if self.env is not None:
            _validate_env(self.env)
        if self.secret_env is not None:
            _validate_env_patch(self.secret_env)
        return self


def _validate_env(value: dict[str, str]) -> None:
    for key in value:
        if not _ENV_KEY_RE.match(key):
            raise ValueError("env keys must match [A-Z_][A-Z0-9_]*")


def _validate_env_patch(value: dict[str, str | None]) -> None:
    for key in value:
        if not _ENV_KEY_RE.match(key):
            raise ValueError("env keys must match [A-Z_][A-Z0-9_]*")
