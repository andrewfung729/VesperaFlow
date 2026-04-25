from datetime import UTC, datetime, timedelta

import pytest
from vesperaflow_core import (
    ExecutionMode,
    RunStatus,
    ScheduleType,
    require_future_datetime,
    require_one_time_schedule_consistency,
    require_run_transition,
    validate_occurrence_key,
)


def test_future_datetime_requires_timezone() -> None:
    with pytest.raises(ValueError, match="explicit timezone"):
        require_future_datetime(datetime(2026, 4, 25, 9, 0), field_name="planned_at")


def test_one_time_schedule_consistency_rejects_recurring_mode() -> None:
    with pytest.raises(ValueError, match="only one-time"):
        require_one_time_schedule_consistency(
            execution_mode=ExecutionMode.RECURRING,
            schedule_type=ScheduleType.SINGLE_RUN,
            planned_at=datetime.now(UTC) + timedelta(hours=1),
        )


def test_run_transition_rejects_terminal_to_running() -> None:
    with pytest.raises(ValueError, match="invalid run transition"):
        require_run_transition(RunStatus.COMPLETED, RunStatus.RUNNING)


def test_occurrence_key_validation() -> None:
    validate_occurrence_key("20260429T010000Z")
    with pytest.raises(ValueError, match="occurrence_key"):
        validate_occurrence_key("2026-04-29T01:00:00Z")
