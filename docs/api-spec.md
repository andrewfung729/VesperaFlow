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
- behavior for one-time tasks, recurring tasks, templates, calendar, one-time kanban, recurring todo, and task detail
- history read model behavior

It does not cover:

- internal service-to-service contracts
- storage schema
- provider-specific execution payloads

## 2. API Style

### 2.1 Transport

- Protocol: HTTPS or local HTTP in development
- Format: JSON request and response bodies
- Time format: ISO 8601 with timezone
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

- `validation_error`
- `not_found`
- `conflict`
- `invalid_state_transition`
- `invalid_schedule_scope`
- `unsupported_operation`
- `execution_unavailable`
- `internal_error`

### 4.4 Pagination

List endpoints that can grow unbounded should support:

- `limit`
- `offset`

### 4.5 Filtering

Read endpoints may support:

- `status`
- `execution_mode`
- `from`
- `to`
- `include_archived`

## 5. Shared Schemas

### 5.1 Template Object

```json
{
  "template_id": "tpl_123",
  "name": "Weekly Research Template",
  "description": "Reusable recurring research task",
  "instruction_source": "Summarize the top announcements...",
  "default_task_title": "Weekly Research",
  "default_execution_mode": "recurring",
  "default_schedule_config": {
    "schedule_type": "recurring_rule",
    "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0"
  },
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
  "execution_mode": "one_time",
  "task_status": "scheduled",
  "template_id": "tpl_123",
  "created_at": "2026-04-24T09:00:00+08:00",
  "updated_at": "2026-04-24T09:00:00+08:00",
  "archived_at": null
}
```

### 5.3 Schedule Object

```json
{
  "schedule_id": "sch_123",
  "task_id": "task_123",
  "schedule_type": "single_run",
  "schedule_status": "active",
  "planned_at": "2026-04-24T23:30:00+08:00",
  "recurrence_rule": null,
  "next_run_at": "2026-04-24T23:30:00+08:00",
  "last_materialized_at": null,
  "created_at": "2026-04-24T09:00:00+08:00",
  "updated_at": "2026-04-24T09:00:00+08:00"
}
```

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
  "created_at": "2026-04-24T23:30:00+08:00",
  "updated_at": "2026-04-24T23:31:00+08:00"
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
  "default_execution_mode": "one_time",
  "default_schedule_config": {
    "schedule_type": "single_run",
    "planned_at": null,
    "recurrence_rule": null
  }
}
```

Response:

- `201 Created`

Validation:

- `name` is required
- `instruction_source` is required
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
  "execution_mode": "one_time",
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
    "recurrence_rule": "RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0"
  }
}
```

Response:

- `201 Created`

```json
{
  "data": {
    "task": {},
    "schedule": {}
  }
}
```

Validation:

- `title` is required
- `instruction_source` is required
- `execution_mode` is required
- one-time tasks must provide `planned_at`
- recurring tasks must provide `recurrence_rule`
- `schedule.schedule_type` must match `execution_mode`

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

- update recurring rule for future occurrences

Request:

```json
{
  "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;BYHOUR=8;BYMINUTE=0"
}
```

Validation:

- task must be `recurring`
- recurrence rule must be valid

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

### 9.1 Update Recurring Occurrence

`PATCH /api/v1/tasks/{task_id}/occurrences/{original_occurrence_at}`

Purpose:

- edit a recurring calendar occurrence with explicit scope

Request:

```json
{
  "scope": "this_occurrence_only",
  "planned_at": "2026-04-29T11:00:00+08:00",
  "instruction_source": null
}
```

Allowed scope values:

- `this_occurrence_only`
- `this_and_future`

Behavior:

- `this_occurrence_only` creates or updates an `OccurrenceOverride`
- `this_and_future` updates the parent recurring definition for future occurrences only

Validation:

- task must be recurring
- `scope` is required
- at least one editable field must be provided
- if `scope = this_occurrence_only`, the targeted occurrence must be future or not yet started

Error cases:

- `400 validation_error` for missing scope
- `409 invalid_schedule_scope` for unsupported scope or invalid series behavior

### 9.2 Cancel Recurring Occurrence

`POST /api/v1/tasks/{task_id}/occurrences/{original_occurrence_at}/cancel`

