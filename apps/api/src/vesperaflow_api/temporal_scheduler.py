"""Temporal Schedule client for one-time task execution."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleCalendarSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleRange,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
)
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.service import RPCError, RPCStatusCode
from vesperaflow_core import (
    ExecutionSnapshot,
    ProfileValidationInput,
    ProfileValidationResult,
    ScheduleType,
    TaskRunInput,
    parse_recurrence_rule,
    temporal_schedule_id,
    utc_now,
    workflow_id_for_run,
)
from vesperaflow_store.models import Run, Task
from vesperaflow_store.models import Schedule as ProductSchedule

from .settings import ApiSettings


class TemporalScheduler:
    def __init__(self, settings: ApiSettings) -> None:
        self._settings: ApiSettings = settings
        self._client: Client | None = None

    async def connect(self) -> None:
        self._client = await Client.connect(
            self._settings.temporal_address,
            namespace=self._settings.temporal_namespace,
            data_converter=pydantic_data_converter,
        )

    async def validate_executor_profile(
        self,
        payload: ProfileValidationInput,
        *,
        timeout_seconds: float = 95.0,
    ) -> ProfileValidationResult:
        client = self._require_client()
        handle = await client.start_workflow(
            "ExecutorProfileValidationWorkflow",
            args=[payload],
            id=f"vesperaflow.profile-validation.{payload.handoff_id}",
            task_queue=self._settings.task_queue,
        )
        try:
            raw_result = cast(
                object,
                await asyncio.wait_for(handle.result(), timeout=timeout_seconds),
            )
        except TimeoutError:
            return ProfileValidationResult(
                ok=False,
                code="profile_validation_timeout",
                message="Executor profile validation timed out.",
            )
        return ProfileValidationResult.model_validate(raw_result)

    async def create_one_time_schedule(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run | None,
    ) -> str:
        if run is None:
            raise ValueError("one-time Temporal schedule requires run")
        client = self._require_client()
        schedule_ref = temporal_schedule_id(schedule.schedule_id)
        _ = await client.create_schedule(
            schedule_ref,
            self._build_schedule(task=task, schedule=schedule, run=run),
        )
        return schedule_ref

    async def replace_one_time_schedule(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run | None,
    ) -> str:
        if run is None:
            raise ValueError("one-time Temporal schedule requires run")
        client = self._require_client()
        schedule_ref = temporal_schedule_id(schedule.schedule_id)
        handle = client.get_schedule_handle(schedule_ref)
        new_schedule = self._build_schedule(task=task, schedule=schedule, run=run)

        async def updater(_: object) -> ScheduleUpdate:
            return ScheduleUpdate(schedule=new_schedule)

        await handle.update(updater)
        return schedule_ref

    async def create_recurring_schedule(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run | None = None,
    ) -> str:
        _ = run
        client = self._require_client()
        schedule_ref = temporal_schedule_id(schedule.schedule_id)
        _ = await client.create_schedule(
            schedule_ref,
            self._build_recurring_schedule(task=task, schedule=schedule),
        )
        return schedule_ref

    async def replace_recurring_schedule(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
    ) -> str:
        client = self._require_client()
        schedule_ref = temporal_schedule_id(schedule.schedule_id)
        handle = client.get_schedule_handle(schedule_ref)
        new_schedule = self._build_recurring_schedule(task=task, schedule=schedule)

        async def updater(_: object) -> ScheduleUpdate:
            return ScheduleUpdate(schedule=new_schedule)

        await handle.update(updater)
        return schedule_ref

    async def pause_schedule(self, schedule_id: str) -> None:
        client = self._require_client()
        handle = client.get_schedule_handle(temporal_schedule_id(schedule_id))
        await handle.pause(note="paused by VesperaFlow")

    async def resume_schedule(self, schedule_id: str) -> None:
        client = self._require_client()
        handle = client.get_schedule_handle(temporal_schedule_id(schedule_id))
        await handle.unpause(note="resumed by VesperaFlow")

    async def run_one_time_now(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run,
    ) -> str:
        await self.delete_schedule(schedule.schedule_id)
        return await self.start_one_time_workflow(
            task=task,
            schedule=schedule,
            run=run,
        )

    async def run_recurring_now(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run,
    ) -> str:
        client = self._require_client()
        workflow_id = workflow_id_for_run(run.run_id)
        planned_at = utc_now()
        workflow_input = TaskRunInput(
            run_id=run.run_id,
            task_id=task.task_id,
            schedule_id=schedule.schedule_id,
            planned_start_at=planned_at,
            occurrence_key=run.occurrence_key,
            schedule_type=ScheduleType.RECURRING_RULE,
            execution_snapshot=ExecutionSnapshot(
                run_id=run.run_id,
                task_id=task.task_id,
                schedule_id=schedule.schedule_id,
                executor=task.executor,
                executor_profile_id=task.executor_profile_id,
                instruction_source=run.instruction_source_snapshot,
                planned_start_at=planned_at,
                working_directory=str(
                    Path(self._settings.run_workspace_root) / run.run_id
                ),
                target_working_directory=task.target_working_directory,
            ),
        )
        handle = await client.start_workflow(
            "TaskRunWorkflow",
            args=[workflow_input],
            id=workflow_id,
            task_queue=self._settings.task_queue,
        )
        return handle.id

    async def start_one_time_workflow(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
        run: Run,
    ) -> str:
        client = self._require_client()
        workflow_id = workflow_id_for_run(run.run_id)
        planned_at = utc_now()
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
                executor_profile_id=task.executor_profile_id,
                instruction_source=run.instruction_source_snapshot,
                planned_start_at=planned_at,
                working_directory=str(
                    Path(self._settings.run_workspace_root) / run.run_id
                ),
                target_working_directory=task.target_working_directory,
            ),
        )
        handle = await client.start_workflow(
            "TaskRunWorkflow",
            args=[workflow_input],
            id=workflow_id,
            task_queue=self._settings.task_queue,
        )
        return handle.id

    async def create_occurrence_override_schedule(
        self,
        *,
        task: Task,
        run: Run,
        override_id: str,
        planned_at: datetime,
    ) -> str:
        if task.target_working_directory is None:
            raise ValueError("task requires target_working_directory")
        client = self._require_client()
        schedule_ref = temporal_schedule_id(f"ovr-{override_id}")
        planned_at = planned_at.astimezone(UTC)
        workflow_input = TaskRunInput(
            run_id=run.run_id,
            task_id=task.task_id,
            schedule_id=run.schedule_id,
            planned_start_at=planned_at,
            occurrence_key=None,
            schedule_type=None,
            execution_snapshot=ExecutionSnapshot(
                run_id=run.run_id,
                task_id=task.task_id,
                schedule_id=run.schedule_id,
                executor=task.executor,
                executor_profile_id=task.executor_profile_id,
                instruction_source=run.instruction_source_snapshot,
                planned_start_at=planned_at,
                working_directory=str(
                    Path(self._settings.run_workspace_root) / run.run_id
                ),
                target_working_directory=task.target_working_directory,
            ),
        )
        schedule = Schedule(
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
        _ = await client.create_schedule(schedule_ref, schedule)
        return schedule_ref

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
        if task.target_working_directory is None:
            raise ValueError("task requires target_working_directory")
        planned_at = schedule.planned_at.astimezone(UTC)
        workflow_input = TaskRunInput(
            run_id=run.run_id,
            task_id=task.task_id,
            schedule_id=schedule.schedule_id,
            planned_start_at=planned_at,
            occurrence_key=None,
            schedule_type=ScheduleType.SINGLE_RUN,
            execution_snapshot=ExecutionSnapshot(
                run_id=run.run_id,
                task_id=task.task_id,
                schedule_id=schedule.schedule_id,
                executor=task.executor,
                executor_profile_id=task.executor_profile_id,
                instruction_source=run.instruction_source_snapshot,
                planned_start_at=planned_at,
                working_directory=str(
                    Path(self._settings.run_workspace_root) / run.run_id
                ),
                target_working_directory=task.target_working_directory,
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

    def _build_recurring_schedule(
        self,
        *,
        task: Task,
        schedule: ProductSchedule,
    ) -> Schedule:
        if schedule.recurrence_rule is None or schedule.recurrence_timezone is None:
            raise ValueError("recurring schedule requires recurrence")
        if task.target_working_directory is None:
            raise ValueError("task requires target_working_directory")
        planned_at = (schedule.next_run_at or utc_now()).astimezone(UTC)
        workflow_input = TaskRunInput(
            run_id=None,
            task_id=task.task_id,
            schedule_id=schedule.schedule_id,
            planned_start_at=planned_at,
            occurrence_key=None,
            schedule_type=ScheduleType.RECURRING_RULE,
            execution_snapshot=ExecutionSnapshot(
                run_id=None,
                task_id=task.task_id,
                schedule_id=schedule.schedule_id,
                executor=task.executor,
                executor_profile_id=task.executor_profile_id,
                instruction_source=task.instruction_source,
                planned_start_at=planned_at,
                working_directory=str(
                    Path(self._settings.run_workspace_root) / schedule.schedule_id
                ),
                target_working_directory=task.target_working_directory,
            ),
        )
        return Schedule(
            action=ScheduleActionStartWorkflow(
                "TaskRunWorkflow",
                args=[workflow_input],
                id=_recurring_workflow_id_prefix(schedule.schedule_id),
                task_queue=self._settings.task_queue,
            ),
            spec=ScheduleSpec(
                cron_expressions=[
                    _recurrence_rule_to_cron_expression(schedule.recurrence_rule)
                ],
                time_zone_name=schedule.recurrence_timezone,
            ),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(seconds=1),
                pause_on_failure=False,
            ),
            state=ScheduleState(
                paused=schedule.schedule_status.value == "paused",
            ),
        )

    def _require_client(self) -> Client:
        if self._client is None:
            raise RuntimeError("Temporal scheduler is not connected")
        return self._client


def _recurrence_rule_to_cron_expression(recurrence_rule: str) -> str:
    spec = parse_recurrence_rule(recurrence_rule)
    if spec.seconds != (0,):
        raise ValueError(
            "recurrence_rule BYSECOND values other than 0 are not supported"
        )
    minutes = _cron_field(spec.minutes)
    hours = _cron_field(spec.hours)
    if spec.freq == "HOURLY":
        return f"{minutes} * * * *"
    if spec.freq == "DAILY":
        return f"{minutes} {hours} * * *"
    weekdays = ",".join(str((weekday + 1) % 7) for weekday in spec.weekdays)
    return f"{minutes} {hours} * * {weekdays}"


def _recurring_workflow_id_prefix(schedule_id: str) -> str:
    # Temporal Schedule appends a scheduled-time suffix to this workflow id by
    # default, giving each recurring action a distinct workflow execution id.
    return f"vesperaflow.occurrence.{schedule_id}"


def _cron_field(values: tuple[int, ...]) -> str:
    return ",".join(str(value) for value in values)
