"""Shared pure domain primitives for VesperaFlow."""

from .contracts import ExecutionSnapshot, ExecutorOutcome, TaskRunInput
from .enums import (
    ExecutionMode,
    ExecutorName,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from .status import derive_task_status
from .temporal_ids import (
    temporal_schedule_id,
    validate_occurrence_key,
    workflow_id_for_occurrence,
    workflow_id_for_run,
)
from .time import to_utc, utc_now
from .validation import (
    require_future_datetime,
    require_one_time_schedule_consistency,
    require_run_transition,
    require_timezone_aware,
)

__all__ = [
    "ExecutionMode",
    "ExecutionSnapshot",
    "ExecutorName",
    "ExecutorOutcome",
    "RunStatus",
    "ScheduleStatus",
    "ScheduleType",
    "TaskStatus",
    "TaskRunInput",
    "derive_task_status",
    "temporal_schedule_id",
    "validate_occurrence_key",
    "workflow_id_for_occurrence",
    "workflow_id_for_run",
    "to_utc",
    "utc_now",
    "require_future_datetime",
    "require_one_time_schedule_consistency",
    "require_run_transition",
    "require_timezone_aware",
]
