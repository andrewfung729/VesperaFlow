# Database Schema Snapshot

- Generated: 2026-04-27
- Regenerate: `uv run python scripts/generate_agent_facts.py`
- Sources: `packages/store/src/vesperaflow_store/models.py`, `packages/store/alembic/versions/`
- Limitations: generated from importable application metadata, not a live deployment.

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
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |

- Primary key: `occurrence_override_id`
- Unique constraint `uq_occurrence_overrides_schedule_original`: `schedule_id`, `original_occurrence_at`
- Foreign key: `schedule_id` -> `schedules.schedule_id`
- Foreign key: `task_id` -> `tasks.task_id`
- Index `ix_occurrence_overrides_schedule_id`: `schedule_id`
- Index `ix_occurrence_overrides_task_id`: `task_id`

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
| `version` | `INTEGER` | no | `1` |
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |
| `archived_at` | `DATETIME` | yes | `` |

- Primary key: `task_id`

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
| `version` | `INTEGER` | no | `1` |
| `created_at` | `DATETIME` | no | `` |
| `updated_at` | `DATETIME` | no | `` |
| `archived_at` | `DATETIME` | yes | `` |

- Primary key: `template_id`
- Index `ix_templates_archived_at_created_at`: `archived_at`, `created_at`
