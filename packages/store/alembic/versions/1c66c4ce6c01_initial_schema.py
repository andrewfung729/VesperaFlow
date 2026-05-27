# pyright: reportUnusedCallResult=false

"""initial schema

Revision ID: 1c66c4ce6c01
Revises:
Create Date: 2026-04-29 11:34:07.420840

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c66c4ce6c01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("instruction_source", sa.Text(), nullable=False),
        sa.Column("normalized_instruction", sa.Text(), nullable=True),
        sa.Column("target_working_directory", sa.Text(), nullable=True),
        sa.Column(
            "execution_mode",
            sa.Enum(
                "one_time",
                "recurring",
                name="executionmode",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column(
            "task_status",
            sa.Enum(
                "scheduled",
                "paused",
                "running",
                "completed",
                "failed",
                "canceled",
                "archived",
                name="taskstatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("template_id", sa.String(length=48), nullable=True),
        sa.Column(
            "executor",
            sa.Enum(
                "claude_code",
                "codex",
                "opencode",
                "debug_printer",
                name="executorname",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("executor_profile_id", sa.String(length=48), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("task_id"),
    )

    # Create templates table
    op.create_table(
        "templates",
        sa.Column("template_id", sa.String(length=48), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instruction_source", sa.Text(), nullable=False),
        sa.Column("default_task_title", sa.String(length=240), nullable=True),
        sa.Column("default_target_working_directory", sa.Text(), nullable=True),
        sa.Column(
            "default_execution_mode",
            sa.Enum(
                "one_time",
                "recurring",
                name="executionmode",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column(
            "default_schedule_type",
            sa.Enum(
                "single_run",
                "recurring_rule",
                name="scheduletype",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("default_planned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("default_recurrence_rule", sa.Text(), nullable=True),
        sa.Column("default_recurrence_timezone", sa.String(length=128), nullable=True),
        sa.Column(
            "default_executor",
            sa.Enum(
                "claude_code",
                "codex",
                "opencode",
                "debug_printer",
                name="executorname",
                native_enum=False,
                length=64,
            ),
            nullable=True,
        ),
        sa.Column("default_executor_profile_id", sa.String(length=48), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("template_id"),
    )
    op.create_index(
        "ix_templates_archived_at_created_at",
        "templates",
        ["archived_at", "created_at"],
        unique=False,
    )

    # Create executor_profiles table
    op.create_table(
        "executor_profiles",
        sa.Column("profile_id", sa.String(length=48), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("executor", sa.String(length=64), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("default_model", sa.String(length=160), nullable=True),
        sa.Column("env", sa.JSON(), nullable=False),
        sa.Column("secret_env", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("profile_id"),
    )
    op.create_index(
        "ix_executor_profiles_archived_at",
        "executor_profiles",
        ["archived_at"],
        unique=False,
    )
    op.create_index(
        "ix_executor_profiles_executor_default",
        "executor_profiles",
        ["executor", "is_default"],
        unique=False,
    )

    # Add foreign keys for executor_profile_id columns
    op.create_foreign_key(
        "fk_tasks_executor_profile_id_executor_profiles",
        "tasks",
        "executor_profiles",
        ["executor_profile_id"],
        ["profile_id"],
    )
    op.create_foreign_key(
        "fk_templates_default_executor_profile_id_executor_profiles",
        "templates",
        "executor_profiles",
        ["default_executor_profile_id"],
        ["profile_id"],
    )

    # Create schedules table
    op.create_table(
        "schedules",
        sa.Column("schedule_id", sa.String(length=48), nullable=False),
        sa.Column("task_id", sa.String(length=48), nullable=False),
        sa.Column(
            "schedule_type",
            sa.Enum(
                "single_run",
                "recurring_rule",
                name="scheduletype",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column(
            "schedule_status",
            sa.Enum(
                "pending",
                "active",
                "paused",
                "completed",
                "canceled",
                name="schedulestatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recurrence_rule", sa.Text(), nullable=True),
        sa.Column("recurrence_timezone", sa.String(length=128), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_materialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_schedule_ref", sa.String(length=240), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
        ),
        sa.PrimaryKeyConstraint("schedule_id"),
        sa.UniqueConstraint("task_id", name="uq_schedules_task_id_vertical_slice"),
    )
    op.create_index("ix_schedules_task_id", "schedules", ["task_id"], unique=False)

    # Create runs table
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("task_id", sa.String(length=48), nullable=False),
        sa.Column("schedule_id", sa.String(length=48), nullable=True),
        sa.Column(
            "run_status",
            sa.Enum(
                "planned",
                "queued",
                "running",
                "completed",
                "failed",
                "canceled",
                name="runstatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("external_execution_ref", sa.String(length=240), nullable=True),
        sa.Column("occurrence_key", sa.String(length=32), nullable=True),
        sa.Column("instruction_source_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.schedule_id"],
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
        ),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint(
            "schedule_id", "occurrence_key", name="uq_runs_schedule_occurrence_key"
        ),
    )
    op.create_index(
        "ix_runs_history_status_finished_at",
        "runs",
        ["run_status", "finished_at"],
        unique=False,
    )
    op.create_index("ix_runs_schedule_id", "runs", ["schedule_id"], unique=False)
    op.create_index("ix_runs_task_id", "runs", ["task_id"], unique=False)

    # Create occurrence_overrides table
    op.create_table(
        "occurrence_overrides",
        sa.Column("occurrence_override_id", sa.String(length=48), nullable=False),
        sa.Column("task_id", sa.String(length=48), nullable=False),
        sa.Column("schedule_id", sa.String(length=48), nullable=False),
        sa.Column("original_occurrence_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("override_occurrence_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("override_instruction_delta", sa.Text(), nullable=True),
        sa.Column(
            "override_status",
            sa.Enum(
                "active",
                "canceled",
                name="occurrenceoverridestatus",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("rescheduled_run_id", sa.String(length=48), nullable=True),
        sa.Column("external_schedule_ref", sa.String(length=240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.schedule_id"],
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
        ),
        sa.ForeignKeyConstraint(
            ["rescheduled_run_id"],
            ["runs.run_id"],
        ),
        sa.PrimaryKeyConstraint("occurrence_override_id"),
        sa.UniqueConstraint(
            "schedule_id",
            "original_occurrence_at",
            name="uq_occurrence_overrides_schedule_original",
        ),
    )
    op.create_index(
        "ix_occurrence_overrides_schedule_id",
        "occurrence_overrides",
        ["schedule_id"],
        unique=False,
    )
    op.create_index(
        "ix_occurrence_overrides_task_id",
        "occurrence_overrides",
        ["task_id"],
        unique=False,
    )

    # Create run_events table
    op.create_table(
        "run_events",
        sa.Column("run_event_id", sa.String(length=48), nullable=False),
        sa.Column("run_id", sa.String(length=48), nullable=False),
        sa.Column("task_id", sa.String(length=48), nullable=False),
        sa.Column("schedule_id", sa.String(length=48), nullable=True),
        sa.Column("event_type", sa.String(length=96), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("temporal_workflow_id", sa.String(length=240), nullable=True),
        sa.Column("temporal_workflow_run_id", sa.String(length=240), nullable=True),
        sa.Column("activity_type", sa.String(length=120), nullable=True),
        sa.Column("activity_attempt", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.run_id"],
        ),
        sa.PrimaryKeyConstraint("run_event_id"),
    )
    op.create_index(
        "ix_run_events_run_id_created_at",
        "run_events",
        ["run_id", "created_at", "run_event_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop run_events table
    op.drop_index("ix_run_events_run_id_created_at", table_name="run_events")
    op.drop_table("run_events")

    # Drop occurrence_overrides table
    op.drop_index("ix_occurrence_overrides_task_id", table_name="occurrence_overrides")
    op.drop_index(
        "ix_occurrence_overrides_schedule_id", table_name="occurrence_overrides"
    )
    op.drop_table("occurrence_overrides")

    # Drop runs table
    op.drop_index("ix_runs_task_id", table_name="runs")
    op.drop_index("ix_runs_schedule_id", table_name="runs")
    op.drop_index("ix_runs_history_status_finished_at", table_name="runs")
    op.drop_table("runs")

    # Drop schedules table
    op.drop_index("ix_schedules_task_id", table_name="schedules")
    op.drop_table("schedules")

    # Drop executor profile foreign keys
    op.drop_constraint(
        "fk_templates_default_executor_profile_id_executor_profiles",
        "templates",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tasks_executor_profile_id_executor_profiles",
        "tasks",
        type_="foreignkey",
    )

    # Drop executor_profiles table
    op.drop_index(
        "ix_executor_profiles_executor_default", table_name="executor_profiles"
    )
    op.drop_index("ix_executor_profiles_archived_at", table_name="executor_profiles")
    op.drop_table("executor_profiles")

    # Drop templates table
    op.drop_index("ix_templates_archived_at_created_at", table_name="templates")
    op.drop_table("templates")

    # Drop tasks table
    op.drop_table("tasks")