Purpose:

- cancel one occurrence of a recurring series without canceling the full series

Request:

```json
{
  "scope": "this_occurrence_only"
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

### 10.2 Get Run

`GET /api/v1/runs/{run_id}`

Response:

- `200 OK` with `Run Object`

### 10.3 Retry Failed One-Time Task

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
      "state": "scheduled",
      "is_occurrence_override": false
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
      "next_run_at": "2026-04-25T08:00:00+08:00",
      "schedule_status": "active",
      "latest_run_outcome": "completed"
    }
  ]
}
```

Behavior:

- returns recurring tasks only
- keeps recurring items stable instead of moving across kanban columns

## 14. Task Detail Endpoint

### 14.1 Get Task Detail

`GET /api/v1/tasks/{task_id}/detail`

Purpose:

- provide a single resource for task inspection from calendar, kanban, recurring todo, or list surfaces

Response:

```json
{
  "data": {
    "task": {},
    "schedule": {},
    "template": null,
    "recent_runs": [],
    "current_actions": [
      "edit",
      "cancel",
      "reschedule"
    ]
  }
}
```

Behavior:

- `current_actions` are derived from task and schedule state
- recurring tasks may include relevant occurrence override context when requested from calendar
- recurring-task actions are derived from conservative task lifecycle states (`scheduled` or `paused`) plus latest run outcome context

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
      "result_summary": "Summary generated successfully"
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

## 16. Live Update Endpoint

### 16.1 Execution Event Stream

`GET /api/v1/streams/runs`

Transport:

- WebSocket or Server-Sent Events

Purpose:

- push execution state changes to active clients

Event shape:

```json
{
  "event_type": "run.updated",
  "task_id": "task_123",
  "run_id": "run_123",
  "run_status": "running",
  "task_status": "running",
  "occurred_at": "2026-04-24T23:31:00+08:00"
}
```

## 17. State-Dependent Action Matrix

### 17.1 Task Actions

| State | Allowed Actions |
|-------|-----------------|
| `scheduled` one-time | update task, reschedule, cancel |
| `scheduled` recurring | update task, update recurrence, pause, cancel |
| `paused` recurring | update task, resume, cancel |
| `running` | inspect only |
| `failed` one-time | inspect, update task, retry, reschedule, archive |
| `completed` one-time | inspect, duplicate, archive |
| `canceled` | inspect, duplicate where supported, archive |

### 17.2 Template Actions

| State | Allowed Actions |
|-------|-----------------|
| active | update, archive, instantiate |
| archived | inspect |

Recurring run failure note:

- a recurring task with a failed latest run remains `scheduled` or `paused` at the task level
- failure is exposed through run resources, history view, and recurring todo `latest_run_outcome`

## 18. Validation Rules

### 18.1 Date and Time

- all scheduled times must be timezone-aware timestamps
- one-time `planned_at` must be in the future at the time of request
- `from` must be earlier than `to`

### 18.2 Mode and Schedule Consistency

- `execution_mode = one_time` requires `schedule_type = single_run`
- `execution_mode = recurring` requires `schedule_type = recurring_rule`

### 18.3 Recurring Scope

- `this_occurrence_only` must not mutate the recurrence rule
- `this_and_future` must not mutate completed past occurrences or finished runs

### 18.4 Template Integrity

- archiving a template must not break task detail for historical tasks
- task creation from template must copy task content rather than reference mutable template fields directly

## 19. HTTP Status Codes

- `200 OK` for successful reads and updates
- `201 Created` for successful creates
- `400 Bad Request` for malformed input
- `404 Not Found` for missing resource ids
- `409 Conflict` for invalid state transition or scope conflict
- `422 Unprocessable Entity` for semantically invalid fields
- `500 Internal Server Error` for unexpected failures

## 20. Open API Questions

- Should direct drag-reschedule in calendar call the same schedule patch endpoint or a dedicated convenience endpoint?
- Should recurring occurrence edits support instruction overrides in MVP, or time-only overrides?
- Should task detail return all recent runs inline or page them through a separate endpoint once history grows?
- Should live updates use WebSocket only, or offer SSE as a simpler local-first default?
