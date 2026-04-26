"""Pure validation helpers for task planning inputs."""

from datetime import UTC, datetime

from .enums import ExecutionMode, RunStatus, ScheduleType


def require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include an explicit timezone")


def require_future_datetime(
    value: datetime,
    *,
    field_name: str,
    now: datetime | None = None,
) -> None:
    require_timezone_aware(value, field_name)
    comparison_now = now or datetime.now(UTC)
    require_timezone_aware(comparison_now, "now")
    if value.astimezone(UTC) <= comparison_now.astimezone(UTC):
        raise ValueError(f"{field_name} must be in the future")


def require_one_time_schedule_consistency(
    *,
    execution_mode: ExecutionMode,
    schedule_type: ScheduleType,
    planned_at: datetime | None,
    now: datetime | None = None,
) -> None:
    if execution_mode is not ExecutionMode.ONE_TIME:
        raise ValueError("only one-time tasks are supported in this slice")
    if schedule_type is not ScheduleType.SINGLE_RUN:
        raise ValueError("one-time tasks require a single-run schedule")
    if planned_at is None:
        raise ValueError("one-time tasks require planned_at")
    require_future_datetime(planned_at, field_name="planned_at", now=now)


def require_template_schedule_defaults(
    *,
    execution_mode: ExecutionMode,
    schedule_type: ScheduleType,
    recurrence_rule: str | None,
    recurrence_timezone: str | None,
) -> None:
    if execution_mode is ExecutionMode.ONE_TIME:
        if schedule_type is not ScheduleType.SINGLE_RUN:
            raise ValueError("one-time template defaults require a single-run schedule")
        if recurrence_rule is not None or recurrence_timezone is not None:
            raise ValueError("one-time template defaults cannot include recurrence")
        return

    if schedule_type is not ScheduleType.RECURRING_RULE:
        raise ValueError(
            "recurring template defaults require a recurring-rule schedule"
        )
    if not recurrence_rule:
        raise ValueError("recurring template defaults require recurrence_rule")
    if not recurrence_timezone:
        raise ValueError("recurring template defaults require recurrence_timezone")


_ALLOWED_RUN_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.PLANNED: {RunStatus.QUEUED, RunStatus.CANCELED},
    RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELED},
    RunStatus.RUNNING: {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELED,
    },
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELED: set(),
}


def require_run_transition(current: RunStatus, target: RunStatus) -> None:
    if current is target:
        return
    if target not in _ALLOWED_RUN_TRANSITIONS[current]:
        raise ValueError(f"invalid run transition: {current} -> {target}")
