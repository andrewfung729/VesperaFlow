# Database Schema Snapshot

- Generated: 2026-05-30
- Regenerate: `uv run python scripts/generate_agent_facts.py`
- Sources: `packages/store/src/vesperaflow_store/models.py`, `packages/store/alembic/versions/`
- Limitations: generated from importable application metadata, not a live deployment.

## `executor_profiles`

| Column | Type | Nullable | Default |
|---|---|---:|---|
| `profile_id` | `VARCHAR(48)` | no | `` |
| `name` | `VARCHAR(120)` | no | `` |
| `executor` | `VARCHAR(64)` | no | `` |
| `is_enabled` | `BOOLEAN` | no | `True` |
| `is_default` | `BOOLEAN` | no | `False` |
| `default_model` | `VARCHAR(160)` | yes | `` |
| `reasoning_level` | `VARCHAR(160)` | yes | `` |
| `env` | `JSON` | no | `dict` |
| `secret_env` | `JSON` | no | `dict` |
| `version` | `INTEGER` | no | `1` |
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |
| `archived_at` | `DATETIME` | yes | `` |

- Primary key: `profile_id`
- Index `ix_executor_profiles_archived_at`: `archived_at`
- Index `ix_executor_profiles_executor_default`: `executor`, `is_default`

## `occurrence_overrides`

| Column | Type | Nullable | Default |
|---|---|---:|---|
| `occurrence_override_id` | `VARCHAR(48)` | no | `` |
| `task_id` | `VARCHAR(48)` | no | `` |
| `schedule_id` | `VARCHAR(48)` | no | `` |
| `original_occurrence_at` | `DATETIME` | no | `` |
| `override_occurrence_at` | `DATETIME` | yes | `` |
| `override_instruction_delta` | `TEXT` | yes | `` |
| `override_status` | `VARCHAR(64)` | no | `` |
| `rescheduled_run_id` | `VARCHAR(48)` | yes | `` |
| `external_schedule_ref` | `VARCHAR(240)` | yes | `` |
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |

- Primary key: `occurrence_override_id`
- Unique constraint `uq_occurrence_overrides_schedule_original`: `schedule_id`, `original_occurrence_at`
- Foreign key: `rescheduled_run_id` -> `runs.run_id`
- Foreign key: `schedule_id` -> `schedules.schedule_id`
- Foreign key: `task_id` -> `tasks.task_id`
- Index `ix_occurrence_overrides_schedule_id`: `schedule_id`
- Index `ix_occurrence_overrides_task_id`: `task_id`

## `profile_validation_handoffs`

| Column | Type | Nullable | Default |
|---|---|---:|---|
| `handoff_id` | `VARCHAR(48)` | no | `` |
| `executor` | `VARCHAR(64)` | no | `` |
| `default_model` | `VARCHAR(160)` | yes | `` |
| `reasoning_level` | `VARCHAR(160)` | yes | `` |
| `env` | `JSON` | no | `dict` |
| `secret_env` | `JSON` | no | `dict` |
| `created_at` | `DATETIME` | no | `` |
| `expires_at` | `DATETIME` | no | `` |

- Primary key: `handoff_id`
- Index `ix_profile_validation_handoffs_expires_at`: `expires_at`

## `run_events`

| Column | Type | Nullable | Default |
|---|---|---:|---|
| `run_event_id` | `VARCHAR(48)` | no | `` |
| `run_id` | `VARCHAR(48)` | no | `` |
| `task_id` | `VARCHAR(48)` | no | `` |
| `schedule_id` | `VARCHAR(48)` | yes | `` |
| `event_type` | `VARCHAR(96)` | no | `` |
| `severity` | `VARCHAR(16)` | no | `` |
| `message` | `TEXT` | no | `` |
| `details` | `JSON` | no | `` |
| `temporal_workflow_id` | `VARCHAR(240)` | yes | `` |
| `temporal_workflow_run_id` | `VARCHAR(240)` | yes | `` |
| `activity_type` | `VARCHAR(120)` | yes | `` |
| `activity_attempt` | `INTEGER` | yes | `` |
| `created_at` | `DATETIME` | no | `` |

- Primary key: `run_event_id`
- Foreign key: `run_id` -> `runs.run_id`
- Index `ix_run_events_run_id_created_at`: `run_id`, `created_at`, `run_event_id`

## `runs`

