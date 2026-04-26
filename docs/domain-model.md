---
title: "VesperaFlow Domain Model"
status: draft
version: "1.0"
aligned_requirements: "docs/requirements.md"
aligned_architecture: "docs/architecture.md"
---

# VesperaFlow Domain Model

## 1. Purpose

This document defines the core domain entities, their relationships, and the state machines that govern planning and execution behavior in VesperaFlow.

It is the source of truth for:

- domain entity definitions
- cardinality and ownership relationships
- lifecycle states
- allowed state transitions
- derived view semantics used by calendar, recurring todo, and one-time kanban

It does not define:

- storage engine implementation details
- API payload shapes
- UI layout or screen design

## 2. Modeling Principles

### 2.1 Separate Intent from Execution

A user's planned AI work must remain distinct from any individual execution attempt.

### 2.2 Separate Reusable Definitions from Live Objects

Templates are reusable blueprints. Tasks are live user work items. Editing a template must not retroactively mutate already-created tasks.

### 2.3 Make Schedule Explicit

Time behavior must not be implied inside a task body. One-time and recurring timing behavior is expressed through an explicit schedule object.

### 2.4 Derive Views from Domain State

Calendar, recurring todo views, and one-time kanban views are read models built from backend state. They are not independent sources of truth.

## 3. Core Entities

### 3.1 Template

Represents a reusable task blueprint.

Fields:

- `template_id`
- `name`
- `description`
- `instruction_source`
- `default_task_title`
- `default_target_working_directory` nullable string; when present, tasks created from the template use it as the default target directory unless the caller overrides it
- `default_execution_mode`
- `default_schedule_config`
- `default_executor` nullable enum: `claude_code`, `debug_printer`; when null, tasks created from the template use the install-level default executor
- `version` monotonically increasing integer, used for optimistic concurrency
- `created_at`
- `updated_at`
- `archived_at` nullable

Notes:

- A template may be created from scratch or from an existing task.
- A template can be edited or archived.
- A template does not execute directly.

### 3.2 Task

Represents a user-owned unit of planned AI work.

Fields:

- `task_id`
- `title`
- `instruction_source`
- `normalized_instruction` nullable
- `target_working_directory` nullable string for legacy rows; new executable tasks require an absolute existing directory where the selected executor performs user work
- `execution_mode` enum: `one_time`, `recurring`
- `task_status` enum, **derived** from schedule and latest run (see §4.4)
- `template_id` nullable
- `executor` enum: `claude_code`, `debug_printer`; resolved from the install-level default or optional template default at task creation time
- `version` monotonically increasing integer, used for optimistic concurrency
- `created_at`
- `updated_at`
- `archived_at` nullable

Notes:

- A task is the primary product object a user creates, reviews, edits, and inspects.
- A task may exist before any run has happened.
- A task may be created from a template but becomes independently editable after creation.
- MVP supports `claude_code` and `debug_printer`; `codex` and `opencode` are post-MVP.
- The target working directory is distinct from a run artifact directory. The target is the user project being changed; the run artifact directory is VesperaFlow-owned storage for executor output.

### 3.3 Schedule

Represents when a task should execute.

Fields:

- `schedule_id`
- `task_id`
- `schedule_type` enum: `single_run`, `recurring_rule`
- `schedule_status` enum
- `planned_at` nullable, timezone-aware timestamp
- `recurrence_rule` nullable, iCalendar RRULE string
- `recurrence_timezone` nullable, IANA timezone name (for example `Asia/Hong_Kong`), required when `schedule_type = recurring_rule`
- `next_run_at` nullable, timezone-aware timestamp in UTC
- `last_materialized_at` nullable
- `external_schedule_ref` nullable
- `version` monotonically increasing integer, used for optimistic concurrency
- `created_at`
- `updated_at`

Notes:

- Every active task has at most one active schedule in MVP.
- One-time tasks use `single_run`.
- Recurring tasks use `recurring_rule`.
- See §12 for timezone and DST semantics.

### 3.4 Run

Represents one concrete execution attempt.

Fields:

- `run_id`
- `task_id`
- `schedule_id` nullable
- `run_status` enum
- `planned_start_at`
- `actual_start_at` nullable
- `finished_at` nullable
- `result_summary` nullable
- `failure_reason` nullable
- `external_execution_ref` nullable
- `created_at`
- `updated_at`

Notes:

- A one-time task typically results in one run.
- A recurring task may generate many runs over time.
- Runs are append-only historical records except for status updates during execution.

