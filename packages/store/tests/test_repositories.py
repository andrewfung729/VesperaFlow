from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
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
async def test_create_one_time_task_persists_debug_printer_executor(
    session: AsyncSession,
) -> None:
    async with session.begin():
        bundle = await repo.create_one_time_task(
            session,
            title="Research",
            instruction_source="Find updates",
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
            executor=ExecutorName.DEBUG_PRINTER,
        )

    task = await repo.get_task(session, bundle.task.task_id)
    assert task.executor is ExecutorName.DEBUG_PRINTER


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
    assert [item.run.run_id for item in history.items] == [
        failed.run.run_id,
        completed.run.run_id,
    ]
    assert history.items[0].task.title == "Failed research"


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
    assert history.items[0].run.run_id == completed.run.run_id
    assert non_history_status.total == 0
    assert non_history_status.items == []
    assert limited.total == 2
    assert len(limited.items) == 1


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
            default_executor=ExecutorName.DEBUG_PRINTER,
        )
        bundle = await repo.instantiate_one_time_task_from_template(
            session,
            template_id=template.template_id,
            target_working_directory=None,
            planned_at=planned_at,
            install_default_executor=ExecutorName.CLAUDE_CODE,
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
    assert detail.task.executor is ExecutorName.DEBUG_PRINTER


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
        )
        bundle = await repo.instantiate_one_time_task_from_template(
            session,
            template_id=template.template_id,
            target_working_directory="/tmp",
            planned_at=datetime.now(UTC) + timedelta(hours=1),
            install_default_executor=ExecutorName.CLAUDE_CODE,
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
                install_default_executor=ExecutorName.CLAUDE_CODE,
            )
