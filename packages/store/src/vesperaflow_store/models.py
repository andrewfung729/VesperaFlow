"""SQLAlchemy models for the MVP vertical slice."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from vesperaflow_core import (
    ExecutionMode,
    ExecutorName,
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
    execution_mode: Mapped[ExecutionMode] = enum_column(ExecutionMode)
    task_status: Mapped[TaskStatus] = enum_column(TaskStatus)
    template_id: Mapped[str | None] = mapped_column(String(48))
    executor: Mapped[ExecutorName] = enum_column(ExecutorName)
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


class Run(Base):
    __tablename__: str = "runs"
    __table_args__: tuple[Index, ...] = (
        Index("ix_runs_task_id", "task_id"),
        Index("ix_runs_schedule_id", "schedule_id"),
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="runs")
    schedule: Mapped[Schedule | None] = relationship(back_populates="runs")
