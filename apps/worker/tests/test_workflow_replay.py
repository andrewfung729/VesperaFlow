from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from temporalio import activity, workflow
from temporalio.api.enums.v1 import EventType
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker
from vesperaflow_core import (
    ExecutionSnapshot,
    ExecutorName,
    ExecutorOutcome,
    MaterializedRun,
    RunStatus,
    ScheduleType,
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
async def test_task_run_workflow_replays_history_before_authoritative_claim_patch(
) -> None:
    history = await _legacy_completed_history()

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


@pytest.mark.asyncio
async def test_task_run_workflow_executes_and_replays_latest_materialized_snapshot(
) -> None:
    received_instructions: list[str] = []
    history = await _build_history(
        materialized_status=RunStatus.QUEUED,
        materialized_instruction="Latest database instruction",
        received_instructions=received_instructions,
    )

    result = await Replayer(
        workflows=[TaskRunWorkflow],
        workflow_runner=_pydantic_sandbox_runner,
        data_converter=pydantic_data_converter,
    ).replay_workflow(history)

    assert received_instructions == ["Latest database instruction"]
    assert result.replay_failure is None


@pytest.mark.asyncio
async def test_task_run_workflow_disables_executor_activity_retries() -> None:
    history = await _build_history()

    scheduled = next(
        event.activity_task_scheduled_event_attributes
        for event in history.events
        if event.event_type is EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED
        and event.activity_task_scheduled_event_attributes.activity_type.name
        == "execute_agent_run"
    )

    assert scheduled.retry_policy.maximum_attempts == 1


@pytest.mark.asyncio
async def test_task_run_workflow_replays_failed_history() -> None:
    history = await _build_history(
        outcome=ExecutorOutcome(
            terminal_status=RunStatus.FAILED,
            failure_reason="Simulated failure",
        ),
    )

    result = await Replayer(
        workflows=[TaskRunWorkflow],
        workflow_runner=_pydantic_sandbox_runner,
        data_converter=pydantic_data_converter,
    ).replay_workflow(history)

    assert result.replay_failure is None


@pytest.mark.asyncio
async def test_task_run_workflow_replays_canceled_history() -> None:
    history = await _build_history(
        outcome=ExecutorOutcome(
            terminal_status=RunStatus.CANCELED,
            failure_reason="Simulated cancellation",
        ),
    )

    result = await Replayer(
        workflows=[TaskRunWorkflow],
        workflow_runner=_pydantic_sandbox_runner,
        data_converter=pydantic_data_converter,
    ).replay_workflow(history)

    assert result.replay_failure is None


@pytest.mark.asyncio
async def test_task_run_workflow_replays_pre_execution_canceled_history() -> None:
    history = await _build_history(
        materialized_status=RunStatus.CANCELED,
    )

    result = await Replayer(
        workflows=[TaskRunWorkflow],
        workflow_runner=_pydantic_sandbox_runner,
        data_converter=pydantic_data_converter,
    ).replay_workflow(history)

    assert result.replay_failure is None


async def _completed_debug_printer_history(recurring: bool = False):
    return await _build_history(recurring=recurring)


async def _legacy_completed_history():
    activities: list[Callable[..., object]] = [
        _make_materialize_run(RunStatus.PLANNED),
        mark_run_queued,
        mark_run_running,
        mark_run_completed,
        complete_single_run_schedule,
        execute_agent_run,
    ]
    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as environment:
        async with Worker(
            environment.client,
            task_queue="vesperaflow-legacy-replay-test",
            workflows=[LegacyTaskRunWorkflow],
            activities=activities,
            workflow_runner=_pydantic_sandbox_runner,
        ):
            planned_at = datetime.now(UTC)
            handle = await environment.client.start_workflow(
                LegacyTaskRunWorkflow.run,
                _task_run_input(planned_at),
                id="vesperaflow-legacy-replay-test-run",
                task_queue="vesperaflow-legacy-replay-test",
            )
            await handle.result()
            return await handle.fetch_history()


async def _build_history(
    *,
    recurring: bool = False,
    materialized_status: RunStatus = RunStatus.PLANNED,
    materialized_instruction: str | None = None,
    received_instructions: list[str] | None = None,
    outcome: ExecutorOutcome | None = None,
):
    task_run_input_factory = _recurring_task_run_input if recurring else _task_run_input

    activities: list[Callable[..., object]] = [
        _make_materialize_run(
            materialized_status,
            instruction_source=materialized_instruction,
        ),
        mark_run_queued,
        _make_claim_run(
            RunStatus.CANCELED
            if materialized_status is RunStatus.CANCELED
            else RunStatus.QUEUED,
            instruction_source=materialized_instruction,
        ),
        mark_run_running,
        mark_run_completed,
        mark_run_failed,
        mark_run_canceled,
        complete_single_run_schedule,
    ]
    if outcome is not None or received_instructions is not None:
        activities.append(
            _make_execute_agent_run(
                outcome
                or ExecutorOutcome(
                    terminal_status=RunStatus.COMPLETED,
                    result_summary="Debug printer completed.",
                    terminal_code="debug_printer_completed",
                ),
                received_instructions=received_instructions,
            )
        )
    else:
        activities.append(execute_agent_run)

    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as environment:
        async with Worker(
            environment.client,
            task_queue="vesperaflow-replay-test",
            workflows=[TaskRunWorkflow],
            activities=activities,
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
        schedule_type=ScheduleType.SINGLE_RUN,
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
        schedule_type=ScheduleType.RECURRING_RULE,
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


def _make_materialize_run(
    status: RunStatus,
    run_id: str = "run_recurring_replay",
    instruction_source: str | None = None,
):
    async def fn(
        payload: TaskRunInput,
        _: str | None = None,
        __: datetime | None = None,
    ) -> str | MaterializedRun:
        if isinstance(payload, dict):
            payload = TaskRunInput.model_validate(payload)
        if payload.run_id is not None and instruction_source is None:
            return status.value
        materialized_run_id = payload.run_id or run_id
        planned_at = (
            payload.planned_start_at
            if payload.run_id is not None
            else datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
        )
        return MaterializedRun(
            run_id=materialized_run_id,
            run_status=status,
            execution_snapshot=ExecutionSnapshot(
                run_id=materialized_run_id,
                task_id=payload.task_id,
                schedule_id=payload.schedule_id,
                executor=ExecutorName.DEBUG_PRINTER,
                instruction_source=(
                    instruction_source or payload.execution_snapshot.instruction_source
                ),
                planned_start_at=planned_at,
                working_directory=f"/tmp/vesperaflow-runs/{materialized_run_id}",
                target_working_directory="/tmp",
            ),
        )

    return activity.defn(name="materialize_run")(fn)


def _make_execute_agent_run(
    outcome: ExecutorOutcome,
    *,
    received_instructions: list[str] | None = None,
):
    async def fn(payload: TaskRunInput) -> ExecutorOutcome:
        if isinstance(payload, dict):
            payload = TaskRunInput.model_validate(payload)
        if received_instructions is not None:
            received_instructions.append(payload.execution_snapshot.instruction_source)
        return outcome

    return activity.defn(name="execute_agent_run")(fn)


def _make_claim_run(
    status: RunStatus,
    *,
    instruction_source: str | None = None,
):
    async def fn(
        run_id: str,
        _: str,
        claim_at: datetime,
    ) -> MaterializedRun:
        return MaterializedRun(
            run_id=run_id,
            run_status=status,
            execution_snapshot=ExecutionSnapshot(
                run_id=run_id,
                task_id="task_replay",
                schedule_id="sch_replay",
                executor=ExecutorName.DEBUG_PRINTER,
                instruction_source=(
                    instruction_source or "Replay the completed debug-printer path."
                ),
                planned_start_at=claim_at,
                working_directory=f"/tmp/vesperaflow-runs/{run_id}",
                target_working_directory="/tmp",
            ),
        )

    return activity.defn(name="claim_run_for_execution")(fn)


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


@workflow.defn(name="TaskRunWorkflow", sandboxed=False)
class LegacyTaskRunWorkflow:
    @workflow.run
    async def run(self, payload: TaskRunInput) -> None:
        status = cast(
            str,
            await workflow.execute_activity(
                "materialize_run",
                payload,
                start_to_close_timeout=timedelta(seconds=30),
            ),
        )
        if status == RunStatus.CANCELED.value or payload.run_id is None:
            return
        workflow_now = workflow.now()
        if payload.planned_start_at > workflow_now:
            await workflow.sleep(payload.planned_start_at - workflow_now)
        await workflow.execute_activity(
            "mark_run_queued",
            args=[payload.run_id, workflow.info().workflow_id],
            start_to_close_timeout=timedelta(seconds=30),
        )
        await workflow.execute_activity(
            "mark_run_running",
            payload.run_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        outcome = cast(
            ExecutorOutcome,
            await workflow.execute_activity(
                "execute_agent_run",
                payload,
                schedule_to_close_timeout=timedelta(hours=6),
                heartbeat_timeout=timedelta(minutes=30),
            ),
        )
        if isinstance(outcome, dict):
            outcome = ExecutorOutcome.model_validate(outcome)
        await workflow.execute_activity(
            "mark_run_completed",
            args=[payload.run_id, outcome.result_summary],
            start_to_close_timeout=timedelta(seconds=30),
        )
        if payload.schedule_id is not None:
            await workflow.execute_activity(
                "complete_single_run_schedule",
                payload.schedule_id,
                start_to_close_timeout=timedelta(seconds=30),
            )
