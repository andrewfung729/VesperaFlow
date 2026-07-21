from datetime import UTC, datetime
from typing import Any, cast

import pytest
from temporalio.client import ScheduleActionStartWorkflow
from vesperaflow_api.settings import ApiSettings
from vesperaflow_api.temporal_scheduler import TemporalScheduler
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from vesperaflow_store.models import Run, Task
from vesperaflow_store.models import Schedule as ProductSchedule


def test_recurring_schedule_action_has_workflow_id_prefix() -> None:
    scheduler = TemporalScheduler(
        ApiSettings(
            database_url="postgresql+asyncpg://test@localhost/test",
            task_queue="test-queue",
        )
    )
    now = datetime(2026, 4, 26, 13, 30, tzinfo=UTC)
    task = Task(
        task_id="task_123",
        title="Daily research",
        instruction_source="Find updates",
        normalized_instruction=None,
        target_working_directory="/tmp",
        execution_mode=ExecutionMode.RECURRING,
        task_status=TaskStatus.SCHEDULED,
        template_id=None,
        executor=ExecutorName.DEBUG_PRINTER,
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    product_schedule = ProductSchedule(
        schedule_id="sch_123",
        task_id=task.task_id,
        schedule_type=ScheduleType.RECURRING_RULE,
        schedule_status=ScheduleStatus.ACTIVE,
        planned_at=None,
        recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=21;BYMINUTE=30",
        recurrence_timezone="Asia/Hong_Kong",
        next_run_at=now,
        last_materialized_at=None,
        external_schedule_ref=None,
        version=1,
        created_at=now,
        updated_at=now,
    )

    schedule = scheduler._build_recurring_schedule(  # noqa: SLF001
        task=task,
        schedule=product_schedule,
    )

    assert isinstance(schedule.action, ScheduleActionStartWorkflow)
    assert schedule.action.id == "vesperaflow.occurrence.sch_123"
    assert schedule.action.task_queue == "test-queue"
    assert schedule.spec.cron_expressions == ["30 21 * * *"]
    assert schedule.spec.time_zone_name == "Asia/Hong_Kong"


@pytest.mark.asyncio
async def test_replace_one_time_schedule_updates_existing_schedule() -> None:
    scheduler = TemporalScheduler(
        ApiSettings(
            database_url="postgresql+asyncpg://test@localhost/test",
            task_queue="test-queue",
        )
    )
    client = _FakeScheduleClient()
    scheduler._client = cast(Any, client)  # noqa: SLF001
    now = datetime(2026, 4, 26, 13, 30, tzinfo=UTC)
    task = Task(
        task_id="task_123",
        title="Research",
        instruction_source="Find updates",
        normalized_instruction=None,
        target_working_directory="/tmp",
        execution_mode=ExecutionMode.ONE_TIME,
        task_status=TaskStatus.SCHEDULED,
        template_id=None,
        executor=ExecutorName.DEBUG_PRINTER,
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    product_schedule = ProductSchedule(
        schedule_id="sch_123",
        task_id=task.task_id,
        schedule_type=ScheduleType.SINGLE_RUN,
        schedule_status=ScheduleStatus.ACTIVE,
        planned_at=now,
        recurrence_rule=None,
        recurrence_timezone=None,
        next_run_at=now,
        last_materialized_at=None,
        external_schedule_ref="vesperaflow.schedule.sch_123",
        version=2,
        created_at=now,
        updated_at=now,
    )
    run = Run(
        run_id="run_123",
        task_id=task.task_id,
        schedule_id=product_schedule.schedule_id,
        run_status=RunStatus.PLANNED,
        planned_start_at=now,
        instruction_source_snapshot=task.instruction_source,
        created_at=now,
        updated_at=now,
    )

    schedule_ref = await scheduler.replace_one_time_schedule(
        task=task,
        schedule=product_schedule,
        run=run,
    )

    assert schedule_ref == "vesperaflow.schedule.sch_123"
    assert client.handle.update_count == 1
    assert client.create_count == 0
    assert client.handle.delete_count == 0


class _FakeScheduleHandle:
    def __init__(self) -> None:
        self.update_count = 0
        self.delete_count = 0

    async def update(self, updater: Any) -> None:
        self.update_count += 1
        _ = await updater(object())

    async def delete(self) -> None:
        self.delete_count += 1


class _FakeScheduleClient:
    def __init__(self) -> None:
        self.handle = _FakeScheduleHandle()
        self.create_count = 0

    def get_schedule_handle(self, _: str) -> _FakeScheduleHandle:
        return self.handle

    async def create_schedule(self, *_: object) -> None:
        self.create_count += 1
