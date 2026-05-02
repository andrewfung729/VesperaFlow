---
title: "VesperaFlow API Specification"
status: draft
version: "1.0"
aligned_requirements: "docs/requirements.md"
aligned_architecture: "docs/architecture.md"
aligned_domain_model: "docs/domain-model.md"
aligned_functional_spec: "docs/functional-spec.md"
---

# VesperaFlow API Specification

## 1. Purpose

This document defines the application-facing API contract for the current VesperaFlow MVP.

It covers:

- resource boundaries
- endpoint responsibilities
- request and response shapes
- validation rules
- error model
- behavior for one-time tasks, recurring tasks, templates, calendar, one-time kanban, recurring todo, task detail, and executor preflight
- history read model behavior

It does not cover:

- internal service-to-service contracts
- storage schema
- executor-specific SDK invocation payloads and SDK event formats
- realtime push interfaces, which are out of scope for MVP

## 2. API Style

### 2.1 Transport

- Protocol: HTTPS or local HTTP in development
- Format: JSON request and response bodies
- Time format: ISO 8601 with an explicit timezone offset on every timestamp
- Resource ids: opaque strings

### 2.2 Versioning

- Base path: `/api/v1`
- Breaking changes require a new versioned base path

### 2.3 Authentication

MVP assumes a single local user. Authentication is out of scope for this phase.

## 3. Resource Model

### 3.1 Primary Resources

- `templates`
- `tasks`
- `schedules`
- `runs`
- `occurrence-overrides`

### 3.2 Read Model Resources

- `calendar-items`
- `kanban-columns`
- `recurring-todo-items`
- `task-detail`
- `history-items`
- `executor-preflight`

## 4. Shared Conventions

### 4.1 Envelope Style

Successful responses may return either a single resource or a list result.

Single resource:

```json
{
  "data": {}
}
```

List resource:

```json
{
  "data": [],
  "meta": {
    "total": 0
  }
}
```

### 4.2 Error Response

All non-2xx responses return:

```json
{
  "error": {
    "code": "string_code",
    "message": "Human-readable summary",
    "details": {}
  }
}
```

### 4.3 Common Error Codes

- `validation_error` — the request payload failed field or format validation
- `not_found` — the addressed resource does not exist
- `conflict` — optimistic concurrency conflict; the client's `If-Match` or `version` did not match current state
- `invalid_state_transition` — the requested action is not valid for the resource's current state
- `invalid_schedule_scope` — recurring-scope parameter is missing or not applicable
- `unsupported_operation` — operation is not supported by the current execution mode
- `execution_unavailable` — the command was rejected because the execution layer could not be reached or rolled back safely; the PostgreSQL write was rolled back and the client should retry
- `executor_not_available` — the requested or default executor is not available on the host; surfaced on task creation and on run start
- `executor_not_authenticated` — the configured executor SDK is installed but not authenticated or not configured for use
- `executor_misconfigured` — the configured executor SDK is present but fails at runtime because of configuration or SDK transport errors
- `executor_workspace_unavailable` — the run artifact directory or selected target working directory cannot be created or accessed
- `internal_error` — unexpected server failure

### 4.4 Pagination

List endpoints that can grow unbounded should support:

- `limit`
- `offset`

The calendar endpoint is additionally bounded by the `from`/`to` window; see §11.

### 4.5 Filtering

Read endpoints may support:

- `status`
- `execution_mode`
- `from`
- `to`
- `include_archived`

### 4.6 Optimistic Concurrency

Mutating endpoints (any `POST`, `PATCH`, or `DELETE` that changes a resource) enforce optimistic concurrency:

- every mutable resource exposes a monotonically increasing `version` integer
- clients must echo the observed `version` using either the `If-Match` header (`If-Match: "42"`) or a `version` field in the request body
- create endpoints do not require `If-Match`; all updates, archives, cancels, pause/resume commands, and scoped occurrence edits require an observed version
- if the server's current version differs, the endpoint returns `409 conflict` with error code `conflict` and does not partially apply
- the server's response to a successful mutation always includes the new `version`

