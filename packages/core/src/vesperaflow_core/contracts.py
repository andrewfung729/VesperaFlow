"""Shared workflow and activity payload contracts.

These are intentionally stdlib-only for the initial scaffold. Introduce Pydantic
here only after the dependency policy is settled, and keep Temporal payloads
version-conscious.
"""

from dataclasses import dataclass
from datetime import datetime

from .enums import ExecutorName, RunStatus


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    run_id: str
    task_id: str
    schedule_id: str | None
    executor: ExecutorName
    instruction_source: str
    planned_start_at: datetime
    working_directory: str


@dataclass(frozen=True, slots=True)
class TaskRunInput:
    run_id: str | None
    task_id: str
    schedule_id: str | None
    planned_start_at: datetime
    occurrence_key: str | None
    execution_snapshot: ExecutionSnapshot


@dataclass(frozen=True, slots=True)
class ExecutorOutcome:
    terminal_status: RunStatus
    result_summary: str | None = None
    result_artifact_ref: str | None = None
    terminal_code: str | None = None
    failure_reason: str | None = None
