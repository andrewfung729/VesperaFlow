"""Temporal Schedule client for one-time task execution."""

from datetime import UTC, timedelta
from pathlib import Path

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleCalendarSpec,
    ScheduleRange,
    ScheduleSpec,
)
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.service import RPCError, RPCStatusCode
from vesperaflow_core import (
    ExecutionSnapshot,
    TaskRunInput,
    temporal_schedule_id,
    workflow_id_for_run,
)
from vesperaflow_store.models import Run, Task
from vesperaflow_store.models import Schedule as ProductSchedule

from .settings import ApiSettings


class TemporalScheduler:
    def __init__(self, settings: ApiSettings) -> None:
        self._settings = settings
        self._client: Client | None = None

    async def connect(self) -> None:
        self._client = await Client.connect(
            self._settings.temporal_address,
            namespace=self._settings.temporal_namespace,
            data_converter=pydantic_data_converter,
        )

    async def create_one_time_schedule(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run,
    ) -> str:
        client = self._require_client()
        schedule_ref = temporal_schedule_id(schedule.schedule_id)
        await client.create_schedule(
            schedule_ref,
            self._build_schedule(task=task, schedule=schedule, run=run),
        )
        return schedule_ref

    async def replace_one_time_schedule(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run,
    ) -> str:
        await self.delete_schedule(schedule.schedule_id)
        return await self.create_one_time_schedule(
            task=task, schedule=schedule, run=run
        )

    async def delete_schedule(self, schedule_id: str) -> None:
        client = self._require_client()
        handle = client.get_schedule_handle(temporal_schedule_id(schedule_id))
        try:
            await handle.delete()
        except RPCError as exc:
            if exc.status is not RPCStatusCode.NOT_FOUND:
                raise
            # Deleting an already-consumed or already-deleted schedule is safe for
            # the product command; the database state remains authoritative.
            return

    def _build_schedule(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run,
    ) -> Schedule:
        if schedule.planned_at is None:
            raise ValueError("single-run schedule requires planned_at")
        planned_at = schedule.planned_at.astimezone(UTC)
        workflow_input = TaskRunInput(
            run_id=run.run_id,
            task_id=task.task_id,
            schedule_id=schedule.schedule_id,
            planned_start_at=planned_at,
            occurrence_key=None,
            execution_snapshot=ExecutionSnapshot(
                run_id=run.run_id,
                task_id=task.task_id,
                schedule_id=schedule.schedule_id,
                executor=task.executor,
                instruction_source=task.instruction_source,
                planned_start_at=planned_at,
                working_directory=str(
                    Path(self._settings.run_workspace_root) / run.run_id
                ),
            ),
        )
        return Schedule(
            action=ScheduleActionStartWorkflow(
                "TaskRunWorkflow",
                args=[workflow_input],
                id=workflow_id_for_run(run.run_id),
                task_queue=self._settings.task_queue,
            ),
            spec=ScheduleSpec(
                calendars=[
                    ScheduleCalendarSpec(
                        second=[ScheduleRange(planned_at.second)],
                        minute=[ScheduleRange(planned_at.minute)],
                        hour=[ScheduleRange(planned_at.hour)],
                        day_of_month=[ScheduleRange(planned_at.day)],
                        month=[ScheduleRange(planned_at.month)],
                        year=[ScheduleRange(planned_at.year)],
                    )
                ],
                end_at=planned_at + timedelta(minutes=1),
                time_zone_name="UTC",
            ),
        )

    def _require_client(self) -> Client:
        if self._client is None:
            raise RuntimeError("Temporal scheduler is not connected")
        return self._client