### 4.7 Timezone Rules

- all `planned_at`, `next_run_at`, `actual_start_at`, `finished_at`, and `original_occurrence_at` fields are serialized in ISO 8601 with an explicit timezone offset
- recurring schedules carry an additional `recurrence_timezone` (IANA zone name) in addition to any RRULE timestamps
- the server evaluates recurrence rules in `recurrence_timezone` and normalizes fire times to UTC; see `docs/domain-model.md` §12 for DST and missed-occurrence rules

## 5. Shared Schemas

### 5.1 Template Object

```json
{
  "template_id": "tpl_123",
  "name": "Weekly Research Template",
  "description": "Reusable recurring research task",
  "instruction_source": "Summarize the top announcements...",
  "default_task_title": "Weekly Research",
  "default_target_working_directory": "/Users/you/project",
  "default_execution_mode": "recurring",
  "default_schedule_config": {
    "schedule_type": "recurring_rule",
    "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0",
    "recurrence_timezone": "Asia/Hong_Kong"
  },
  "default_executor": "debug_printer",
  "version": 1,
  "created_at": "2026-04-24T09:00:00+08:00",
  "updated_at": "2026-04-24T09:00:00+08:00",
  "archived_at": null
}
```

### 5.2 Task Object

```json
{
  "task_id": "task_123",
  "title": "Nightly Deep Research",
  "instruction_source": "Research competitor pricing changes...",
  "normalized_instruction": null,
  "target_working_directory": "/Users/you/project",
  "execution_mode": "one_time",
  "task_status": "scheduled",
  "template_id": "tpl_123",
  "executor": "claude_code",
  "executor_profile_id": "xpr_default_claude_code",
  "version": 1,
  "created_at": "2026-04-24T09:00:00+08:00",
  "updated_at": "2026-04-24T09:00:00+08:00",
  "archived_at": null
}
```

`task_status` is a server-derived projection; see `docs/domain-model.md` §4.4.

`executor` identifies the resolved coding-agent runtime that will perform this task's runs. `executor_profile_id` identifies the profile that supplied executor-level defaults such as model and environment for future runs. MVP supports:

- `claude_code` — Claude Agent SDK
- `codex` — Codex CLI non-interactive `codex exec` transport
- `kimi_code` — Kimi CLI text transport
- `debug_printer` — local runtime simulator that logs the execution snapshot and completes successfully

Clients must pass `executor_profile_id`, pass the legacy `executor` field, or reference a template that supplies a default executor/profile. If only `executor` is provided, the backend resolves that executor's default profile. There is no install-level executor fallback. `opencode` and additional runtimes are post-MVP. VesperaFlow does not call LLM APIs directly; the chosen executor runtime performs the work. See `docs/adr/002-execution-engine-choice.md`.

Executor profile responses include `secret_env_keys` only. Secret env values are write-only in the API response even though this local-first v1 stores them in PostgreSQL.

`target_working_directory` is the absolute existing directory where the executor performs user work. It is distinct from the per-run artifact workspace used by VesperaFlow to store summaries and transcripts.

Templates may define `default_target_working_directory`. When present, creating or instantiating a task from that template may omit `target_working_directory`; the backend copies the template default onto the task. Callers can still provide a task-specific target directory to override the template default.

### 5.3 Schedule Object

```json
{
  "schedule_id": "sch_123",
  "task_id": "task_123",
  "schedule_type": "single_run",
  "schedule_status": "active",
  "planned_at": "2026-04-24T23:30:00+08:00",
  "recurrence_rule": null,
  "recurrence_timezone": null,
  "next_run_at": "2026-04-24T23:30:00+08:00",
  "last_materialized_at": null,
  "external_schedule_ref": "vesperaflow.schedule.sch_123",
  "version": 1,
  "created_at": "2026-04-24T09:00:00+08:00",
  "updated_at": "2026-04-24T09:00:00+08:00"
}
```

