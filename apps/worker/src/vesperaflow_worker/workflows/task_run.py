"""TaskRunWorkflow Temporal workflow definition."""

from datetime import timedelta
from typing import cast

from temporalio import workflow
from vesperaflow_core.contracts import ExecutorOutcome, MaterializedRun, TaskRunInput
from vesperaflow_core.enums import RunStatus, ScheduleType
from vesperaflow_core.temporal_ids import occurrence_key_for_datetime


@workflow.defn(name="TaskRunWorkflow")
class TaskRunWorkflow:
    @workflow.run
    async def run(self, payload: TaskRunInput) -> None:
        workflow.logger.info(
            "workflow.task_run.started",
            extra=_workflow_log_context(payload),
        )
        original_run_id = payload.run_id
        if payload.run_id is None:
            occurrence_key = payload.occurrence_key or occurrence_key_for_datetime(
                workflow.info().start_time
            )
            workflow.logger.info(
                "workflow.task_run.materializing_recurring_run",
                extra={
                    **_workflow_log_context(payload),
                    "occurrence_key": occurrence_key,
                },
            )
            # String-based activity lookup returns Any; cast is required because
            # importing the activity class into workflow code would pull in
            # sandbox-restricted dependencies (DB session, drivers, etc.).
            materialized = cast(
                MaterializedRun | str,
                await workflow.execute_activity(
                    "materialize_run",
                    args=[
                        payload.model_copy(update={"occurrence_key": occurrence_key}),
                        workflow.info().workflow_id,
                        workflow.info().start_time,
                    ],
                    start_to_close_timeout=timedelta(seconds=30),
                ),
            )
        else:
            workflow.logger.info(
                "workflow.task_run.loading_existing_run",
                extra=_workflow_log_context(payload),
            )
            # See cast above: string-based activity lookup returns Any.
            materialized = cast(
                MaterializedRun | str,
                await workflow.execute_activity(
                    "materialize_run",
                    payload,
                    start_to_close_timeout=timedelta(seconds=30),
                ),
            )
        if isinstance(materialized, str):
            if payload.run_id is None:
                raise ValueError("materialize_run returned no run_id")
            current_status = materialized
            run_id = payload.run_id
            execution_payload = payload
        else:
            if isinstance(materialized, dict):
                materialized = MaterializedRun.model_validate(materialized)
            current_status = materialized.run_status.value
            run_id = materialized.run_id
            execution_payload = payload.model_copy(
                update={
                    "run_id": run_id,
                    "planned_start_at": (
                        materialized.execution_snapshot.planned_start_at
                    ),
                    "execution_snapshot": materialized.execution_snapshot,
                }
            )
        if current_status == RunStatus.CANCELED.value:
            workflow.logger.info(
                "workflow.task_run.pre_execution_canceled",
                extra=_workflow_log_context(execution_payload, run_id=run_id),
            )
            return
        workflow_now = workflow.now()
        if execution_payload.planned_start_at > workflow_now:
            workflow.logger.info(
                "workflow.task_run.sleep_scheduled",
                extra=_workflow_log_context(execution_payload, run_id=run_id),
            )
            await workflow.sleep(execution_payload.planned_start_at - workflow_now)
            workflow.logger.info(
                "workflow.task_run.sleep_completed",
                extra=_workflow_log_context(execution_payload, run_id=run_id),
            )

        workflow.logger.info(
            "workflow.task_run.queueing_run",
            extra=_workflow_log_context(execution_payload, run_id=run_id),
        )
        await workflow.execute_activity(
            "mark_run_queued",
            args=[run_id, workflow.info().workflow_id],
            start_to_close_timeout=timedelta(seconds=30),
        )
        workflow.logger.info(
            "workflow.task_run.marking_running",
            extra=_workflow_log_context(execution_payload, run_id=run_id),
        )
        await workflow.execute_activity(
            "mark_run_running",
            run_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        workflow.logger.info(
            "workflow.task_run.executor_starting",
            extra=_workflow_log_context(execution_payload, run_id=run_id),
        )
        # See cast above: string-based activity lookup returns Any.
        outcome = cast(
            ExecutorOutcome,
            await workflow.execute_activity(
                "execute_agent_run",
                execution_payload,
                schedule_to_close_timeout=timedelta(hours=6),
                heartbeat_timeout=timedelta(minutes=30),
            ),
        )
        if isinstance(outcome, dict):
            outcome = ExecutorOutcome.model_validate(outcome)

        workflow.logger.info(
            "workflow.task_run.terminal_branch_selected",
            extra={
                **_workflow_log_context(execution_payload, run_id=run_id),
                "terminal_status": outcome.terminal_status.value,
                "terminal_code": outcome.terminal_code,
            },
        )
        if outcome.terminal_status is RunStatus.COMPLETED:
            await workflow.execute_activity(
                "mark_run_completed",
                args=[run_id, outcome.result_summary],
                start_to_close_timeout=timedelta(seconds=30),
            )
        elif outcome.terminal_status is RunStatus.CANCELED:
            await workflow.execute_activity(
                "mark_run_canceled",
                args=[run_id, outcome.failure_reason],
                start_to_close_timeout=timedelta(seconds=30),
            )
        else:
            await workflow.execute_activity(
                "mark_run_failed",
                args=[
                    run_id,
                    outcome.failure_reason
                    or outcome.terminal_code
                    or "executor_failed",
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

        if (
            original_run_id is not None
            and payload.schedule_id is not None
            and payload.schedule_type is ScheduleType.SINGLE_RUN
        ):
            workflow.logger.info(
                "workflow.task_run.completing_single_run_schedule",
                extra=_workflow_log_context(execution_payload, run_id=run_id),
            )
            await workflow.execute_activity(
                "complete_single_run_schedule",
                payload.schedule_id,
                start_to_close_timeout=timedelta(seconds=30),
            )
        workflow.logger.info(
            "workflow.task_run.completed",
            extra=_workflow_log_context(execution_payload, run_id=run_id),
        )


def _workflow_log_context(
    payload: TaskRunInput,
    *,
    run_id: str | None = None,
) -> dict[str, object]:
    info = workflow.info()
    return {
        "workflow_id": info.workflow_id,
        "workflow_run_id": info.run_id,
        "task_id": payload.task_id,
        "schedule_id": payload.schedule_id,
        "run_id": run_id or payload.run_id,
        "executor": payload.execution_snapshot.executor.value,
    }
