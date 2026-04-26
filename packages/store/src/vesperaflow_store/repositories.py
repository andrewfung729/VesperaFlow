"""Repository functions used by the API and Temporal activities."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from vesperaflow_core import (
    ExecutionMode,
    ExecutionSnapshot,
    ExecutorName,
    MaterializedRun,
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
from .models import Run, Schedule, Task, Template


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
    runs: list[Run]


@dataclass(frozen=True, slots=True)
class HistoryItem:
    run: Run
    task: Task


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
class TemplatePage:
    items: list[Template]
    total: int


async def create_one_time_task(
    session: AsyncSession,
    *,
    title: str,
    instruction_source: str,
    target_working_directory: str,
    planned_at: datetime,
    template_id: str | None = None,
    executor: ExecutorName = ExecutorName.CLAUDE_CODE,
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
        default_planned_at=to_utc(default_planned_at)
        if default_planned_at
        else None,
        default_recurrence_rule=default_recurrence_rule,
        default_recurrence_timezone=default_recurrence_timezone,
        default_executor=default_executor,
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
    filters = []
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
    install_default_executor: ExecutorName,
    title: str | None = None,
    instruction_source: str | None = None,
    executor: ExecutorName | None = None,
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
    return await create_one_time_task(
        session,
        title=title or template.default_task_title or template.name,
        instruction_source=instruction_source or template.instruction_source,
        target_working_directory=resolved_target_working_directory,
        planned_at=resolved_planned_at,
        template_id=template.template_id,
        executor=executor or template.default_executor or install_default_executor,
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


async def get_schedule_for_task(session: AsyncSession, task_id: str) -> Schedule:
    statement = select(Schedule).where(Schedule.task_id == task_id)
    schedule = (await session.scalars(statement)).one_or_none()
    if schedule is None:
        raise NotFoundError(f"schedule not found for task: {task_id}")
    return schedule


async def get_latest_run(session: AsyncSession, task_id: str) -> Run | None:
    statement = (
        select(Run)
        .where(Run.task_id == task_id)
        .order_by(Run.created_at.desc(), Run.run_id.desc())
        .limit(1)
    )
    return (await session.scalars(statement)).one_or_none()


async def list_runs_for_task(session: AsyncSession, task_id: str) -> list[Run]:
    await get_task(session, task_id)
    statement = (
        select(Run).where(Run.task_id == task_id).order_by(Run.created_at.desc())
    )
    return list(await session.scalars(statement))


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

    filters = [
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
    rows = (await session.execute(statement)).all()
    return HistoryPage(
        items=[HistoryItem(run=run, task=task) for run, task in rows],
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


async def get_task_detail(session: AsyncSession, task_id: str) -> TaskDetail:
    task = await get_task(session, task_id)
    schedule = await get_schedule_for_task(session, task_id)
    runs = await list_runs_for_task(session, task_id)
    latest_run = runs[0] if runs else None
    return TaskDetail(task=task, schedule=schedule, latest_run=latest_run, runs=runs)


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


async def update_recurring_task_schedule(
    session: AsyncSession,
    *,
    task_id: str,
    version: int,
    recurrence_rule: str,
    recurrence_timezone: str,
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
    existing = await _get_run_for_occurrence(
        session,
        schedule_id=schedule.schedule_id,
        occurrence_key=occurrence_key,
    )
    if existing is not None:
        return _materialized_run_response(
            run=existing,
            task=task,
            workflow_id=workflow_id,
            run_workspace_root=run_workspace_root,
        )

    now = utc_now()
    run_status = (
        RunStatus.PLANNED
        if schedule.schedule_status is ScheduleStatus.ACTIVE
        else RunStatus.CANCELED
    )
    run = Run(
        run_id=new_id("run"),
        task_id=task.task_id,
        schedule_id=schedule.schedule_id,
        run_status=run_status,
        planned_start_at=to_utc(planned_start_at),
        actual_start_at=None,
        finished_at=now if run_status is RunStatus.CANCELED else None,
        result_summary=None,
        failure_reason=None
        if run_status is RunStatus.PLANNED
        else "recurring schedule was inactive at materialization",
        external_execution_ref=workflow_id,
        occurrence_key=occurrence_key,
        created_at=now,
        updated_at=now,
    )
    schedule.last_materialized_at = run.planned_start_at
    if schedule.schedule_status is ScheduleStatus.ACTIVE:
        if schedule.recurrence_rule is None or schedule.recurrence_timezone is None:
            raise InvalidStateTransitionError(
                "recurring schedule is missing recurrence"
            )
        schedule.next_run_at = next_occurrence_after(
            recurrence_rule=schedule.recurrence_rule,
            recurrence_timezone=schedule.recurrence_timezone,
            after=run.planned_start_at,
        )
    schedule.updated_at = now
    session.add(run)
    await _recompute_task_status(session, task)
    await session.flush()
    return _materialized_run_response(
        run=run,
        task=task,
        workflow_id=workflow_id,
        run_workspace_root=run_workspace_root,
    )


async def mark_run_queued(
    session: AsyncSession,
    *,
    run_id: str,
    external_execution_ref: str | None = None,
) -> Run:
    run = await _set_run_status(
        session,
        run_id=run_id,
        target=RunStatus.QUEUED,
        external_execution_ref=external_execution_ref,
    )
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def mark_run_running(session: AsyncSession, *, run_id: str) -> Run:
    run = await _set_run_status(session, run_id=run_id, target=RunStatus.RUNNING)
    if run.actual_start_at is None:
        run.actual_start_at = utc_now()
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def mark_run_completed(
    session: AsyncSession,
    *,
    run_id: str,
    result_summary: str | None,
) -> Run:
    run = await _set_run_status(session, run_id=run_id, target=RunStatus.COMPLETED)
    run.result_summary = result_summary
    run.failure_reason = None
    run.finished_at = run.finished_at or utc_now()
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def mark_run_failed(
    session: AsyncSession,
    *,
    run_id: str,
    failure_reason: str,
) -> Run:
    run = await _set_run_status(session, run_id=run_id, target=RunStatus.FAILED)
    run.failure_reason = failure_reason
    run.finished_at = run.finished_at or utc_now()
    await _recompute_task_status_by_id(session, run.task_id)
    return run


async def mark_run_canceled(
    session: AsyncSession,
    *,
    run_id: str,
    failure_reason: str | None = None,
) -> Run:
    run = await _set_run_status(session, run_id=run_id, target=RunStatus.CANCELED)
    run.failure_reason = failure_reason
    run.finished_at = run.finished_at or utc_now()
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


async def get_one_time_kanban(session: AsyncSession) -> dict[str, list[TaskDetail]]:
    statement = (
        select(Task)
        .where(Task.execution_mode == ExecutionMode.ONE_TIME)
        .options(selectinload(Task.schedules), selectinload(Task.runs))
        .order_by(Task.created_at.desc())
    )
    tasks = list(await session.scalars(statement))
    board = {
        "upcoming": [],
        "running": [],
        "completed": [],
        "failed": [],
        "canceled": [],
    }
    for task in tasks:
        schedule = task.schedules[0] if task.schedules else None
        latest_run = sorted(task.runs, key=lambda run: run.created_at, reverse=True)
        detail = TaskDetail(
            task=task,
            schedule=schedule,
            latest_run=latest_run[0] if latest_run else None,
            runs=latest_run,
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
    return [(task, schedule) for task, schedule in (await session.execute(statement))]


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
        latest.setdefault(run.task_id, run)
    return latest


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


def _materialized_run_response(
    *,
    run: Run,
    task: Task,
    workflow_id: str,
    run_workspace_root: str,
) -> MaterializedRun:
    return MaterializedRun(
        run_id=run.run_id,
        run_status=run.run_status,
        execution_snapshot=ExecutionSnapshot(
            run_id=run.run_id,
            task_id=task.task_id,
            schedule_id=run.schedule_id,
            executor=task.executor,
            instruction_source=task.instruction_source,
            planned_start_at=run.planned_start_at,
            working_directory=str(Path(run_workspace_root) / run.run_id),
            target_working_directory=task.target_working_directory,
        ),
    )
