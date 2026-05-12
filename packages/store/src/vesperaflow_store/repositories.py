"""Repository functions used by the API and Temporal activities."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from vesperaflow_core import (
    ExecutionMode,
    ExecutionSnapshot,
    ExecutorName,
    MaterializedRun,
    OccurrenceEditScope,
    OccurrenceOverrideStatus,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
    derive_task_status,
    next_occurrence_after,
    occurrence_key_for_datetime,
    require_future_datetime,
    require_recurring_schedule_consistency,
    require_run_transition,
    require_template_schedule_defaults,
    to_utc,
    utc_now,
)

from .errors import ConflictError, InvalidStateTransitionError, NotFoundError
from .models import (
    ExecutorProfile,
    OccurrenceOverride,
    Run,
    RunEvent,
    Schedule,
    Task,
    Template,
)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


@dataclass(frozen=True, slots=True)
class TaskBundle:
    task: Task
    schedule: Schedule
    run: Run | None


@dataclass(frozen=True, slots=True)
class TaskDetail:
    task: Task
    schedule: Schedule | None
    latest_run: Run | None


@dataclass(frozen=True, slots=True)
class HistoryItem:
    run_id: str
    task_id: str
    title: str
    execution_mode: ExecutionMode
    run_status: RunStatus
    finished_at: datetime
    outcome_preview: str | None
    outcome_truncated: bool
    outcome_source: str | None


@dataclass(frozen=True, slots=True)
class RunPreview:
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


@dataclass(frozen=True, slots=True)
class RunPreviewPage:
    items: list[RunPreview]
    total: int


@dataclass(frozen=True, slots=True)
class RunEventPage:
    items: list[RunEvent]
    total: int


@dataclass(frozen=True, slots=True)
class RunReaderContext:
    task: Task
    schedule: Schedule | None
    run: Run
    previous_run_id: str | None
    next_run_id: str | None


@dataclass(frozen=True, slots=True)
class HistoryPage:
    items: list[HistoryItem]
    total: int


@dataclass(frozen=True, slots=True)
class RecurringTodoItem:
    task: Task
    schedule: Schedule
    latest_run: Run | None


@dataclass(frozen=True, slots=True)
class RecurringTodoPage:
    items: list[RecurringTodoItem]
    total: int


@dataclass(frozen=True, slots=True)
class CalendarItem:
    task: Task
    schedule: Schedule
    occurrence_at: datetime
    state: TaskStatus
    original_occurrence_at: datetime | None
    occurrence_override: OccurrenceOverride | None


@dataclass(frozen=True, slots=True)
class CalendarPage:
    items: list[CalendarItem]
    total: int


@dataclass(frozen=True, slots=True)
class TemplatePage:
    items: list[Template]
    total: int


@dataclass(frozen=True, slots=True)
class ExecutorProfilePage:
    items: list[ExecutorProfile]
    total: int


DEFAULT_EXECUTOR_PROFILE_NAMES: dict[ExecutorName, str] = {
    ExecutorName.CLAUDE_CODE: "Claude Code",
    ExecutorName.CODEX: "Codex",
    ExecutorName.OPENCODE: "OpenCode",
    ExecutorName.KIMI_CODE: "Kimi Code",
    ExecutorName.DEBUG_PRINTER: "Debug Printer",
}


RUN_OUTCOME_PREVIEW_LIMIT = 80


async def ensure_default_executor_profiles(session: AsyncSession) -> None:
    for executor, name in DEFAULT_EXECUTOR_PROFILE_NAMES.items():
        existing = await _default_executor_profile(session, executor)
        if existing is not None:
            continue
        now = utc_now()
        session.add(
            ExecutorProfile(
                profile_id=new_id("xpr"),
                name=name,
                executor=executor,
                is_enabled=True,
                is_default=True,
                default_model=None,
                env={},
                secret_env={},
                version=1,
                created_at=now,
                updated_at=now,
                archived_at=None,
            )
        )
    await session.flush()


async def create_executor_profile(
    session: AsyncSession,
    *,
    name: str,
    executor: ExecutorName,
    is_enabled: bool = True,
    is_default: bool = False,
    default_model: str | None = None,
    env: dict[str, str] | None = None,
    secret_env: dict[str, str] | None = None,
) -> ExecutorProfile:
    if is_default:
        await _clear_default_executor_profile(session, executor)
    now = utc_now()
    profile = ExecutorProfile(
        profile_id=new_id("xpr"),
        name=name,
        executor=executor,
        is_enabled=is_enabled,
        is_default=is_default,
        default_model=default_model,
        env=dict(env or {}),
        secret_env=dict(secret_env or {}),
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    session.add(profile)
    await session.flush()
    return profile


async def get_executor_profile(
    session: AsyncSession, profile_id: str
) -> ExecutorProfile:
    profile = await session.get(ExecutorProfile, profile_id)
    if profile is None:
        raise NotFoundError(f"executor profile not found: {profile_id}")
    return profile


async def list_executor_profiles(
    session: AsyncSession,
    *,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> ExecutorProfilePage:
    filters: list[ColumnElement[bool]] = []
    if not include_archived:
        filters.append(ExecutorProfile.archived_at.is_(None))

    total_statement = select(func.count()).select_from(ExecutorProfile).where(*filters)
    total = (await session.execute(total_statement)).scalar_one()
    statement = (
        select(ExecutorProfile)
        .where(*filters)
        .order_by(
            ExecutorProfile.executor.asc(),
            ExecutorProfile.is_default.desc(),
            ExecutorProfile.name.asc(),
            ExecutorProfile.profile_id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return ExecutorProfilePage(
        items=list(await session.scalars(statement)), total=total
    )


async def update_executor_profile(
    session: AsyncSession,
    *,
    profile_id: str,
    version: int,
    name: str | None = None,
    is_enabled: bool | None = None,
    is_default: bool | None = None,
    default_model: str | None = None,
    set_default_model: bool = False,
    env: dict[str, str] | None = None,
    set_env: bool = False,
    secret_env: dict[str, str | None] | None = None,
) -> ExecutorProfile:
    profile = await get_executor_profile(session, profile_id)
    _require_version(profile.version, version)
    if profile.archived_at is not None:
        raise InvalidStateTransitionError("archived executor profiles cannot be edited")

    if is_default is True and not profile.is_default:
        await _clear_default_executor_profile(session, profile.executor)
    if name is not None:
        profile.name = name
    if is_enabled is not None:
        profile.is_enabled = is_enabled
    if is_default is not None:
        profile.is_default = is_default
    if set_default_model or default_model is not None:
        profile.default_model = default_model
    if set_env or env is not None:
        profile.env = dict(env or {})
    if secret_env is not None:
        updated_secret_env = dict(profile.secret_env or {})
        for key, value in secret_env.items():
            if value is None:
                _ = updated_secret_env.pop(key, None)
            else:
                updated_secret_env[key] = value
        profile.secret_env = updated_secret_env

    profile.version += 1
    profile.updated_at = utc_now()
    await session.flush()
    return profile


async def archive_executor_profile(
    session: AsyncSession,
    *,
    profile_id: str,
    version: int,
) -> ExecutorProfile:
    profile = await get_executor_profile(session, profile_id)
    _require_version(profile.version, version)
    if profile.archived_at is None:
        now = utc_now()
        profile.archived_at = now
        profile.is_enabled = False
        profile.is_default = False
        profile.version += 1
        profile.updated_at = now
    await session.flush()
    return profile


async def resolve_executor_profile(
    session: AsyncSession,
    *,
    executor_profile_id: str | None,
    executor: ExecutorName,
) -> ExecutorProfile:
    if executor_profile_id is not None:
        profile = await get_executor_profile(session, executor_profile_id)
        if profile.executor != executor:
            raise ValueError("executor_profile_id does not match executor")
    else:
        await ensure_default_executor_profiles(session)
        profile = await _default_executor_profile(session, executor)
        if profile is None:
            raise ValueError(f"default executor profile not found for {executor.value}")
    if profile.archived_at is not None:
        raise InvalidStateTransitionError("archived executor profiles cannot be used")
    if not profile.is_enabled:
        raise InvalidStateTransitionError("disabled executor profiles cannot be used")
    return profile


async def create_one_time_task(
    session: AsyncSession,
    *,
    title: str,
    instruction_source: str,
    target_working_directory: str,
    planned_at: datetime,
    template_id: str | None = None,
    executor: ExecutorName = ExecutorName.CLAUDE_CODE,
    executor_profile_id: str | None = None,
) -> TaskBundle:
    planned_at_utc = to_utc(planned_at)
    require_future_datetime(planned_at_utc, field_name="planned_at")
    now = utc_now()

    task = Task(
        task_id=new_id("task"),
        title=title,
        instruction_source=instruction_source,
        normalized_instruction=None,
        target_working_directory=target_working_directory,
        execution_mode=ExecutionMode.ONE_TIME,
        task_status=TaskStatus.SCHEDULED,
        template_id=template_id,
        executor=executor,
        executor_profile_id=executor_profile_id,
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    schedule = Schedule(
        schedule_id=new_id("sch"),
        task_id=task.task_id,
        schedule_type=ScheduleType.SINGLE_RUN,
        schedule_status=ScheduleStatus.ACTIVE,
        planned_at=planned_at_utc,
        recurrence_rule=None,
        recurrence_timezone=None,
        next_run_at=planned_at_utc,
        last_materialized_at=None,
        external_schedule_ref=None,
        version=1,
        created_at=now,
        updated_at=now,
    )
    run = Run(
        run_id=new_id("run"),
        task_id=task.task_id,
        schedule_id=schedule.schedule_id,
        run_status=RunStatus.PLANNED,
        planned_start_at=planned_at_utc,
        actual_start_at=None,
        finished_at=None,
        instruction_source_snapshot=instruction_source,
        result_summary=None,
        failure_reason=None,
        external_execution_ref=None,
        occurrence_key=None,
        created_at=now,
        updated_at=now,
    )
    session.add_all([task, schedule, run])
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=run)


async def create_recurring_task(
    session: AsyncSession,
    *,
    title: str,
    instruction_source: str,
    target_working_directory: str,
    recurrence_rule: str,
    recurrence_timezone: str,
    template_id: str | None = None,
    executor: ExecutorName = ExecutorName.CLAUDE_CODE,
    executor_profile_id: str | None = None,
) -> TaskBundle:
    _require_recurring_schedule(
        schedule_type=ScheduleType.RECURRING_RULE,
        recurrence_rule=recurrence_rule,
        recurrence_timezone=recurrence_timezone,
    )
    now = utc_now()
    next_run_at = next_occurrence_after(
        recurrence_rule=recurrence_rule,
        recurrence_timezone=recurrence_timezone,
        after=now,
    )
    task = Task(
        task_id=new_id("task"),
        title=title,
        instruction_source=instruction_source,
        normalized_instruction=None,
        target_working_directory=target_working_directory,
        execution_mode=ExecutionMode.RECURRING,
        task_status=TaskStatus.SCHEDULED,
        template_id=template_id,
        executor=executor,
        executor_profile_id=executor_profile_id,
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    schedule = Schedule(
        schedule_id=new_id("sch"),
        task_id=task.task_id,
        schedule_type=ScheduleType.RECURRING_RULE,
        schedule_status=ScheduleStatus.ACTIVE,
        planned_at=None,
        recurrence_rule=recurrence_rule,
        recurrence_timezone=recurrence_timezone,
        next_run_at=next_run_at,
        last_materialized_at=None,
        external_schedule_ref=None,
        version=1,
        created_at=now,
        updated_at=now,
    )
    session.add_all([task, schedule])
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=None)


async def create_template(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    instruction_source: str,
    default_task_title: str | None,
    default_target_working_directory: str | None,
    default_execution_mode: ExecutionMode,
    default_schedule_type: ScheduleType,
    default_planned_at: datetime | None = None,
    default_recurrence_rule: str | None = None,
    default_recurrence_timezone: str | None = None,
    default_executor: ExecutorName | None = None,
    default_executor_profile_id: str | None = None,
) -> Template:
    _require_template_defaults(
        default_execution_mode=default_execution_mode,
        default_schedule_type=default_schedule_type,
        default_recurrence_rule=default_recurrence_rule,
        default_recurrence_timezone=default_recurrence_timezone,
    )
    now = utc_now()
    template = Template(
        template_id=new_id("tpl"),
        name=name,
        description=description,
        instruction_source=instruction_source,
        default_task_title=default_task_title,
        default_target_working_directory=default_target_working_directory,
        default_execution_mode=default_execution_mode,
        default_schedule_type=default_schedule_type,
        default_planned_at=to_utc(default_planned_at) if default_planned_at else None,
        default_recurrence_rule=default_recurrence_rule,
        default_recurrence_timezone=default_recurrence_timezone,
        default_executor=default_executor,
        default_executor_profile_id=default_executor_profile_id,
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    session.add(template)
    await session.flush()
    return template


async def get_template(session: AsyncSession, template_id: str) -> Template:
    template = await session.get(Template, template_id)
    if template is None:
        raise NotFoundError(f"template not found: {template_id}")
    return template


async def list_templates(
    session: AsyncSession,
    *,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> TemplatePage:
    filters: list[ColumnElement[bool]] = []
    if not include_archived:
        filters.append(Template.archived_at.is_(None))

    total_statement = select(func.count()).select_from(Template).where(*filters)
    total = (await session.execute(total_statement)).scalar_one()
    statement = (
        select(Template)
        .where(*filters)
        .order_by(Template.created_at.desc(), Template.template_id.desc())
        .limit(limit)
        .offset(offset)
    )
    return TemplatePage(items=list(await session.scalars(statement)), total=total)


async def update_template(
    session: AsyncSession,
    *,
    template_id: str,
    version: int,
    name: str | None = None,
    description: str | None = None,
    set_description: bool = False,
    instruction_source: str | None = None,
    default_task_title: str | None = None,
    set_default_task_title: bool = False,
    default_target_working_directory: str | None = None,
    set_default_target_working_directory: bool = False,
    default_execution_mode: ExecutionMode | None = None,
    default_schedule_type: ScheduleType | None = None,
    default_planned_at: datetime | None = None,
    set_default_planned_at: bool = False,
    default_recurrence_rule: str | None = None,
    set_default_recurrence_rule: bool = False,
    default_recurrence_timezone: str | None = None,
    set_default_recurrence_timezone: bool = False,
    default_executor: ExecutorName | None = None,
    set_default_executor: bool = False,
    default_executor_profile_id: str | None = None,
    set_default_executor_profile_id: bool = False,
) -> Template:
    template = await get_template(session, template_id)
    _require_version(template.version, version)
    if template.archived_at is not None:
        raise InvalidStateTransitionError("archived templates cannot be edited")

    next_execution_mode = default_execution_mode or template.default_execution_mode
    next_schedule_type = default_schedule_type or template.default_schedule_type
    next_recurrence_rule = (
        default_recurrence_rule
        if set_default_recurrence_rule or default_recurrence_rule is not None
        else template.default_recurrence_rule
    )
    next_recurrence_timezone = (
        default_recurrence_timezone
        if set_default_recurrence_timezone or default_recurrence_timezone is not None
        else template.default_recurrence_timezone
    )
    _require_template_defaults(
        default_execution_mode=next_execution_mode,
        default_schedule_type=next_schedule_type,
        default_recurrence_rule=next_recurrence_rule,
        default_recurrence_timezone=next_recurrence_timezone,
    )

    if name is not None:
        template.name = name
    if set_description or description is not None:
        template.description = description
    if instruction_source is not None:
        template.instruction_source = instruction_source
    if set_default_task_title or default_task_title is not None:
        template.default_task_title = default_task_title
    if (
        set_default_target_working_directory
        or default_target_working_directory is not None
    ):
        template.default_target_working_directory = default_target_working_directory
    if default_execution_mode is not None:
        template.default_execution_mode = default_execution_mode
    if default_schedule_type is not None:
        template.default_schedule_type = default_schedule_type
    if set_default_planned_at or default_planned_at is not None:
        template.default_planned_at = (
            to_utc(default_planned_at) if default_planned_at else None
        )
    if set_default_recurrence_rule or default_recurrence_rule is not None:
        template.default_recurrence_rule = default_recurrence_rule
    if set_default_recurrence_timezone or default_recurrence_timezone is not None:
        template.default_recurrence_timezone = default_recurrence_timezone
    if set_default_executor or default_executor is not None:
        template.default_executor = default_executor
    if set_default_executor_profile_id or default_executor_profile_id is not None:
        template.default_executor_profile_id = default_executor_profile_id

    template.version += 1
    template.updated_at = utc_now()
    await session.flush()
    return template


async def archive_template(
    session: AsyncSession,
    *,
    template_id: str,
    version: int,
) -> Template:
    template = await get_template(session, template_id)
    _require_version(template.version, version)
    if template.archived_at is None:
        now = utc_now()
        template.archived_at = now
        template.updated_at = now
        template.version += 1
    await session.flush()
    return template


async def instantiate_one_time_task_from_template(
    session: AsyncSession,
    *,
    template_id: str,
    target_working_directory: str | None,
    planned_at: datetime | None,
    title: str | None = None,
    instruction_source: str | None = None,
    executor: ExecutorName | None = None,
    executor_profile_id: str | None = None,
) -> TaskBundle:
    template = await get_template(session, template_id)
    if template.archived_at is not None:
        raise InvalidStateTransitionError("archived templates cannot be instantiated")
    if template.default_execution_mode is not ExecutionMode.ONE_TIME:
        raise InvalidStateTransitionError(
            "recurring task instantiation is not implemented"
        )

    resolved_planned_at = planned_at or template.default_planned_at
    if resolved_planned_at is None:
        raise ValueError("one-time template instantiation requires planned_at")
    resolved_target_working_directory = (
        target_working_directory or template.default_target_working_directory
    )
    if resolved_target_working_directory is None:
        raise ValueError("template instantiation requires target_working_directory")
    resolved_executor = executor or template.default_executor
    if resolved_executor is None:
        raise ValueError(
            "template instantiation requires executor_profile_id or executor"
        )
    resolved_executor_profile_id = (
        executor_profile_id or template.default_executor_profile_id
    )
    return await create_one_time_task(
        session,
        title=title or template.default_task_title or template.name,
        instruction_source=instruction_source or template.instruction_source,
        target_working_directory=resolved_target_working_directory,
        planned_at=resolved_planned_at,
        template_id=template.template_id,
        executor=resolved_executor,
        executor_profile_id=resolved_executor_profile_id,
    )


async def set_schedule_external_ref(
    session: AsyncSession,
    *,
    schedule_id: str,
    external_schedule_ref: str,
) -> Schedule:
    schedule = await get_schedule(session, schedule_id)
    schedule.external_schedule_ref = external_schedule_ref
    schedule.updated_at = utc_now()
    await session.flush()
    return schedule


async def get_task(session: AsyncSession, task_id: str) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise NotFoundError(f"task not found: {task_id}")
    return task


async def get_schedule(session: AsyncSession, schedule_id: str) -> Schedule:
    schedule = await session.get(Schedule, schedule_id)
    if schedule is None:
        raise NotFoundError(f"schedule not found: {schedule_id}")
    return schedule


async def get_run(session: AsyncSession, run_id: str) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise NotFoundError(f"run not found: {run_id}")
    return run


async def record_run_event(
    session: AsyncSession,
    *,
    run_id: str,
    event_type: str,
    message: str,
    severity: str = "info",
    details: dict[str, object] | None = None,
    temporal_workflow_id: str | None = None,
    temporal_workflow_run_id: str | None = None,
    activity_type: str | None = None,
    activity_attempt: int | None = None,
) -> RunEvent:
    run = await get_run(session, run_id)
    event = RunEvent(
        run_event_id=new_id("evt"),
        run_id=run.run_id,
        task_id=run.task_id,
        schedule_id=run.schedule_id,
        event_type=event_type,
        severity=severity,
        message=message,
        details=details or {},
        temporal_workflow_id=temporal_workflow_id,
        temporal_workflow_run_id=temporal_workflow_run_id,
        activity_type=activity_type,
        activity_attempt=activity_attempt,
        created_at=utc_now(),
    )
    session.add(event)
    await session.flush()
    return event


async def list_run_events(
    session: AsyncSession,
    *,
    run_id: str,
    limit: int = 100,
    offset: int = 0,
) -> RunEventPage:
    _ = await get_run(session, run_id)
    filters: list[ColumnElement[bool]] = [RunEvent.run_id == run_id]
    total_statement = select(func.count()).select_from(RunEvent).where(*filters)
    total = (await session.execute(total_statement)).scalar_one()
    statement = (
        select(RunEvent)
        .where(*filters)
        .order_by(RunEvent.created_at.asc(), RunEvent.run_event_id.asc())
        .limit(limit)
        .offset(offset)
    )
    return RunEventPage(
        items=list(await session.scalars(statement)),
        total=total,
    )


async def get_schedule_for_task(session: AsyncSession, task_id: str) -> Schedule:
    statement = select(Schedule).where(Schedule.task_id == task_id)
    schedule = (await session.scalars(statement)).one_or_none()
    if schedule is None:
        raise NotFoundError(f"schedule not found for task: {task_id}")
    return schedule


async def _get_schedule_for_task_or_none(
    session: AsyncSession, task_id: str
) -> Schedule | None:
    statement = select(Schedule).where(Schedule.task_id == task_id)
    return (await session.scalars(statement)).one_or_none()


async def get_latest_run(session: AsyncSession, task_id: str) -> Run | None:
    statement = (
        select(Run)
        .where(Run.task_id == task_id)
        .order_by(Run.created_at.desc(), Run.run_id.desc())
        .limit(1)
    )
    return (await session.scalars(statement)).one_or_none()


async def list_run_previews_for_task(
    session: AsyncSession,
    *,
    task_id: str,
    status: RunStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> RunPreviewPage:
    _ = await get_task(session, task_id)
    filters: list[ColumnElement[bool]] = [Run.task_id == task_id]
    if status is not None:
        filters.append(Run.run_status == status)

    total_statement = select(func.count()).select_from(Run).where(*filters)
    total = (await session.execute(total_statement)).scalar_one()

    statement = (
        select(Run)
        .where(*filters)
        .order_by(Run.created_at.desc(), Run.run_id.desc())
        .limit(limit)
        .offset(offset)
    )
    runs = (await session.scalars(statement)).all()
    return RunPreviewPage(
        items=[_to_run_preview(run) for run in runs],
        total=total,
    )


async def get_run_reader_context(
    session: AsyncSession,
    *,
    task_id: str,
    run_id: str,
) -> RunReaderContext:
    run = await get_run(session, run_id)
    if run.task_id != task_id:
        raise NotFoundError(f"run not found for task: {run_id}")
    task = await get_task(session, task_id)
    schedule = await _get_schedule_for_task_or_none(session, task_id)

    previous_statement = (
        select(Run.run_id)
        .where(
            Run.task_id == task_id,
            (
                (Run.created_at > run.created_at)
                | ((Run.created_at == run.created_at) & (Run.run_id > run.run_id))
            ),
        )
        .order_by(Run.created_at.asc(), Run.run_id.asc())
        .limit(1)
    )
    next_statement = (
        select(Run.run_id)
        .where(
            Run.task_id == task_id,
            (
                (Run.created_at < run.created_at)
                | ((Run.created_at == run.created_at) & (Run.run_id < run.run_id))
            ),
        )
        .order_by(Run.created_at.desc(), Run.run_id.desc())
        .limit(1)
    )
    previous_run_id = (await session.execute(previous_statement)).scalar_one_or_none()
    next_run_id = (await session.execute(next_statement)).scalar_one_or_none()
    return RunReaderContext(
        task=task,
        schedule=schedule,
        run=run,
        previous_run_id=previous_run_id,
        next_run_id=next_run_id,
    )


async def list_history(
    session: AsyncSession,
    *,
    status: RunStatus | None = None,
    execution_mode: ExecutionMode | None = None,
    finished_from: datetime | None = None,
    finished_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> HistoryPage:
    history_statuses = {RunStatus.COMPLETED, RunStatus.FAILED}
    if status is not None:
        if status not in history_statuses:
            return HistoryPage(items=[], total=0)
        history_statuses = {status}

    filters: list[ColumnElement[bool]] = [
        Run.run_status.in_(history_statuses),
        Run.finished_at.is_not(None),
    ]
    if execution_mode is not None:
        filters.append(Task.execution_mode == execution_mode)
    if finished_from is not None:
        filters.append(Run.finished_at >= to_utc(finished_from))
    if finished_to is not None:
        filters.append(Run.finished_at <= to_utc(finished_to))

    total_statement = select(func.count()).select_from(Run).join(Task).where(*filters)
    total = (await session.execute(total_statement)).scalar_one()

    statement = (
        select(Run, Task)
        .join(Task)
        .where(*filters)
        .order_by(Run.finished_at.desc(), Run.run_id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows: list[tuple[Run, Task]] = list((await session.execute(statement)).tuples())
    items: list[HistoryItem] = []
    for run, task in rows:
        if run.finished_at is None:
            continue
        outcome_preview, outcome_truncated, outcome_source = run_outcome_preview_values(
            run
        )
        items.append(
            HistoryItem(
                run_id=run.run_id,
                task_id=run.task_id,
                title=task.title,
                execution_mode=task.execution_mode,
                run_status=run.run_status,
                finished_at=run.finished_at,
                outcome_preview=outcome_preview,
                outcome_truncated=outcome_truncated,
                outcome_source=outcome_source,
            )
        )
    return HistoryPage(
        items=items,
        total=total,
    )


async def list_recurring_todo(
    session: AsyncSession,
    *,
    status: ScheduleStatus | None = None,
    include_paused: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> RecurringTodoPage:
    requested_statuses = _recurring_todo_statuses(
        status=status,
        include_paused=include_paused,
    )
    if not requested_statuses:
        return RecurringTodoPage(items=[], total=0)

    rows: list[tuple[Task, Schedule]] = []
    if ScheduleStatus.ACTIVE in requested_statuses:
        rows.extend(
            await _list_recurring_todo_rows(
                session,
                status=ScheduleStatus.ACTIVE,
                order_by_next_run=True,
            )
        )
    if ScheduleStatus.PAUSED in requested_statuses:
        rows.extend(
            await _list_recurring_todo_rows(
                session,
                status=ScheduleStatus.PAUSED,
                order_by_next_run=False,
            )
        )

    paged_rows = rows[offset : offset + limit]
    latest_runs = await _latest_runs_by_task_id(
        session,
        task_ids=[task.task_id for task, _ in paged_rows],
    )
    return RecurringTodoPage(
        items=[
            RecurringTodoItem(
                task=task,
                schedule=schedule,
                latest_run=latest_runs.get(task.task_id),
            )
            for task, schedule in paged_rows
        ],
        total=len(rows),
    )


async def list_calendar_items(
    session: AsyncSession,
    *,
    window_from: datetime,
    window_to: datetime,
    include_completed: bool = False,
    limit: int = 500,
    offset: int = 0,
) -> CalendarPage:
    window_start = to_utc(window_from)
    window_end = to_utc(window_to)
    if window_start >= window_end:
        raise ValueError("calendar from must be before to")

    items: list[CalendarItem] = []
    items.extend(
        await _one_time_calendar_items(
            session,
            window_start=window_start,
            window_end=window_end,
            include_completed=include_completed,
        )
    )
    items.extend(
        await _recurring_calendar_items(
            session,
            window_start=window_start,
            window_end=window_end,
        )
    )
    items.sort(
        key=lambda item: (
            item.occurrence_at,
            item.task.title.lower(),
            item.task.task_id,
        )
    )
    return CalendarPage(items=items[offset : offset + limit], total=len(items))


async def upsert_occurrence_override(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
    original_occurrence_at: datetime,
    planned_at: datetime | None = None,
    instruction_source: str | None = None,
) -> OccurrenceOverride:
    task, schedule = await _get_active_recurring_task_and_schedule(
        session,
        task_id=task_id,
        version=version,
        action="edited",
    )
    original_at_utc = to_utc(original_occurrence_at).replace(microsecond=0)
    _require_projected_occurrence(schedule, original_at_utc)
    await _require_occurrence_not_started(
        session,
        schedule_id=schedule.schedule_id,
        original_occurrence_at=original_at_utc,
    )
    if planned_at is None and instruction_source is None:
        raise ValueError("occurrence update requires planned_at or instruction_source")

    override_at_utc = (
        to_utc(planned_at).replace(microsecond=0) if planned_at is not None else None
    )
    if override_at_utc is not None:
        require_future_datetime(override_at_utc, field_name="planned_at")
        if override_at_utc < original_at_utc:
            raise ValueError("planned_at cannot be earlier than original_occurrence_at")

    override = await _get_occurrence_override(
        session,
        schedule_id=schedule.schedule_id,
        original_occurrence_at=original_at_utc,
    )
    now = utc_now()
    if override is None:
        override = OccurrenceOverride(
            occurrence_override_id=new_id("ovr"),
            task_id=task.task_id,
            schedule_id=schedule.schedule_id,
            original_occurrence_at=original_at_utc,
            override_occurrence_at=override_at_utc,
            override_instruction_delta=instruction_source,
            override_status=OccurrenceOverrideStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add(override)
    else:
        if planned_at is not None:
            override.override_occurrence_at = override_at_utc
        if instruction_source is not None:
            override.override_instruction_delta = instruction_source
        override.override_status = OccurrenceOverrideStatus.ACTIVE
        override.updated_at = now

    if override_at_utc is not None:
        effective_instruction = (
            override.override_instruction_delta or task.instruction_source
        )
        if override.rescheduled_run_id is not None:
            rescheduled_run = await get_run(session, override.rescheduled_run_id)
            rescheduled_run.planned_start_at = override_at_utc
            rescheduled_run.instruction_source_snapshot = effective_instruction
            rescheduled_run.updated_at = now
        else:
            rescheduled_run = Run(
                run_id=new_id("run"),
                task_id=task.task_id,
                schedule_id=schedule.schedule_id,
                run_status=RunStatus.PLANNED,
                planned_start_at=override_at_utc,
                actual_start_at=None,
                finished_at=None,
                instruction_source_snapshot=effective_instruction,
                result_summary=None,
                failure_reason=None,
                external_execution_ref=None,
                occurrence_key=occurrence_key_for_datetime(override_at_utc),
                created_at=now,
                updated_at=now,
            )
            session.add(rescheduled_run)
            override.rescheduled_run_id = rescheduled_run.run_id
    else:
        if override.rescheduled_run_id is not None:
            rescheduled_run = await get_run(session, override.rescheduled_run_id)
            rescheduled_run.run_status = RunStatus.CANCELED
            rescheduled_run.finished_at = now
            rescheduled_run.updated_at = now
            override.rescheduled_run_id = None

    schedule.version += 1
    schedule.updated_at = now
    task.version += 1
    task.updated_at = now
    await session.flush()
    return override


async def cancel_occurrence(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
    original_occurrence_at: datetime,
) -> OccurrenceOverride:
    task, schedule = await _get_active_recurring_task_and_schedule(
        session,
        task_id=task_id,
        version=version,
        action="canceled",
    )
    original_at_utc = to_utc(original_occurrence_at).replace(microsecond=0)
    _require_projected_occurrence(schedule, original_at_utc)
    await _require_occurrence_not_started(
        session,
        schedule_id=schedule.schedule_id,
        original_occurrence_at=original_at_utc,
    )
    override = await _get_occurrence_override(
        session,
        schedule_id=schedule.schedule_id,
        original_occurrence_at=original_at_utc,
    )
    now = utc_now()
    if override is None:
        override = OccurrenceOverride(
            occurrence_override_id=new_id("ovr"),
            task_id=task.task_id,
            schedule_id=schedule.schedule_id,
            original_occurrence_at=original_at_utc,
            override_occurrence_at=None,
            override_instruction_delta=None,
            override_status=OccurrenceOverrideStatus.CANCELED,
            created_at=now,
            updated_at=now,
        )
        session.add(override)
    else:
        override.override_status = OccurrenceOverrideStatus.CANCELED
        override.updated_at = now
        if override.rescheduled_run_id is not None:
            rescheduled_run = await get_run(session, override.rescheduled_run_id)
            rescheduled_run.run_status = RunStatus.CANCELED
            rescheduled_run.finished_at = now
            rescheduled_run.updated_at = now
    schedule.version += 1
    schedule.updated_at = now
    task.version += 1
    task.updated_at = now
    await session.flush()
    return override


async def update_recurring_occurrence_scope(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
    original_occurrence_at: datetime,
    scope: OccurrenceEditScope,
    planned_at: datetime | None = None,
    instruction_source: str | None = None,
    recurrence_rule: str | None = None,
    recurrence_timezone: str | None = None,
) -> TaskBundle | OccurrenceOverride:
    if scope is OccurrenceEditScope.THIS_OCCURRENCE_ONLY:
        return await upsert_occurrence_override(
            session,
            task_id=task_id,
            version=version,
            original_occurrence_at=original_occurrence_at,
            planned_at=planned_at,
            instruction_source=instruction_source,
        )
    if scope is not OccurrenceEditScope.THIS_AND_FUTURE:
        raise InvalidStateTransitionError("unsupported recurring occurrence scope")  # pyright: ignore[reportUnreachable]

    current_schedule = await get_schedule_for_task(session, task_id)
    _require_projected_occurrence(current_schedule, to_utc(original_occurrence_at))
    if (
        recurrence_rule is None
        and recurrence_timezone is None
        and instruction_source is None
    ):
        raise ValueError(
            "this_and_future requires recurrence_rule, "
            + "recurrence_timezone, or instruction_source"
        )
    if instruction_source is not None:
        _ = await update_task(
            session,
            task_id=task_id,
            version=(await get_task(session, task_id)).version,
            instruction_source=instruction_source,
        )
    return await update_recurring_task_schedule(
        session,
        task_id=task_id,
        version=version,
        recurrence_rule=recurrence_rule or current_schedule.recurrence_rule or "",
        recurrence_timezone=(
            recurrence_timezone or current_schedule.recurrence_timezone or ""
        ),
    )


async def get_task_detail(session: AsyncSession, task_id: str) -> TaskDetail:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    latest_run = await get_latest_run(session, task_id)
    return TaskDetail(task=task, schedule=schedule, latest_run=latest_run)


async def list_tasks(
    session: AsyncSession,
    *,
    execution_mode: ExecutionMode | None = None,
    status: TaskStatus | None = None,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Task]:
    statement: Select[tuple[Task]] = select(Task).order_by(Task.created_at.desc())
    if execution_mode is not None:
        statement = statement.where(Task.execution_mode == execution_mode)
    if status is not None:
        statement = statement.where(Task.task_status == status)
    if not include_archived:
        statement = statement.where(Task.archived_at.is_(None))
    statement = statement.limit(limit).offset(offset)
    return list(await session.scalars(statement))


async def update_task(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
    title: str | None = None,
    instruction_source: str | None = None,
) -> Task:
    task = await get_task(session, task_id)
    _require_version(task.version, version)
    if task.archived_at is not None or task.task_status is TaskStatus.RUNNING:
        raise InvalidStateTransitionError("task cannot be edited in its current state")
    if task.task_status is TaskStatus.COMPLETED:
        raise InvalidStateTransitionError("completed tasks cannot be edited")
    if title is not None:
        task.title = title
    if instruction_source is not None:
        task.instruction_source = instruction_source
    task.version += 1
    task.updated_at = utc_now()
    await session.flush()
    return task


async def archive_task(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
) -> Task:
    task = await get_task(session, task_id)
    _require_version(task.version, version)
    if task.task_status is TaskStatus.RUNNING:
        raise InvalidStateTransitionError("running tasks cannot be archived")
    if task.archived_at is None:
        task.archived_at = utc_now()
        await _recompute_task_status(session, task)
    await session.flush()
    return task


async def unarchive_task(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    _require_version(task.version, version)
    if task.archived_at is None:
        raise InvalidStateTransitionError("task is not archived")
    task.archived_at = None
    latest_run = await get_latest_run(session, task_id)
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=latest_run)


async def reschedule_one_time_task(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
    planned_at: datetime,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    run = await _get_planned_run_for_schedule(session, schedule.schedule_id)
    _require_version(schedule.version, version)
    if task.execution_mode is not ExecutionMode.ONE_TIME:
        raise InvalidStateTransitionError("only one-time schedules can be rescheduled")
    if schedule.schedule_status is not ScheduleStatus.ACTIVE:
        raise InvalidStateTransitionError("only active schedules can be rescheduled")
    if run.run_status is not RunStatus.PLANNED:
        raise InvalidStateTransitionError("only planned runs can be rescheduled")

    planned_at_utc = to_utc(planned_at)
    require_future_datetime(planned_at_utc, field_name="planned_at")
    now = utc_now()
    schedule.planned_at = planned_at_utc
    schedule.next_run_at = planned_at_utc
    schedule.version += 1
    schedule.updated_at = now
    run.planned_start_at = planned_at_utc
    run.updated_at = now
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=run)


async def cancel_one_time_task(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    run = await _get_planned_run_for_schedule(session, schedule.schedule_id)
    _require_version(schedule.version, version)
    if task.execution_mode is not ExecutionMode.ONE_TIME:
        raise InvalidStateTransitionError("only one-time schedules can be canceled")
    if schedule.schedule_status is not ScheduleStatus.ACTIVE:
        raise InvalidStateTransitionError("only active schedules can be canceled")
    if run.run_status is not RunStatus.PLANNED:
        raise InvalidStateTransitionError("only planned runs can be canceled")

    now = utc_now()
    schedule.schedule_status = ScheduleStatus.CANCELED
    schedule.next_run_at = None
    schedule.version += 1
    schedule.updated_at = now
    run.run_status = RunStatus.CANCELED
    run.finished_at = now
    run.updated_at = now
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=run)


async def run_one_time_now(
    session: AsyncSession,
    *,
    task_id: str,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    if task.execution_mode is not ExecutionMode.ONE_TIME:
        raise InvalidStateTransitionError("only one-time tasks can be run now")
    if schedule.schedule_status is not ScheduleStatus.ACTIVE:
        raise InvalidStateTransitionError("only active schedules can be run now")
    run = await get_latest_run(session, task_id)
    if run is None or run.run_status is not RunStatus.PLANNED:
        raise InvalidStateTransitionError("only planned runs can be run now")

    now = utc_now()
    schedule.schedule_status = ScheduleStatus.COMPLETED
    schedule.next_run_at = None
    schedule.version += 1
    schedule.updated_at = now
    run.planned_start_at = now
    run.updated_at = now
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=run)


async def run_recurring_now(
    session: AsyncSession,
    *,
    task_id: str,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    if task.execution_mode is not ExecutionMode.RECURRING:
        raise InvalidStateTransitionError("only recurring tasks can be run now")
    if schedule.schedule_status is not ScheduleStatus.ACTIVE:
        raise InvalidStateTransitionError("only active schedules can be run now")

    now = utc_now()
    occurrence_key = occurrence_key_for_datetime(now)
    existing = await _get_run_for_occurrence(
        session,
        schedule_id=schedule.schedule_id,
        occurrence_key=occurrence_key,
    )
    if existing is not None:
        run = existing
    else:
        run = Run(
            run_id=new_id("run"),
            task_id=task.task_id,
            schedule_id=schedule.schedule_id,
            run_status=RunStatus.PLANNED,
            planned_start_at=now,
            actual_start_at=None,
            finished_at=None,
            instruction_source_snapshot=task.instruction_source,
            result_summary=None,
            failure_reason=None,
            external_execution_ref=None,
            occurrence_key=occurrence_key,
            created_at=now,
            updated_at=now,
        )
        session.add(run)

    run.planned_start_at = now
    run.updated_at = now
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(
        task=task,
        schedule=schedule,
        run=run,
    )


async def update_recurring_task_schedule(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
    recurrence_rule: str,
    recurrence_timezone: str,
    title: str | None = None,
    instruction_source: str | None = None,
    target_working_directory: str | None = None,
    executor: ExecutorName | None = None,
    executor_profile_id: str | None = None,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    _require_version(schedule.version, version)
    _require_active_recurring_task(task, schedule, action="updated")
    _require_recurring_schedule(
        schedule_type=ScheduleType.RECURRING_RULE,
        recurrence_rule=recurrence_rule,
        recurrence_timezone=recurrence_timezone,
    )

    now = utc_now()
    if title is not None:
        task.title = title
    if instruction_source is not None:
        task.instruction_source = instruction_source
    if target_working_directory is not None:
        task.target_working_directory = target_working_directory
    if executor is not None:
        task.executor = executor
    if executor_profile_id is not None:
        task.executor_profile_id = executor_profile_id
    schedule.recurrence_rule = recurrence_rule
    schedule.recurrence_timezone = recurrence_timezone
    schedule.next_run_at = (
        next_occurrence_after(
            recurrence_rule=recurrence_rule,
            recurrence_timezone=recurrence_timezone,
            after=now,
        )
        if schedule.schedule_status is ScheduleStatus.ACTIVE
        else None
    )
    schedule.version += 1
    schedule.updated_at = now
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=None)


async def pause_recurring_task(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    _require_version(schedule.version, version)
    _require_active_recurring_task(task, schedule, action="paused")
    if schedule.schedule_status is not ScheduleStatus.ACTIVE:
        raise InvalidStateTransitionError(
            "only active recurring schedules can be paused"
        )

    schedule.schedule_status = ScheduleStatus.PAUSED
    schedule.next_run_at = None
    schedule.version += 1
    schedule.updated_at = utc_now()
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=None)


async def resume_recurring_task(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    _require_version(schedule.version, version)
    if task.execution_mode is not ExecutionMode.RECURRING:
        raise InvalidStateTransitionError("only recurring schedules can be resumed")
    if schedule.schedule_status is not ScheduleStatus.PAUSED:
        raise InvalidStateTransitionError(
            "only paused recurring schedules can be resumed"
        )
    if schedule.recurrence_rule is None or schedule.recurrence_timezone is None:
        raise InvalidStateTransitionError("recurring schedule is missing recurrence")

    now = utc_now()
    schedule.schedule_status = ScheduleStatus.ACTIVE
    schedule.next_run_at = next_occurrence_after(
        recurrence_rule=schedule.recurrence_rule,
        recurrence_timezone=schedule.recurrence_timezone,
        after=now,
    )
    schedule.version += 1
    schedule.updated_at = now
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=None)


async def cancel_recurring_task(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
) -> TaskBundle:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    _require_version(schedule.version, version)
    if task.execution_mode is not ExecutionMode.RECURRING:
        raise InvalidStateTransitionError("only recurring schedules can be canceled")
    if schedule.schedule_status not in {ScheduleStatus.ACTIVE, ScheduleStatus.PAUSED}:
        raise InvalidStateTransitionError(
            "only active or paused recurring schedules can be canceled"
        )

    schedule.schedule_status = ScheduleStatus.CANCELED
    schedule.next_run_at = None
    schedule.version += 1
    schedule.updated_at = utc_now()
    await _recompute_task_status(session, task)
    await session.flush()
    return TaskBundle(task=task, schedule=schedule, run=None)


async def materialize_run(
    session: AsyncSession,
    *,
    payload_task_id: str,
    payload_schedule_id: str | None,
    payload_run_id: str | None,
    planned_start_at: datetime,
    occurrence_key: str | None,
    workflow_id: str,
    run_workspace_root: str,
) -> MaterializedRun:
    if payload_run_id is not None:
        run = await get_run(session, payload_run_id)
        task = await get_task(session, run.task_id)
        _ = await record_run_event(
            session,
            run_id=run.run_id,
            event_type="run.materialization_reused",
            message="Existing run loaded for execution.",
            details={"run_status": run.run_status.value},
            temporal_workflow_id=workflow_id,
        )
        return _materialized_run_response(
            run=run,
            task=task,
            workflow_id=workflow_id,
            run_workspace_root=run_workspace_root,
        )
    if payload_schedule_id is None:
        raise ValueError("recurring materialization requires schedule_id")

    schedule = await get_schedule(session, payload_schedule_id)
    if schedule.task_id != payload_task_id:
        raise InvalidStateTransitionError("schedule does not belong to task")
    task = await get_task(session, schedule.task_id)
    if task.execution_mode is not ExecutionMode.RECURRING:
        raise InvalidStateTransitionError("only recurring schedules materialize runs")
    if occurrence_key is None:
        occurrence_key = occurrence_key_for_datetime(planned_start_at)
    planned_start_at_utc = to_utc(planned_start_at)
    existing = await _get_run_for_occurrence(
        session,
        schedule_id=schedule.schedule_id,
        occurrence_key=occurrence_key,
    )
    if existing is not None:
        _ = await record_run_event(
            session,
            run_id=existing.run_id,
            event_type="run.materialization_reused",
            message="Existing recurring occurrence run loaded for execution.",
            details={
                "occurrence_key": occurrence_key,
                "run_status": existing.run_status.value,
            },
            temporal_workflow_id=workflow_id,
        )
        return _materialized_run_response(
            run=existing,
            task=task,
            workflow_id=workflow_id,
            run_workspace_root=run_workspace_root,
        )

    now = utc_now()
    override = await _get_occurrence_override(
        session,
        schedule_id=schedule.schedule_id,
        original_occurrence_at=planned_start_at_utc.replace(microsecond=0),
    )
    if override is not None and override.rescheduled_run_id is not None:
        noop_run = Run(
            run_id=new_id("run"),
            task_id=task.task_id,
            schedule_id=schedule.schedule_id,
            run_status=RunStatus.CANCELED,
            planned_start_at=planned_start_at_utc,
            actual_start_at=None,
            finished_at=now,
            instruction_source_snapshot=(
                override.override_instruction_delta or task.instruction_source
            ),
            result_summary=None,
            failure_reason="recurring occurrence was rescheduled to a different time",
            external_execution_ref=workflow_id,
            occurrence_key=occurrence_key,
            created_at=now,
            updated_at=now,
        )
        schedule.last_materialized_at = planned_start_at_utc
        if schedule.schedule_status is ScheduleStatus.ACTIVE:
            if schedule.recurrence_rule is None or schedule.recurrence_timezone is None:
                raise InvalidStateTransitionError(
                    "recurring schedule is missing recurrence"
                )
            schedule.next_run_at = next_occurrence_after(
                recurrence_rule=schedule.recurrence_rule,
                recurrence_timezone=schedule.recurrence_timezone,
                after=planned_start_at_utc,
            )
        schedule.updated_at = now
        session.add(noop_run)
        await _recompute_task_status(session, task)
        await session.flush()
        _ = await record_run_event(
            session,
            run_id=noop_run.run_id,
            event_type="run.skipped_rescheduled",
            message=(
                "Recurring occurrence skipped because it was"
                " rescheduled to a different time."
            ),
            details={"occurrence_key": occurrence_key},
            severity="warning",
            temporal_workflow_id=workflow_id,
        )
        return _materialized_run_response(
            run=noop_run,
            task=task,
            workflow_id=workflow_id,
            run_workspace_root=run_workspace_root,
        )
    run_status = (
        RunStatus.PLANNED
        if (
            schedule.schedule_status is ScheduleStatus.ACTIVE
            and (
                override is None
                or override.override_status is OccurrenceOverrideStatus.ACTIVE
            )
        )
        else RunStatus.CANCELED
    )
    effective_planned_start_at = (
        override.override_occurrence_at
        if override is not None and override.override_occurrence_at is not None
        else planned_start_at_utc
    )
    effective_instruction = (
        override.override_instruction_delta
        if override is not None and override.override_instruction_delta is not None
        else task.instruction_source
    )
    run = Run(
        run_id=new_id("run"),
        task_id=task.task_id,
        schedule_id=schedule.schedule_id,
        run_status=run_status,
        planned_start_at=effective_planned_start_at,
        actual_start_at=None,
        finished_at=now if run_status is RunStatus.CANCELED else None,
        instruction_source_snapshot=effective_instruction,
        result_summary=None,
        failure_reason=None
        if run_status is RunStatus.PLANNED
        else "recurring occurrence was canceled or inactive at materialization",
        external_execution_ref=workflow_id,
        occurrence_key=occurrence_key,
        created_at=now,
        updated_at=now,
    )
    schedule.last_materialized_at = planned_start_at_utc
    if schedule.schedule_status is ScheduleStatus.ACTIVE:
        if schedule.recurrence_rule is None or schedule.recurrence_timezone is None:
            raise InvalidStateTransitionError(
                "recurring schedule is missing recurrence"
            )
        schedule.next_run_at = next_occurrence_after(
            recurrence_rule=schedule.recurrence_rule,
            recurrence_timezone=schedule.recurrence_timezone,
            after=planned_start_at_utc,
        )
    schedule.updated_at = now
    session.add(run)
    await _recompute_task_status(session, task)
    await session.flush()
    if run_status is RunStatus.CANCELED:
        _ = await record_run_event(
            session,
            run_id=run.run_id,
            event_type="run.skipped_canceled",
            message="Recurring occurrence skipped because it was canceled or inactive.",
            details={"occurrence_key": occurrence_key},
            severity="warning",
            temporal_workflow_id=workflow_id,
        )
    else:
        _ = await record_run_event(
            session,
            run_id=run.run_id,
            event_type="run.materialized",
            message="Recurring occurrence run materialized.",
            details={"occurrence_key": occurrence_key},
            temporal_workflow_id=workflow_id,
        )
    return _materialized_run_response(
        run=run,
        task=task,
        workflow_id=workflow_id,
        run_workspace_root=run_workspace_root,
        instruction_source=effective_instruction,
    )


async def mark_run_queued(
    session: AsyncSession,
    *,
    run_id: str,
    external_execution_ref: str | None = None,
    temporal_workflow_id: str | None = None,
    temporal_workflow_run_id: str | None = None,
    activity_type: str | None = None,
    activity_attempt: int | None = None,
) -> Run:
    status_changed = await _run_status_will_change(
        session,
        run_id=run_id,
        target=RunStatus.QUEUED,
    )
    run = await _set_run_status(
        session,
        run_id=run_id,
        target=RunStatus.QUEUED,
        external_execution_ref=external_execution_ref,
    )
    if status_changed:
        _ = await record_run_event(
            session,
            run_id=run.run_id,
            event_type="run.queued",
            message="Run queued for execution.",
            details={"external_execution_ref": external_execution_ref},
            temporal_workflow_id=temporal_workflow_id,
            temporal_workflow_run_id=temporal_workflow_run_id,
            activity_type=activity_type,
            activity_attempt=activity_attempt,
        )
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def mark_run_running(
    session: AsyncSession,
    *,
    run_id: str,
    temporal_workflow_id: str | None = None,
    temporal_workflow_run_id: str | None = None,
    activity_type: str | None = None,
    activity_attempt: int | None = None,
) -> Run:
    status_changed = await _run_status_will_change(
        session,
        run_id=run_id,
        target=RunStatus.RUNNING,
    )
    run = await _set_run_status(session, run_id=run_id, target=RunStatus.RUNNING)
    if run.actual_start_at is None:
        run.actual_start_at = utc_now()
    if status_changed:
        _ = await record_run_event(
            session,
            run_id=run.run_id,
            event_type="run.running",
            message="Run execution started.",
            temporal_workflow_id=temporal_workflow_id,
            temporal_workflow_run_id=temporal_workflow_run_id,
            activity_type=activity_type,
            activity_attempt=activity_attempt,
        )
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def mark_run_completed(
    session: AsyncSession,
    *,
    run_id: str,
    result_summary: str | None,
    temporal_workflow_id: str | None = None,
    temporal_workflow_run_id: str | None = None,
    activity_type: str | None = None,
    activity_attempt: int | None = None,
) -> Run:
    status_changed = await _run_status_will_change(
        session,
        run_id=run_id,
        target=RunStatus.COMPLETED,
    )
    run = await _set_run_status(session, run_id=run_id, target=RunStatus.COMPLETED)
    run.result_summary = result_summary
    run.failure_reason = None
    run.finished_at = run.finished_at or utc_now()
    if status_changed:
        _ = await record_run_event(
            session,
            run_id=run.run_id,
            event_type="run.completed",
            message="Run completed successfully.",
            details={"has_result_summary": result_summary is not None},
            temporal_workflow_id=temporal_workflow_id,
            temporal_workflow_run_id=temporal_workflow_run_id,
            activity_type=activity_type,
            activity_attempt=activity_attempt,
        )
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def mark_run_failed(
    session: AsyncSession,
    *,
    run_id: str,
    failure_reason: str,
    temporal_workflow_id: str | None = None,
    temporal_workflow_run_id: str | None = None,
    activity_type: str | None = None,
    activity_attempt: int | None = None,
) -> Run:
    status_changed = await _run_status_will_change(
        session,
        run_id=run_id,
        target=RunStatus.FAILED,
    )
    run = await _set_run_status(session, run_id=run_id, target=RunStatus.FAILED)
    run.failure_reason = failure_reason
    run.finished_at = run.finished_at or utc_now()
    if status_changed:
        _ = await record_run_event(
            session,
            run_id=run.run_id,
            event_type="run.failed",
            message="Run failed.",
            details={"has_failure_reason": bool(failure_reason)},
            severity="error",
            temporal_workflow_id=temporal_workflow_id,
            temporal_workflow_run_id=temporal_workflow_run_id,
            activity_type=activity_type,
            activity_attempt=activity_attempt,
        )
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def mark_run_canceled(
    session: AsyncSession,
    *,
    run_id: str,
    failure_reason: str | None = None,
    temporal_workflow_id: str | None = None,
    temporal_workflow_run_id: str | None = None,
    activity_type: str | None = None,
    activity_attempt: int | None = None,
) -> Run:
    status_changed = await _run_status_will_change(
        session,
        run_id=run_id,
        target=RunStatus.CANCELED,
    )
    run = await _set_run_status(session, run_id=run_id, target=RunStatus.CANCELED)
    run.failure_reason = failure_reason
    run.finished_at = run.finished_at or utc_now()
    if status_changed:
        _ = await record_run_event(
            session,
            run_id=run.run_id,
            event_type="run.canceled",
            message="Run canceled.",
            details={"has_failure_reason": failure_reason is not None},
            severity="warning",
            temporal_workflow_id=temporal_workflow_id,
            temporal_workflow_run_id=temporal_workflow_run_id,
            activity_type=activity_type,
            activity_attempt=activity_attempt,
        )
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def complete_single_run_schedule(
    session: AsyncSession,
    *,
    schedule_id: str,
) -> Schedule:
    schedule = await get_schedule(session, schedule_id)
    if schedule.schedule_type is not ScheduleType.SINGLE_RUN:
        raise InvalidStateTransitionError("only single-run schedules can complete")
    if schedule.schedule_status is ScheduleStatus.COMPLETED:
        return schedule
    if schedule.schedule_status is not ScheduleStatus.ACTIVE:
        raise InvalidStateTransitionError("only active schedules can complete")
    schedule.schedule_status = ScheduleStatus.COMPLETED
    schedule.next_run_at = None
    schedule.version += 1
    schedule.updated_at = utc_now()
    await _recompute_task_status_by_id(session, schedule.task_id)
    await session.flush()
    return schedule


async def get_one_time_kanban(
    session: AsyncSession,
    *,
    include_canceled: bool = True,
) -> dict[str, list[TaskDetail]]:
    statement = (
        select(Task)
        .where(
            Task.execution_mode == ExecutionMode.ONE_TIME,
            Task.archived_at.is_(None),
        )
        .options(selectinload(Task.schedules), selectinload(Task.runs))
        .order_by(Task.created_at.desc())
    )
    tasks = list(await session.scalars(statement))
    board: dict[str, list[TaskDetail]] = {
        "upcoming": [],
        "running": [],
        "completed": [],
        "failed": [],
    }
    if include_canceled:
        board["canceled"] = []
    for task in tasks:
        if not include_canceled and task.task_status is TaskStatus.CANCELED:
            continue
        schedule = task.schedules[0] if task.schedules else None
        latest_run = sorted(task.runs, key=lambda run: run.created_at, reverse=True)
        detail = TaskDetail(
            task=task,
            schedule=schedule,
            latest_run=latest_run[0] if latest_run else None,
        )
        if task.task_status is TaskStatus.RUNNING:
            board["running"].append(detail)
        elif task.task_status is TaskStatus.COMPLETED:
            board["completed"].append(detail)
        elif task.task_status is TaskStatus.FAILED:
            board["failed"].append(detail)
        elif task.task_status is TaskStatus.CANCELED:
            board["canceled"].append(detail)
        else:
            board["upcoming"].append(detail)
    return board


async def _one_time_calendar_items(
    session: AsyncSession,
    *,
    window_start: datetime,
    window_end: datetime,
    include_completed: bool,
) -> list[CalendarItem]:
    filters = [
        Task.execution_mode == ExecutionMode.ONE_TIME,
        Task.archived_at.is_(None),
        Schedule.schedule_type == ScheduleType.SINGLE_RUN,
        Run.planned_start_at >= window_start,
        Run.planned_start_at <= window_end,
        Task.task_status != TaskStatus.CANCELED,
        Schedule.schedule_status != ScheduleStatus.CANCELED,
        Run.run_status != RunStatus.CANCELED,
    ]
    if not include_completed:
        filters.append(
            Run.run_status.in_({RunStatus.PLANNED, RunStatus.QUEUED, RunStatus.RUNNING})
        )

    statement = (
        select(Task, Schedule, Run)
        .join(Schedule, Schedule.task_id == Task.task_id)
        .join(Run, Run.schedule_id == Schedule.schedule_id)
        .where(*filters)
    )
    result = await session.execute(statement)
    return [
        CalendarItem(
            task=task,
            schedule=schedule,
            occurrence_at=_db_datetime_to_utc(run.planned_start_at),
            state=task.task_status,
            original_occurrence_at=None,
            occurrence_override=None,
        )
        for task, schedule, run in result.tuples()
    ]


async def _recurring_calendar_items(
    session: AsyncSession,
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[CalendarItem]:
    statement = (
        select(Task, Schedule)
        .join(Schedule)
        .where(
            Task.execution_mode == ExecutionMode.RECURRING,
            Task.archived_at.is_(None),
            Schedule.schedule_type == ScheduleType.RECURRING_RULE,
            Schedule.schedule_status == ScheduleStatus.ACTIVE,
        )
    )
    rows = (await session.execute(statement)).tuples().all()
    overrides = await _occurrence_overrides_by_schedule_id(
        session,
        schedule_ids=[schedule.schedule_id for _, schedule in rows],
    )

    items: list[CalendarItem] = []
    seen_originals: set[tuple[str, datetime]] = set()
    for task, schedule in rows:
        if schedule.recurrence_rule is None or schedule.recurrence_timezone is None:
            continue
        schedule_overrides = overrides.get(schedule.schedule_id, {})
        for original_at in _project_occurrences(
            recurrence_rule=schedule.recurrence_rule,
            recurrence_timezone=schedule.recurrence_timezone,
            window_start=window_start,
            window_end=window_end,
        ):
            seen_originals.add((schedule.schedule_id, original_at))
            override = schedule_overrides.get(original_at)
            if (
                override is not None
                and override.override_status is OccurrenceOverrideStatus.CANCELED
            ):
                continue
            occurrence_at = (
                override.override_occurrence_at
                if override is not None and override.override_occurrence_at is not None
                else original_at
            )
            occurrence_at = _db_datetime_to_utc(occurrence_at)
            if window_start <= occurrence_at <= window_end:
                items.append(
                    CalendarItem(
                        task=task,
                        schedule=schedule,
                        occurrence_at=occurrence_at,
                        state=task.task_status,
                        original_occurrence_at=original_at,
                        occurrence_override=override,
                    )
                )
        for original_at, override in schedule_overrides.items():
            if (schedule.schedule_id, original_at) in seen_originals:
                continue
            if override.override_status is OccurrenceOverrideStatus.CANCELED:
                continue
            if override.override_occurrence_at is None:
                continue
            override_occurrence_at = _db_datetime_to_utc(
                override.override_occurrence_at
            )
            if window_start <= override_occurrence_at <= window_end:
                items.append(
                    CalendarItem(
                        task=task,
                        schedule=schedule,
                        occurrence_at=override_occurrence_at,
                        state=task.task_status,
                        original_occurrence_at=original_at,
                        occurrence_override=override,
                    )
                )
    return items


def _project_occurrences(
    *,
    recurrence_rule: str,
    recurrence_timezone: str,
    window_start: datetime,
    window_end: datetime,
    max_occurrences: int = 500,
) -> list[datetime]:
    occurrences: list[datetime] = []
    cursor = window_start - timedelta(microseconds=1)
    while len(occurrences) < max_occurrences:
        next_at = next_occurrence_after(
            recurrence_rule=recurrence_rule,
            recurrence_timezone=recurrence_timezone,
            after=cursor,
        )
        if next_at > window_end:
            break
        occurrences.append(next_at)
        cursor = next_at
    return occurrences


async def _occurrence_overrides_by_schedule_id(
    session: AsyncSession,
    *,
    schedule_ids: list[str],
) -> dict[str, dict[datetime, OccurrenceOverride]]:
    if not schedule_ids:
        return {}
    statement = select(OccurrenceOverride).where(
        OccurrenceOverride.schedule_id.in_(schedule_ids)
    )
    by_schedule: dict[str, dict[datetime, OccurrenceOverride]] = {}
    for override in await session.scalars(statement):
        by_schedule.setdefault(override.schedule_id, {})[
            _db_datetime_to_utc(override.original_occurrence_at)
        ] = override
    return by_schedule


def run_outcome_preview_values(run: Run) -> tuple[str | None, bool, str | None]:
    if run.result_summary is not None:
        full_text = run.result_summary
        source = "result_summary"
    elif run.failure_reason is not None:
        full_text = run.failure_reason
        source = "failure_reason"
    else:
        return None, False, None

    if len(full_text) > RUN_OUTCOME_PREVIEW_LIMIT:
        return f"{full_text[: RUN_OUTCOME_PREVIEW_LIMIT - 3]}...", True, source
    return full_text, False, source


def _to_run_preview(run: Run) -> RunPreview:
    outcome_preview, outcome_truncated, outcome_source = run_outcome_preview_values(run)
    return RunPreview(
        run_id=run.run_id,
        task_id=run.task_id,
        schedule_id=run.schedule_id,
        run_status=run.run_status,
        planned_start_at=run.planned_start_at,
        actual_start_at=run.actual_start_at,
        finished_at=run.finished_at,
        occurrence_key=run.occurrence_key,
        created_at=run.created_at,
        updated_at=run.updated_at,
        outcome_preview=outcome_preview,
        outcome_truncated=outcome_truncated,
        outcome_source=outcome_source,
    )


def _db_datetime_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return to_utc(value)


async def _list_recurring_todo_rows(
    session: AsyncSession,
    *,
    status: ScheduleStatus,
    order_by_next_run: bool,
) -> list[tuple[Task, Schedule]]:
    statement = (
        select(Task, Schedule)
        .join(Schedule)
        .where(
            Task.execution_mode == ExecutionMode.RECURRING,
            Task.archived_at.is_(None),
            Schedule.schedule_type == ScheduleType.RECURRING_RULE,
            Schedule.schedule_status == status,
        )
    )
    if order_by_next_run:
        statement = statement.order_by(
            Schedule.next_run_at.asc(),
            Schedule.updated_at.desc(),
            Task.task_id.asc(),
        )
    else:
        statement = statement.order_by(Schedule.updated_at.desc(), Task.task_id.asc())
    result = await session.execute(statement)
    return list(result.tuples())


def _recurring_todo_statuses(
    *,
    status: ScheduleStatus | None,
    include_paused: bool,
) -> tuple[ScheduleStatus, ...]:
    supported = {ScheduleStatus.ACTIVE, ScheduleStatus.PAUSED}
    if status is not None:
        return (status,) if status in supported else ()
    if include_paused:
        return (ScheduleStatus.ACTIVE, ScheduleStatus.PAUSED)
    return (ScheduleStatus.ACTIVE,)


async def _latest_runs_by_task_id(
    session: AsyncSession,
    *,
    task_ids: list[str],
) -> dict[str, Run]:
    if not task_ids:
        return {}
    statement = (
        select(Run)
        .where(Run.task_id.in_(task_ids))
        .order_by(Run.task_id.asc(), Run.created_at.desc(), Run.run_id.desc())
    )
    latest: dict[str, Run] = {}
    for run in await session.scalars(statement):
        _ = latest.setdefault(run.task_id, run)
    return latest


async def _get_active_recurring_task_and_schedule(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
    action: str,
) -> tuple[Task, Schedule]:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    _require_version(schedule.version, version)
    _require_active_recurring_task(task, schedule, action=action)
    if schedule.schedule_status is not ScheduleStatus.ACTIVE:
        raise InvalidStateTransitionError(
            f"only active recurring schedules can be {action}"
        )
    return task, schedule


async def get_occurrence_override(
    session: AsyncSession, occurrence_override_id: str
) -> OccurrenceOverride:
    override = await session.get(OccurrenceOverride, occurrence_override_id)
    if override is None:
        raise NotFoundError(f"occurrence override not found: {occurrence_override_id}")
    return override


async def _get_occurrence_override(
    session: AsyncSession,
    *,
    schedule_id: str,
    original_occurrence_at: datetime,
) -> OccurrenceOverride | None:
    statement = select(OccurrenceOverride).where(
        OccurrenceOverride.schedule_id == schedule_id,
        OccurrenceOverride.original_occurrence_at == original_occurrence_at,
    )
    return (await session.scalars(statement)).one_or_none()


def _require_projected_occurrence(
    schedule: Schedule,
    original_occurrence_at: datetime,
) -> None:
    if schedule.schedule_type is not ScheduleType.RECURRING_RULE:
        raise InvalidStateTransitionError("only recurring occurrences can be edited")
    if schedule.recurrence_rule is None or schedule.recurrence_timezone is None:
        raise InvalidStateTransitionError("recurring schedule is missing recurrence")
    probe = original_occurrence_at - timedelta(microseconds=1)
    projected = next_occurrence_after(
        recurrence_rule=schedule.recurrence_rule,
        recurrence_timezone=schedule.recurrence_timezone,
        after=probe,
    )
    if projected != original_occurrence_at:
        raise InvalidStateTransitionError(
            "original_occurrence_at is not projected by the recurrence rule"
        )


async def _require_occurrence_not_started(
    session: AsyncSession,
    *,
    schedule_id: str,
    original_occurrence_at: datetime,
) -> None:
    require_future_datetime(original_occurrence_at, field_name="original_occurrence_at")
    existing = await _get_run_for_occurrence(
        session,
        schedule_id=schedule_id,
        occurrence_key=occurrence_key_for_datetime(original_occurrence_at),
    )
    if existing is not None and existing.run_status is not RunStatus.PLANNED:
        raise InvalidStateTransitionError("occurrence already started")


async def _set_run_status(
    session: AsyncSession,
    *,
    run_id: str,
    target: RunStatus,
    external_execution_ref: str | None = None,
) -> Run:
    run = await get_run(session, run_id)
    if run.run_status is target:
        return run
    try:
        require_run_transition(run.run_status, target)
    except ValueError as exc:
        raise InvalidStateTransitionError(str(exc)) from exc
    run.run_status = target
    run.updated_at = utc_now()
    if external_execution_ref is not None:
        run.external_execution_ref = external_execution_ref
    await session.flush()
    return run


async def _run_status_will_change(
    session: AsyncSession,
    *,
    run_id: str,
    target: RunStatus,
) -> bool:
    run = await get_run(session, run_id)
    return run.run_status is not target


async def _get_planned_run_for_schedule(
    session: AsyncSession,
    schedule_id: str,
) -> Run:
    statement = select(Run).where(
        Run.schedule_id == schedule_id,
        Run.run_status == RunStatus.PLANNED,
    )
    run = (await session.scalars(statement)).one_or_none()
    if run is None:
        raise NotFoundError(f"planned run not found for schedule: {schedule_id}")
    return run


async def _get_run_for_occurrence(
    session: AsyncSession,
    *,
    schedule_id: str,
    occurrence_key: str,
) -> Run | None:
    statement = select(Run).where(
        Run.schedule_id == schedule_id,
        Run.occurrence_key == occurrence_key,
    )
    return (await session.scalars(statement)).one_or_none()


async def _recompute_task_status_by_id(session: AsyncSession, task_id: str) -> None:
    task = await get_task(session, task_id)
    await _recompute_task_status(session, task)


async def _recompute_task_status(session: AsyncSession, task: Task) -> None:
    schedule = await get_schedule_for_task(session, task.task_id)
    latest_run = await get_latest_run(session, task.task_id)
    task.task_status = derive_task_status(
        execution_mode=task.execution_mode,
        archived_at=task.archived_at,
        schedule_status=schedule.schedule_status,
        latest_run_status=latest_run.run_status if latest_run else None,
    )
    task.version += 1
    task.updated_at = utc_now()


def _require_version(current: int, observed: int) -> None:
    if current != observed:
        raise ConflictError("resource version conflict")


def _require_template_defaults(
    *,
    default_execution_mode: ExecutionMode,
    default_schedule_type: ScheduleType,
    default_recurrence_rule: str | None,
    default_recurrence_timezone: str | None,
) -> None:
    try:
        require_template_schedule_defaults(
            execution_mode=default_execution_mode,
            schedule_type=default_schedule_type,
            recurrence_rule=default_recurrence_rule,
            recurrence_timezone=default_recurrence_timezone,
        )
    except ValueError as exc:
        raise InvalidStateTransitionError(str(exc)) from exc


def _require_recurring_schedule(
    *,
    schedule_type: ScheduleType,
    recurrence_rule: str | None,
    recurrence_timezone: str | None,
) -> None:
    try:
        require_recurring_schedule_consistency(
            execution_mode=ExecutionMode.RECURRING,
            schedule_type=schedule_type,
            recurrence_rule=recurrence_rule,
            recurrence_timezone=recurrence_timezone,
        )
    except ValueError as exc:
        raise InvalidStateTransitionError(str(exc)) from exc


def _require_active_recurring_task(
    task: Task,
    schedule: Schedule,
    *,
    action: str,
) -> None:
    if task.execution_mode is not ExecutionMode.RECURRING:
        raise InvalidStateTransitionError(f"only recurring schedules can be {action}")
    if schedule.schedule_type is not ScheduleType.RECURRING_RULE:
        raise InvalidStateTransitionError(f"only recurring schedules can be {action}")
    if schedule.schedule_status is ScheduleStatus.CANCELED:
        raise InvalidStateTransitionError(
            "canceled recurring schedules cannot be edited"
        )


async def _default_executor_profile(
    session: AsyncSession, executor: ExecutorName
) -> ExecutorProfile | None:
    statement = (
        select(ExecutorProfile)
        .where(
            ExecutorProfile.executor == executor,
            ExecutorProfile.is_default.is_(True),
            ExecutorProfile.archived_at.is_(None),
        )
        .order_by(ExecutorProfile.created_at.asc(), ExecutorProfile.profile_id.asc())
        .limit(1)
    )
    return await session.scalar(statement)


async def _clear_default_executor_profile(
    session: AsyncSession, executor: ExecutorName
) -> None:
    statement = select(ExecutorProfile).where(
        ExecutorProfile.executor == executor,
        ExecutorProfile.is_default.is_(True),
        ExecutorProfile.archived_at.is_(None),
    )
    for profile in await session.scalars(statement):
        profile.is_default = False
        profile.updated_at = utc_now()


def _materialized_run_response(
    *,
    run: Run,
    task: Task,
    workflow_id: str,
    run_workspace_root: str,
    instruction_source: str | None = None,
) -> MaterializedRun:
    _ = workflow_id
    return MaterializedRun(
        run_id=run.run_id,
        run_status=run.run_status,
        execution_snapshot=ExecutionSnapshot(
            run_id=run.run_id,
            task_id=task.task_id,
            schedule_id=run.schedule_id,
            executor=task.executor,
            executor_profile_id=task.executor_profile_id,
            instruction_source=instruction_source or run.instruction_source_snapshot,
            planned_start_at=run.planned_start_at,
            working_directory=str(Path(run_workspace_root) / run.run_id),
            target_working_directory=task.target_working_directory,
        ),
    )
