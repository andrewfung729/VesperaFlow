"""Task status derivation rules."""

from datetime import datetime

from .enums import ExecutionMode, RunStatus, ScheduleStatus, TaskStatus


def derive_task_status(
    *,
    execution_mode: ExecutionMode,
    archived_at: datetime | None,
    schedule_status: ScheduleStatus | None,
    latest_run_status: RunStatus | None,
) -> TaskStatus:
    if archived_at is not None:
        return TaskStatus.ARCHIVED

    if execution_mode is ExecutionMode.RECURRING:
        if schedule_status is ScheduleStatus.PAUSED:
            return TaskStatus.PAUSED
        if schedule_status is ScheduleStatus.CANCELED:
            return TaskStatus.CANCELED
        return TaskStatus.SCHEDULED

    if latest_run_status is RunStatus.RUNNING:
        return TaskStatus.RUNNING
    if latest_run_status is RunStatus.COMPLETED:
        return TaskStatus.COMPLETED
    if latest_run_status is RunStatus.FAILED:
        return TaskStatus.FAILED
    if latest_run_status is RunStatus.CANCELED:
        return TaskStatus.CANCELED
    if schedule_status is ScheduleStatus.CANCELED:
        return TaskStatus.CANCELED
    return TaskStatus.SCHEDULED
