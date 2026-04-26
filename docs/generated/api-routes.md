# API Route Snapshot

- Generated: 2026-04-26
- Regenerate: `uv run python scripts/generate_agent_facts.py`
- Sources: `apps/api/src/vesperaflow_api/app.py`, `apps/api/src/vesperaflow_api/routes/`, `apps/api/src/vesperaflow_api/schemas/`
- Limitations: generated from importable application metadata, not a live deployment.

| Methods | Path | Handler | Request model | Response annotation |
|---|---|---|---|---|
| `GET` | `/api/v1/tasks` | `list_tasks` | `` | `ListEnvelope` |
| `POST` | `/api/v1/tasks` | `create_task` | `TaskCreateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}` | `get_task` | `` | `DataEnvelope` |
| `PATCH` | `/api/v1/tasks/{task_id}` | `update_task` | `TaskUpdateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}/detail` | `get_task_detail` | `` | `DataEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}/runs` | `list_runs` | `` | `ListEnvelope` |
| `GET` | `/api/v1/tasks/{task_id}/schedule` | `get_schedule` | `` | `DataEnvelope` |
| `PATCH` | `/api/v1/tasks/{task_id}/schedule` | `update_schedule` | `ScheduleUpdateRequest` | `DataEnvelope` |
| `POST` | `/api/v1/tasks/{task_id}/schedule/cancel` | `cancel_schedule` | `VersionedCommand` | `DataEnvelope` |
| `GET` | `/api/v1/templates` | `list_templates` | `` | `ListEnvelope` |
| `POST` | `/api/v1/templates` | `create_template` | `TemplateCreateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/templates/{template_id}` | `get_template` | `` | `DataEnvelope` |
| `PATCH` | `/api/v1/templates/{template_id}` | `update_template` | `TemplateUpdateRequest` | `DataEnvelope` |
| `POST` | `/api/v1/templates/{template_id}/archive` | `archive_template` | `VersionedCommand` | `DataEnvelope` |
| `POST` | `/api/v1/templates/{template_id}/instantiate` | `instantiate_template` | `TemplateInstantiateRequest` | `DataEnvelope` |
| `GET` | `/api/v1/views/history` | `get_history` | `` | `ListEnvelope` |
| `GET` | `/api/v1/views/kanban` | `get_kanban` | `` | `DataEnvelope` |

## Error Envelopes

- Store errors map to `ErrorEnvelope` with 404, 409, or 500 status.
- `ValueError` and request validation errors map to 422 `validation_error`.
- `unsupported_operation` and `execution_unavailable` runtime errors map to 409.
