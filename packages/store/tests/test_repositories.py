from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import ExecutorName, RunStatus, ScheduleStatus, TaskStatus
from vesperaflow_store import Base, create_engine, create_session_factory
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import ConflictError


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
