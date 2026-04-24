---
title: "VesperaFlow System Architecture"
status: draft
version: "1.0"
aligned_requirements: "docs/requirements.md"
---

# VesperaFlow System Architecture

## 1. Purpose

This document defines the formal system architecture for VesperaFlow aligned to the current MVP scope in `docs/requirements.md`.

It focuses on:

- system boundaries
- core domain concepts
- component responsibilities
- data flow between layers
- architectural decisions needed to support MVP features

It does not define:

- product strategy or user value framing
- detailed UI copy or interaction mockups
- full API payload schemas
- implementation task breakdown

## 2. Scope Alignment

### 2.1 In Scope for MVP

This architecture must support the current must-have capabilities defined in `docs/requirements.md`:

- create one-time deferred tasks
- create recurring scheduled tasks
- review planned and completed work
- separate planning from execution
- reuse task templates
- provide calendar view for time-based planning
- provide kanban view for one-time task execution state
- provide todo-style recurring task management view

### 2.2 Explicitly Deferred

The architecture should avoid blocking future support for these items, but they are not first-class MVP design drivers:

- suggested execution timing
- proactive overnight notifications
- multi-user collaboration
- enterprise approval flows
- advanced agent composition
- provider cost optimization

### 2.3 Design Items Requiring Downscope

The following ideas are not required for MVP and should be treated as optional or deferred:

- dashboard as a primary delivery requirement
- `Needs Approval` as a mandatory execution state
- full agents management surface
- full skills management surface
- prompt generation as an independently optimized subsystem

## 3. Architecture Principles

### 3.1 Local-First

The system is primarily designed for an individual user running the application locally. Data ownership, ease of startup, and operational simplicity take priority over distributed scale.

### 3.2 Plan First, Execute Later

The system must preserve the separation between task planning and task execution. A user should be able to define work now and execute it later without losing intent or traceability.

### 3.3 Human-Visible State

Every planned task and every execution run must have a clear visible state that can be surfaced in calendar and the appropriate operational management view.

### 3.4 Stable Core, Replaceable Executors

Task planning, scheduling, and run tracking should remain stable even if the underlying execution provider changes.

### 3.5 MVP Over Platform Ambition

The initial design should favor a small number of clear domain concepts over a generalized orchestration platform.

## 4. System Context

At a high level, the system consists of four layers:

1. A local web client for task planning and review
2. An application backend that owns product logic and domain state
3. A scheduling and durable execution layer
4. One or more AI execution providers

```text
User
  |
  v
Web UI
  |
  v
Application Backend
  | \
  |  \--> Local Data Store
  |
  v
Scheduling / Durable Execution Layer
  |
  v
AI Executor Adapter(s)
  |
  v
LLM / Agent Provider
```

## 5. Logical Components

### 5.1 Web UI

The UI is responsible for user-facing planning and review workflows.

Primary responsibilities:

- create and edit tasks
- choose one-time versus recurring mode
- manage templates
- render calendar view
- render kanban view for one-time tasks
- render recurring task list / todo view
- render history view for completed and failed runs
- show task and run details

The UI should not own:

- scheduling truth
- execution state transitions
- provider-specific orchestration rules

### 5.2 Application Backend

The backend is the system of record for product semantics.

Primary responsibilities:

- validate user intent
- persist tasks, templates, schedules, and runs
- translate task definitions into executable jobs
- synchronize user-visible state with execution state
- expose read and write interfaces to the UI

The backend is the place where product rules live, such as:

- what makes a task one-time versus recurring
- when a task remains editable
- how run history relates to task definitions
- which states appear in kanban
- how recurring tasks are represented in the recurring todo view
- how history entries are projected from run records
- how recurring task lifecycle remains separate from recurring run outcomes

### 5.3 Scheduling / Durable Execution Layer

This layer is responsible for time-based triggering and reliable progression of execution.

Primary responsibilities:

- wake jobs at scheduled times
- preserve execution continuity across restarts
- track workflow progress
- support retries or terminal failure states where needed

This layer should not be treated as the product domain model. It supports execution durability, but product state naming and UX semantics remain owned by the backend.

### 5.4 AI Executor Adapter

This component converts a planned task into a provider-specific execution request.

Primary responsibilities:

- map task content into an execution payload
- invoke the configured provider
- stream or collect execution progress
- normalize outcomes back into backend-owned run states

By isolating executor logic, the system avoids coupling task planning to a single provider.

