from datetime import UTC, datetime

import pytest
from temporalio import activity
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker
from vesperaflow_core import (
    ExecutionSnapshot,
    ExecutorName,
    ExecutorOutcome,
    RunStatus,
    TaskRunInput,
)
from vesperaflow_worker.main import _pydantic_sandbox_runner
from vesperaflow_worker.workflows import TaskRunWorkflow


@pytest.mark.asyncio
async def test_task_run_workflow_replays_completed_history() -> None:
    history = await _completed_debug_printer_history()

    result = await Replayer(
        workflows=[TaskRunWorkflow],
        workflow_runner=_pydantic_sandbox_runner,
        data_converter=pydantic_data_converter,
    ).replay_workflow(history)

    assert result.replay_failure is None


async def _completed_debug_printer_history():
    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as environment:
        async with Worker(
            environment.client,
            task_queue="vesperaflow-replay-test",
            workflows=[TaskRunWorkflow],
            activities=[
                materialize_run,
                mark_run_queued,
                mark_run_running,
                execute_agent_run,
                mark_run_completed,
                mark_run_failed,
                mark_run_canceled,
                complete_single_run_schedule,
            ],
            workflow_runner=_pydantic_sandbox_runner,
        ):
            planned_at = datetime.now(UTC)
            handle = await environment.client.start_workflow(
                TaskRunWorkflow.run,
                _task_run_input(planned_at),
                id="vesperaflow-replay-test-run",
                task_queue="vesperaflow-replay-test",
            )
            await handle.result()
            return await handle.fetch_history()


def _task_run_input(planned_at: datetime) -> TaskRunInput:
    return TaskRunInput(
        run_id="run_replay",
        task_id="task_replay",
        schedule_id="sch_replay",
        planned_start_at=planned_at,
        occurrence_key=None,
        execution_snapshot=ExecutionSnapshot(
            run_id="run_replay",
            task_id="task_replay",
            schedule_id="sch_replay",
            executor=ExecutorName.DEBUG_PRINTER,
            instruction_source="Replay the completed debug-printer path.",
            planned_start_at=planned_at,
            working_directory="/tmp/vesperaflow-runs/run_replay",
            target_working_directory="/tmp",
        ),
    )


@activity.defn(name="materialize_run")
async def materialize_run(_: TaskRunInput) -> str:
    return RunStatus.PLANNED.value


@activity.defn(name="mark_run_queued")
async def mark_run_queued(_: str, __: str) -> None:
    return None


@activity.defn(name="mark_run_running")
async def mark_run_running(_: str) -> None:
    return None


@activity.defn(name="execute_agent_run")
async def execute_agent_run(_: TaskRunInput) -> ExecutorOutcome:
    return ExecutorOutcome(
        terminal_status=RunStatus.COMPLETED,
        result_summary="Debug printer completed.",
        terminal_code="debug_printer_completed",
    )


@activity.defn(name="mark_run_completed")
async def mark_run_completed(_: str, __: str | None) -> None:
    return None


@activity.defn(name="mark_run_failed")
async def mark_run_failed(_: str, __: str) -> None:
    return None


@activity.defn(name="mark_run_canceled")
async def mark_run_canceled(_: str, __: str | None) -> None:
    return None


@activity.defn(name="complete_single_run_schedule")
async def complete_single_run_schedule(_: str) -> None:
    return None
