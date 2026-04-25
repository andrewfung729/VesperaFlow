"""Task and one-time board routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import ExecutionMode, ScheduleType, TaskStatus
from vesperaflow_store import repositories as repo

from ..dependencies import get_session
from ..schemas.tasks import (
    DataEnvelope,
    KanbanBoardResponse,
    KanbanCardResponse,
    ListEnvelope,
    RunResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskResponse,
    TaskUpdateRequest,
    VersionedCommand,
    bundle_response,
)

router = APIRouter()


@router.post("/tasks", status_code=201)
async def create_task(
    payload: TaskCreateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    if payload.execution_mode is not ExecutionMode.ONE_TIME:
        raise RuntimeError("unsupported_operation: recurring tasks are not implemented")
    if (
        payload.schedule.schedule_type is not ScheduleType.SINGLE_RUN
        or payload.schedule.planned_at is None
    ):
        raise ValueError(
            "one-time tasks require schedule_type single_run and planned_at"
        )
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title=payload.title,
            instruction_source=payload.instruction_source,
            planned_at=payload.schedule.planned_at,
            template_id=payload.template_id,
            executor=payload.executor or request.app.state.settings.default_executor,
        )
        try:
            schedule_ref = await request.app.state.scheduler.create_one_time_schedule(
                task=bundle.task,
                schedule=bundle.schedule,
                run=bundle.run,
            )
        except Exception as exc:
            raise RuntimeError(
                "execution_unavailable: Temporal schedule creation failed"
            ) from exc
        await repo.set_schedule_external_ref(
            session,
            schedule_id=bundle.schedule.schedule_id,
            external_schedule_ref=schedule_ref,
        )
    return DataEnvelope(
        data=bundle_response(bundle.task, bundle.schedule, bundle.run).model_dump()
    )


@router.get("/tasks")
async def list_tasks(
    session: Annotated[AsyncSession, Depends(get_session)],
    execution_mode: ExecutionMode | None = None,
    status: TaskStatus | None = None,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> ListEnvelope:
    tasks = await repo.list_tasks(
        session,
        execution_mode=execution_mode,
        status=status,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    data = []
    for task in tasks:
        data.append(TaskResponse.from_model(task).model_dump())
    return ListEnvelope(data=data, meta={"total": len(tasks)})


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    task = await repo.get_task(session, task_id)
    return DataEnvelope(data=TaskResponse.from_model(task).model_dump())


@router.get("/tasks/{task_id}/detail")
async def get_task_detail(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    detail = await repo.get_task_detail(session, task_id)
    return DataEnvelope(data=TaskDetailResponse.from_detail(detail).model_dump())


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = _observed_version(payload.version, if_match)
    async with session.begin():
        task = await repo.update_task(
            session,
            task_id=task_id,
            version=version,
            title=payload.title,
            instruction_source=payload.instruction_source,
        )
    return DataEnvelope(data=TaskResponse.from_model(task).model_dump())


@router.get("/tasks/{task_id}/schedule")
async def get_schedule(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    schedule = await repo.get_schedule_for_task(session, task_id)
    return DataEnvelope(data=ScheduleResponse.from_model(schedule).model_dump())


@router.patch("/tasks/{task_id}/schedule")
async def update_schedule(
    task_id: str,
    payload: ScheduleUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = _observed_version(payload.version, if_match)
    async with session.begin():
        bundle = await repo.reschedule_one_time_task(
            session,
            task_id=task_id,
            version=version,
            planned_at=payload.planned_at,
        )
        schedule_ref = await request.app.state.scheduler.replace_one_time_schedule(
            task=bundle.task,
            schedule=bundle.schedule,
            run=bundle.run,
        )
        await repo.set_schedule_external_ref(
            session,
            schedule_id=bundle.schedule.schedule_id,
            external_schedule_ref=schedule_ref,
        )
    return DataEnvelope(
        data=bundle_response(bundle.task, bundle.schedule, bundle.run).model_dump()
    )


@router.post("/tasks/{task_id}/schedule/cancel")
async def cancel_schedule(
    task_id: str,
    payload: VersionedCommand,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = _observed_version(payload.version, if_match)
    async with session.begin():
        bundle = await repo.cancel_one_time_task(
            session,
            task_id=task_id,
            version=version,
        )
        await request.app.state.scheduler.delete_schedule(bundle.schedule.schedule_id)
    return DataEnvelope(
        data=bundle_response(bundle.task, bundle.schedule, bundle.run).model_dump()
    )


@router.get("/tasks/{task_id}/runs")
async def list_runs(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListEnvelope:
    runs = await repo.list_runs_for_task(session, task_id)
    return ListEnvelope(
        data=[RunResponse.from_model(run).model_dump() for run in runs],
        meta={"total": len(runs)},
    )


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


def _observed_version(body_version: int | None, if_match: str | None) -> int:
    if body_version is not None:
        return body_version
    if if_match is None:
        raise ValueError("version is required")
    return int(if_match.strip('"'))
