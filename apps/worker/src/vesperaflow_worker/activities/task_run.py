"""TaskRunActivities Temporal activity definitions."""

import asyncio
import logging
import tempfile
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from temporalio import activity
from vesperaflow_core import (
    ExecutorOutcome,
    MaterializedRun,
    ProfileValidationInput,
    ProfileValidationResult,
    RunStatus,
    TaskRunInput,
)
from vesperaflow_store import create_engine, create_session_factory
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import InvalidStateTransitionError, NotFoundError

from vesperaflow_worker.executors.base import (
    ExecutorAdapter,
    ExecutorRuntimeConfig,
    ExecutorUnavailableError,
)

logger = logging.getLogger(__name__)


class ActivityEventContext(TypedDict, total=False):
    temporal_workflow_id: str | None
    temporal_workflow_run_id: str | None
    activity_type: str | None
    activity_attempt: int | None


class TaskRunActivities:
    def __init__(
        self,
        database_url: str,
        executor: ExecutorAdapter,
        run_workspace_root: str,
    ) -> None:
        engine = create_engine(database_url)
        self._engine: AsyncEngine = engine
        self._session_factory: async_sessionmaker[AsyncSession] = (
            create_session_factory(engine)
        )
        self._executor: ExecutorAdapter = executor
        self._run_workspace_root: str = run_workspace_root

    @activity.defn(name="materialize_run")
    async def materialize_run(
        self,
        payload: TaskRunInput,
        workflow_id: str | None = None,
        workflow_start_time: datetime | None = None,
    ) -> MaterializedRun | str:
        if isinstance(payload, dict):
            payload = TaskRunInput.model_validate(payload)
        logger.info(
            "activity.materialize_run.starting",
            extra=_activity_log_context(payload=payload),
        )
        try:
            if payload.run_id is not None and workflow_id is None:
                async with self._session_factory() as session:
                    async with session.begin():
                        run = await repo.get_run(session, payload.run_id)
                        _ = await repo.record_run_event(
                            session,
                            run_id=run.run_id,
                            event_type="run.materialization_reused",
                            message="Existing run loaded for execution.",
                            details={"run_status": run.run_status.value},
                            **_activity_event_context(),
                        )
                        logger.info(
                            "activity.materialize_run.succeeded",
                            extra=_activity_log_context(
                                payload=payload,
                                run_id=run.run_id,
                                run_status=run.run_status.value,
                            ),
                        )
                        return run.run_status.value
            if workflow_id is None or workflow_start_time is None:
                raise ValueError("recurring materialization requires workflow metadata")
            async with self._session_factory() as session:
                async with session.begin():
                    materialized = await repo.materialize_run(
                        session,
                        payload_task_id=payload.task_id,
                        payload_schedule_id=payload.schedule_id,
                        payload_run_id=payload.run_id,
                        planned_start_at=workflow_start_time,
                        occurrence_key=payload.occurrence_key,
                        workflow_id=workflow_id,
                        run_workspace_root=self._run_workspace_root,
                    )
                    logger.info(
                        "activity.materialize_run.succeeded",
                        extra=_activity_log_context(
                            payload=payload,
                            run_id=materialized.run_id,
                            run_status=materialized.run_status.value,
                        ),
                    )
                    return materialized
        except Exception:
            logger.exception(
                "activity.materialize_run.failed",
                extra=_activity_log_context(payload=payload),
            )
            raise

    @activity.defn(name="validate_executor_profile")
    async def validate_executor_profile(
        self,
        payload: ProfileValidationInput,
    ) -> ProfileValidationResult:
        if isinstance(payload, dict):
            payload = ProfileValidationInput.model_validate(payload)
        logger.info(
            "activity.validate_executor_profile.starting",
            extra=_profile_validation_log_context(payload),
        )
        runtime_config: ExecutorRuntimeConfig | None = None
        try:
            runtime_config = await self._validation_runtime_config(payload)
            with tempfile.TemporaryDirectory(
                prefix="vesperaflow-profile-validation-"
            ) as workspace:
                result = await self._executor.validate_profile(
                    payload.executor,
                    runtime_config,
                    Path(workspace),
                )
            logger.info(
                "activity.validate_executor_profile.completed",
                extra={
                    **_profile_validation_log_context(payload),
                    "validation_ok": result.ok,
                    "validation_code": result.code,
                },
            )
            return result
        except Exception as exc:
            logger.exception(
                "activity.validate_executor_profile.failed",
                extra=_profile_validation_log_context(payload),
            )
            return ProfileValidationResult(
                ok=False,
                code="profile_validation_error",
                message=f"Executor profile validation failed: {exc}",
            )
        finally:
            await self._delete_validation_handoff(payload.handoff_id)

    @activity.defn(name="mark_run_queued")
    async def mark_run_queued(self, run_id: str, external_execution_ref: str) -> None:
        logger.info(
            "activity.mark_run_queued.starting",
            extra=_activity_log_context(run_id=run_id),
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    run = await repo.mark_run_queued(
                        session,
                        run_id=run_id,
                        external_execution_ref=external_execution_ref,
                        **_activity_event_context(),
                    )
                    logger.info(
                        "activity.mark_run_queued.succeeded",
                        extra=_activity_log_context(
                            run_id=run.run_id,
                            task_id=run.task_id,
                            schedule_id=run.schedule_id,
                            run_status=run.run_status.value,
                        ),
                    )
        except Exception:
            logger.exception(
                "activity.mark_run_queued.failed",
                extra=_activity_log_context(run_id=run_id),
            )
            raise

    @activity.defn(name="mark_run_running")
    async def mark_run_running(self, run_id: str) -> None:
        logger.info(
            "activity.mark_run_running.starting",
            extra=_activity_log_context(run_id=run_id),
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    run = await repo.mark_run_running(
                        session,
                        run_id=run_id,
                        **_activity_event_context(),
                    )
                    logger.info(
                        "activity.mark_run_running.succeeded",
                        extra=_activity_log_context(
                            run_id=run.run_id,
                            task_id=run.task_id,
                            schedule_id=run.schedule_id,
                            run_status=run.run_status.value,
                        ),
                    )
        except Exception:
            logger.exception(
                "activity.mark_run_running.failed",
                extra=_activity_log_context(run_id=run_id),
            )
            raise

    @activity.defn(name="execute_agent_run")
    async def execute_agent_run(self, payload: TaskRunInput) -> ExecutorOutcome:
        if isinstance(payload, dict):
            payload = TaskRunInput.model_validate(payload)
        logger.info(
            "activity.execute_agent_run.starting",
            extra=_activity_log_context(payload=payload),
        )
        runtime_config: ExecutorRuntimeConfig | None = None
        profile_error: Exception | None = None
        try:
            runtime_config = await self._executor_runtime_config(payload)
        except (InvalidStateTransitionError, NotFoundError, ValueError) as exc:
            profile_error = exc
        await self._record_executor_event(
            payload,
            event_type="executor.started",
            message="Executor invocation started.",
            details=_executor_event_details(payload, runtime_config),
        )
        heartbeat_task = asyncio.create_task(_heartbeat_loop(interval_seconds=60))
        try:
            if profile_error is not None:
                raise ExecutorUnavailableError(str(profile_error))
            outcome = await self._executor.execute(
                payload.execution_snapshot,
                runtime_config,
            )
        except ExecutorUnavailableError as exc:
            outcome = ExecutorOutcome(
                terminal_status=RunStatus.FAILED,
                failure_reason=str(exc),
                terminal_code="executor_unavailable",
            )
        except Exception as exc:
            logger.exception(
                "activity.execute_agent_run.executor_error",
                extra=_activity_log_context(payload=payload),
            )
            outcome = ExecutorOutcome(
                terminal_status=RunStatus.FAILED,
                failure_reason=str(exc),
                terminal_code="executor_error",
            )
        finally:
            _ = heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

        terminal_event_type = _executor_terminal_event_type(outcome.terminal_status)
        try:
            await self._record_executor_event(
                payload,
                event_type=terminal_event_type,
                message=_executor_terminal_message(outcome.terminal_status),
                severity="error"
                if outcome.terminal_status is RunStatus.FAILED
                else "warning"
                if outcome.terminal_status is RunStatus.CANCELED
                else "info",
                details={
                    **_executor_event_details(payload, runtime_config),
                    "terminal_status": outcome.terminal_status.value,
                    "terminal_code": outcome.terminal_code,
                    "has_result_summary": outcome.result_summary is not None,
                    "has_failure_reason": outcome.failure_reason is not None,
                },
            )
        except Exception:
            logger.exception(
                "activity.execute_agent_run.terminal_event_record_failed",
                extra=_activity_log_context(
                    payload=payload,
                    run_status=outcome.terminal_status.value,
                    terminal_code=outcome.terminal_code,
                ),
            )
        logger.info(
            "activity.execute_agent_run.succeeded",
            extra=_activity_log_context(
                payload=payload,
                run_status=outcome.terminal_status.value,
                terminal_code=outcome.terminal_code,
            ),
        )
        return outcome

    @activity.defn(name="mark_run_completed")
    async def mark_run_completed(self, run_id: str, result_summary: str | None) -> None:
        logger.info(
            "activity.mark_run_completed.starting",
            extra=_activity_log_context(run_id=run_id),
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    run = await repo.mark_run_completed(
                        session,
                        run_id=run_id,
                        result_summary=result_summary,
                        **_activity_event_context(),
                    )
                    logger.info(
                        "activity.mark_run_completed.succeeded",
                        extra=_activity_log_context(
                            run_id=run.run_id,
                            task_id=run.task_id,
                            schedule_id=run.schedule_id,
                            run_status=run.run_status.value,
                        ),
                    )
        except Exception:
            logger.exception(
                "activity.mark_run_completed.failed",
                extra=_activity_log_context(run_id=run_id),
            )
            raise

    @activity.defn(name="mark_run_failed")
    async def mark_run_failed(self, run_id: str, failure_reason: str) -> None:
        logger.info(
            "activity.mark_run_failed.starting",
            extra=_activity_log_context(run_id=run_id),
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    run = await repo.mark_run_failed(
                        session,
                        run_id=run_id,
                        failure_reason=failure_reason,
                        **_activity_event_context(),
                    )
                    logger.info(
                        "activity.mark_run_failed.succeeded",
                        extra=_activity_log_context(
                            run_id=run.run_id,
                            task_id=run.task_id,
                            schedule_id=run.schedule_id,
                            run_status=run.run_status.value,
                        ),
                    )
        except Exception:
            logger.exception(
                "activity.mark_run_failed.failed",
                extra=_activity_log_context(run_id=run_id),
            )
            raise

    @activity.defn(name="mark_run_canceled")
    async def mark_run_canceled(self, run_id: str, failure_reason: str | None) -> None:
        logger.info(
            "activity.mark_run_canceled.starting",
            extra=_activity_log_context(run_id=run_id),
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    run = await repo.mark_run_canceled(
                        session,
                        run_id=run_id,
                        failure_reason=failure_reason,
                        **_activity_event_context(),
                    )
                    logger.info(
                        "activity.mark_run_canceled.succeeded",
                        extra=_activity_log_context(
                            run_id=run.run_id,
                            task_id=run.task_id,
                            schedule_id=run.schedule_id,
                            run_status=run.run_status.value,
                        ),
                    )
        except Exception:
            logger.exception(
                "activity.mark_run_canceled.failed",
                extra=_activity_log_context(run_id=run_id),
            )
            raise

    @activity.defn(name="complete_single_run_schedule")
    async def complete_single_run_schedule(self, schedule_id: str) -> None:
        logger.info(
            "activity.complete_single_run_schedule.starting",
            extra=_activity_log_context(schedule_id=schedule_id),
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    schedule = await repo.complete_single_run_schedule(
                        session, schedule_id=schedule_id
                    )
                    logger.info(
                        "activity.complete_single_run_schedule.succeeded",
                        extra=_activity_log_context(
                            task_id=schedule.task_id,
                            schedule_id=schedule.schedule_id,
                        ),
                    )
        except Exception:
            logger.exception(
                "activity.complete_single_run_schedule.failed",
                extra=_activity_log_context(schedule_id=schedule_id),
            )
            raise

    async def _record_executor_event(
        self,
        payload: TaskRunInput,
        *,
        event_type: str,
        message: str,
        details: dict[str, object],
        severity: str = "info",
    ) -> None:
        if payload.run_id is None:
            return
        async with self._session_factory() as session:
            async with session.begin():
                _ = await repo.record_run_event(
                    session,
                    run_id=payload.run_id,
                    event_type=event_type,
                    message=message,
                    severity=severity,
                    details=details,
                    **_activity_event_context(),
                )

    async def _executor_runtime_config(
        self,
        payload: TaskRunInput,
    ) -> ExecutorRuntimeConfig | None:
        profile_id = payload.execution_snapshot.executor_profile_id
        if profile_id is None:
            return None
        async with self._session_factory() as session:
            profile = await repo.get_executor_profile(session, profile_id)
            if profile.archived_at is not None:
                raise InvalidStateTransitionError(
                    "archived executor profiles cannot be used"
                )
            if not profile.is_enabled:
                raise InvalidStateTransitionError(
                    "disabled executor profiles cannot be used"
                )
            if profile.executor != payload.execution_snapshot.executor:
                raise ValueError("executor profile does not match execution snapshot")
            env = dict(profile.env or {})
            env.update(profile.secret_env or {})
            return ExecutorRuntimeConfig(
                executor_profile_id=profile.profile_id,
                executor_profile_name=profile.name,
                default_model=profile.default_model,
                reasoning_level=profile.reasoning_level,
                env=env,
            )

    async def _validation_runtime_config(
        self,
        payload: ProfileValidationInput,
    ) -> ExecutorRuntimeConfig:
        async with self._session_factory() as session:
            handoff = await repo.get_profile_validation_handoff(
                session,
                payload.handoff_id,
            )
            if handoff.executor != payload.executor:
                raise ValueError("validation handoff executor mismatch")
            if handoff.default_model != payload.default_model:
                raise ValueError("validation handoff default model mismatch")
            if handoff.reasoning_level != payload.reasoning_level:
                raise ValueError("validation handoff reasoning level mismatch")
            env = dict(handoff.env or {})
            env.update(handoff.secret_env or {})
            return ExecutorRuntimeConfig(
                executor_profile_id=None,
                executor_profile_name="Profile validation",
                default_model=handoff.default_model,
                reasoning_level=handoff.reasoning_level,
                env=env,
            )

    async def _delete_validation_handoff(self, handoff_id: str) -> None:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await repo.delete_profile_validation_handoff(session, handoff_id)
        except Exception:
            logger.exception(
                "activity.validate_executor_profile.handoff_cleanup_failed",
                extra={"handoff_id": handoff_id},
            )

    async def close(self) -> None:
        await self._engine.dispose()


async def _heartbeat_loop(interval_seconds: float = 60.0) -> None:
    """Send Temporal activity heartbeats at a fixed interval.

    The interval should be well below the activity's *heartbeat_timeout*
    (currently 5 minutes in ``TaskRunWorkflow``) so that long-running
    executor invocations are not mistaken for dead activities.
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            activity.heartbeat()
        except asyncio.CancelledError:
            break


def _profile_validation_log_context(
    payload: ProfileValidationInput,
) -> dict[str, object]:
    return {
        **_activity_info_dict(),
        "handoff_id": payload.handoff_id,
        "executor": payload.executor.value,
        "default_model": payload.default_model,
        "reasoning_level": payload.reasoning_level,
    }


def _activity_log_context(
    *,
    payload: TaskRunInput | None = None,
    run_id: str | None = None,
    task_id: str | None = None,
    schedule_id: str | None = None,
    run_status: str | None = None,
    terminal_code: str | None = None,
) -> dict[str, object]:
    activity_context = _activity_info_dict()
    snapshot = payload.execution_snapshot if payload is not None else None
    return {
        **activity_context,
        "task_id": task_id or (payload.task_id if payload is not None else None),
        "schedule_id": schedule_id
        or (payload.schedule_id if payload is not None else None),
        "run_id": run_id or (payload.run_id if payload is not None else None),
        "executor": snapshot.executor.value if snapshot is not None else None,
        "run_status": run_status,
        "terminal_code": terminal_code,
    }


def _activity_info_dict() -> dict[str, object]:
    try:
        info = activity.info()
    except RuntimeError:
        return {}
    return {
        "workflow_id": info.workflow_id,
        "workflow_run_id": info.workflow_run_id,
        "activity_type": info.activity_type,
        "activity_attempt": info.attempt,
    }


def _activity_event_context() -> ActivityEventContext:
    try:
        info = activity.info()
    except RuntimeError:
        return {}
    return {
        "temporal_workflow_id": info.workflow_id,
        "temporal_workflow_run_id": info.workflow_run_id,
        "activity_type": info.activity_type,
        "activity_attempt": info.attempt,
    }


def _executor_event_details(
    payload: TaskRunInput,
    runtime_config: ExecutorRuntimeConfig | None = None,
) -> dict[str, object]:
    details: dict[str, object] = {
        "executor": payload.execution_snapshot.executor.value,
        "executor_profile_id": payload.execution_snapshot.executor_profile_id,
        "executor_model": runtime_config.default_model if runtime_config else None,
        "executor_reasoning_level": (
            runtime_config.reasoning_level if runtime_config else None
        ),
    }
    if runtime_config is not None:
        details["executor_profile_name"] = runtime_config.executor_profile_name
    return details


def _executor_terminal_event_type(status: RunStatus) -> str:
    if status is RunStatus.COMPLETED:
        return "executor.completed"
    if status is RunStatus.CANCELED:
        return "executor.canceled"
    return "executor.failed"


def _executor_terminal_message(status: RunStatus) -> str:
    if status is RunStatus.COMPLETED:
        return "Executor invocation completed successfully."
    if status is RunStatus.CANCELED:
        return "Executor invocation was canceled."
    return "Executor invocation failed."
