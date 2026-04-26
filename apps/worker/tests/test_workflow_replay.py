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
    MaterializedRun,
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


@pytest.mark.asyncio
async def test_task_run_workflow_replays_recurring_materialized_history() -> None:
    history = await _completed_debug_printer_history(recurring=True)

    result = await Replayer(
        workflows=[TaskRunWorkflow],
        workflow_runner=_pydantic_sandbox_runner,
        data_converter=pydantic_data_converter,
    ).replay_workflow(history)

    assert result.replay_failure is None


async def _completed_debug_printer_history(recurring: bool = False):
    task_run_input_factory = _recurring_task_run_input if recurring else _task_run_input
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
                task_run_input_factory(planned_at),
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


def _recurring_task_run_input(planned_at: datetime) -> TaskRunInput:
    return TaskRunInput(
        run_id=None,
        task_id="task_recurring_replay",
        schedule_id="sch_recurring_replay",
        planned_start_at=planned_at,
        occurrence_key=None,
        execution_snapshot=ExecutionSnapshot(
            run_id=None,
            task_id="task_recurring_replay",
            schedule_id="sch_recurring_replay",
            executor=ExecutorName.DEBUG_PRINTER,
            instruction_source="Replay the recurring debug-printer path.",
            planned_start_at=planned_at,
            working_directory="/tmp/vesperaflow-runs/sch_recurring_replay",
            target_working_directory="/tmp",
        ),
    )


@activity.defn(name="materialize_run")
async def materialize_run(
    payload: TaskRunInput,
    _: str | None = None,
    __: datetime | None = None,
) -> str | MaterializedRun:
    if isinstance(payload, dict):
        payload = TaskRunInput.model_validate(payload)
    if payload.run_id is not None:
        return RunStatus.PLANNED.value
    planned_at = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
    return MaterializedRun(
        run_id="run_recurring_replay",
        run_status=RunStatus.PLANNED,
        execution_snapshot=ExecutionSnapshot(
            run_id="run_recurring_replay",
            task_id=payload.task_id,
            schedule_id=payload.schedule_id,
            executor=ExecutorName.DEBUG_PRINTER,
            instruction_source=payload.execution_snapshot.instruction_source,
            planned_start_at=planned_at,
            working_directory="/tmp/vesperaflow-runs/run_recurring_replay",
            target_working_directory="/tmp",
        ),
    )


@activity.defn(name="mark_run_queued")
async def mark_run_queued(_: str, __: str) -> None:
    return None


@activity.defn(name="mark_run_running")
async def mark_run_running(_: str) -> None:
    return None


@activity.defn(name="execute_agent_run")
async def execute_agent_run(payload: TaskRunInput) -> ExecutorOutcome:
    if isinstance(payload, dict):
        TaskRunInput.model_validate(payload)
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
