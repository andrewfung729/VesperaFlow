"""SQLAlchemy models for the MVP vertical slice."""

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
    OccurrenceOverrideStatus,
    RunStatus,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)


class Base(DeclarativeBase):
    pass


def enum_values[EnumT: enum.StrEnum](enum_cls: type[EnumT]) -> list[str]:
    return [member.value for member in enum_cls]


def enum_column[EnumT: enum.StrEnum](
    enum_type: type[EnumT], length: int = 64
) -> Mapped[EnumT]:
    return mapped_column(
        Enum(
            enum_type,
            native_enum=False,
            length=length,
            values_callable=enum_values,
        ),
        nullable=False,
    )


class Task(Base):
    __tablename__: str = "tasks"

    task_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    instruction_source: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_instruction: Mapped[str | None] = mapped_column(Text)
    target_working_directory: Mapped[str | None] = mapped_column(Text)
    execution_mode: Mapped[ExecutionMode] = enum_column(ExecutionMode)
    task_status: Mapped[TaskStatus] = enum_column(TaskStatus)
    template_id: Mapped[str | None] = mapped_column(String(48))
    executor: Mapped[ExecutorName] = enum_column(ExecutorName)
    executor_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("executor_profiles.profile_id")
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    schedules: Mapped[list["Schedule"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    runs: Mapped[list["Run"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    occurrence_overrides: Mapped[list["OccurrenceOverride"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    executor_profile: Mapped["ExecutorProfile | None"] = relationship()


class ExecutorProfile(Base):
    __tablename__: str = "executor_profiles"
    __table_args__: tuple[Index, ...] = (
        Index("ix_executor_profiles_executor_default", "executor", "is_default"),
        Index("ix_executor_profiles_archived_at", "archived_at"),
    )

    profile_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    executor: Mapped[ExecutorName] = enum_column(ExecutorName)
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False)
    default_model: Mapped[str | None] = mapped_column(String(160))
    env: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    secret_env: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Template(Base):
    __tablename__: str = "templates"
    __table_args__: tuple[Index, ...] = (
        Index("ix_templates_archived_at_created_at", "archived_at", "created_at"),
    )

    template_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    instruction_source: Mapped[str] = mapped_column(Text, nullable=False)
    default_task_title: Mapped[str | None] = mapped_column(String(240))
    default_target_working_directory: Mapped[str | None] = mapped_column(Text)
    default_execution_mode: Mapped[ExecutionMode] = enum_column(ExecutionMode)
    default_schedule_type: Mapped[ScheduleType] = enum_column(ScheduleType)
    default_planned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    default_recurrence_rule: Mapped[str | None] = mapped_column(Text)
    default_recurrence_timezone: Mapped[str | None] = mapped_column(String(128))
    default_executor: Mapped[ExecutorName | None] = mapped_column(
        Enum(
            ExecutorName,
            native_enum=False,
            length=64,
            values_callable=enum_values,
        )
    )
    default_executor_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("executor_profiles.profile_id")
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    default_executor_profile: Mapped[ExecutorProfile | None] = relationship()


class Schedule(Base):
    __tablename__: str = "schedules"
    __table_args__: tuple[Index | UniqueConstraint, ...] = (
        Index("ix_schedules_task_id", "task_id"),
        UniqueConstraint("task_id", name="uq_schedules_task_id_vertical_slice"),
    )

    schedule_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.task_id"), nullable=False)
    schedule_type: Mapped[ScheduleType] = enum_column(ScheduleType)
    schedule_status: Mapped[ScheduleStatus] = enum_column(ScheduleStatus)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recurrence_rule: Mapped[str | None] = mapped_column(Text)
    recurrence_timezone: Mapped[str | None] = mapped_column(String(128))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_materialized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    external_schedule_ref: Mapped[str | None] = mapped_column(String(240))
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="schedules")
    runs: Mapped[list["Run"]] = relationship(back_populates="schedule")
    occurrence_overrides: Mapped[list["OccurrenceOverride"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )


class Run(Base):
    __tablename__: str = "runs"
    __table_args__: tuple[Index | UniqueConstraint, ...] = (
        Index("ix_runs_task_id", "task_id"),
        Index("ix_runs_schedule_id", "schedule_id"),
        Index("ix_runs_history_status_finished_at", "run_status", "finished_at"),
        UniqueConstraint(
            "schedule_id",
            "occurrence_key",
            name="uq_runs_schedule_occurrence_key",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.task_id"), nullable=False)
    schedule_id: Mapped[str | None] = mapped_column(ForeignKey("schedules.schedule_id"))
    run_status: Mapped[RunStatus] = enum_column(RunStatus)
    planned_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    external_execution_ref: Mapped[str | None] = mapped_column(String(240))
    occurrence_key: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="runs")
    schedule: Mapped[Schedule | None] = relationship(back_populates="runs")
    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class RunEvent(Base):
    __tablename__: str = "run_events"
    __table_args__: tuple[Index, ...] = (
        Index(
            "ix_run_events_run_id_created_at",
            "run_id",
            "created_at",
            "run_event_id",
        ),
    )

    run_event_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(48), nullable=False)
    schedule_id: Mapped[str | None] = mapped_column(String(48))
    event_type: Mapped[str] = mapped_column(String(96), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(240))
    temporal_workflow_run_id: Mapped[str | None] = mapped_column(String(240))
    activity_type: Mapped[str | None] = mapped_column(String(120))
    activity_attempt: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    run: Mapped[Run] = relationship(back_populates="events")


class OccurrenceOverride(Base):
    __tablename__: str = "occurrence_overrides"
    __table_args__: tuple[Index | UniqueConstraint, ...] = (
        Index("ix_occurrence_overrides_task_id", "task_id"),
        Index("ix_occurrence_overrides_schedule_id", "schedule_id"),
        UniqueConstraint(
            "schedule_id",
            "original_occurrence_at",
            name="uq_occurrence_overrides_schedule_original",
        ),
    )

    occurrence_override_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.task_id"), nullable=False)
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey("schedules.schedule_id"), nullable=False
    )
    original_occurrence_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    override_occurrence_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    override_instruction_delta: Mapped[str | None] = mapped_column(Text)
    override_status: Mapped[OccurrenceOverrideStatus] = enum_column(
        OccurrenceOverrideStatus
    )
    rescheduled_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.run_id"), nullable=True
    )
    external_schedule_ref: Mapped[str | None] = mapped_column(
        String(240), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="occurrence_overrides")
    schedule: Mapped[Schedule] = relationship(back_populates="occurrence_overrides")
    rescheduled_run: Mapped["Run | None"] = relationship()
