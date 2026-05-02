"""API schemas for view routes."""

from datetime import datetime

from pydantic import BaseModel
from vesperaflow_core import ExecutionMode, RunStatus, ScheduleStatus, TaskStatus
from vesperaflow_store.repositories import CalendarItem, HistoryItem, RecurringTodoItem


class KanbanCardResponse(BaseModel):
    card_id: str
    task_id: str
    title: str
    kanban_column: str
    next_run_at: datetime | None
    latest_run_status: RunStatus | None


class KanbanBoardResponse(BaseModel):
    columns: dict[str, list[KanbanCardResponse]]


class HistoryItemResponse(BaseModel):
    history_item_id: str
    run_id: str
    task_id: str
    title: str
    execution_mode: ExecutionMode
    run_status: RunStatus
    finished_at: datetime
    outcome_preview: str | None
    outcome_truncated: bool
    outcome_source: str | None

    @classmethod
    def from_item(cls, item: HistoryItem) -> "HistoryItemResponse":
        return cls(
            history_item_id=f"hist_{item.run_id}",
            run_id=item.run_id,
            task_id=item.task_id,
            title=item.title,
            execution_mode=item.execution_mode,
            run_status=item.run_status,
            finished_at=item.finished_at,
            outcome_preview=item.outcome_preview,
            outcome_truncated=item.outcome_truncated,
            outcome_source=item.outcome_source,
        )


class CalendarItemResponse(BaseModel):
    calendar_item_id: str
    task_id: str
    schedule_id: str
    title: str
    execution_mode: ExecutionMode
    occurrence_at: datetime
    original_occurrence_at: datetime | None
    state: TaskStatus
    is_occurrence_override: bool
    schedule_version: int

    @classmethod
    def from_item(cls, item: CalendarItem) -> "CalendarItemResponse":
        occurrence_key = item.original_occurrence_at or item.occurrence_at
        item_id = f"cal_{item.schedule.schedule_id}_{occurrence_key.isoformat()}"
        return cls(
            calendar_item_id=item_id,
            task_id=item.task.task_id,
            schedule_id=item.schedule.schedule_id,
            title=item.task.title,
            execution_mode=item.task.execution_mode,
            occurrence_at=item.occurrence_at,
            original_occurrence_at=item.original_occurrence_at,
            state=item.state,
            is_occurrence_override=item.occurrence_override is not None,
            schedule_version=item.schedule.version,
        )


class RecurringTodoItemResponse(BaseModel):
    item_id: str
    task_id: str
    title: str
    recurrence_rule: str
    recurrence_timezone: str
    next_run_at: datetime | None
    schedule_status: ScheduleStatus
    task_status: TaskStatus
    schedule_version: int
    latest_run_id: str | None
    latest_run_outcome: RunStatus | None
    latest_run_finished_at: datetime | None
    result_summary: str | None
    failure_reason: str | None

    @classmethod
    def from_item(cls, item: RecurringTodoItem) -> "RecurringTodoItemResponse":
        if item.schedule.recurrence_rule is None:
            raise ValueError("recurring todo item requires recurrence_rule")
        if item.schedule.recurrence_timezone is None:
            raise ValueError("recurring todo item requires recurrence_timezone")
        return cls(
            item_id=f"todo_{item.task.task_id}",
            task_id=item.task.task_id,
            title=item.task.title,
            recurrence_rule=item.schedule.recurrence_rule,
            recurrence_timezone=item.schedule.recurrence_timezone,
            next_run_at=item.schedule.next_run_at,
            schedule_status=item.schedule.schedule_status,
            task_status=item.task.task_status,
            schedule_version=item.schedule.version,
            latest_run_id=item.latest_run.run_id if item.latest_run else None,
            latest_run_outcome=item.latest_run.run_status if item.latest_run else None,
            latest_run_finished_at=(
                item.latest_run.finished_at if item.latest_run else None
            ),
            result_summary=item.latest_run.result_summary if item.latest_run else None,
            failure_reason=item.latest_run.failure_reason if item.latest_run else None,
        )
