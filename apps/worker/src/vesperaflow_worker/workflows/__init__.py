"""Temporal workflows."""

from datetime import timedelta

from temporalio import workflow
from vesperaflow_core import ExecutorOutcome, RunStatus, TaskRunInput


@workflow.defn(name="TaskRunWorkflow")
class TaskRunWorkflow:
    @workflow.run
    async def run(self, payload: TaskRunInput) -> None:
        if payload.run_id is None:
            raise ValueError("TaskRunWorkflow requires run_id for the vertical slice")

        current_status = await workflow.execute_activity(
            "materialize_run",
            payload,
            start_to_close_timeout=timedelta(seconds=30),
        )
        if current_status == RunStatus.CANCELED.value:
            return

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
        outcome = await workflow.execute_activity(
            "execute_agent_run",
            payload,
            schedule_to_close_timeout=timedelta(hours=6),
            heartbeat_timeout=timedelta(minutes=5),
        )
        if isinstance(outcome, dict):
            outcome = ExecutorOutcome.model_validate(outcome)
        if not isinstance(outcome, ExecutorOutcome):
            raise TypeError("execute_agent_run returned an invalid outcome")

        if outcome.terminal_status is RunStatus.COMPLETED:
            await workflow.execute_activity(
                "mark_run_completed",
                args=[payload.run_id, outcome.result_summary],
                start_to_close_timeout=timedelta(seconds=30),
            )
        elif outcome.terminal_status is RunStatus.CANCELED:
            await workflow.execute_activity(
                "mark_run_canceled",
                args=[payload.run_id, outcome.failure_reason],
                start_to_close_timeout=timedelta(seconds=30),
            )
        else:
            await workflow.execute_activity(
                "mark_run_failed",
                args=[
                    payload.run_id,
                    outcome.failure_reason
                    or outcome.terminal_code
                    or "executor_failed",
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

        if payload.schedule_id is not None:
            await workflow.execute_activity(
                "complete_single_run_schedule",
                payload.schedule_id,
                start_to_close_timeout=timedelta(seconds=30),
            )
