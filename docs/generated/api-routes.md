# API Route Snapshot

- Generated: 2026-05-02
- Regenerate: `uv run python scripts/generate_agent_facts.py`
- Sources: `apps/api/src/vesperaflow_api/app.py`, `apps/api/src/vesperaflow_api/routes/`, `apps/api/src/vesperaflow_api/schemas/`
- Limitations: generated from importable application metadata, not a live deployment.

| Methods | Path | Handler | Request model | Response annotation |
|---|---|---|---|---|
| `GET` | `/api/v1/executor-profiles` | `list_executor_profiles` | `` | `ListEnvelope` |
| `POST` | `/api/v1/executor-profiles` | `create_executor_profile` | `ExecutorProfileCreateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/executor-profiles/{profile_id}` | `get_executor_profile` | `` | `DataEnvelope` |
| `PATCH` | `/api/v1/executor-profiles/{profile_id}` | `update_executor_profile` | `ExecutorProfileUpdateRequest` | `DataEnvelope` |
| `POST` | `/api/v1/executor-profiles/{profile_id}/archive` | `archive_executor_profile` | `VersionedCommand` | `DataEnvelope` |
| `GET` | `/api/v1/executors/preflight` | `preflight_executor` | `` | `DataEnvelope` |
| `GET` | `/api/v1/runs/{run_id}` | `get_run` | `` | `DataEnvelope` |
| `GET` | `/api/v1/runs/{run_id}/events` | `list_run_events` | `` | `ListEnvelope` |
| `GET` | `/api/v1/tasks` | `list_tasks` | `` | `ListEnvelope` |
| `POST` | `/api/v1/tasks` | `create_task` | `TaskCreateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}` | `get_task` | `` | `DataEnvelope` |
| `PATCH` | `/api/v1/tasks/{task_id}` | `update_task` | `TaskUpdateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}/detail` | `get_task_detail` | `` | `DataEnvelope` |
| `POST` | `/api/v1/tasks/{task_id}/occurrences/cancel` | `cancel_occurrence` | `OccurrenceCancelRequest` | `DataEnvelope` |
| `POST` | `/api/v1/tasks/{task_id}/occurrences/update` | `update_occurrence` | `OccurrenceUpdateRequest` | `DataEnvelope` |
| `POST` | `/api/v1/tasks/{task_id}/run-now` | `run_task_now` | `` | `DataEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}/runs` | `list_runs` | `` | `ListEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}/runs/{run_id}/reader` | `get_run_reader_detail` | `` | `DataEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}/schedule` | `get_schedule` | `` | `DataEnvelope` |
| `PATCH` | `/api/v1/tasks/{task_id}/schedule` | `update_schedule` | `ScheduleUpdateRequest` | `DataEnvelope` |
| `POST` | `/api/v1/tasks/{task_id}/schedule/cancel` | `cancel_schedule` | `VersionedCommand` | `DataEnvelope` |
| `POST` | `/api/v1/tasks/{task_id}/schedule/pause` | `pause_schedule` | `VersionedCommand` | `DataEnvelope` |
| `POST` | `/api/v1/tasks/{task_id}/schedule/resume` | `resume_schedule` | `VersionedCommand` | `DataEnvelope` |
| `GET` | `/api/v1/templates` | `list_templates` | `` | `ListEnvelope` |
| `POST` | `/api/v1/templates` | `create_template` | `TemplateCreateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/templates/{template_id}` | `get_template` | `` | `DataEnvelope` |
| `PATCH` | `/api/v1/templates/{template_id}` | `update_template` | `TemplateUpdateRequest` | `DataEnvelope` |
| `POST` | `/api/v1/templates/{template_id}/archive` | `archive_template` | `VersionedCommand` | `DataEnvelope` |
| `POST` | `/api/v1/templates/{template_id}/instantiate` | `instantiate_template` | `TemplateInstantiateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/views/calendar` | `get_calendar` | `` | `ListEnvelope` |
| `GET` | `/api/v1/views/history` | `get_history` | `` | `ListEnvelope` |
| `GET` | `/api/v1/views/kanban` | `get_kanban` | `` | `DataEnvelope` |
| `GET` | `/api/v1/views/recurring-todo` | `get_recurring_todo` | `` | `ListEnvelope` |

## Error Envelopes

- Store errors map to `ErrorEnvelope` with 404, 409, or 500 status.
- `ValueError` and request validation errors map to 422 `validation_error`.
- `unsupported_operation` and `execution_unavailable` runtime errors map to 409.
