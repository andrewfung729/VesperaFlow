"""Task and one-time board routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import ExecutionMode, ScheduleType, TaskStatus
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import InvalidStateTransitionError

from ..dependencies import get_session
from ..schemas.tasks import (
    DataEnvelope,
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
from ._shared import observed_version, require_existing_absolute_directory

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
        template = None
        if payload.template_id is not None:
            template = await repo.get_template(session, payload.template_id)
            if template.archived_at is not None:
                raise InvalidStateTransitionError(
                    "archived templates cannot create tasks"
                )
        raw_target_working_directory = (
            payload.target_working_directory
            or (template.default_target_working_directory if template else None)
        )
        if raw_target_working_directory is None:
            raise ValueError("target_working_directory is required")
        target_working_directory = require_existing_absolute_directory(
            raw_target_working_directory
        )
        bundle = await repo.create_one_time_task(
            session,
            title=payload.title,
            instruction_source=payload.instruction_source,
            target_working_directory=target_working_directory,
            planned_at=payload.schedule.planned_at,
            template_id=payload.template_id,
            executor=payload.executor
            or (template.default_executor if template else None)
            or request.app.state.settings.default_executor,
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
    version = observed_version(payload.version, if_match)
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
    version = observed_version(payload.version, if_match)
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
    version = observed_version(payload.version, if_match)
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
