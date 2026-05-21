from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    OccurrenceOverrideStatus,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
    occurrence_key_for_datetime,
    utc_now,
)
from vesperaflow_store import Base, create_engine, create_session_factory
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import ConflictError, InvalidStateTransitionError


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    async with session_factory() as active_session:
        yield active_session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_one_time_task_creates_task_schedule_and_planned_run(
    session: AsyncSession,
) -> None:
    planned_at = datetime.now(UTC) + timedelta(hours=1)
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=planned_at,
        )

    assert bundle.task.task_status is TaskStatus.SCHEDULED
    assert bundle.task.target_working_directory == "/tmp"
    assert bundle.schedule.schedule_status is ScheduleStatus.ACTIVE
    assert bundle.run.run_status is RunStatus.PLANNED


@pytest.mark.asyncio
async def test_create_one_time_task_persists_pi_executor(
    session: AsyncSession,
) -> None:
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
            executor=ExecutorName.PI,
        )

    task = await repo.get_task(session, bundle.task.task_id)
    assert task.executor is ExecutorName.PI


@pytest.mark.asyncio
async def test_executor_profile_crud_persists_pi_runtime_choices(
    session: AsyncSession,
) -> None:
    async with session.begin():
        profile = await repo.create_executor_profile(
            session,
            name="Pi default",
            executor=ExecutorName.PI,
            is_default=True,
            default_model="sonnet",
            env={"FOO": "bar"},
            secret_env={"TOKEN": "secret"},
        )

    stored = await repo.get_executor_profile(session, profile.profile_id)
    assert stored.executor is ExecutorName.PI
    assert stored.default_model == "sonnet"
    assert stored.env == {"FOO": "bar"}
    assert stored.secret_env == {"TOKEN": "secret"}


@pytest.mark.asyncio
async def test_default_executor_profile_resolves_for_task(
    session: AsyncSession,
) -> None:
    async with session.begin():
        await repo.ensure_default_executor_profiles(session)
        await repo.ensure_default_executor_profiles(session)
        profile = await repo.resolve_executor_profile(
            session,
            executor_profile_id=None,
            executor=ExecutorName.DEBUG_PRINTER,
        )
        opencode_profile = await repo.resolve_executor_profile(
            session,
            executor_profile_id=None,
            executor=ExecutorName.OPENCODE,
        )
        pi_profile = await repo.resolve_executor_profile(
            session,
            executor_profile_id=None,
            executor=ExecutorName.PI,
        )
        profiles_page = await repo.list_executor_profiles(session)
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
            executor=profile.executor,
            executor_profile_id=profile.profile_id,
        )

    task = await repo.get_task(session, bundle.task.task_id)
    assert task.executor is ExecutorName.DEBUG_PRINTER
    assert task.executor_profile_id == profile.profile_id
    assert opencode_profile.name == "OpenCode"
    assert opencode_profile.default_model is None
    assert pi_profile.name == "Pi"
    assert pi_profile.default_model is None
    assert [item.executor for item in profiles_page.items].count(ExecutorName.PI) == 1


@pytest.mark.asyncio
async def test_reschedule_requires_observed_schedule_version(
    session: AsyncSession,
) -> None:
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )

    with pytest.raises(ConflictError):
        async with session.begin():
            await repo.reschedule_one_time_task(
                session,
                task_id=bundle.task.task_id,
                version=99,
                planned_at=datetime.now(UTC) + timedelta(hours=2),
            )


@pytest.mark.asyncio
async def test_terminal_run_updates_task_and_schedule_state(
    session: AsyncSession,
) -> None:
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await repo.mark_run_queued(session, run_id=bundle.run.run_id)
        await repo.mark_run_running(session, run_id=bundle.run.run_id)
        await repo.mark_run_completed(
            session,
            run_id=bundle.run.run_id,
            result_summary="Done",
        )
        await repo.complete_single_run_schedule(
            session,
            schedule_id=bundle.schedule.schedule_id,
        )

    detail = await repo.get_task_detail(session, bundle.task.task_id)
    assert detail.task.task_status is TaskStatus.COMPLETED
    assert detail.schedule is not None
    assert detail.schedule.schedule_status is ScheduleStatus.COMPLETED
    assert detail.latest_run is not None
    assert detail.latest_run.result_summary == "Done"


