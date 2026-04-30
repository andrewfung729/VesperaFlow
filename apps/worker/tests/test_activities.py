from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from vesperaflow_core import (
    ExecutionSnapshot,
    ExecutorName,
    ExecutorOutcome,
    RunStatus,
    ScheduleType,
    TaskRunInput,
)
from vesperaflow_store import Base, create_engine, create_session_factory
from vesperaflow_store import repositories as repo
from vesperaflow_worker.activities import TaskRunActivities
from vesperaflow_worker.executors.base import ExecutorAdapter
from vesperaflow_worker.settings import WorkerSettings


class FakeExecutor(ExecutorAdapter):
    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        _ = snapshot
        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary="Sensitive executor output",
            terminal_code="fake_completed",
        )


@pytest_asyncio.fixture
async def activity_context(tmp_path) -> AsyncIterator[tuple[str, str, str]]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}"
    engine = create_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        async with session.begin():
            bundle = await repo.create_one_time_task(
                session,
                title="Activity task",
                instruction_source="Sensitive prompt text",
                target_working_directory="/tmp",
                planned_at=datetime.now(UTC) + timedelta(hours=1),
                executor=ExecutorName.DEBUG_PRINTER,
            )
            if bundle.run is None:
                raise AssertionError("one-time task should create a planned run")
            run_id = bundle.run.run_id
            task_id = bundle.task.task_id
    await engine.dispose()
    yield database_url, task_id, run_id


@pytest.mark.asyncio
async def test_execute_agent_run_records_events_and_sanitized_logs(
    activity_context: tuple[str, str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_url, task_id, run_id = activity_context
    caplog.set_level("INFO")
    activities = TaskRunActivities(
        database_url=database_url,
        executor=FakeExecutor(),
        run_workspace_root="/tmp/vesperaflow-runs",
    )
    payload = TaskRunInput(
        run_id=run_id,
        task_id=task_id,
        schedule_id="sch_123",
        planned_start_at=datetime.now(UTC),
        occurrence_key=None,
        schedule_type=ScheduleType.SINGLE_RUN,
        execution_snapshot=ExecutionSnapshot(
            run_id=run_id,
            task_id=task_id,
            schedule_id="sch_123",
            executor=ExecutorName.DEBUG_PRINTER,
            instruction_source="Sensitive prompt text",
            planned_start_at=datetime.now(UTC),
            working_directory="/tmp/vesperaflow-runs/run_123",
            target_working_directory="/tmp",
        ),
    )

    try:
        outcome = await activities.execute_agent_run(payload)
    finally:
        await activities.close()

    engine = create_engine(database_url)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        events = await repo.list_run_events(session, run_id=run_id)
    await engine.dispose()

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert [event.event_type for event in events.items] == [
        "executor.started",
        "executor.completed",
    ]
    assert events.items[1].details["terminal_code"] == "fake_completed"
    activity_records = [
        record
        for record in caplog.records
        if record.name.startswith("vesperaflow_worker")
    ]
    assert any(getattr(record, "run_id", None) == run_id for record in activity_records)
    assert any(
        getattr(record, "task_id", None) == task_id for record in activity_records
    )
    assert "Sensitive prompt text" not in caplog.text
    assert "Sensitive executor output" not in caplog.text
    assert database_url not in caplog.text


def test_worker_settings_log_context_is_sanitized() -> None:
    from vesperaflow_worker.main import _settings_log_context

    settings = WorkerSettings(
        database_url="postgresql+asyncpg://user:secret@localhost/db",
        anthropic_api_key="sk-secret",
        codex_model="gpt-5.2",
    )

    context = _settings_log_context(settings)

    assert context["codex_model_present"] is True
    assert "database_url" not in context
    assert "anthropic_api_key" not in context
    assert "sk-secret" not in str(context)
