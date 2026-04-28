"""TaskRunActivities Temporal activity definitions."""

import asyncio
from contextlib import suppress
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from temporalio import activity
from vesperaflow_core import ExecutorOutcome, MaterializedRun, RunStatus, TaskRunInput
from vesperaflow_store import create_engine, create_session_factory
from vesperaflow_store import repositories as repo

from vesperaflow_worker.executors.base import ExecutorAdapter, ExecutorUnavailableError


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
        if payload.run_id is not None and workflow_id is None:
            async with self._session_factory() as session:
                run = await repo.get_run(session, payload.run_id)
                return run.run_status.value
        if workflow_id is None or workflow_start_time is None:
            raise ValueError("recurring materialization requires workflow metadata")
        async with self._session_factory() as session:
            async with session.begin():
                return await repo.materialize_run(
                    session,
                    payload_task_id=payload.task_id,
                    payload_schedule_id=payload.schedule_id,
                    payload_run_id=payload.run_id,
                    planned_start_at=workflow_start_time,
                    occurrence_key=payload.occurrence_key,
                    workflow_id=workflow_id,
                    run_workspace_root=self._run_workspace_root,
                )

    @activity.defn(name="mark_run_queued")
    async def mark_run_queued(self, run_id: str, external_execution_ref: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                _ = await repo.mark_run_queued(
                    session,
                    run_id=run_id,
                    external_execution_ref=external_execution_ref,
                )

    @activity.defn(name="mark_run_running")
    async def mark_run_running(self, run_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                _ = await repo.mark_run_running(session, run_id=run_id)

    @activity.defn(name="execute_agent_run")
    async def execute_agent_run(self, payload: TaskRunInput) -> ExecutorOutcome:
        if isinstance(payload, dict):
            payload = TaskRunInput.model_validate(payload)
        heartbeat_task = asyncio.create_task(_heartbeat_loop(interval_seconds=60))
        try:
            return await self._executor.execute(payload.execution_snapshot)
        except ExecutorUnavailableError as exc:
            return ExecutorOutcome(
                terminal_status=RunStatus.FAILED,
                failure_reason=str(exc),
                terminal_code="executor_unavailable",
            )
        except Exception as exc:
            return ExecutorOutcome(
                terminal_status=RunStatus.FAILED,
                failure_reason=str(exc),
                terminal_code="executor_error",
            )
        finally:
            _ = heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

    @activity.defn(name="mark_run_completed")
    async def mark_run_completed(self, run_id: str, result_summary: str | None) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                _ = await repo.mark_run_completed(
                    session,
                    run_id=run_id,
                    result_summary=result_summary,
                )

    @activity.defn(name="mark_run_failed")
    async def mark_run_failed(self, run_id: str, failure_reason: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                _ = await repo.mark_run_failed(
                    session,
                    run_id=run_id,
                    failure_reason=failure_reason,
                )

    @activity.defn(name="mark_run_canceled")
    async def mark_run_canceled(self, run_id: str, failure_reason: str | None) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                _ = await repo.mark_run_canceled(
                    session,
                    run_id=run_id,
                    failure_reason=failure_reason,
                )

    @activity.defn(name="complete_single_run_schedule")
    async def complete_single_run_schedule(self, schedule_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                _ = await repo.complete_single_run_schedule(
                    session, schedule_id=schedule_id
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