### 5.5 Local Data Store

The local store persists product-facing state that should remain queryable independent of execution history internals.

Primary responsibilities:

- task definitions
- recurring schedule definitions
- template definitions
- run summaries
- view-friendly metadata
- history read-model projections

The local store should preserve the information required to render product views even if the underlying execution system changes later.

## 6. Domain Model

Some early discussions use terms such as `schedule`, `run`, and `vibe`. In the formal architecture, the core domain should be normalized into a smaller set of stable concepts.

### 6.1 Core Entities

#### Task

Represents user-defined AI work.

Key attributes:

- task id
- title or summary
- original instruction text
- execution mode: `one_time` or `recurring`
- editable definition fields
- linked template id, if created from a template
- lifecycle status visible to product surfaces

#### Schedule

Represents when a task should execute.

Key attributes:

- schedule id
- task id
- schedule type: `single_run` or `recurring_rule`
- next planned execution time
- recurrence rule, if any
- active / paused state

#### Run

Represents one concrete execution attempt generated from a task and schedule.

Key attributes:

- run id
- task id
- schedule id, if applicable
- planned start time
- actual start time
- terminal outcome
- summary of result
- external workflow reference

#### Template

Represents a reusable task definition.

Key attributes:

- template id
- template name
- reusable task content
- default execution settings
- created / updated timestamps

### 6.2 Supporting Concepts

#### Task Mode

- `one_time`
- `recurring`

#### Run State

Suggested backend-owned states:

- `planned`
- `ready`
- `running`
- `completed`
- `failed`
- `canceled`
- `paused`

These are backend semantics. UI columns may group or rename them.

#### View Grouping

Kanban columns should be derived from domain state rather than treated as the source of truth. For MVP, kanban applies only to one-time tasks:

- `Upcoming` maps to `planned`, `ready`, and scheduled future work
- `Running` maps to active execution
- `Completed` maps to successful terminal runs
- `Failed` maps to unsuccessful terminal runs
- `Paused` is not a kanban column; it remains a recurring schedule state surfaced in recurring todo and task detail

`Needs Approval` should remain deferred unless a clear approval requirement enters the PRD.

Recurring tasks should be exposed through a separate todo-style management view oriented around:

- task title
- recurrence rule
- next run time
- active versus paused state
- latest run outcome summary

## 7. Primary Flows

### 7.1 One-Time Deferred Task Flow

```text
User creates task
  -> Backend validates and stores task
  -> Backend creates single-run schedule
  -> Scheduler triggers execution at planned time
  -> Executor runs provider job
  -> Backend records run outcome
  -> UI surfaces result in calendar / kanban / detail view
```

### 7.2 Recurring Task Flow

```text
User creates recurring task
  -> Backend stores task and recurrence rule
  -> Scheduler materializes each due run
  -> Executor performs run
  -> Backend appends run history
  -> UI shows future occurrences and past outcomes
```

### 7.3 Template Reuse Flow

```text
User creates or saves template
  -> Backend stores reusable definition
  -> User starts new task from template
  -> Backend copies template content into a new task
  -> New task becomes independently editable
```

### 7.4 Calendar Flow

```text
UI requests upcoming scheduled work
  -> Backend returns time-oriented task and run projections
  -> UI renders upcoming executions by date/time
  -> User opens an item for details or editing
```

### 7.5 Kanban Flow

```text
UI requests one-time work grouped by execution state
  -> Backend returns one-time task / run summaries with derived status
  -> UI renders cards grouped by product-visible state
  -> User opens a card for details or action
```

### 7.6 Recurring Todo Flow

```text
UI requests recurring tasks
  -> Backend returns recurring task summaries with next run and schedule state
  -> Backend decorates items with latest run outcome where relevant
  -> UI renders a todo-style list of recurring work
  -> User opens an item to inspect, pause, resume, or edit recurrence
```

### 7.7 History Flow

```text
UI requests history view
  -> Backend returns historical run summaries joined with task metadata
  -> UI renders completed and failed runs in reverse chronological order
  -> User opens an item to inspect related task detail
```

## 8. State Ownership

One of the key SA tasks is making ownership explicit.

### 8.1 UI-Owned State

- current filters
- selected view mode
- expanded card or modal state
- temporary form state before save

### 8.2 Backend-Owned State

- task definition truth
- template truth
- schedule truth
- run summary truth
- status mapping rules
- editability rules

