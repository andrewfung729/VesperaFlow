"""Task and one-time board routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    OccurrenceEditScope,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from vesperaflow_core.client_contracts import (
    OccurrenceCancelRequest,
    OccurrenceUpdateRequest,
    ScheduleUpdateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
    VersionedCommand,
)
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import InvalidStateTransitionError
from vesperaflow_store.models import ExecutorProfile, OccurrenceOverride, Run

from ..dependencies import get_scheduler, get_session
from ..schemas.tasks import (
    DataEnvelope,
    ListEnvelope,
    OccurrenceOverrideResponse,
    RunPreviewResponse,
    RunReaderDetailResponse,
    RunResponse,
    ScheduleResponse,
    TaskDetailResponse,
    TaskResponse,
    bundle_response,
)
from ..temporal_scheduler import TemporalScheduler
from ._shared import observed_version, require_existing_absolute_directory

router = APIRouter()


@router.post("/tasks", status_code=201)
async def create_task(
    payload: TaskCreateRequest,
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
        executor_profile = await _resolve_task_executor_profile(
            session,
            executor_profile_id=payload.executor_profile_id
            or (
                template.default_executor_profile_id
                if template and payload.executor is None
                else None
            ),
            executor=payload.executor
            or (template.default_executor if template else None),
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
                executor=executor_profile.executor,
                executor_profile_id=executor_profile.profile_id,
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
                executor=executor_profile.executor,
                executor_profile_id=executor_profile.profile_id,
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
            executor_profile = await _resolve_optional_task_executor_profile(
                session,
                executor_profile_id=payload.executor_profile_id,
                executor=payload.executor,
            )
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
                executor=executor_profile.executor if executor_profile else None,
                executor_profile_id=(
                    executor_profile.profile_id if executor_profile else None
                ),
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


async def _resolve_task_executor_profile(
    session: AsyncSession,
    *,
    executor_profile_id: str | None,
    executor: ExecutorName | None,
) -> ExecutorProfile:
    if executor_profile_id is None:
        if executor is None:
            raise ValueError("executor_profile_id or executor is required")
        return await repo.resolve_executor_profile(
            session,
            executor_profile_id=None,
            executor=executor,
        )
    profile = await repo.get_executor_profile(session, executor_profile_id)
    _require_usable_executor_profile(profile)
    if executor is not None and profile.executor != executor:
        raise ValueError("executor_profile_id does not match executor")
    return profile


async def _resolve_optional_task_executor_profile(
    session: AsyncSession,
    *,
    executor_profile_id: str | None,
    executor: ExecutorName | None,
) -> ExecutorProfile | None:
    if executor_profile_id is None and executor is None:
        return None
    if executor_profile_id is None:
        if executor is None:
            return None
        return await repo.resolve_executor_profile(
            session,
            executor_profile_id=None,
            executor=executor,
        )
    profile = await repo.get_executor_profile(session, executor_profile_id)
    _require_usable_executor_profile(profile)
    if executor is not None and profile.executor != executor:
        raise ValueError("executor_profile_id does not match executor")
    return profile


def _require_usable_executor_profile(profile: ExecutorProfile) -> None:
    if profile.archived_at is not None:
        raise InvalidStateTransitionError("archived executor profiles cannot be used")
    if not profile.is_enabled:
        raise InvalidStateTransitionError("disabled executor profiles cannot be used")


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


@router.post("/tasks/{task_id}/archive")
async def archive_task(
    task_id: str,
    payload: VersionedCommand,
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        task = await repo.archive_task(
            session,
            task_id=task_id,
            version=version,
        )
        schedule = await repo.get_schedule_for_task(session, task_id)
    await scheduler.delete_schedule(schedule.schedule_id)
    return DataEnvelope(data=TaskResponse.from_model(task).model_dump())


@router.post("/tasks/{task_id}/unarchive")
async def unarchive_task(
    task_id: str,
    payload: VersionedCommand,
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        bundle = await repo.unarchive_task(
            session,
            task_id=task_id,
            version=version,
        )

    schedule_ref: str | None = None
    if bundle.task.execution_mode == ExecutionMode.ONE_TIME:
        if (
            bundle.schedule.schedule_status == ScheduleStatus.ACTIVE
            and bundle.run is not None
        ):
            schedule_ref = await scheduler.create_one_time_schedule(
                task=bundle.task,
                schedule=bundle.schedule,
                run=bundle.run,
            )
    elif bundle.task.execution_mode == ExecutionMode.RECURRING:
        if bundle.schedule.schedule_status in {
            ScheduleStatus.ACTIVE,
            ScheduleStatus.PAUSED,
        }:
            schedule_ref = await scheduler.create_recurring_schedule(
                task=bundle.task,
                schedule=bundle.schedule,
            )

    if schedule_ref is not None:
        async with session.begin():
            _ = await repo.set_schedule_external_ref(
                session,
                schedule_id=bundle.schedule.schedule_id,
                external_schedule_ref=schedule_ref,
            )

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
    run: Run | None = None
    async with session.begin():
        task = await repo.get_task(session, task_id)
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
        if isinstance(result, OccurrenceOverride) and payload.planned_at is not None:
            if result.rescheduled_run_id is None:
                raise ValueError("time override requires rescheduled_run_id")
            run = await repo.get_run(session, result.rescheduled_run_id)
    if isinstance(result, OccurrenceOverride):
        if payload.planned_at is not None:
            if result.external_schedule_ref is not None:
                await scheduler.delete_schedule(
                    f"ovr-{result.occurrence_override_id}"
                )
            assert run is not None
            schedule_ref = await scheduler.create_occurrence_override_schedule(
                task=task,
                run=run,
                override_id=result.occurrence_override_id,
                planned_at=payload.planned_at,
            )
            async with session.begin():
                result.external_schedule_ref = schedule_ref
        elif result.external_schedule_ref is not None:
            await scheduler.delete_schedule(
                f"ovr-{result.occurrence_override_id}"
            )
            async with session.begin():
                result.external_schedule_ref = None
        data = OccurrenceOverrideResponse.from_model(result).model_dump()
    else:
        schedule_ref = await scheduler.replace_recurring_schedule(
            task=result.task,
            schedule=result.schedule,
        )
        async with session.begin():
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
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
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
    if override.external_schedule_ref is not None:
        await scheduler.delete_schedule(
            f"ovr-{override.occurrence_override_id}"
        )
        async with session.begin():
            override.external_schedule_ref = None
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


@router.get("/tasks/{task_id}/runs/{run_id}")
async def get_run_detail(
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
