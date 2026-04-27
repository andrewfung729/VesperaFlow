"""API schemas for the vertical task slice."""

from collections.abc import Iterable
from datetime import datetime
from typing import cast

from pydantic import BaseModel, Field
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    OccurrenceEditScope,
    OccurrenceOverrideStatus,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from vesperaflow_store.models import OccurrenceOverride, Run, Schedule, Task
from vesperaflow_store.repositories import TaskDetail


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class DataEnvelope(BaseModel):
    data: object


class ListEnvelope(BaseModel):
    data: list[object]
    meta: dict[str, int]


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
    schedule: ScheduleCreate


class TaskUpdateRequest(BaseModel):
    version: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    instruction_source: str | None = Field(default=None, min_length=1)


class ScheduleUpdateRequest(BaseModel):
    version: int | None = None
    planned_at: datetime | None = None
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


class TaskResponse(BaseModel):
    task_id: str
    title: str
    instruction_source: str
    normalized_instruction: str | None
    target_working_directory: str | None
    execution_mode: ExecutionMode
    task_status: TaskStatus
    template_id: str | None
    executor: ExecutorName
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @classmethod
    def from_model(cls, task: Task) -> "TaskResponse":
        return cls.model_validate(_model_dict(task))


class ScheduleResponse(BaseModel):
    schedule_id: str
    task_id: str
    schedule_type: ScheduleType
    schedule_status: ScheduleStatus
    planned_at: datetime | None
    recurrence_rule: str | None
    recurrence_timezone: str | None
    next_run_at: datetime | None
    last_materialized_at: datetime | None
    external_schedule_ref: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, schedule: Schedule) -> "ScheduleResponse":
        return cls.model_validate(_model_dict(schedule))


class RunResponse(BaseModel):
    run_id: str
    task_id: str
    schedule_id: str | None
    run_status: RunStatus
    planned_start_at: datetime
    actual_start_at: datetime | None
    finished_at: datetime | None
    result_summary: str | None
    failure_reason: str | None
    external_execution_ref: str | None
    occurrence_key: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, run: Run) -> "RunResponse":
        return cls.model_validate(_model_dict(run))


class OccurrenceOverrideResponse(BaseModel):
    occurrence_override_id: str
    task_id: str
    schedule_id: str
    original_occurrence_at: datetime
    override_occurrence_at: datetime | None
    override_instruction_delta: str | None
    override_status: OccurrenceOverrideStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, override: OccurrenceOverride) -> "OccurrenceOverrideResponse":
        return cls.model_validate(_model_dict(override))


class TaskBundleResponse(BaseModel):
    task: TaskResponse
    schedule: ScheduleResponse
    run: RunResponse | None = None


class TaskDetailResponse(BaseModel):
    task: TaskResponse
    schedule: ScheduleResponse | None
    latest_run: RunResponse | None
    runs: list[RunResponse]

    @classmethod
    def from_detail(cls, detail: TaskDetail) -> "TaskDetailResponse":
        return cls(
            task=TaskResponse.from_model(detail.task),
            schedule=(
                ScheduleResponse.from_model(detail.schedule)
                if detail.schedule
                else None
            ),
            latest_run=RunResponse.from_model(detail.latest_run)
            if detail.latest_run
            else None,
            runs=[RunResponse.from_model(run) for run in detail.runs],
        )


def bundle_response(
    task: Task, schedule: Schedule, run: Run | None
) -> TaskBundleResponse:
    return TaskBundleResponse(
        task=TaskResponse.from_model(task),
        schedule=ScheduleResponse.from_model(schedule),
        run=RunResponse.from_model(run) if run else None,
    )


def _model_dict(model: object) -> dict[str, object]:
    table = cast(object, getattr(model, "__table__"))
    columns = cast(Iterable[object], getattr(table, "columns"))
    result: dict[str, object] = {}
    for column in columns:
        name = cast(str, getattr(column, "name"))
        result[name] = getattr(model, name)
    return result
