"""API schemas for the vertical task slice."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from vesperaflow_store.models import Run, Schedule, Task
from vesperaflow_store.repositories import TaskDetail


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class DataEnvelope(BaseModel):
    data: Any


class ListEnvelope(BaseModel):
    data: list[Any]
    meta: dict[str, int]


class ScheduleCreate(BaseModel):
    schedule_type: ScheduleType
    planned_at: datetime | None = None
    recurrence_rule: str | None = None
    recurrence_timezone: str | None = None


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    instruction_source: str = Field(min_length=1)
    target_working_directory: str = Field(min_length=1)
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
    planned_at: datetime


class VersionedCommand(BaseModel):
    version: int | None = None


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
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, run: Run) -> "RunResponse":
        return cls.model_validate(_model_dict(run))


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


class KanbanCardResponse(BaseModel):
    card_id: str
    task_id: str
    title: str
    kanban_column: str
    next_run_at: datetime | None
    latest_run_status: RunStatus | None
    result_summary: str | None


class KanbanBoardResponse(BaseModel):
    columns: dict[str, list[KanbanCardResponse]]


def bundle_response(
    task: Task, schedule: Schedule, run: Run | None
) -> TaskBundleResponse:
    return TaskBundleResponse(
        task=TaskResponse.from_model(task),
        schedule=ScheduleResponse.from_model(schedule),
        run=RunResponse.from_model(run) if run else None,
    )


def _model_dict(model: Any) -> dict[str, Any]:
    return {
        column.name: getattr(model, column.name) for column in model.__table__.columns
    }
