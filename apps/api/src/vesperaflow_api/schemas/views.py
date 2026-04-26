"""API schemas for view routes."""

from datetime import datetime

from pydantic import BaseModel
from vesperaflow_core import ExecutionMode, RunStatus
from vesperaflow_store.repositories import HistoryItem


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


class HistoryItemResponse(BaseModel):
    history_item_id: str
    run_id: str
    task_id: str
    title: str
    execution_mode: ExecutionMode
    run_status: RunStatus
    finished_at: datetime
    result_summary: str | None
    failure_reason: str | None

    @classmethod
    def from_item(cls, item: HistoryItem) -> "HistoryItemResponse":
        if item.run.finished_at is None:
            raise ValueError("history item requires finished_at")
        return cls(
            history_item_id=f"hist_{item.run.run_id}",
            run_id=item.run.run_id,
            task_id=item.task.task_id,
            title=item.task.title,
            execution_mode=item.task.execution_mode,
            run_status=item.run.run_status,
            finished_at=item.run.finished_at,
            result_summary=item.run.result_summary,
            failure_reason=item.run.failure_reason,
        )