`recurrence_timezone` is required for recurring schedules and null for single-run schedules.

### 5.4 Run Object

```json
{
  "run_id": "run_123",
  "task_id": "task_123",
  "schedule_id": "sch_123",
  "run_status": "running",
  "planned_start_at": "2026-04-24T23:30:00+08:00",
  "actual_start_at": "2026-04-24T23:31:00+08:00",
  "finished_at": null,
  "result_summary": null,
  "failure_reason": null,
  "external_execution_ref": "wf_abc",
  "occurrence_key": null,
  "created_at": "2026-04-24T23:30:00+08:00",
  "updated_at": "2026-04-24T23:31:00+08:00"
}
```

### 5.4.1 Run Preview Object

Run list and history surfaces return a lightweight preview payload instead of full
`result_summary` or `failure_reason`.

```json
{
  "run_id": "run_123",
  "task_id": "task_123",
  "schedule_id": "sch_123",
  "run_status": "failed",
  "planned_start_at": "2026-04-24T23:30:00+08:00",
  "actual_start_at": "2026-04-24T23:31:00+08:00",
  "finished_at": "2026-04-24T23:35:00+08:00",
  "occurrence_key": null,
  "created_at": "2026-04-24T23:30:00+08:00",
  "updated_at": "2026-04-24T23:35:00+08:00",
  "outcome_preview": "Executor failed after validation step...",
  "outcome_truncated": true,
  "outcome_source": "failure_reason"
}
```

Preview behavior:

- source priority is `result_summary`, then `failure_reason`
- preview length is capped at 240 characters
- previews longer than 240 characters are truncated and suffixed with `...`
- `outcome_truncated` indicates truncation
- `outcome_source` is `result_summary`, `failure_reason`, or `null`

### 5.4.2 Run Event Object

Run events are the persisted execution timeline for a run. They are safe for
default UI display and do not include full instructions, credentials, or full
executor output.

```json
{
  "run_event_id": "evt_123",
  "run_id": "run_123",
  "task_id": "task_123",
  "schedule_id": "sch_123",
  "event_type": "executor.completed",
  "severity": "info",
  "message": "Executor invocation completed successfully.",
  "details": {
    "executor": "debug_printer",
    "terminal_code": "debug_printer_completed"
  },
  "temporal_workflow_id": "vesperaflow.run.run_123",
  "temporal_workflow_run_id": "temporal-run-id",
  "activity_type": "execute_agent_run",
  "activity_attempt": 1,
  "created_at": "2026-04-24T23:35:00+08:00"
}
```

### 5.5 Occurrence Override Object

```json
{
  "occurrence_override_id": "ovr_123",
  "task_id": "task_456",
  "schedule_id": "sch_456",
  "original_occurrence_at": "2026-04-29T09:00:00+08:00",
  "override_occurrence_at": "2026-04-29T11:00:00+08:00",
  "override_instruction_delta": null,
  "override_status": "active",
  "created_at": "2026-04-24T10:00:00+08:00",
  "updated_at": "2026-04-24T10:00:00+08:00"
}
```

### 5.6 Executor Preflight Object

```json
{
  "executor": "claude_code",
  "status": "available",
  "code": "executor_preflight_passed",
  "message": "Claude Code target workspace is available",
  "details": {
    "live": false
  }
}
```

`status` is one of:

- `available`
- `warning`
- `unavailable`

`code` is stable enough for clients to branch on. Claude Code preflight may
return `executor_workspace_unavailable` or `executor_preflight_passed` from the
API without running an agent. Kimi Code and Codex additionally check that their
CLI binary is available on `PATH`. Authentication and runtime configuration
failures are reported by the Worker when a task runs.

### 5.7 Executor Preflight Endpoint

`GET /api/v1/executors/preflight`

Query params:

- `executor`: `claude_code`, `codex`, `kimi_code`, or `debug_printer`; defaults to `claude_code`
- `target_working_directory`: absolute target workspace path to validate

Response:

- `200 OK` with `Executor Preflight Object`

Behavior:

- `debug_printer` returns available without a target workspace
- `claude_code`, `codex`, and `kimi_code` validate that the target workspace is an
  existing absolute directory visible to the API process; `codex` and
  `kimi_code` also verify that their CLI binary is on `PATH`
- live executor auth/configuration checks are intentionally not performed by
  the API because executor invocation belongs to Worker Activities

## 6. Template Endpoints

### 6.1 Create Template

`POST /api/v1/templates`

Purpose:

- create a template directly without first creating a task

Request:

```json
{
  "name": "Nightly Research",
  "description": "Reusable overnight research task",
  "instruction_source": "Research product launches...",
  "default_task_title": "Nightly Research",
  "default_target_working_directory": "/Users/you/project",
  "default_execution_mode": "one_time",
  "default_schedule_config": {
    "schedule_type": "single_run",
    "planned_at": null,
    "recurrence_rule": null
  },
  "default_executor": "debug_printer"
}
```

Response:

- `201 Created`

Validation:

- `name` is required
- `instruction_source` is required
- `default_target_working_directory`, when provided, must be absolute and must refer to an existing directory on the API/Worker host
- `default_execution_mode` must be `one_time` or `recurring`
- if `default_schedule_config.schedule_type = recurring_rule`, `recurrence_rule` is required

### 6.2 List Templates

`GET /api/v1/templates`

Query params:

- `include_archived`
- `limit`
- `offset`

Response:

```json
{
  "data": [
    {
      "template_id": "tpl_123",
      "name": "Nightly Research"
    }
  ],
  "meta": {
    "total": 1
  }
}
```

### 6.3 Get Template

`GET /api/v1/templates/{template_id}`

Response:

- `200 OK` with full `Template Object`

### 6.4 Update Template

`PATCH /api/v1/templates/{template_id}`

Purpose:

- edit a template without mutating already-created tasks

Request:

```json
{
  "name": "Updated Template Name",
  "instruction_source": "Updated instructions..."
}
```

Response:

- `200 OK`

### 6.5 Archive Template

`POST /api/v1/templates/{template_id}/archive`

Purpose:

- remove a template from active selection without deleting dependent task history

Response:

- `200 OK`

### 6.6 Instantiate Task from Template

`POST /api/v1/templates/{template_id}/instantiate`

Purpose:

- create a new task prefilled from a template

Request:

```json
{
  "title": "Tonight's Research Run",
  "target_working_directory": "/Users/you/override-project",
  "execution_mode": "one_time",
  "schedule": {
    "schedule_type": "single_run",
    "planned_at": "2026-04-24T23:30:00+08:00"
  }
}
```

Response:

- `201 Created`
- returns `task`, `schedule`

`target_working_directory` is optional when the template has `default_target_working_directory`; otherwise it is required.

## 7. Task Endpoints

### 7.1 Create Task

`POST /api/v1/tasks`

Purpose:

- create one-time or recurring tasks directly

Request for one-time:

```json
{
  "title": "Overnight Research",
  "instruction_source": "Research funding announcements...",
  "target_working_directory": "/Users/you/project",
  "execution_mode": "one_time",
  "executor_profile_id": "xpr_default_claude_code",
  "template_id": null,
  "schedule": {
    "schedule_type": "single_run",
    "planned_at": "2026-04-24T23:30:00+08:00"
  }
}
```

Request for recurring:

```json
{
  "title": "Daily Digest",
  "instruction_source": "Summarize key updates...",
  "execution_mode": "recurring",
  "template_id": "tpl_123",
  "schedule": {
    "schedule_type": "recurring_rule",
    "recurrence_rule": "RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
    "recurrence_timezone": "Asia/Hong_Kong"
  }
}
```

Response:

- `201 Created`