### 3.5 Occurrence Override

Represents a single-instance exception to a recurring schedule.

Fields:

- `occurrence_override_id`
- `task_id`
- `schedule_id`
- `original_occurrence_at`
- `override_occurrence_at` nullable
- `override_instruction_delta` nullable
- `override_status` enum: `active`, `canceled`
- `created_at`
- `updated_at`

Notes:

- This entity is used when a user edits only one instance of a recurring series.
- It does not replace the parent recurring task or recurring schedule.
- MVP supports both time overrides and instruction overrides for a single occurrence.
- Calendar read models are generated by combining the parent schedule with matching overrides in the requested time window.

## 4. Supporting Enums

### 4.1 Task Status

`task_status` captures the current user-visible lifecycle of the task definition. It is a derived projection, not an independently writable column; see §4.4.

Values:

- `scheduled`
- `paused`
- `running`
- `completed`
- `failed`
- `canceled`
- `archived`

Semantics:

- `scheduled`: task has an active future one-time run or active recurring schedule
- `paused`: recurring schedule is temporarily inactive
- `running`: one-time task execution is currently in progress
- `completed`: terminal state for one-time tasks after successful execution
- `failed`: terminal state for one-time tasks after failed execution
- `canceled`: one-time task or recurring series future work has been canceled before further execution
- `archived`: hidden from active planning surfaces but preserved historically

### 4.2 Schedule Status

Values:

- `pending`
- `active`
- `paused`
- `completed`
- `canceled`

Semantics:

- `pending`: created but not yet activated
- `active`: eligible to trigger future execution
- `paused`: temporarily disabled
- `completed`: single-run schedule already fired and requires no future triggers
- `canceled`: no further triggers will occur

### 4.3 Run Status

Values:

- `planned`
- `queued`
- `running`
- `completed`
- `failed`
- `canceled`

Semantics:

- `planned`: run record has been materialized but execution has not started
- `queued`: handed off for execution but not yet actively running
- `running`: execution in progress
- `completed`: terminal success
- `failed`: terminal failure
- `canceled`: terminal cancellation before completion

### 4.4 Task Status Derivation

`task_status` is a deterministic projection computed from the task's `execution_mode`, its `archived_at` timestamp, its active `schedule.schedule_status`, and the status of its most recent `Run`.

Derivation table for one-time tasks:

| Condition | `task_status` |
|---|---|
| `archived_at` is not null | `archived` |
| Latest run `run_status = running` | `running` |
| Latest run `run_status = completed` | `completed` |
| Latest run `run_status = failed` | `failed` |
| Latest run `run_status = canceled` and schedule `canceled` | `canceled` |
| No run yet, schedule `active` or `pending` | `scheduled` |
| Schedule `canceled` and no terminal run | `canceled` |

Derivation table for recurring tasks:

| Condition | `task_status` |
|---|---|
| `archived_at` is not null | `archived` |
| Schedule `active` | `scheduled` |
| Schedule `paused` | `paused` |
| Schedule `canceled` | `canceled` |
| Schedule `pending` | `scheduled` |

Rules:

- Recurring tasks never transition to `running`, `completed`, or `failed` at the task level; run outcomes are surfaced through `latest_run_outcome` on recurring read models.
- The derivation is recomputed and cached after every persistence Activity that mutates a `Schedule` or terminal `Run`.
- The cached value is the source of truth for API responses, but the derivation rules above are the authoritative definition.

## 5. Entity Relationships

### 5.1 Cardinality

- One `Template` can produce many `Task` records
- One `Task` can reference zero or one `Template`
- One `Task` has zero or one active `Schedule` in MVP
- One `Schedule` belongs to exactly one `Task`
- One `Task` can have many `Run` records over time
- One `Run` belongs to exactly one `Task`
- One `Schedule` can generate many `Run` records over time
- One recurring `Schedule` can have many `OccurrenceOverride` records

### 5.2 Relationship Rules

- Deleting or archiving a template must not delete tasks created from it
- Canceling a schedule must not delete historical runs
- Archiving a task must preserve schedule and run history for audit and display
- A recurring task must never create a second active schedule for the same task in MVP
- A one-time task must never create more than one non-canceled planned run in MVP
- Editing only one recurring occurrence must not mutate the parent recurrence rule

## 6. Aggregate Boundaries

### 6.1 Template Aggregate

Owns:

- template metadata
- reusable instruction defaults
- reusable timing defaults

Does not own:

- derived tasks
- run history

### 6.2 Task Aggregate

Owns:

- task definition
- task lifecycle status
- current linked schedule
- recent run summary projection

This is the main aggregate boundary for product logic.

### 6.3 Run Aggregate

Owns:

- execution attempt state
- outcome metadata
- external execution reference

Run records should be append-oriented and independent enough to preserve history even if task settings change later.

### 6.4 Occurrence Override Aggregate

Owns:

- one-off recurrence exceptions
- single-instance time changes
- single-instance instruction overrides

Does not own:

- parent recurring definition
- historical runs outside the overridden occurrence

## 7. State Machines

### 7.1 Task State Machine

#### Allowed States

- `scheduled`
- `paused`
- `running`
- `completed`
- `failed`
- `canceled`
- `archived`

#### Allowed Transitions

- `scheduled -> running`
- `scheduled -> paused`
- `scheduled -> canceled`
- `paused -> scheduled`
- `paused -> canceled`
- `running -> completed`
- `running -> failed`
- `completed -> archived`
- `failed -> scheduled`
- `failed -> archived`
- `canceled -> archived`

#### Transition Rules

- `scheduled -> running` occurs when a one-time run enters active execution
- `scheduled -> paused` is valid only for recurring tasks
- `scheduled -> canceled` is valid when future execution is intentionally stopped
- `running -> completed` is valid when active execution succeeds
- `running -> failed` is valid when active execution fails
- `failed -> scheduled` is valid only for one-time tasks when the user explicitly retries or reschedules

#### Invalid Transitions

- `completed -> running`
- `canceled -> running`
- `archived -> running`
- `completed -> scheduled`
- `canceled -> scheduled`

### 7.2 Schedule State Machine

#### Allowed States

- `pending`
- `active`
- `paused`
- `completed`
- `canceled`

#### Allowed Transitions

- `pending -> active`
- `active -> paused`
- `active -> completed`
- `active -> canceled`
- `paused -> active`
- `paused -> canceled`

#### Transition Rules

- One-time schedules typically move `pending -> active -> completed` or `pending -> active -> canceled`
- Recurring schedules typically move `pending -> active -> paused`, `paused -> active`, or `active -> canceled`
- `completed` is terminal and used only for single-run schedules after their planned trigger has been consumed

### 7.3 Run State Machine

#### Allowed States

- `planned`
- `queued`
- `running`
- `completed`
- `failed`
- `canceled`

#### Allowed Transitions

- `planned -> queued`
- `planned -> canceled`
- `queued -> running`
- `queued -> failed`
- `queued -> canceled`
- `running -> completed`
- `running -> failed`
- `running -> canceled`

#### Transition Rules

- A run may be materialized in `planned` before the execution layer has accepted it
- `planned -> canceled` is allowed if the task is canceled before execution starts
- `queued -> failed` is allowed if handoff succeeds but execution cannot begin correctly
- Terminal run states are `completed`, `failed`, and `canceled`

## 8. Cross-Entity Invariants

- A `task.execution_mode = one_time` must have a `schedule.schedule_type = single_run`
- A `task.execution_mode = recurring` must have a `schedule.schedule_type = recurring_rule`
- A `task_status = paused` implies `schedule_status = paused`
- A `run_status = running` implies visible active execution context; for one-time tasks it implies `task_status = running`
- A one-time task with a successful terminal run should not retain an active schedule
- A canceled schedule must not produce new runs
- A recurring task may have many historical runs but only one active schedule in MVP
- A recurring task remains `scheduled` or `paused` at the task level even when its latest run has failed
- Template edits affect only future tasks created from that template
- A mutating write that observes a stale `version` must fail with a conflict and must not be partially applied

## 9. Editing Rules

### 9.1 Task Editing

- A task in `scheduled`, `paused`, `failed`, or `canceled` may be edited where the action is valid for its execution mode
- A task in `running` may not have execution-critical fields edited
- A one-time task in `completed` may not be edited as an active task; it must be duplicated explicitly to create new planned work

### 9.2 Template Editing

- Templates may be edited at any time
- Template edits apply only to future task instantiations

### 9.3 Schedule Editing

- A single-run schedule may be rescheduled before the run starts
- A recurring schedule may have its future recurrence changed while preserving historical runs
- Editing a recurring task from calendar must support two scopes: `this_occurrence_only` and `this_and_future`
- Schedule edits must not mutate already-finished runs

### 9.4 Recurring Edit Scope Rules

- `this_occurrence_only` creates or updates an `OccurrenceOverride`
- `this_and_future` updates the parent recurring schedule and task definition for future occurrences only
- Historical occurrences and finished runs remain unchanged in both cases