### 8.3 Scheduler-Owned State

- trigger timing
- durable workflow progression
- internal retry bookkeeping

### 8.4 Provider-Owned State

- provider execution internals
- model-specific logs or session details
- provider-specific token accounting where available

## 9. Data Boundaries

### 9.1 Product Store Versus Execution Store

The product must not rely exclusively on execution-engine internals for user-facing queries.

Therefore:

- user-facing lists should come from product-controlled records
- execution-engine identifiers should be stored as references, not used as primary user-facing objects
- task and template retrieval should remain available even if execution history is archived or rotated

### 9.2 Event Synchronization

The backend should receive execution progress and translate it into product-facing updates.

Typical synchronization points:

- schedule created
- schedule paused or resumed
- run started
- run completed
- run failed
- run canceled

## 10. Read Models for Core Views

The current product direction strongly implies three primary operational views and one task creation surface. These should be reflected in architecture as explicit read models.

### 10.1 Calendar Read Model

Purpose:

- render one-time tasks on specific dates
- render recurring task occurrences as future planned executions
- support time-oriented inspection and adjustment

Required fields:

- item id
- task id
- title
- execution mode
- scheduled timestamp or occurrence window
- current state

### 10.2 Kanban Read Model

Purpose:

- render one-time operational status by grouped state
- support quick review of what needs attention

Required fields:

- card id
- task id
- latest run id, if any
- title
- grouped status
- next execution time
- latest outcome summary

Rules:

- only one-time tasks are included
- cards are grouped by derived execution state

### 10.3 Recurring Todo Read Model

Purpose:

- render recurring work as a list of ongoing commitments rather than transient execution cards
- support quick pause, resume, inspect, and edit actions

Required fields:

- `item_id`
- `task_id`
- `title`
- `recurrence_rule`
- `next_run_at`
- `schedule_status`
- `latest_run_outcome`

### 10.4 Task Detail Read Model

Purpose:

- show a task definition together with its schedule and recent runs

Required fields:

- task definition
- schedule information
- template origin, if any
- recent run list
- current editable actions

## 11. API Surface Areas

Formal payload design belongs in a separate API specification, but the architecture should define responsibility boundaries.

### 11.1 Task Management Interface

Supports:

- create task
- update task
- delete or cancel task
- retrieve task detail

### 11.2 Schedule Management Interface

Supports:

- create single-run schedule
- create recurring schedule
- pause schedule
- resume schedule
- reschedule future execution

### 11.3 Template Management Interface

Supports:

- create template
- list templates
- update template
- delete template
- instantiate task from template

### 11.4 View Query Interface

Supports:

- fetch calendar items
- fetch one-time kanban groups
- fetch recurring todo items
- fetch run history

### 11.5 Execution Update Interface

Supports:

- receive status updates from execution layer
- push live status updates to UI if needed

## 12. Non-Functional Requirements

### 12.1 Reliability

The system should not miss due executions under normal local operation and restart scenarios.

### 12.2 Recoverability

After local restart, the system should recover:

- active schedules
- pending one-time tasks
- run history references

### 12.3 Observability

The user should be able to inspect:

- what was planned
- what actually ran
- whether it succeeded or failed

Developer-facing observability should also make it possible to trace a run from task definition to external execution reference.

### 12.4 Simplicity of Deployment

The architecture should remain operable by one user on one machine with minimal setup.

## 13. Architecture Decisions to Record Separately

These topics should be tracked as ADRs rather than remaining implicit:

- why the product is local-first
- why a durable scheduling engine is used instead of simple cron
- why task, schedule, and run are separate domain objects
- why kanban state is derived from backend semantics rather than UI-only labels
- why executor integrations are abstracted behind adapters

## 14. Open Architecture Questions

- Should recurring future occurrences be materialized ahead of time or generated on demand for calendar rendering?
- How should the system model a one-off exception created by editing only a single recurring occurrence?
- How much provider-specific metadata should be preserved in run detail without leaking executor complexity into product views?
- Should task creation store both original natural language input and normalized execution instructions as first-class fields?
- Is `vibe` retained as a user-facing concept, or replaced by a more literal `task` / `template` vocabulary in formal specs?

## 15. Recommended Next Documents

This architecture document should be followed by:

1. `docs/domain-model.md`
2. `docs/functional-spec.md`
3. `docs/api-spec.md`
4. `docs/ux-spec.md`
5. `docs/adr/001-local-first.md`