```json
{
  "data": {
    "task": {},
    "schedule": {},
    "run": null
  }
}
```

Validation:

- `title` is required
- `instruction_source` is required
- request must include `executor_profile_id` or `executor`, unless a referenced template supplies a default executor/profile
- `target_working_directory` is required unless a referenced template supplies `default_target_working_directory`; the resolved value must be absolute and must refer to an existing directory on the API/Worker host
- `execution_mode` is required
- one-time tasks must provide `planned_at` with a timezone offset in the future
- recurring tasks must provide `recurrence_rule` and `recurrence_timezone`
- `schedule.schedule_type` must match `execution_mode`
- recurrence frequency must not exceed once per 15 minutes (see `docs/domain-model.md` §12.5)
- `executor`, if provided, must be `claude_code`, `codex`, `kimi_code`, or `debug_printer`; if omitted the request or template must provide `executor_profile_id`
- if the target working directory is invalid, the endpoint returns `422 validation_error`
- recurring Temporal Schedule fires materialize a product run in the first Workflow Activity, keyed by `(schedule_id, occurrence_key)`
- SDK import, authentication, and runtime configuration failures are reported by the Worker on run start

### 7.2 List Tasks

`GET /api/v1/tasks`

Query params:

- `execution_mode`
- `status`
- `include_archived`
- `limit`
- `offset`

Purpose:

- generic listing for task management surfaces

### 7.3 Get Task

`GET /api/v1/tasks/{task_id}`

Response:

- `200 OK` with `Task Object`

### 7.4 Update Task

`PATCH /api/v1/tasks/{task_id}`

Purpose:

- update task definition fields that are valid in the current state

Request:

```json
{
  "title": "Updated Title",
  "instruction_source": "Updated instructions..."
}
```

Validation:

- task must not be archived
- execution-critical edits may be rejected when task is `running`

### 7.5 Archive Task

`POST /api/v1/tasks/{task_id}/archive`

Purpose:

- hide task from active planning surfaces while preserving history

### 7.6 Duplicate Task

`POST /api/v1/tasks/{task_id}/duplicate`

Purpose:

- create a new task from an existing task definition

### 7.7 Run One-Time Task Now

`POST /api/v1/tasks/{task_id}/run-now`

Purpose:

- trigger a planned one-time task immediately instead of waiting for its scheduled time

Response:

- `200 OK` with `Run Object`

Validation:

- task must be `one_time`
- schedule must be `active`
- latest run must be `planned`

Behavior:

- deletes the future Temporal Schedule to prevent duplicate execution
- starts `TaskRunWorkflow` directly via the Temporal Client
- the workflow skips its sleep timer because `planned_start_at` is set to the current time
- on success the run transitions through `queued` → `running` → terminal state as normal

## 8. Schedule Endpoints

### 8.1 Get Schedule

`GET /api/v1/tasks/{task_id}/schedule`

Response:

- `200 OK` with `Schedule Object`

### 8.2 Update One-Time Schedule

`PATCH /api/v1/tasks/{task_id}/schedule`

Purpose:

- reschedule one-time work before it starts

Request:

```json
{
  "planned_at": "2026-04-25T00:30:00+08:00"
}
```

Validation:

- task must be `one_time`
- schedule must not be `completed` or `canceled`
- new `planned_at` must be in the future

### 8.3 Update Recurring Schedule

`PATCH /api/v1/tasks/{task_id}/schedule`

Purpose:

- update recurring rule and run parameters for future occurrences

Request:

```json
{
  "version": 3,
  "title": "Weekday repo triage",
  "instruction_source": "Review stale issues and open a short summary.",
  "target_working_directory": "/Users/you/project",
  "executor": "codex",
  "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;BYHOUR=8;BYMINUTE=0",
  "recurrence_timezone": "Asia/Hong_Kong"
}
```

Validation:

