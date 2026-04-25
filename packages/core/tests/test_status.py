from datetime import UTC, datetime

from vesperaflow_core import ExecutionMode, RunStatus, ScheduleStatus, TaskStatus
from vesperaflow_core.status import derive_task_status


def test_archived_task_status_wins_over_other_state() -> None:
    assert (
        derive_task_status(
            execution_mode=ExecutionMode.ONE_TIME,
            archived_at=datetime(2026, 4, 25, tzinfo=UTC),
            schedule_status=ScheduleStatus.ACTIVE,
            latest_run_status=RunStatus.RUNNING,
        )
        is TaskStatus.ARCHIVED
    )


def test_recurring_active_schedule_is_scheduled() -> None:
    assert (
        derive_task_status(
            execution_mode=ExecutionMode.RECURRING,
            archived_at=None,
            schedule_status=ScheduleStatus.ACTIVE,
            latest_run_status=RunStatus.FAILED,
        )
        is TaskStatus.SCHEDULED
    )


def test_one_time_failed_run_is_failed() -> None:
    assert (
        derive_task_status(
            execution_mode=ExecutionMode.ONE_TIME,
            archived_at=None,
            schedule_status=ScheduleStatus.COMPLETED,
            latest_run_status=RunStatus.FAILED,
        )
        is TaskStatus.FAILED
    )
