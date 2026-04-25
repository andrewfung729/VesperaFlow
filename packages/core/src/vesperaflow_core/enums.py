"""Shared domain enums.

Keep this module dependency-free so Temporal workflows can import it safely.
"""

from enum import StrEnum


class ExecutionMode(StrEnum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"


class ExecutorName(StrEnum):
    CLAUDE_CODE = "claude_code"
    DEBUG_PRINTER = "debug_printer"


class ScheduleType(StrEnum):
    SINGLE_RUN = "single_run"
    RECURRING_RULE = "recurring_rule"


class TaskStatus(StrEnum):
    SCHEDULED = "scheduled"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    ARCHIVED = "archived"


class ScheduleStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELED = "canceled"


class RunStatus(StrEnum):
    PLANNED = "planned"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
