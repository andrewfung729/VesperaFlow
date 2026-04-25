"""Shared workflow and activity payload contracts.

All contracts use Pydantic v2 for runtime validation, serialization, and
version-conscious schema evolution across Temporal boundaries.
"""

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from .enums import ExecutorName, RunStatus


class ExecutionSnapshot(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    run_id: str
    task_id: str
    schedule_id: str | None = None
    executor: ExecutorName
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
    execution_snapshot: ExecutionSnapshot


class ExecutorOutcome(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    terminal_status: RunStatus
    result_summary: str | None = None
    result_artifact_ref: str | None = None
    terminal_code: str | None = None
    failure_reason: str | None = None
