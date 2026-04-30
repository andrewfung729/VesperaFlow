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
from vesperaflow_store.models import OccurrenceOverride, Run, RunEvent, Schedule, Task
from vesperaflow_store.repositories import RunPreview, RunReaderContext, TaskDetail


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
    title: str | None = Field(default=None, min_length=1, max_length=240)
    instruction_source: str | None = Field(default=None, min_length=1)
    target_working_directory: str | None = Field(default=None, min_length=1)
    executor: ExecutorName | None = None
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


class RunEventResponse(BaseModel):
    run_event_id: str
    run_id: str
    task_id: str
    schedule_id: str | None
    event_type: str
    severity: str
    message: str
    details: dict[str, object]
    temporal_workflow_id: str | None
    temporal_workflow_run_id: str | None
    activity_type: str | None
    activity_attempt: int | None
    created_at: datetime

    @classmethod
    def from_model(cls, event: RunEvent) -> "RunEventResponse":
        return cls.model_validate(_model_dict(event))


class RunPreviewResponse(BaseModel):
    run_id: str
    task_id: str
    schedule_id: str | None
    run_status: RunStatus
    planned_start_at: datetime
    actual_start_at: datetime | None
    finished_at: datetime | None
    occurrence_key: str | None
    created_at: datetime
    updated_at: datetime
    outcome_preview: str | None
    outcome_truncated: bool
    outcome_source: str | None

    @classmethod
    def from_preview(cls, preview: RunPreview) -> "RunPreviewResponse":
        return cls(
            run_id=preview.run_id,
            task_id=preview.task_id,
            schedule_id=preview.schedule_id,
            run_status=preview.run_status,
            planned_start_at=preview.planned_start_at,
            actual_start_at=preview.actual_start_at,
            finished_at=preview.finished_at,
            occurrence_key=preview.occurrence_key,
            created_at=preview.created_at,
            updated_at=preview.updated_at,
            outcome_preview=preview.outcome_preview,
            outcome_truncated=preview.outcome_truncated,
            outcome_source=preview.outcome_source,
        )


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
        )


class RunReaderDetailResponse(BaseModel):
    task: TaskResponse
    schedule: ScheduleResponse | None
    run: RunResponse
    previous_run_id: str | None
    next_run_id: str | None

    @classmethod
    def from_context(cls, context: RunReaderContext) -> "RunReaderDetailResponse":
        return cls(
            task=TaskResponse.from_model(context.task),
            schedule=(
                ScheduleResponse.from_model(context.schedule)
                if context.schedule
                else None
            ),
            run=RunResponse.from_model(context.run),
            previous_run_id=context.previous_run_id,
            next_run_id=context.next_run_id,
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