- task must be `recurring`
- recurrence rule must be valid
- recurrence frequency must not exceed once per 15 minutes
- if `recurrence_timezone` is omitted the server keeps the prior value
- if `target_working_directory` is provided it must be an absolute existing directory
- if `executor` is provided it must be one of the supported executor names

### 8.4 Pause Recurring Schedule

`POST /api/v1/tasks/{task_id}/schedule/pause`

Purpose:

- stop future recurring runs without deleting task history

Validation:

- only valid for recurring tasks with active schedule

### 8.5 Resume Recurring Schedule

`POST /api/v1/tasks/{task_id}/schedule/resume`

Purpose:

- reactivate future recurring runs

Validation:

- only valid for recurring tasks with paused schedule

### 8.6 Cancel Future Execution

`POST /api/v1/tasks/{task_id}/schedule/cancel`

Purpose:

- cancel future scheduled execution

Behavior:

- for one-time tasks, cancels the pending future execution
- for recurring tasks, cancels the recurring schedule entirely

## 9. Recurring Occurrence Editing Endpoints

Occurrence edits are POST endpoints with the occurrence timestamp in the body. An earlier draft passed the timestamp in the URL path; that design was dropped because URL-encoding of ISO timestamps with timezone offsets was awkward and hard to parse consistently across clients.

### 9.1 Update Recurring Occurrence

`POST /api/v1/tasks/{task_id}/occurrences/update`

Purpose:

- edit a recurring calendar occurrence with explicit scope

Request:

```json
{
  "original_occurrence_at": "2026-04-29T09:00:00+08:00",
  "scope": "this_occurrence_only",
  "version": 3,
  "planned_at": "2026-04-29T11:00:00+08:00",
  "instruction_source": null,
  "recurrence_rule": null,
  "recurrence_timezone": null
}
```

Allowed scope values:

- `this_occurrence_only`
- `this_and_future`

Behavior:

- `this_occurrence_only` creates or updates an `OccurrenceOverride`; `planned_at`, `instruction_source`, or both may be provided
- `this_and_future` updates the parent recurring definition for future occurrences only; callers may provide `recurrence_rule`, `recurrence_timezone`, `instruction_source`, or a combination

Validation:

- task must be recurring
- `original_occurrence_at` is required and must match a projected occurrence of the active recurrence rule
- `scope` is required
- at least one editable field must be provided
- if `scope = this_occurrence_only`, the targeted occurrence must be future or not yet started
- single-occurrence `planned_at` overrides must not be earlier than
  `original_occurrence_at`; moving an occurrence earlier than the recurring
  Temporal Schedule fire time is deferred until a future Temporal schedule
  mutation design

Error cases:

- `400 validation_error` for missing `original_occurrence_at` or `scope`
- `409 invalid_schedule_scope` for unsupported scope or invalid series behavior
- `409 conflict` if the resource `version` does not match

### 9.2 Cancel Recurring Occurrence

`POST /api/v1/tasks/{task_id}/occurrences/cancel`

Purpose:

- cancel one occurrence of a recurring series without canceling the full series

Request:

```json
{
  "original_occurrence_at": "2026-04-29T09:00:00+08:00",
  "scope": "this_occurrence_only",
  "version": 3
}
```

Behavior:

- creates or updates an `OccurrenceOverride` with `override_status = canceled`

## 10. Run Endpoints

### 10.1 List Runs for Task

`GET /api/v1/tasks/{task_id}/runs`

Query params:

- `status`
- `limit`
- `offset`

Response:

- `200 OK` with `Run Preview Object[]`

Notes:

- this endpoint is optimized for run list/archive surfaces
- full outcomes are intentionally omitted from list payloads

### 10.2 Get Run

`GET /api/v1/runs/{run_id}`

Response:

- `200 OK` with `Run Object`

### 10.2.1 List Run Events

`GET /api/v1/runs/{run_id}/events`

Query params:

- `limit`
- `offset`

Response:

- `200 OK` with `Run Event Object[]`

Notes:

