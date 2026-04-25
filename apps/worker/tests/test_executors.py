import pytest
from vesperaflow_core import ExecutionSnapshot, ExecutorName, RunStatus
from vesperaflow_worker.executors import (
    DebugPrinterExecutor,
    ExecutorRouter,
    ExecutorUnavailableError,
    FakeExecutor,
    build_executor,
)


@pytest.mark.asyncio
async def test_fake_executor_success(snapshot: ExecutionSnapshot) -> None:
    outcome = await FakeExecutor().execute(snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.result_summary is not None


@pytest.mark.asyncio
async def test_fake_executor_failure(snapshot: ExecutionSnapshot) -> None:
    outcome = await FakeExecutor(fail=True).execute(snapshot)

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.failure_reason == "fake_executor_failure"


@pytest.mark.asyncio
async def test_debug_printer_executor_logs_snapshot(
    snapshot: ExecutionSnapshot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    debug_snapshot = snapshot.model_copy(
        update={"executor": ExecutorName.DEBUG_PRINTER}
    )
    caplog.set_level("INFO")

    outcome = await DebugPrinterExecutor().execute(debug_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "debug_printer_completed"
    assert outcome.result_summary == (
        "Debug printer completed run run_123 for task task_123."
    )
    assert debug_snapshot.model_dump_json() in caplog.text


@pytest.mark.asyncio
async def test_executor_router_dispatches_debug_printer(
    snapshot: ExecutionSnapshot,
) -> None:
    debug_snapshot = snapshot.model_copy(
        update={"executor": ExecutorName.DEBUG_PRINTER}
    )
    executor = build_executor("auto")

    outcome = await executor.execute(debug_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "debug_printer_completed"


@pytest.mark.asyncio
async def test_executor_router_rejects_unknown_executor(
    snapshot: ExecutionSnapshot,
) -> None:
    router = ExecutorRouter(
        claude_code=FakeExecutor(),
        debug_printer=DebugPrinterExecutor(),
    )
    invalid_snapshot = snapshot.model_copy(update={"executor": "unknown"})

    with pytest.raises(ExecutorUnavailableError, match="unknown executor"):
        await router.execute(invalid_snapshot)


@pytest.fixture
def snapshot() -> ExecutionSnapshot:
    from datetime import UTC, datetime

    return ExecutionSnapshot(
        run_id="run_123",
        task_id="task_123",
        schedule_id="sch_123",
        executor=ExecutorName.CLAUDE_CODE,
        instruction_source="Do work",
        planned_start_at=datetime.now(UTC),
        working_directory="/tmp/vesperaflow-runs/run_123",
    )
