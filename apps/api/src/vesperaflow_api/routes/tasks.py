"""Task and one-time board routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import (
    ExecutionMode,
    OccurrenceEditScope,
    RunStatus,
    ScheduleType,
    TaskStatus,
)
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import InvalidStateTransitionError
from vesperaflow_store.models import OccurrenceOverride

from ..dependencies import get_scheduler, get_session, get_settings
from ..schemas.tasks import (
    DataEnvelope,
    ListEnvelope,
    OccurrenceCancelRequest,
    OccurrenceOverrideResponse,
    OccurrenceUpdateRequest,
    RunPreviewResponse,
    RunReaderDetailResponse,
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
from ..settings import ApiSettings
from ..temporal_scheduler import TemporalScheduler
from ._shared import observed_version, require_existing_absolute_directory

router = APIRouter()


@router.post("/tasks", status_code=201)
async def create_task(
    payload: TaskCreateRequest,
    settings: Annotated[ApiSettings, Depends(get_settings)],
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    async with session.begin():
        template = None
        if payload.template_id is not None:
            template = await repo.get_template(session, payload.template_id)
            if template.archived_at is not None:
                raise InvalidStateTransitionError(
                    "archived templates cannot create tasks"
                )
        raw_target_working_directory = payload.target_working_directory or (
            template.default_target_working_directory if template else None
        )
        if raw_target_working_directory is None:
            raise ValueError("target_working_directory is required")
        target_working_directory = require_existing_absolute_directory(
            raw_target_working_directory
        )
        executor = (
            payload.executor
            or (template.default_executor if template else None)
            or settings.default_executor
        )
        if payload.execution_mode is ExecutionMode.ONE_TIME:
            if (
                payload.schedule.schedule_type is not ScheduleType.SINGLE_RUN
                or payload.schedule.planned_at is None
            ):
                raise ValueError(
                    "one-time tasks require schedule_type single_run and planned_at"
                )
            bundle = await repo.create_one_time_task(
                session,
                title=payload.title,
                instruction_source=payload.instruction_source,
                target_working_directory=target_working_directory,
                planned_at=payload.schedule.planned_at,
                template_id=payload.template_id,
                executor=executor,
            )
            create_schedule = scheduler.create_one_time_schedule
        else:
            if (
                payload.schedule.schedule_type is not ScheduleType.RECURRING_RULE
                or payload.schedule.recurrence_rule is None
                or payload.schedule.recurrence_timezone is None
            ):
                raise ValueError(
                    "recurring tasks require schedule_type "
                    + "recurring_rule, recurrence_rule, and recurrence_timezone"
                )
            bundle = await repo.create_recurring_task(
                session,
                title=payload.title,
                instruction_source=payload.instruction_source,
                target_working_directory=target_working_directory,
                recurrence_rule=payload.schedule.recurrence_rule,
                recurrence_timezone=payload.schedule.recurrence_timezone,
                template_id=payload.template_id,
                executor=executor,
            )
            create_schedule = scheduler.create_recurring_schedule
        try:
            schedule_ref = await create_schedule(
                task=bundle.task,
                schedule=bundle.schedule,
                run=bundle.run,
            )
        except Exception as exc:
            raise RuntimeError(
                "execution_unavailable: Temporal schedule creation failed"
            ) from exc
        _ = await repo.set_schedule_external_ref(
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
    data: list[object] = []
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
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        current_schedule = await repo.get_schedule_for_task(session, task_id)
        if current_schedule.schedule_type is ScheduleType.SINGLE_RUN:
            if payload.planned_at is None:
                raise ValueError("one-time schedule updates require planned_at")
            bundle = await repo.reschedule_one_time_task(
                session,
                task_id=task_id,
                version=version,
                planned_at=payload.planned_at,
            )
            schedule_ref = await scheduler.replace_one_time_schedule(
                task=bundle.task,
                schedule=bundle.schedule,
                run=bundle.run,
            )
        else:
            recurrence_rule = (
                payload.recurrence_rule or current_schedule.recurrence_rule
            )
            recurrence_timezone = (
                payload.recurrence_timezone or current_schedule.recurrence_timezone
            )
            target_working_directory = (
                require_existing_absolute_directory(payload.target_working_directory)
                if payload.target_working_directory is not None
                else None
            )
            if recurrence_rule is None or recurrence_timezone is None:
                raise ValueError(
                    "recurring schedule updates require "
                    + "recurrence_rule and recurrence_timezone"
                )
            bundle = await repo.update_recurring_task_schedule(
                session,
                task_id=task_id,
                version=version,
                recurrence_rule=recurrence_rule,
                recurrence_timezone=recurrence_timezone,
                title=payload.title,
                instruction_source=payload.instruction_source,
                target_working_directory=target_working_directory,
                executor=payload.executor,
            )
            schedule_ref = await scheduler.replace_recurring_schedule(
                task=bundle.task,
                schedule=bundle.schedule,
            )
        _ = await repo.set_schedule_external_ref(
            session,
            schedule_id=bundle.schedule.schedule_id,
            external_schedule_ref=schedule_ref,
        )
    return DataEnvelope(
        data=bundle_response(bundle.task, bundle.schedule, bundle.run).model_dump()
    )


@router.post("/tasks/{task_id}/schedule/pause")
async def pause_schedule(
    task_id: str,
    payload: VersionedCommand,
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        bundle = await repo.pause_recurring_task(
            session,
            task_id=task_id,
            version=version,
        )
        await scheduler.pause_schedule(bundle.schedule.schedule_id)
    return DataEnvelope(
        data=bundle_response(bundle.task, bundle.schedule, bundle.run).model_dump()
    )


@router.post("/tasks/{task_id}/schedule/resume")
async def resume_schedule(
    task_id: str,
    payload: VersionedCommand,
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        bundle = await repo.resume_recurring_task(
            session,
            task_id=task_id,
            version=version,
        )
        await scheduler.resume_schedule(bundle.schedule.schedule_id)
    return DataEnvelope(
        data=bundle_response(bundle.task, bundle.schedule, bundle.run).model_dump()
    )


@router.post("/tasks/{task_id}/schedule/cancel")
async def cancel_schedule(
    task_id: str,
    payload: VersionedCommand,
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        current_schedule = await repo.get_schedule_for_task(session, task_id)
        if current_schedule.schedule_type is ScheduleType.SINGLE_RUN:
            bundle = await repo.cancel_one_time_task(
                session,
                task_id=task_id,
                version=version,
            )
        else:
            bundle = await repo.cancel_recurring_task(
                session,
                task_id=task_id,
                version=version,
            )
        await scheduler.delete_schedule(bundle.schedule.schedule_id)
    return DataEnvelope(
        data=bundle_response(bundle.task, bundle.schedule, bundle.run).model_dump()
    )


@router.post("/tasks/{task_id}/occurrences/update")
async def update_occurrence(
    task_id: str,
    payload: OccurrenceUpdateRequest,
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        result = await repo.update_recurring_occurrence_scope(
            session,
            task_id=task_id,
            version=version,
            original_occurrence_at=payload.original_occurrence_at,
            scope=payload.scope,
            planned_at=payload.planned_at,
            instruction_source=payload.instruction_source,
            recurrence_rule=payload.recurrence_rule,
            recurrence_timezone=payload.recurrence_timezone,
        )
        if isinstance(result, OccurrenceOverride):
            data = OccurrenceOverrideResponse.from_model(result).model_dump()
        else:
            schedule_ref = await scheduler.replace_recurring_schedule(
                task=result.task,
                schedule=result.schedule,
            )
            _ = await repo.set_schedule_external_ref(
                session,
                schedule_id=result.schedule.schedule_id,
                external_schedule_ref=schedule_ref,
            )
            data = bundle_response(
                result.task,
                result.schedule,
                result.run,
            ).model_dump()
    return DataEnvelope(data=data)


@router.post("/tasks/{task_id}/occurrences/cancel")
async def cancel_occurrence(
    task_id: str,
    payload: OccurrenceCancelRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    if payload.scope is not OccurrenceEditScope.THIS_OCCURRENCE_ONLY:
        raise InvalidStateTransitionError(
            "only this_occurrence_only cancel is supported for occurrences"
        )
    version = observed_version(payload.version, if_match)
    async with session.begin():
        override = await repo.cancel_occurrence(
            session,
            task_id=task_id,
            version=version,
            original_occurrence_at=payload.original_occurrence_at,
        )
    return DataEnvelope(
        data=OccurrenceOverrideResponse.from_model(override).model_dump()
    )


@router.post("/tasks/{task_id}/run-now")
async def run_task_now(
    task_id: str,
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    async with session.begin():
        task = await repo.get_task(session, task_id)
        if task.execution_mode == ExecutionMode.ONE_TIME:
            bundle = await repo.run_one_time_now(session, task_id=task_id)
            if bundle.run is None:
                raise ValueError("run-now requires an existing run")
            try:
                workflow_ref = await scheduler.run_one_time_now(
                    task=bundle.task,
                    schedule=bundle.schedule,
                    run=bundle.run,
                )
            except Exception as exc:
                raise RuntimeError(
                    "execution_unavailable: Temporal workflow start failed"
                ) from exc
        elif task.execution_mode == ExecutionMode.RECURRING:
            bundle = await repo.run_recurring_now(session, task_id=task_id)
            if bundle.run is None:
                raise ValueError("run-now requires an existing run")
            try:
                workflow_ref = await scheduler.run_recurring_now(
                    task=bundle.task,
                    schedule=bundle.schedule,
                    run=bundle.run,
                )
            except Exception as exc:
                raise RuntimeError(
                    "execution_unavailable: Temporal workflow start failed"
                ) from exc
        else:
            raise InvalidStateTransitionError(
                "run-now is only supported for one-time and recurring tasks"
            )
        _ = await repo.set_schedule_external_ref(
            session,
            schedule_id=bundle.schedule.schedule_id,
            external_schedule_ref=workflow_ref,
        )
    return DataEnvelope(data=RunResponse.from_model(bundle.run).model_dump())


@router.get("/tasks/{task_id}/runs")
async def list_runs(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    status: RunStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListEnvelope:
    runs = await repo.list_run_previews_for_task(
        session,
        task_id=task_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ListEnvelope(
        data=[RunPreviewResponse.from_preview(run).model_dump() for run in runs.items],
        meta={"total": runs.total},
    )


@router.get("/tasks/{task_id}/runs/{run_id}/reader")
async def get_run_reader_detail(
    task_id: str,
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    context = await repo.get_run_reader_context(
        session,
        task_id=task_id,
        run_id=run_id,
    )
    return DataEnvelope(data=RunReaderDetailResponse.from_context(context).model_dump())
