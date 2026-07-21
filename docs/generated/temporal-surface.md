# Temporal Surface Snapshot

- Generated: 2026-07-20
- Regenerate: `uv run python scripts/generate_agent_facts.py`
- Sources: `apps/api/src/vesperaflow_api/temporal_scheduler.py`, `apps/worker/src/vesperaflow_worker/main.py`, `apps/worker/src/vesperaflow_worker/workflows/`, `apps/worker/src/vesperaflow_worker/activities/`, `packages/core/src/vesperaflow_core/contracts.py`
- Limitations: generated from importable application metadata, not a live deployment.

- Default API task queue: `vesperaflow-default`
- Default Worker task queue: `vesperaflow-default`
- Default namespace: `default`
- Workflow type: `TaskRunWorkflow`
- Workflow class: `vesperaflow_worker.workflows.task_run.TaskRunWorkflow`
- Schedule ID helper: `vesperaflow.schedule.sch_example`
- Workflow ID helper: `vesperaflow.run.<run_id>`
- Data converter: `temporalio.contrib.pydantic.pydantic_data_converter`

## Activities

- `materialize_run`
- `claim_run_for_execution`
- `validate_executor_profile`
- `mark_run_queued`
- `mark_run_running`
- `execute_agent_run`
- `mark_run_completed`
- `mark_run_failed`
- `mark_run_canceled`
- `complete_single_run_schedule`

## Payload Models

### `TaskRunInput`

| Field | Type | Required |
|---|---|---:|
| `run_id` | `str | None` | no |
| `task_id` | `str` | yes |
| `schedule_id` | `str | None` | no |
| `planned_start_at` | `datetime` | yes |
| `occurrence_key` | `str | None` | no |
| `schedule_type` | `ScheduleType | None` | no |
| `execution_snapshot` | `ExecutionSnapshot` | yes |

### `ExecutionSnapshot`

| Field | Type | Required |
|---|---|---:|
| `run_id` | `str | None` | yes |
| `task_id` | `str` | yes |
| `schedule_id` | `str | None` | no |
| `executor` | `ExecutorName` | yes |
| `executor_profile_id` | `str | None` | no |
| `instruction_source` | `str` | yes |
| `planned_start_at` | `datetime` | yes |
| `working_directory` | `str` | yes |
| `target_working_directory` | `str | None` | no |

## Schedule Behavior

- One-time API creation creates a Temporal Schedule whose action starts `TaskRunWorkflow`.
- The product `runs` row is created before Schedule creation and passed to the Workflow by `run_id`.
- Recurring API creation creates a Temporal Schedule whose action starts `TaskRunWorkflow` without a pre-existing `run_id`.
- The first persistence Activity materializes each recurring occurrence into a product `runs` row idempotently by `(schedule_id, occurrence_key)`.
- Pause/resume/update/cancel commands mutate both PostgreSQL schedule truth and the matching Temporal Schedule.