| Column | Type | Nullable | Default |
|---|---|---:|---|
| `run_id` | `VARCHAR(48)` | no | `` |
| `task_id` | `VARCHAR(48)` | no | `` |
| `schedule_id` | `VARCHAR(48)` | yes | `` |
| `run_status` | `VARCHAR(64)` | no | `` |
| `planned_start_at` | `DATETIME` | no | `` |
| `actual_start_at` | `DATETIME` | yes | `` |
| `finished_at` | `DATETIME` | yes | `` |
| `instruction_source_snapshot` | `TEXT` | no | `` |
| `result_summary` | `TEXT` | yes | `` |
| `failure_reason` | `TEXT` | yes | `` |
| `external_execution_ref` | `VARCHAR(240)` | yes | `` |
| `occurrence_key` | `VARCHAR(32)` | yes | `` |
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |

- Primary key: `run_id`
- Unique constraint `uq_runs_schedule_occurrence_key`: `schedule_id`, `occurrence_key`
- Foreign key: `schedule_id` -> `schedules.schedule_id`
- Foreign key: `task_id` -> `tasks.task_id`
- Index `ix_runs_history_status_finished_at`: `run_status`, `finished_at`
- Index `ix_runs_schedule_id`: `schedule_id`
- Index `ix_runs_task_id`: `task_id`

## `schedules`

| Column | Type | Nullable | Default |
|---|---|---:|---|
| `schedule_id` | `VARCHAR(48)` | no | `` |
| `task_id` | `VARCHAR(48)` | no | `` |
| `schedule_type` | `VARCHAR(64)` | no | `` |
| `schedule_status` | `VARCHAR(64)` | no | `` |
| `planned_at` | `DATETIME` | yes | `` |
| `recurrence_rule` | `TEXT` | yes | `` |
| `recurrence_timezone` | `VARCHAR(128)` | yes | `` |
| `next_run_at` | `DATETIME` | yes | `` |
| `last_materialized_at` | `DATETIME` | yes | `` |
| `external_schedule_ref` | `VARCHAR(240)` | yes | `` |
| `version` | `INTEGER` | no | `1` |
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |

- Primary key: `schedule_id`
- Unique constraint `uq_schedules_task_id_vertical_slice`: `task_id`
- Foreign key: `task_id` -> `tasks.task_id`
- Index `ix_schedules_task_id`: `task_id`

## `tasks`

| Column | Type | Nullable | Default |
|---|---|---:|---|
| `task_id` | `VARCHAR(48)` | no | `` |
| `title` | `VARCHAR(240)` | no | `` |
| `instruction_source` | `TEXT` | no | `` |
| `normalized_instruction` | `TEXT` | yes | `` |
| `target_working_directory` | `TEXT` | yes | `` |
| `execution_mode` | `VARCHAR(64)` | no | `` |
| `task_status` | `VARCHAR(64)` | no | `` |
| `template_id` | `VARCHAR(48)` | yes | `` |
| `executor` | `VARCHAR(64)` | no | `` |
| `executor_profile_id` | `VARCHAR(48)` | yes | `` |
| `version` | `INTEGER` | no | `1` |
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |
| `archived_at` | `DATETIME` | yes | `` |

- Primary key: `task_id`
- Foreign key: `executor_profile_id` -> `executor_profiles.profile_id`

## `templates`

| Column | Type | Nullable | Default |
|---|---|---:|---|
| `template_id` | `VARCHAR(48)` | no | `` |
| `name` | `VARCHAR(240)` | no | `` |
| `description` | `TEXT` | yes | `` |
| `instruction_source` | `TEXT` | no | `` |
| `default_task_title` | `VARCHAR(240)` | yes | `` |
| `default_target_working_directory` | `TEXT` | yes | `` |
| `default_execution_mode` | `VARCHAR(64)` | no | `` |
| `default_schedule_type` | `VARCHAR(64)` | no | `` |
| `default_planned_at` | `DATETIME` | yes | `` |
| `default_recurrence_rule` | `TEXT` | yes | `` |
| `default_recurrence_timezone` | `VARCHAR(128)` | yes | `` |
| `default_executor` | `VARCHAR(64)` | yes | `` |
| `default_executor_profile_id` | `VARCHAR(48)` | yes | `` |
| `version` | `INTEGER` | no | `1` |
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |
| `archived_at` | `DATETIME` | yes | `` |

- Primary key: `template_id`
- Foreign key: `default_executor_profile_id` -> `executor_profiles.profile_id`
- Index `ix_templates_archived_at_created_at`: `archived_at`, `created_at`
