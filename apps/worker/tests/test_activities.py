from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from vesperaflow_core import (
    ExecutionSnapshot,
    ExecutorName,
    ExecutorOutcome,
    MaterializedRun,
    ProfileValidationInput,
    ProfileValidationResult,
    RunStatus,
    ScheduleType,
    TaskRunInput,
)
from vesperaflow_store import Base, create_engine, create_session_factory
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import NotFoundError
from vesperaflow_worker.activities import TaskRunActivities
from vesperaflow_worker.executors.base import ExecutorAdapter, ExecutorRuntimeConfig
from vesperaflow_worker.settings import WorkerSettings


class FakeExecutor(ExecutorAdapter):
    def __init__(self) -> None:
        self.runtime_config: ExecutorRuntimeConfig | None = None
        self.validation_runtime_config: ExecutorRuntimeConfig | None = None

    async def execute(
        self,
        snapshot: ExecutionSnapshot,
        runtime_config: ExecutorRuntimeConfig | None = None,
    ) -> ExecutorOutcome:
        _ = snapshot
        self.runtime_config = runtime_config
        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary="Sensitive executor output",
            terminal_code="fake_completed",
        )

    async def validate_profile(
        self,
        executor: ExecutorName,
        runtime_config: ExecutorRuntimeConfig,
        workspace: Path,
    ) -> ProfileValidationResult:
        _ = executor
        if not workspace.exists():
            raise AssertionError("validation workspace should exist")
        self.validation_runtime_config = runtime_config
        return ProfileValidationResult(
            ok=True,
            code="profile_validation_passed",
            message="validated",
        )


@pytest_asyncio.fixture
async def activity_context(tmp_path) -> AsyncIterator[tuple[str, str, str, str]]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}"
    engine = create_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        async with session.begin():
            profile = await repo.create_executor_profile(
                session,
                name="Debug Activity Profile",
                executor=ExecutorName.DEBUG_PRINTER,
                default_model="debug-model",
                reasoning_level="high",
                env={"VISIBLE": "1"},
                secret_env={"SECRET": "hidden"},
            )
            bundle = await repo.create_one_time_task(
                session,
                title="Activity task",
                instruction_source="Sensitive prompt text",
                target_working_directory="/tmp",
                planned_at=datetime.now(UTC) + timedelta(hours=1),
                executor=ExecutorName.DEBUG_PRINTER,
                executor_profile_id=profile.profile_id,
            )
            if bundle.run is None:
                raise AssertionError("one-time task should create a planned run")
            run_id = bundle.run.run_id
            task_id = bundle.task.task_id
            profile_id = profile.profile_id
    await engine.dispose()
    yield database_url, task_id, run_id, profile_id


@pytest.mark.asyncio
async def test_execute_agent_run_records_events_and_sanitized_logs(
    activity_context: tuple[str, str, str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_url, task_id, run_id, profile_id = activity_context
    caplog.set_level("INFO")
    fake_executor = FakeExecutor()
    activities = TaskRunActivities(
        database_url=database_url,
        executor=fake_executor,
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
            executor_profile_id=profile_id,
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
    assert fake_executor.runtime_config is not None
    assert fake_executor.runtime_config.default_model == "debug-model"
    assert fake_executor.runtime_config.reasoning_level == "high"
    assert fake_executor.runtime_config.env == {"VISIBLE": "1", "SECRET": "hidden"}
    assert [event.event_type for event in events.items] == [
        "executor.started",
        "executor.completed",
    ]
    assert events.items[1].details["terminal_code"] == "fake_completed"
    assert events.items[0].details["executor_profile_id"] == profile_id
    assert events.items[0].details["executor_model"] == "debug-model"
    assert events.items[0].details["executor_reasoning_level"] == "high"
    assert "hidden" not in str(events.items[0].details)
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


@pytest.mark.asyncio
async def test_claim_existing_run_uses_latest_database_snapshot(
    activity_context: tuple[str, str, str, str],
) -> None:
    database_url, task_id, run_id, _ = activity_context
    engine = create_engine(database_url)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        async with session.begin():
            task = await repo.get_task(session, task_id)
            run = await repo.get_run(session, run_id)
            updated_instruction = "Updated after Temporal schedule creation"
            _ = await repo.update_task(
                session,
                task_id=task_id,
                version=task.version,
                instruction_source=updated_instruction,
            )
            planned_start_at = run.planned_start_at
    await engine.dispose()

    activities = TaskRunActivities(
        database_url=database_url,
        executor=FakeExecutor(),
        run_workspace_root="/tmp/vesperaflow-runs",
    )
    try:
        materialized = await activities.claim_run_for_execution(
            run_id,
            "vesperaflow.run.test",
            planned_start_at,
        )
    finally:
        await activities.close()

    assert isinstance(materialized, MaterializedRun)
    assert materialized.run_status is RunStatus.QUEUED
    assert materialized.execution_snapshot.instruction_source == updated_instruction


@pytest.mark.asyncio
async def test_validate_executor_profile_loads_handoff_and_removes_secret_record(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'validation.db'}"
    engine = create_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        async with session.begin():
            handoff = await repo.create_profile_validation_handoff(
                session,
                executor=ExecutorName.CODEX,
                default_model="gpt-5.2",
                reasoning_level="xhigh",
                env={"VISIBLE": "1"},
                secret_env={"TOKEN": "secret"},
            )
            validation_input = ProfileValidationInput(
                handoff_id=handoff.handoff_id,
                executor=handoff.executor,
                default_model=handoff.default_model,
                reasoning_level=handoff.reasoning_level,
            )
    fake_executor = FakeExecutor()
    activities = TaskRunActivities(
        database_url=database_url,
        executor=fake_executor,
        run_workspace_root="/tmp/vesperaflow-runs",
    )

    try:
        result = await activities.validate_executor_profile(validation_input)
    finally:
        await activities.close()

    async with session_factory() as session:
        with pytest.raises(NotFoundError):
            await repo.get_profile_validation_handoff(session, handoff.handoff_id)
    await engine.dispose()

    assert result.ok is True
    assert fake_executor.validation_runtime_config is not None
    assert fake_executor.validation_runtime_config.default_model == "gpt-5.2"
    assert fake_executor.validation_runtime_config.reasoning_level == "xhigh"
    assert fake_executor.validation_runtime_config.env == {
        "VISIBLE": "1",
        "TOKEN": "secret",
    }


def test_worker_settings_log_context_is_sanitized() -> None:
    from vesperaflow_worker.main import _settings_log_context

    settings = WorkerSettings(
        database_url="postgresql+asyncpg://user:secret@localhost/db",
    )

    context = _settings_log_context(settings)

    assert "database_url" not in context