- events are ordered by `created_at asc, run_event_id asc`
- event details are short structured metadata, not executor transcripts

### 10.3 Get Run Reader Detail

`GET /api/v1/tasks/{task_id}/runs/{run_id}/reader`

Response:

- `200 OK`

```json
{
  "data": {
    "task": {},
    "schedule": {},
    "run": {},
    "previous_run_id": "run_122",
    "next_run_id": "run_121"
  }
}
```

Behavior:

- returns full selected `run` outcome plus task/schedule context
- `previous_run_id` and `next_run_id` are based on run archive ordering:
  `created_at desc, run_id desc`

### 10.4 Retry Failed One-Time Task

`POST /api/v1/tasks/{task_id}/retry`

Purpose:

- schedule a new future run based on an existing failed one-time task

Request:

```json
{
  "planned_at": "2026-04-25T01:00:00+08:00"
}
```

Validation:

- task must be `one_time`
- latest terminal status must be `failed` or `canceled`
- `planned_at` must be future

## 11. Calendar Endpoints

### 11.1 List Calendar Items

`GET /api/v1/views/calendar`

Query params:

- `from`
- `to`
- `include_completed`

Response:

```json
{
  "data": [
    {
      "calendar_item_id": "cal_123",
      "task_id": "task_123",
      "title": "Overnight Research",
      "execution_mode": "one_time",
      "occurrence_at": "2026-04-24T23:30:00+08:00",
      "original_occurrence_at": null,
      "state": "scheduled",
      "is_occurrence_override": false,
      "schedule_version": 1
    }
  ]
}
```

Behavior:

- includes one-time future tasks
- includes projected recurring occurrences
- reflects occurrence overrides where applicable

Validation:

- `from` must be before `to`

## 12. One-Time Kanban Endpoints

### 12.1 Get One-Time Kanban Board

`GET /api/v1/views/kanban`

Query params:

- `include_canceled`

Response:

```json
{
  "data": {
    "columns": [
      {
        "column_id": "upcoming",
        "title": "Upcoming",
        "items": [
          {
            "card_id": "card_123",
            "task_id": "task_123",
            "title": "Overnight Research",
            "kanban_column": "upcoming",
            "next_run_at": "2026-04-24T23:30:00+08:00",
            "latest_run_status": null,
            "result_summary": null
          }
        ]
      }
    ]
  }
}
```

Behavior:

- returns one-time tasks only
- groups cards into `upcoming`, `running`, `completed`, `failed`
- completed cards are included by default until archived; clients may add filtering later without changing backend state semantics

## 13. Recurring Todo Endpoints

### 13.1 Get Recurring Todo List

`GET /api/v1/views/recurring-todo`

Query params:

- `status`
- `include_paused`

Response:

```json
{
  "data": [
    {
      "item_id": "todo_123",
      "task_id": "task_456",
      "title": "Daily Digest",
      "recurrence_rule": "RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
      "recurrence_timezone": "Asia/Hong_Kong",
      "next_run_at": "2026-04-25T08:00:00+08:00",
      "schedule_status": "active",
      "task_status": "scheduled",
      "schedule_version": 3,
      "latest_run_id": "run_789",
      "latest_run_outcome": "completed",
      "latest_run_finished_at": "2026-04-24T08:02:00+08:00",
      "result_summary": "Digest completed",
      "failure_reason": null
    }
  ],
  "meta": {
    "total": 1
  }
}
```

Behavior:

- returns recurring tasks only
- keeps recurring items stable instead of moving across kanban columns
- returns active items first by `next_run_at`, followed by paused items by
  recent schedule update
- exposes latest run outcome context without converting the parent recurring
  task to failed or completed

## 14. Task Detail Endpoint

### 14.1 Get Task Detail

`GET /api/v1/tasks/{task_id}/detail`

Purpose:

- provide a single resource for task inspection from calendar, kanban, recurring todo, or list surfaces
- include only the latest run summary; run lists are fetched through run/history endpoints

Response:

