from datetime import UTC, datetime

from temporalio.client import ScheduleActionStartWorkflow
from vesperaflow_api.settings import ApiSettings
from vesperaflow_api.temporal_scheduler import TemporalScheduler
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from vesperaflow_store.models import Schedule as ProductSchedule
from vesperaflow_store.models import Task


def test_recurring_schedule_action_has_workflow_id_prefix() -> None:
    scheduler = TemporalScheduler(ApiSettings(database_url="postgresql+asyncpg://test@localhost/test", task_queue="test-queue"))
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
