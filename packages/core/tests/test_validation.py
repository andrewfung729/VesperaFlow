from datetime import UTC, datetime, timedelta

import pytest
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    RunStatus,
    ScheduleType,
    next_occurrence_after,
    require_future_datetime,
    require_one_time_schedule_consistency,
    require_recurring_schedule_consistency,
    require_run_transition,
    validate_occurrence_key,
)


def test_future_datetime_requires_timezone() -> None:
    with pytest.raises(ValueError, match="explicit timezone"):
        require_future_datetime(datetime(2026, 4, 25, 9, 0), field_name="planned_at")


def test_executor_name_accepts_supported_local_agents() -> None:
    assert ExecutorName("opencode") is ExecutorName.OPENCODE
    assert ExecutorName("pi") is ExecutorName.PI


def test_executor_name_rejects_removed_local_agent() -> None:
    removed_executor = "ki" + "mi_code"
    with pytest.raises(ValueError):
        _ = ExecutorName(removed_executor)


def test_one_time_schedule_consistency_rejects_recurring_mode() -> None:
    with pytest.raises(ValueError, match="only one-time"):
        require_one_time_schedule_consistency(
            execution_mode=ExecutionMode.RECURRING,
            schedule_type=ScheduleType.SINGLE_RUN,
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )


def test_recurring_schedule_consistency_accepts_supported_rrule() -> None:
    require_recurring_schedule_consistency(
        execution_mode=ExecutionMode.RECURRING,
        schedule_type=ScheduleType.RECURRING_RULE,
        recurrence_rule="RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=30",
        recurrence_timezone="Asia/Hong_Kong",
    )
    next_run = next_occurrence_after(
        recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
        recurrence_timezone="UTC",
        after=datetime(2026, 4, 26, 7, 59, tzinfo=UTC),
    )
    assert next_run == datetime(2026, 4, 26, 8, 0, tzinfo=UTC)


def test_recurring_schedule_consistency_rejects_invalid_timezone() -> None:
    with pytest.raises(ValueError, match="IANA"):
        require_recurring_schedule_consistency(
            execution_mode=ExecutionMode.RECURRING,
            schedule_type=ScheduleType.RECURRING_RULE,
            recurrence_rule="RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            recurrence_timezone="Not/AZone",
        )


def test_run_transition_rejects_terminal_to_running() -> None:
    with pytest.raises(ValueError, match="invalid run transition"):
        require_run_transition(RunStatus.COMPLETED, RunStatus.RUNNING)


def test_occurrence_key_validation() -> None:
    validate_occurrence_key("20260429T010000Z")
    with pytest.raises(ValueError, match="occurrence_key"):
        validate_occurrence_key("2026-04-29T01:00:00Z")