@pytest.mark.asyncio
async def test_run_status_transitions_create_ordered_events(
    session: AsyncSession,
) -> None:
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await repo.mark_run_queued(
            session,
            run_id=bundle.run.run_id,
            external_execution_ref="workflow-run-1",
        )
        await repo.mark_run_running(session, run_id=bundle.run.run_id)
        await repo.mark_run_completed(
            session,
            run_id=bundle.run.run_id,
            result_summary="Done",
        )

    events = await repo.list_run_events(session, run_id=bundle.run.run_id)

    assert events.total == 3
    assert [event.event_type for event in events.items] == [
        "run.queued",
        "run.running",
        "run.completed",
    ]
    assert events.items[0].details == {"external_execution_ref": "workflow-run-1"}
    assert events.items[2].details == {"has_result_summary": True}


@pytest.mark.asyncio
async def test_recurring_lifecycle_and_materialized_run_keeps_parent_stable(
    session: AsyncSession,
) -> None:
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        task_id = bundle.task.task_id
        schedule_id = bundle.schedule.schedule_id
        schedule_version = bundle.schedule.version
        assert bundle.run is None
        assert bundle.schedule.next_run_at is not None

    planned_start_at = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
    occurrence_key = occurrence_key_for_datetime(planned_start_at)
    async with session.begin():
        materialized = await repo.materialize_run(
            session,
            payload_task_id=task_id,
            payload_schedule_id=schedule_id,
            payload_run_id=None,
            planned_start_at=planned_start_at,
            occurrence_key=occurrence_key,
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        duplicate = await repo.materialize_run(
            session,
            payload_task_id=task_id,
            payload_schedule_id=schedule_id,
            payload_run_id=None,
            planned_start_at=planned_start_at,
            occurrence_key=occurrence_key,
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        await repo.mark_run_queued(session, run_id=materialized.run_id)
        await repo.mark_run_running(session, run_id=materialized.run_id)
        await repo.mark_run_failed(
            session,
            run_id=materialized.run_id,
            failure_reason="Executor failed",
        )

    detail = await repo.get_task_detail(session, task_id)
    assert duplicate.run_id == materialized.run_id
    assert detail.task.task_status is TaskStatus.SCHEDULED
    assert detail.latest_run is not None
    assert detail.latest_run.run_status is RunStatus.FAILED
    assert detail.latest_run.occurrence_key == occurrence_key
    assert detail.schedule is not None
    assert detail.schedule.last_materialized_at == planned_start_at
    assert detail.schedule.next_run_at is not None
    await session.rollback()

    async with session.begin():
        paused = await repo.pause_recurring_task(
            session,
            task_id=task_id,
            version=schedule_version,
        )
        paused_version = paused.schedule.version
    assert paused.task.task_status is TaskStatus.PAUSED
    assert paused.schedule.next_run_at is None

    async with session.begin():
        resumed = await repo.resume_recurring_task(
            session,
            task_id=task_id,
            version=paused_version,
        )
    assert resumed.task.task_status is TaskStatus.SCHEDULED
    assert resumed.schedule.schedule_status is ScheduleStatus.ACTIVE
    assert resumed.schedule.next_run_at is not None


@pytest.mark.asyncio
async def test_recurring_materialization_records_materialized_and_reused_events(
    session: AsyncSession,
) -> None:
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        planned_start_at = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
        occurrence_key = occurrence_key_for_datetime(planned_start_at)
        materialized = await repo.materialize_run(
            session,
            payload_task_id=bundle.task.task_id,
            payload_schedule_id=bundle.schedule.schedule_id,
            payload_run_id=None,
            planned_start_at=planned_start_at,
            occurrence_key=occurrence_key,
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        duplicate = await repo.materialize_run(
            session,
            payload_task_id=bundle.task.task_id,
            payload_schedule_id=bundle.schedule.schedule_id,
            payload_run_id=None,
            planned_start_at=planned_start_at,
            occurrence_key=occurrence_key,
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )

    events = await repo.list_run_events(session, run_id=materialized.run_id)

    assert duplicate.run_id == materialized.run_id
    assert [event.event_type for event in events.items] == [
        "run.materialized",
        "run.materialization_reused",
    ]
    assert events.items[0].temporal_workflow_id == "vesperaflow-recurring-workflow"


@pytest.mark.asyncio
async def test_recurring_todo_lists_active_then_paused_with_latest_outcome(
    session: AsyncSession,
) -> None:
    active_earlier_at = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
    active_later_at = datetime(2026, 4, 27, 2, 0, tzinfo=UTC)
    paused_old_updated_at = datetime(2026, 4, 25, 9, 0, tzinfo=UTC)
    paused_recent_updated_at = datetime(2026, 4, 25, 10, 0, tzinfo=UTC)
    async with session.begin():
        active_later = await repo.create_recurring_task(
            session,
            title="Active later",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=10;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        active_earlier = await repo.create_recurring_task(
            session,
            title="Active earlier",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        paused_old = await repo.create_recurring_task(
            session,
            title="Paused old",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        paused_recent = await repo.create_recurring_task(
            session,
            title="Paused recent",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=30",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        one_time = await repo.create_one_time_task(
            session,
            title="One-time task",
            instruction_source="Find one-time updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )

        active_later.schedule.next_run_at = active_later_at
        active_earlier.schedule.next_run_at = active_earlier_at
        await repo.pause_recurring_task(
            session,
            task_id=paused_old.task.task_id,
            version=paused_old.schedule.version,
        )
        paused_old.schedule.updated_at = paused_old_updated_at
        await repo.pause_recurring_task(
            session,
            task_id=paused_recent.task.task_id,
            version=paused_recent.schedule.version,
        )
        paused_recent.schedule.updated_at = paused_recent_updated_at

        materialized = await repo.materialize_run(
            session,
            payload_task_id=active_earlier.task.task_id,
            payload_schedule_id=active_earlier.schedule.schedule_id,
            payload_run_id=None,
            planned_start_at=active_earlier_at,
            occurrence_key=occurrence_key_for_datetime(active_earlier_at),
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        await repo.mark_run_queued(session, run_id=materialized.run_id)
        await repo.mark_run_running(session, run_id=materialized.run_id)
        await repo.mark_run_failed(
            session,
            run_id=materialized.run_id,
            failure_reason="Executor failed",
        )
        active_earlier.schedule.next_run_at = active_earlier_at
        assert one_time.task.execution_mode is ExecutionMode.ONE_TIME

    todo = await repo.list_recurring_todo(session)
    active_only = await repo.list_recurring_todo(session, include_paused=False)

    assert [item.task.title for item in todo.items] == [
        "Active earlier",
        "Active later",
        "Paused recent",
        "Paused old",
    ]
    assert todo.total == 4
    assert todo.items[0].task.task_status is TaskStatus.SCHEDULED
    assert todo.items[0].latest_run is not None
    assert todo.items[0].latest_run.run_status is RunStatus.FAILED
    assert active_only.total == 2
    assert [item.schedule.schedule_status for item in active_only.items] == [
        ScheduleStatus.ACTIVE,
        ScheduleStatus.ACTIVE,
    ]


@pytest.mark.asyncio
async def test_calendar_projects_one_time_and_active_recurring_items(
    session: AsyncSession,
) -> None:
    occurrence_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    async with session.begin():
        one_time = await repo.create_one_time_task(
            session,
            title="One-time calendar task",
            instruction_source="Run once",
            target_working_directory="/tmp",
            planned_at=occurrence_at,
            executor=ExecutorName.DEBUG_PRINTER,
        )
        recurring = await repo.create_recurring_task(
            session,
            title="Daily calendar task",
            instruction_source="Run daily",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        paused = await repo.create_recurring_task(
            session,
            title="Paused calendar task",
            instruction_source="Do not show",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        canceled = await repo.create_one_time_task(
            session,
            title="Canceled calendar task",
            instruction_source="Do not show",
            target_working_directory="/tmp",
            planned_at=occurrence_at,
            executor=ExecutorName.DEBUG_PRINTER,
        )
        await repo.pause_recurring_task(
            session,
            task_id=paused.task.task_id,
            version=paused.schedule.version,
        )
        await repo.cancel_one_time_task(
            session,
            task_id=canceled.task.task_id,
            version=canceled.schedule.version,
        )

    calendar = await repo.list_calendar_items(
        session,
        window_from=occurrence_at - timedelta(minutes=1),
        window_to=occurrence_at + timedelta(minutes=1),
    )

    assert calendar.total == 2
    assert [item.task.title for item in calendar.items] == [
        "Daily calendar task",
        "One-time calendar task",
    ]
    assert {item.task.task_id for item in calendar.items} == {
        one_time.task.task_id,
        recurring.task.task_id,
    }


@pytest.mark.asyncio
async def test_occurrence_override_moves_and_cancels_single_occurrence(
    session: AsyncSession,
) -> None:
    original_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    moved_at = datetime(2030, 1, 1, 2, 0, tzinfo=UTC)
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily override task",
            instruction_source="Original instructions",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        override = await repo.upsert_occurrence_override(
            session,
            task_id=bundle.task.task_id,
            version=bundle.schedule.version,
            original_occurrence_at=original_at,
            planned_at=moved_at,
            instruction_source="Override instructions",
        )
        task_id = bundle.task.task_id
        schedule_version = bundle.schedule.version

    calendar = await repo.list_calendar_items(
        session,
        window_from=original_at - timedelta(minutes=1),
        window_to=moved_at + timedelta(minutes=1),
    )
    assert calendar.total == 1
    assert calendar.items[0].occurrence_at == moved_at
    assert calendar.items[0].occurrence_override is not None
    assert override.override_instruction_delta == "Override instructions"
    await session.rollback()

    async with session.begin():
        canceled = await repo.cancel_occurrence(
            session,
            task_id=task_id,
            version=schedule_version,
            original_occurrence_at=original_at,
        )

    assert canceled.override_status.value == "canceled"
    calendar_after_cancel = await repo.list_calendar_items(
        session,
        window_from=original_at - timedelta(minutes=1),
        window_to=moved_at + timedelta(minutes=1),
    )
    assert calendar_after_cancel.total == 0


@pytest.mark.asyncio
async def test_upsert_occurrence_override_creates_rescheduled_run(
    session: AsyncSession,
) -> None:
    original_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    moved_at = datetime(2030, 1, 1, 2, 0, tzinfo=UTC)
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily override task",
            instruction_source="Original instructions",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        override = await repo.upsert_occurrence_override(
            session,
            task_id=bundle.task.task_id,
            version=bundle.schedule.version,
            original_occurrence_at=original_at,
            planned_at=moved_at,
            instruction_source="Override instructions",
        )

    assert override.rescheduled_run_id is not None
    rescheduled_run = await repo.get_run(session, override.rescheduled_run_id)
    assert rescheduled_run.run_status is RunStatus.PLANNED
    assert rescheduled_run.planned_start_at.replace(tzinfo=UTC) == moved_at
    assert rescheduled_run.occurrence_key == occurrence_key_for_datetime(moved_at)


@pytest.mark.asyncio
async def test_upsert_occurrence_override_removes_rescheduled_run(
    session: AsyncSession,
) -> None:
    original_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    moved_at = datetime(2030, 1, 1, 2, 0, tzinfo=UTC)
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily override task",
            instruction_source="Original instructions",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        override = await repo.upsert_occurrence_override(
            session,
            task_id=bundle.task.task_id,
            version=bundle.schedule.version,
            original_occurrence_at=original_at,
            planned_at=moved_at,
            instruction_source="Override instructions",
        )
        run_id = override.rescheduled_run_id
        assert run_id is not None

    async with session.begin():
        updated = await repo.upsert_occurrence_override(
            session,
            task_id=bundle.task.task_id,
            version=bundle.schedule.version,
            original_occurrence_at=original_at,
            instruction_source="Instruction-only override",
        )

    assert updated.rescheduled_run_id is None
    canceled_run = await repo.get_run(session, run_id)
    assert canceled_run.run_status is RunStatus.CANCELED


@pytest.mark.asyncio
async def test_cancel_occurrence_cancels_rescheduled_run(
    session: AsyncSession,
) -> None:
    original_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    moved_at = datetime(2030, 1, 1, 2, 0, tzinfo=UTC)
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily override task",
            instruction_source="Original instructions",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        override = await repo.upsert_occurrence_override(
            session,
            task_id=bundle.task.task_id,
            version=bundle.schedule.version,
            original_occurrence_at=original_at,
            planned_at=moved_at,
            instruction_source="Override instructions",
        )
        run_id = override.rescheduled_run_id
        assert run_id is not None

    async with session.begin():
        canceled = await repo.cancel_occurrence(
            session,
            task_id=bundle.task.task_id,
            version=bundle.schedule.version,
            original_occurrence_at=original_at,
        )

    assert canceled.override_status is OccurrenceOverrideStatus.CANCELED
    canceled_run = await repo.get_run(session, run_id)
    assert canceled_run.run_status is RunStatus.CANCELED


@pytest.mark.asyncio
async def test_materialize_run_skips_rescheduled_occurrence(
    session: AsyncSession,
) -> None:
    original_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    moved_at = datetime(2030, 1, 1, 2, 0, tzinfo=UTC)
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily override task",
            instruction_source="Original instructions",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        _ = await repo.upsert_occurrence_override(
            session,
            task_id=bundle.task.task_id,
            version=bundle.schedule.version,
            original_occurrence_at=original_at,
            planned_at=moved_at,
            instruction_source="Override instructions",
        )

    materialized = await repo.materialize_run(
        session,
        payload_task_id=bundle.task.task_id,
        payload_schedule_id=bundle.schedule.schedule_id,
        payload_run_id=None,
        planned_start_at=original_at,
        occurrence_key=occurrence_key_for_datetime(original_at),
        workflow_id="wf-original-time",
        run_workspace_root="/tmp/vesperaflow-runs",
    )

    assert materialized.run_status is RunStatus.CANCELED
    assert materialized.execution_snapshot.planned_start_at == original_at


@pytest.mark.asyncio
async def test_materialize_run_finds_override_despite_microsecond_drift(
    session: AsyncSession,
) -> None:
    original_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    moved_at = datetime(2030, 1, 1, 2, 0, tzinfo=UTC)
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily microsecond drift task",
            instruction_source="Original instructions",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
            executor=ExecutorName.DEBUG_PRINTER,
        )
        _ = await repo.upsert_occurrence_override(
            session,
            task_id=bundle.task.task_id,
            version=bundle.schedule.version,
            original_occurrence_at=original_at,
            planned_at=moved_at,
            instruction_source="Override instructions",
        )

    # Temporal workflow_start_time may carry microseconds; ensure the original
    # recurring occurrence is still identified and skipped (CANCELED) so the
    # independent one-time schedule can execute at the override time.
    planned_with_microseconds = original_at.replace(microsecond=123456)
    materialized = await repo.materialize_run(
        session,
        payload_task_id=bundle.task.task_id,
        payload_schedule_id=bundle.schedule.schedule_id,
        payload_run_id=None,
        planned_start_at=planned_with_microseconds,
        occurrence_key=occurrence_key_for_datetime(planned_with_microseconds),
        workflow_id="wf-override-drift",
        run_workspace_root="/tmp/vesperaflow-runs",
    )
    assert materialized.run_status is RunStatus.CANCELED


@pytest.mark.asyncio
async def test_history_lists_completed_and_failed_runs_in_reverse_finished_order(
    session: AsyncSession,
) -> None:
    older_finished_at = datetime(2026, 4, 25, 9, 0, tzinfo=UTC)
    newer_finished_at = datetime(2026, 4, 25, 10, 0, tzinfo=UTC)
    async with session.begin():
        completed = await repo.create_one_time_task(
            session,
            title="Completed research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )
        failed = await repo.create_one_time_task(
            session,
            title="Failed research",
            instruction_source="Find more updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=2),
        )
        planned = await repo.create_one_time_task(
            session,
            title="Still planned",
            instruction_source="Wait for later",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=3),
        )

        await repo.mark_run_queued(session, run_id=completed.run.run_id)
        await repo.mark_run_running(session, run_id=completed.run.run_id)
        completed_run = await repo.mark_run_completed(
            session,
            run_id=completed.run.run_id,
            result_summary="Done",
        )
        completed_run.finished_at = older_finished_at

        await repo.mark_run_queued(session, run_id=failed.run.run_id)
        await repo.mark_run_running(session, run_id=failed.run.run_id)
        failed_run = await repo.mark_run_failed(
            session,
            run_id=failed.run.run_id,
            failure_reason="Executor failed",
        )
        failed_run.finished_at = newer_finished_at
        assert planned.run.run_status is RunStatus.PLANNED

    history = await repo.list_history(session)

    assert history.total == 2
    assert [item.run_id for item in history.items] == [
        failed.run.run_id,
        completed.run.run_id,
    ]
    assert history.items[0].title == "Failed research"


@pytest.mark.asyncio
async def test_history_filters_by_status_mode_and_finished_window(
    session: AsyncSession,
) -> None:
    finished_at = datetime(2026, 4, 25, 9, 0, tzinfo=UTC)
    async with session.begin():
        completed = await repo.create_one_time_task(
            session,
            title="Completed research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )
        failed = await repo.create_one_time_task(
            session,
            title="Failed research",
            instruction_source="Find more updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=2),
        )

        await repo.mark_run_queued(session, run_id=completed.run.run_id)
        await repo.mark_run_running(session, run_id=completed.run.run_id)
        completed_run = await repo.mark_run_completed(
            session,
            run_id=completed.run.run_id,
            result_summary="Done",
        )
        completed_run.finished_at = finished_at

        await repo.mark_run_queued(session, run_id=failed.run.run_id)
        await repo.mark_run_running(session, run_id=failed.run.run_id)
        failed_run = await repo.mark_run_failed(
            session,
            run_id=failed.run.run_id,
            failure_reason="Executor failed",
        )
        failed_run.finished_at = finished_at + timedelta(hours=3)

    history = await repo.list_history(
        session,
        status=RunStatus.COMPLETED,
        execution_mode=completed.task.execution_mode,
        finished_from=finished_at - timedelta(minutes=1),
        finished_to=finished_at + timedelta(minutes=1),
    )
    non_history_status = await repo.list_history(session, status=RunStatus.RUNNING)
    limited = await repo.list_history(session, limit=1, offset=1)

    assert history.total == 1
    assert history.items[0].run_id == completed.run.run_id
    assert non_history_status.total == 0
    assert non_history_status.items == []
    assert limited.total == 2
    assert len(limited.items) == 1


@pytest.mark.asyncio
async def test_run_preview_lists_support_filters_and_truncation(
    session: AsyncSession,
) -> None:
    first_planned = datetime(2026, 4, 30, 0, 0, tzinfo=UTC)
    second_planned = datetime(2026, 5, 1, 0, 0, tzinfo=UTC)
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Preview task",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
        )
        first = await repo.materialize_run(
            session,
            payload_task_id=bundle.task.task_id,
            payload_schedule_id=bundle.schedule.schedule_id,
            payload_run_id=None,
            planned_start_at=first_planned,
            occurrence_key=occurrence_key_for_datetime(first_planned),
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        await repo.mark_run_queued(session, run_id=first.run_id)
        await repo.mark_run_running(session, run_id=first.run_id)
        _ = await repo.mark_run_failed(
            session,
            run_id=first.run_id,
            failure_reason="x" * 300,
        )
        second = await repo.materialize_run(
            session,
            payload_task_id=bundle.task.task_id,
            payload_schedule_id=bundle.schedule.schedule_id,
            payload_run_id=None,
            planned_start_at=second_planned,
            occurrence_key=occurrence_key_for_datetime(second_planned),
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        await repo.mark_run_queued(session, run_id=second.run_id)
        await repo.mark_run_running(session, run_id=second.run_id)
        _ = await repo.mark_run_completed(
            session,
            run_id=second.run_id,
            result_summary="Done",
        )

    failed_only = await repo.list_run_previews_for_task(
        session,
        task_id=bundle.task.task_id,
        status=RunStatus.FAILED,
        limit=1,
        offset=0,
    )

    assert failed_only.total == 1
    assert len(failed_only.items) == 1
    assert failed_only.items[0].run_status is RunStatus.FAILED
    assert failed_only.items[0].outcome_source == "failure_reason"
    assert failed_only.items[0].outcome_truncated is True
    assert failed_only.items[0].outcome_preview is not None
    assert failed_only.items[0].outcome_preview.endswith("...")
    assert len(failed_only.items[0].outcome_preview) == 80


@pytest.mark.asyncio
async def test_run_reader_context_returns_adjacent_runs_in_archive_order(
    session: AsyncSession,
) -> None:
    oldest = datetime(2026, 4, 30, 0, 0, tzinfo=UTC)
    middle = datetime(2026, 5, 1, 0, 0, tzinfo=UTC)
    newest = datetime(2026, 5, 2, 0, 0, tzinfo=UTC)
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Reader task",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Asia/Hong_Kong",
        )
        first_run = await repo.materialize_run(
            session,
            payload_task_id=bundle.task.task_id,
            payload_schedule_id=bundle.schedule.schedule_id,
            payload_run_id=None,
            planned_start_at=oldest,
            occurrence_key=occurrence_key_for_datetime(oldest),
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        second_run = await repo.materialize_run(
            session,
            payload_task_id=bundle.task.task_id,
            payload_schedule_id=bundle.schedule.schedule_id,
            payload_run_id=None,
            planned_start_at=middle,
            occurrence_key=occurrence_key_for_datetime(middle),
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        third_run = await repo.materialize_run(
            session,
            payload_task_id=bundle.task.task_id,
            payload_schedule_id=bundle.schedule.schedule_id,
            payload_run_id=None,
            planned_start_at=newest,
            occurrence_key=occurrence_key_for_datetime(newest),
            workflow_id="vesperaflow-recurring-workflow",
            run_workspace_root="/tmp/vesperaflow-runs",
        )
        first_id = first_run.run_id
        second_id = second_run.run_id
        third_id = third_run.run_id

    middle_context = await repo.get_run_reader_context(
        session,
        task_id=bundle.task.task_id,
        run_id=second_id,
    )
    newest_context = await repo.get_run_reader_context(
        session,
        task_id=bundle.task.task_id,
        run_id=third_id,
    )
    oldest_context = await repo.get_run_reader_context(
        session,
        task_id=bundle.task.task_id,
        run_id=first_id,
    )

    assert middle_context.run.run_id == second_id
    assert middle_context.previous_run_id == third_id
    assert middle_context.next_run_id == first_id
    assert newest_context.previous_run_id is None
    assert newest_context.next_run_id == second_id
    assert oldest_context.previous_run_id == second_id
    assert oldest_context.next_run_id is None


@pytest.mark.asyncio
async def test_templates_can_be_listed_updated_and_archived(
    session: AsyncSession,
) -> None:
    async with session.begin():
        template = await repo.create_template(
            session,
            name="Nightly research",
            description="Reusable research",
            instruction_source="Find updates",
            default_task_title="Nightly run",
            default_target_working_directory="/tmp",
            default_execution_mode=ExecutionMode.ONE_TIME,
            default_schedule_type=ScheduleType.SINGLE_RUN,
            default_executor=ExecutorName.DEBUG_PRINTER,
        )
        template_id = template.template_id
        template_version = template.version

    active_templates = await repo.list_templates(session)
    assert active_templates.total == 1
    assert active_templates.items[0].template_id == template_id
    await session.rollback()

    async with session.begin():
        updated = await repo.update_template(
            session,
            template_id=template_id,
            version=template_version,
            name="Updated research",
            description=None,
            set_description=True,
            instruction_source="Find updated details",
            default_target_working_directory=None,
            set_default_target_working_directory=True,
        )
        updated_version = updated.version
        updated_name = updated.name
        updated_description = updated.description
        updated_default_target = updated.default_target_working_directory
    assert updated_version == 2
    assert updated_name == "Updated research"
    assert updated_description is None
    assert updated_default_target is None

    async with session.begin():
        archived = await repo.archive_template(
            session,
            template_id=template_id,
            version=updated_version,
        )
        archived_at = archived.archived_at

    active_after_archive = await repo.list_templates(session)
    all_after_archive = await repo.list_templates(session, include_archived=True)
    assert archived_at is not None
    assert active_after_archive.total == 0
    assert all_after_archive.total == 1


@pytest.mark.asyncio
async def test_archive_one_time_task_sets_archived_at_and_derives_archived_status(
    session: AsyncSession,
) -> None:
    planned_at = datetime.now(UTC) + timedelta(hours=1)
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=planned_at,
        )
    task_id = bundle.task.task_id
    task_version = bundle.task.version

    async with session.begin():
        archived = await repo.archive_task(
            session,
            task_id=task_id,
            version=task_version,
        )

    assert archived.archived_at is not None
    assert archived.task_status is TaskStatus.ARCHIVED
    assert archived.version == task_version + 1


@pytest.mark.asyncio
async def test_archive_recurring_task_sets_archived_at_and_derives_archived_status(
    session: AsyncSession,
) -> None:
    async with session.begin():
        bundle = await repo.create_recurring_task(
            session,
            title="Daily standup",
            instruction_source="Summarize progress",
            target_working_directory="/tmp",
            recurrence_rule="FREQ=DAILY;BYHOUR=9;BYMINUTE=0;BYSECOND=0",
            recurrence_timezone="Asia/Taipei",
        )
    task_id = bundle.task.task_id
    task_version = bundle.task.version

    async with session.begin():
        archived = await repo.archive_task(
            session,
            task_id=task_id,
            version=task_version,
        )

    assert archived.archived_at is not None
    assert archived.task_status is TaskStatus.ARCHIVED
    assert archived.version == task_version + 1


@pytest.mark.asyncio
async def test_archive_running_task_rejected(
    session: AsyncSession,
) -> None:
    planned_at = datetime.now(UTC) + timedelta(hours=1)
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=planned_at,
        )
        run = await repo.get_latest_run(session, bundle.task.task_id)
        assert run is not None
        run.run_status = RunStatus.RUNNING
        run.actual_start_at = utc_now()
        await repo._recompute_task_status(session, bundle.task)

    with pytest.raises(
        InvalidStateTransitionError, match="running tasks cannot be archived"
    ):
        async with session.begin():
            await repo.archive_task(
                session,
                task_id=bundle.task.task_id,
                version=bundle.task.version,
            )


@pytest.mark.asyncio
async def test_unarchive_task_clears_archived_at_and_restores_status(
    session: AsyncSession,
) -> None:
    planned_at = datetime.now(UTC) + timedelta(hours=1)
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=planned_at,
        )
    task_id = bundle.task.task_id

    async with session.begin():
        archived = await repo.archive_task(
            session,
            task_id=task_id,
            version=bundle.task.version,
        )
    archived_version = archived.version

    async with session.begin():
        restored = await repo.unarchive_task(
            session,
            task_id=task_id,
            version=archived_version,
        )

    assert restored.task.archived_at is None
    assert restored.task.task_status is TaskStatus.SCHEDULED
    assert restored.task.version == archived_version + 1


@pytest.mark.asyncio
async def test_unarchive_non_archived_task_rejected(
    session: AsyncSession,
) -> None:
    planned_at = datetime.now(UTC) + timedelta(hours=1)
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=planned_at,
        )

    with pytest.raises(InvalidStateTransitionError, match="task is not archived"):
        async with session.begin():
            await repo.unarchive_task(
                session,
                task_id=bundle.task.task_id,
                version=bundle.task.version,
            )


@pytest.mark.asyncio
async def test_template_instantiation_copies_fields_without_tracking_edits(
    session: AsyncSession,
) -> None:
    planned_at = datetime.now(UTC) + timedelta(hours=1)
    async with session.begin():
        template = await repo.create_template(
            session,
            name="Research template",
            description=None,
            instruction_source="Original instructions",
            default_task_title="Original title",
            default_target_working_directory="/tmp",
            default_execution_mode=ExecutionMode.ONE_TIME,
            default_schedule_type=ScheduleType.SINGLE_RUN,
            default_executor=ExecutorName.PI,
        )
        bundle = await repo.instantiate_one_time_task_from_template(
            session,
            template_id=template.template_id,
            target_working_directory=None,
            planned_at=planned_at,
        )
        await repo.update_template(
            session,
            template_id=template.template_id,
            version=template.version,
            name="Edited template",
            instruction_source="Edited instructions",
            default_task_title="Edited title",
        )

    detail = await repo.get_task_detail(session, bundle.task.task_id)
    assert detail.task.template_id == template.template_id
    assert detail.task.title == "Original title"
    assert detail.task.instruction_source == "Original instructions"
    assert detail.task.target_working_directory == "/tmp"
    assert detail.task.executor is ExecutorName.PI


@pytest.mark.asyncio
async def test_archived_template_cannot_be_instantiated_but_tasks_remain_readable(
    session: AsyncSession,
) -> None:
    async with session.begin():
        template = await repo.create_template(
            session,
            name="Research template",
            description=None,
            instruction_source="Original instructions",
            default_task_title="Original title",
            default_target_working_directory=None,
            default_execution_mode=ExecutionMode.ONE_TIME,
            default_schedule_type=ScheduleType.SINGLE_RUN,
            default_executor=ExecutorName.DEBUG_PRINTER,
        )
        bundle = await repo.instantiate_one_time_task_from_template(
            session,
            template_id=template.template_id,
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )
        task_id = bundle.task.task_id
        template_id = template.template_id
        await repo.archive_template(
            session,
            template_id=template_id,
            version=template.version,
        )

    detail = await repo.get_task_detail(session, task_id)
    assert detail.task.title == "Original title"
    await session.rollback()

    with pytest.raises(
        InvalidStateTransitionError,
        match="archived templates cannot be instantiated",
    ):
        async with session.begin():
            await repo.instantiate_one_time_task_from_template(
                session,
                template_id=template_id,
                target_working_directory="/tmp",
                planned_at=datetime.now(UTC) + timedelta(hours=2),
            )


@pytest.mark.asyncio
async def test_template_instantiation_requires_explicit_executor_or_default(
    session: AsyncSession,
) -> None:
    async with session.begin():
        template = await repo.create_template(
            session,
            name="Research template",
            description=None,
            instruction_source="Original instructions",
            default_task_title="Original title",
            default_target_working_directory="/tmp",
            default_execution_mode=ExecutionMode.ONE_TIME,
            default_schedule_type=ScheduleType.SINGLE_RUN,
        )

    with pytest.raises(
        ValueError,
        match="template instantiation requires executor_profile_id or executor",
    ):
        async with session.begin():
            await repo.instantiate_one_time_task_from_template(
                session,
                template_id=template.template_id,
                target_working_directory=None,
                planned_at=datetime.now(UTC) + timedelta(hours=1),
            )
