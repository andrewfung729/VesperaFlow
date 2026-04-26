"""View routes (kanban, history)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import ExecutionMode, RunStatus
from vesperaflow_store import repositories as repo

from ..dependencies import get_session
from ..schemas.tasks import DataEnvelope, ListEnvelope
from ..schemas.views import HistoryItemResponse, KanbanBoardResponse, KanbanCardResponse

router = APIRouter()


@router.get("/views/kanban")
async def get_kanban(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    board = await repo.get_one_time_kanban(session)
    response = KanbanBoardResponse(
        columns={
            column: [
                KanbanCardResponse(
                    card_id=detail.task.task_id,
                    task_id=detail.task.task_id,
                    title=detail.task.title,
                    kanban_column=column,
                    next_run_at=detail.schedule.next_run_at
                    if detail.schedule
                    else None,
                    latest_run_status=detail.latest_run.run_status
                    if detail.latest_run
                    else None,
                    result_summary=detail.latest_run.result_summary
                    if detail.latest_run
                    else None,
                )
                for detail in details
            ]
            for column, details in board.items()
        }
    )
    return DataEnvelope(data=response.model_dump())


@router.get("/views/history")
async def get_history(
    session: Annotated[AsyncSession, Depends(get_session)],
    status: RunStatus | None = None,
    execution_mode: ExecutionMode | None = None,
    finished_from: Annotated[
        datetime | None,
        Query(alias="from"),
    ] = None,
    finished_to: Annotated[
        datetime | None,
        Query(alias="to"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListEnvelope:
    history = await repo.list_history(
        session,
        status=status,
        execution_mode=execution_mode,
        finished_from=finished_from,
        finished_to=finished_to,
        limit=limit,
        offset=offset,
    )
    return ListEnvelope(
        data=[
            HistoryItemResponse.from_item(item).model_dump()
            for item in history.items
        ],
        meta={"total": history.total},
    )
