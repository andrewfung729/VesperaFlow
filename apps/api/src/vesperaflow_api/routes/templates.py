"""Template routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import ExecutionMode, ExecutorName, ScheduleType
from vesperaflow_core.client_contracts import (
    TemplateCreateRequest,
    TemplateInstantiateRequest,
    TemplateUpdateRequest,
    VersionedCommand,
)
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import InvalidStateTransitionError
from vesperaflow_store.models import ExecutorProfile

from ..dependencies import get_scheduler, get_session
from ..schemas.tasks import (
    DataEnvelope,
    ListEnvelope,
    bundle_response,
)
from ..schemas.templates import TemplateResponse
from ..temporal_scheduler import TemporalScheduler
from ._shared import observed_version, optional_existing_absolute_directory

router = APIRouter()


@router.post("/templates", status_code=201)
async def create_template(
    payload: TemplateCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    schedule = payload.default_schedule_config
    default_target_working_directory = optional_existing_absolute_directory(
        payload.default_target_working_directory
    )
    async with session.begin():
        default_executor_profile = await _resolve_optional_template_profile(
            session,
            executor_profile_id=payload.default_executor_profile_id,
            executor=payload.default_executor,
        )
        template = await repo.create_template(
            session,
            name=payload.name,
            description=payload.description,
            instruction_source=payload.instruction_source,
            default_task_title=payload.default_task_title,
            default_target_working_directory=default_target_working_directory,
            default_execution_mode=payload.default_execution_mode,
            default_schedule_type=schedule.schedule_type,
            default_planned_at=schedule.planned_at,
            default_recurrence_rule=schedule.recurrence_rule,
            default_recurrence_timezone=schedule.recurrence_timezone,
            default_executor=(
                default_executor_profile.executor
                if default_executor_profile
                else payload.default_executor
            ),
            default_executor_profile_id=(
                default_executor_profile.profile_id
                if default_executor_profile
                else None
            ),
        )
    return DataEnvelope(data=TemplateResponse.from_model(template).model_dump())


@router.get("/templates")
async def list_templates(
    session: Annotated[AsyncSession, Depends(get_session)],
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListEnvelope:
    page = await repo.list_templates(
        session,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return ListEnvelope(
        data=[
            TemplateResponse.from_model(template).model_dump()
            for template in page.items
        ],
        meta={"total": page.total},
    )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    template = await repo.get_template(session, template_id)
    return DataEnvelope(data=TemplateResponse.from_model(template).model_dump())


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: str,
    payload: TemplateUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    schedule = payload.default_schedule_config
    payload_fields = payload.model_fields_set
    schedule_fields: set[str] = schedule.model_fields_set if schedule else set()
    default_target_working_directory = optional_existing_absolute_directory(
        payload.default_target_working_directory
    )
    should_update_executor_profile = (
        "default_executor_profile_id" in payload_fields
        or "default_executor" in payload_fields
    )
    async with session.begin():
        default_executor_profile = await _resolve_optional_template_profile(
            session,
            executor_profile_id=(
                payload.default_executor_profile_id
                if should_update_executor_profile
                else None
            ),
            executor=(
                payload.default_executor if should_update_executor_profile else None
            ),
        )
        template = await repo.update_template(
            session,
            template_id=template_id,
            version=version,
            name=payload.name,
            description=payload.description,
            set_description="description" in payload_fields,
            instruction_source=payload.instruction_source,
            default_task_title=payload.default_task_title,
            set_default_task_title="default_task_title" in payload_fields,
            default_target_working_directory=default_target_working_directory,
            set_default_target_working_directory=(
                "default_target_working_directory" in payload_fields
            ),
            default_execution_mode=payload.default_execution_mode,
            default_schedule_type=schedule.schedule_type if schedule else None,
            default_planned_at=schedule.planned_at if schedule else None,
            set_default_planned_at="planned_at" in schedule_fields,
            default_recurrence_rule=schedule.recurrence_rule if schedule else None,
            set_default_recurrence_rule="recurrence_rule" in schedule_fields,
            default_recurrence_timezone=schedule.recurrence_timezone
            if schedule
            else None,
            set_default_recurrence_timezone="recurrence_timezone" in schedule_fields,
            default_executor=(
                default_executor_profile.executor
                if default_executor_profile
                else payload.default_executor
            ),
            set_default_executor=should_update_executor_profile,
            default_executor_profile_id=(
                default_executor_profile.profile_id
                if default_executor_profile
                else payload.default_executor_profile_id
            ),
            set_default_executor_profile_id=should_update_executor_profile,
        )
    return DataEnvelope(data=TemplateResponse.from_model(template).model_dump())


@router.post("/templates/{template_id}/archive")
async def archive_template(
    template_id: str,
    payload: VersionedCommand,
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        template = await repo.archive_template(
            session,
            template_id=template_id,
            version=version,
        )
    return DataEnvelope(data=TemplateResponse.from_model(template).model_dump())


@router.post("/templates/{template_id}/instantiate", status_code=201)
async def instantiate_template(
    template_id: str,
    payload: TemplateInstantiateRequest,
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    if payload.execution_mode not in (None, ExecutionMode.ONE_TIME):
        raise RuntimeError("unsupported_operation: recurring tasks are not implemented")
    schedule = payload.schedule
    if schedule is not None and schedule.schedule_type is not ScheduleType.SINGLE_RUN:
        raise InvalidStateTransitionError(
            "template instantiation currently supports single-run schedules only"
        )
    target_working_directory = optional_existing_absolute_directory(
        payload.target_working_directory
    )
    async with session.begin():
        executor_profile = await _resolve_instantiation_profile(
            session,
            template_id=template_id,
            executor_profile_id=payload.executor_profile_id,
            executor=payload.executor,
        )
        bundle = await repo.instantiate_one_time_task_from_template(
            session,
            template_id=template_id,
            target_working_directory=target_working_directory,
            planned_at=schedule.planned_at if schedule else None,
            title=payload.title,
            instruction_source=payload.instruction_source,
            executor=executor_profile.executor,
            executor_profile_id=executor_profile.profile_id,
        )
        try:
            schedule_ref = await scheduler.create_one_time_schedule(
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


async def _resolve_optional_template_profile(
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


async def _resolve_instantiation_profile(
    session: AsyncSession,
    *,
    template_id: str,
    executor_profile_id: str | None,
    executor: ExecutorName | None,
) -> ExecutorProfile:
    if executor_profile_id is not None:
        profile = await repo.get_executor_profile(session, executor_profile_id)
        _require_usable_executor_profile(profile)
        if executor is not None and profile.executor != executor:
            raise ValueError("executor_profile_id does not match executor")
        return profile
    template = await repo.get_template(session, template_id)
    if template.default_executor_profile_id is not None and executor is None:
        profile = await repo.get_executor_profile(
            session,
            template.default_executor_profile_id,
        )
        _require_usable_executor_profile(profile)
        return profile
    return await repo.resolve_executor_profile(
        session,
        executor_profile_id=None,
        executor=_required_executor(executor or template.default_executor),
    )


def _required_executor(executor: ExecutorName | None) -> ExecutorName:
    if executor is None:
        raise ValueError("executor_profile_id or executor is required")
    return executor


def _require_usable_executor_profile(profile: ExecutorProfile) -> None:
    if profile.archived_at is not None:
        raise InvalidStateTransitionError("archived executor profiles cannot be used")
    if not profile.is_enabled:
        raise InvalidStateTransitionError("disabled executor profiles cannot be used")