```json
{
  "data": {
    "task": {},
    "schedule": {},
    "latest_run": null
  }
}
```

Behavior:

- recurring tasks may include relevant occurrence override context when requested from calendar
- recurring-task actions are derived from conservative task lifecycle states (`scheduled` or `paused`) plus latest run outcome context
- full run history is paged through run and history endpoints
- archived tasks remain readable through this endpoint by id, but are omitted from default active list endpoints unless `include_archived` is provided

Optional query params:

- `occurrence_at`

Purpose of `occurrence_at`:

- resolve detail in the context of a specific recurring occurrence

## 15. History Endpoint

### 15.1 Get History View

`GET /api/v1/views/history`

Query params:

- `status`
- `execution_mode`
- `from`
- `to`
- `limit`
- `offset`

Response:

```json
{
  "data": [
    {
      "history_item_id": "hist_123",
      "run_id": "run_123",
      "task_id": "task_123",
      "title": "Overnight Research",
      "execution_mode": "one_time",
      "run_status": "completed",
      "finished_at": "2026-04-25T01:12:00+08:00",
      "outcome_preview": "Summary generated successfully",
      "outcome_truncated": false,
      "outcome_source": "result_summary"
    }
  ],
  "meta": {
    "total": 1
  }
}
```

Behavior:

- returns completed and failed runs across one-time and recurring tasks
- is a derived read model built from `Run` plus task metadata
- preserves historical visibility even if the parent task or template is later archived

## 16. State-Dependent Action Matrix

### 16.1 Task Actions

| State | Allowed Actions |
|-------|-----------------|
| `scheduled` one-time | update task, reschedule, cancel |
| `scheduled` recurring | update task, update recurrence, pause, cancel |
| `paused` recurring | update task, resume, cancel |
| `running` | inspect only |
| `failed` one-time | inspect, update task, retry, reschedule, archive |
| `completed` one-time | inspect, duplicate, archive |
| `canceled` | inspect, duplicate where supported, archive |

### 16.2 Template Actions

| State | Allowed Actions |
|-------|-----------------|
| active | update, archive, instantiate |
| archived | inspect |

Recurring run failure note:

- a recurring task with a failed latest run remains `scheduled` or `paused` at the task level
- failure is exposed through run resources, history view, and recurring todo `latest_run_outcome`

## 17. Validation Rules

### 17.1 Date and Time

- all scheduled times must be timezone-aware timestamps
- one-time `planned_at` must be in the future at the time of request
- recurring schedules must provide a valid IANA `recurrence_timezone`
- recurrence frequency must not exceed once per 15 minutes
- `from` must be earlier than `to`

### 17.2 Mode and Schedule Consistency

- `execution_mode = one_time` requires `schedule_type = single_run`
- `execution_mode = recurring` requires `schedule_type = recurring_rule`

### 17.3 Recurring Scope

- `this_occurrence_only` must not mutate the recurrence rule
- `this_and_future` must not mutate completed past occurrences or finished runs

### 17.4 Template Integrity

- archiving a template must not break task detail for historical tasks
- task creation from template must copy task content rather than reference mutable template fields directly

## 18. HTTP Status Codes

- `200 OK` for successful reads and updates
- `201 Created` for successful creates
- `400 Bad Request` for malformed input
- `404 Not Found` for missing resource ids
- `409 Conflict` for invalid state transition or scope conflict
- `422 Unprocessable Entity` for semantically invalid fields
- `500 Internal Server Error` for unexpected failures

## 19. API Decisions

- Calendar drag-reschedule is not part of MVP. All calendar rescheduling uses explicit task, schedule, or occurrence edit endpoints.
- If drag-reschedule is added later, it should call the same schedule or occurrence mutation endpoints instead of introducing a drag-specific API.
- Task detail includes only the latest run summary; run lists are loaded through paged run/history endpoints.
- `If-Match` or request-body `version` is required for all mutations of existing resources, even in the single-user local MVP.
