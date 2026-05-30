"""Shared workflow and activity payload contracts.

All contracts use Pydantic v2 for runtime validation, serialization, and
version-conscious schema evolution across Temporal boundaries.
"""

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from .enums import ExecutorName, ExecutorPreflightStatus, RunStatus, ScheduleType

type ProfileValidationDetailValue = str | bool | None


class ExecutionSnapshot(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    run_id: str | None
    task_id: str
    schedule_id: str | None = None
    executor: ExecutorName
    executor_profile_id: str | None = None
    instruction_source: str
    planned_start_at: datetime
    working_directory: str
    target_working_directory: str | None = None


class TaskRunInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    run_id: str | None = None
    task_id: str
    schedule_id: str | None = None
    planned_start_at: datetime
    occurrence_key: str | None = None
    schedule_type: ScheduleType | None = None
    execution_snapshot: ExecutionSnapshot


class MaterializedRun(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    run_id: str
    run_status: RunStatus
    execution_snapshot: ExecutionSnapshot


class ExecutorOutcome(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    terminal_status: RunStatus
    result_summary: str | None = None
    result_artifact_ref: str | None = None
    terminal_code: str | None = None
    failure_reason: str | None = None


class ExecutorPreflightResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    executor: ExecutorName
    status: ExecutorPreflightStatus
    code: str
    message: str
    details: dict[str, str | bool | None] = Field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.status == ExecutorPreflightStatus.AVAILABLE


class ProfileValidationInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    handoff_id: str
    executor: ExecutorName
    default_model: str | None = None
    reasoning_level: str | None = None


class ProfileValidationResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    ok: bool
    code: str
    message: str
    details: dict[str, ProfileValidationDetailValue] = Field(default_factory=dict)