## 10. Derived Read Models

### 10.1 Calendar Item

Derived from:

- task
- schedule
- future run occurrence or next run projection

Required fields:

- `calendar_item_id`
- `task_id`
- `title`
- `execution_mode`
- `occurrence_at`
- `state`

Rules:

- One-time tasks appear once at their scheduled time
- Recurring tasks appear as future occurrences based on the active recurrence rule
- Historical completed runs belong to history views, not the default forward-looking calendar

### 10.2 Kanban Card

Derived from:

- task
- latest relevant run
- schedule state

Required fields:

- `card_id`
- `task_id`
- `title`
- `kanban_column`
- `next_run_at` nullable
- `latest_run_status` nullable
- `result_summary` nullable

Rules:

- only one-time tasks are eligible
- `Upcoming` includes scheduled future work
- `Running` includes active runs
- `Completed` includes successful terminal outcomes
- `Failed` includes failed terminal outcomes
- `Paused` is not a kanban column for MVP

### 10.3 Recurring Todo Item

Derived from:

- recurring task
- schedule
- latest relevant run

Required fields:

- `item_id`
- `task_id`
- `title`
- `recurrence_rule`
- `next_run_at`
- `schedule_status`
- `latest_run_outcome` nullable
- `latest_outcome_summary` nullable

Rules:

- only recurring tasks are eligible
- items remain stable over time instead of moving across transient execution columns
- schedule state is primary and stable, using conservative task-level semantics of `scheduled` or `paused`
- latest failure may be shown as an attribute without removing the task from recurring management

### 10.4 Suggested Kanban Mapping

- `Upcoming`: `task_status = scheduled` with no active run
- `Running`: `task_status = running`
- `Completed`: latest run `completed` for a one-time task
- `Failed`: latest run `failed` for a one-time task
- `Canceled`: optional filter or hidden from default board

## 11. Example Lifecycles

### 11.1 One-Time Task Lifecycle

```text
Template? optional
  -> Task(scheduled)
  -> Schedule(single_run, active)
  -> Run(planned/queued/running)
  -> Run(completed or failed or canceled)
  -> Schedule(completed or canceled)
  -> Task(completed or failed or canceled)
```

### 11.2 Recurring Task Lifecycle

```text
Task(scheduled)
  -> Schedule(recurring_rule, active)
  -> Run #1
  -> Run #2
  -> Run #N
  -> Task remains scheduled while schedule active
  -> Task(paused) if schedule paused
  -> Task(canceled or archived) if future execution terminated
```

## 12. Timezone and Recurrence Semantics

### 12.1 Authoritative Storage Format

- All `planned_at`, `next_run_at`, and run timestamp fields are stored in UTC as timezone-aware values
- API payloads serialize timestamps using ISO 8601 with an explicit timezone offset

### 12.2 Recurrence Evaluation Timezone

- Recurring schedules carry an explicit `recurrence_timezone` (IANA zone name) alongside the RRULE
- Each occurrence is produced by evaluating the RRULE in `recurrence_timezone`, then normalized to UTC when stored or compared
- If `recurrence_timezone` is absent on a legacy record, the system falls back to UTC and surfaces a warning

### 12.3 DST Transitions

- A daily recurrence at an unambiguous local time (for example 08:00) fires once per calendar day in the configured zone, following the zone's DST rules
- If a local time does not exist on a given day due to DST spring-forward, the occurrence is shifted forward to the next valid local time on that day
- If a local time occurs twice on a given day due to DST fall-back, the first occurrence is used
- These rules apply only to recurrence evaluation; one-time `planned_at` is already an absolute instant and is not affected

### 12.4 Missed Occurrences During Pause

- While a recurring schedule is `paused`, no runs are created for occurrences whose fire time falls inside the pause window
- On resume, missed occurrences are not backfilled; execution continues from the next future occurrence after the resume instant
- This policy is explicit because silent backfill can trigger a burst of executor invocations without user intent

### 12.5 Frequency Bounds

- MVP rejects recurrence rules with an effective frequency more often than once per 15 minutes
- The bound exists to prevent accidental high-frequency scheduling
- The bound is fixed for MVP and is not configurable per deployment

### 12.6 Archived Task Retrieval

- Archived tasks remain queryable through the same task detail endpoint by id
- Archived tasks are excluded from default active lists unless an explicit `include_archived` filter is provided
- A separate archive-only history surface is not part of MVP
