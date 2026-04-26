"""Shared pure domain primitives for VesperaFlow."""

from .contracts import ExecutionSnapshot, ExecutorOutcome, MaterializedRun, TaskRunInput
from .enums import (
    ExecutionMode,
    ExecutorName,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from .recurrence import next_occurrence_after, parse_recurrence_rule
from .status import derive_task_status
from .temporal_ids import (
    occurrence_key_for_datetime,
    temporal_schedule_id,
    validate_occurrence_key,
    workflow_id_for_occurrence,
    workflow_id_for_run,
)
from .time import to_utc, utc_now
from .validation import (
    require_future_datetime,
    require_one_time_schedule_consistency,
    require_recurring_schedule_consistency,
    require_run_transition,
    require_template_schedule_defaults,
    require_timezone_aware,
)

__all__ = [
    "ExecutionMode",
    "ExecutionSnapshot",
    "ExecutorName",
    "ExecutorOutcome",
    "MaterializedRun",
    "RunStatus",
    "ScheduleStatus",
    "ScheduleType",
    "TaskStatus",
    "TaskRunInput",
    "derive_task_status",
    "next_occurrence_after",
    "occurrence_key_for_datetime",
    "parse_recurrence_rule",
    "temporal_schedule_id",
    "validate_occurrence_key",
    "workflow_id_for_occurrence",
    "workflow_id_for_run",
    "to_utc",
    "utc_now",
    "require_future_datetime",
    "require_one_time_schedule_consistency",
    "require_recurring_schedule_consistency",
    "require_run_transition",
    "require_template_schedule_defaults",
    "require_timezone_aware",
]
