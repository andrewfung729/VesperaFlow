---
title: "VesperaFlow System Architecture"
status: draft
version: "1.0"
aligned_requirements: "docs/requirements.md"
aligned_temporal_architecture: "docs/temporal-architecture.md"
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
- Temporal-specific Workflow, Activity, Worker, and retry/timeout design, which is defined in `docs/temporal-architecture.md`

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

### 3.1 Local-First (Scoped)

The system is primarily designed for an individual user running the application locally. Data ownership, ease of startup, and operational simplicity take priority over distributed scale.

This is a scoped interpretation of local-first, not a pure offline-first product:

- Product data and run history are stored locally in the user-owned PostgreSQL instance
- Local development and startup must be possible with `docker compose` against local services only
- AI execution is performed by a locally installed coding-agent runtime (see §6.4), invoked through its official SDK in VesperaFlow's Worker process. The runtime, in turn, talks to its own upstream LLM provider, which requires network connectivity at execution time
- VesperaFlow itself never calls an LLM provider API; it only invokes the executor runtime
- Temporal server coordination also requires local network connectivity to the Temporal dev stack

A fully offline or peer-to-peer sync model is explicitly out of scope for MVP.

### 3.2 Plan First, Execute Later

The system must preserve the separation between task planning and task execution. A user should be able to define work now and execute it later without losing intent or traceability.

### 3.3 Human-Visible State

Every planned task and every execution run must have a clear visible state that can be surfaced in calendar and the appropriate operational management view.

### 3.4 Stable Core, Replaceable Executors

Task planning, scheduling, and run tracking should remain stable even if the underlying execution provider changes.

### 3.5 MVP Over Platform Ambition

The initial design should favor a small number of clear domain concepts over a generalized orchestration platform.

### 3.6 Single Durable Scheduler

Temporal is the sole scheduling system for VesperaFlow. All time-based triggering — recurring runs, one-time deferred runs, and any future time-based behavior — is implemented through Temporal Schedules and Temporal timers.

VesperaFlow does not use:

- operating-system `cron` or `at`
- in-process schedulers such as APScheduler, Celery beat, or RQ scheduled jobs
- PostgreSQL-backed polling schedulers
- application-level delay queues or sleep loops
- any hybrid fallback between Temporal and another scheduler

This is a single-path decision, not a preference. Adding a second scheduling mechanism is out of scope. See `docs/adr/002-execution-engine-choice.md`.

## 4. Technical Selection

This section records the current implementation-oriented architecture choices that best fit the MVP domain model and expected near-term evolution.

### 4.1 Frontend

Recommended selection:

- `Vue 3`
- `Tailwind CSS`

Rationale:

- the product is an authenticated planning and operations interface rather than an SEO-first content surface
- the primary UI complexity is view switching, task composition, filtering, and detail inspection across calendar, kanban, recurring todo, and history
- Vue provides a clear component model for these interaction-heavy surfaces
- Tailwind CSS supports fast MVP iteration, but should still be constrained by shared design tokens and reusable UI primitives

Implementation note:

- domain and workflow rules must remain backend-owned; frontend state should stay focused on presentation, form interaction, and user-driven filtering

### 4.2 Backend API

Recommended selection:

- `FastAPI`

Rationale:

- the backend is primarily a typed product API for task, schedule, run, template, and read-model management
- FastAPI fits schema validation, explicit request and response contracts, and local-first MVP development speed
- Python keeps the API layer aligned with the selected Temporal SDK and reduces cross-language workflow boundaries

Implementation note:

- route handlers should stay thin; domain services should own lifecycle rules, projection logic, and workflow-triggering behavior

### 4.3 Primary Data Store

Recommended selection:

- `PostgreSQL`

Rationale:

- the MVP domain is strongly relational, especially across `Task`, `Schedule`, `Run`, `Template`, and `OccurrenceOverride`
- calendar, history, recurring todo, and task detail all rely on filtering, joining, sorting, and integrity constraints
- PostgreSQL is a better fit than document-oriented storage for preserving product truth and supporting stable read models

Architectural rule:

- PostgreSQL remains the product system of record for user-facing domain state and read-model projections

### 4.4 Durable Execution and Scheduling

Recommended selection:

- `Temporal.io`
- `Temporal Python SDK`

Rationale:

- durable execution is a core product capability rather than a peripheral background job
- the system must support future scheduled work, recurring runs, retries, execution continuity, and long-running orchestration
- Temporal is expected to be the primary workflow engine beyond MVP, so adopting it now avoids a later architecture pivot in the core execution path

Architectural rule:

- Temporal is the execution orchestration layer, not the system of record
- workflow progress, retries, timers, and durable execution state may live in Temporal
- product-visible truth for tasks, schedules, runs, and history remains persisted in PostgreSQL through backend-owned synchronization
- recurring scheduling should prefer Temporal Schedules over Temporal Cron Jobs

### 4.5 Temporal Alignment Rules

Temporal should be modeled as a durable orchestration system rather than a generic background queue.

High-level rules:

- Workflows coordinate durable execution, waiting, cancellation, retries, and state transitions
- Activities own external I/O, database writes, and executor SDK invocations
- Temporal Schedules back all scheduled execution, both recurring and one-time deferred; no alternative scheduler is used
- PostgreSQL remains authoritative for product-facing tasks, schedules, runs, and read models
- FastAPI remains the public command boundary and must not host the main Worker runtime
- Workflow code changes require a Temporal-safe rollout path and replay verification

Detailed Temporal implementation architecture is defined separately in `docs/temporal-architecture.md`, including Workflow types, Activity groups, task queues, Worker topology, Temporal identifiers, retry/timeout policy, idempotency, and replay testing.

### 4.6 Realtime Updates

Current decision:

- realtime updates are explicitly out of scope for MVP

Rationale:

- the primary MVP value is reliable deferred execution and later review, not live collaborative or streaming supervision
- manual refresh and normal polling-based reads are sufficient for the current scope

Future note:

- the backend may later expose SSE or WebSocket streams, but current architecture should not depend on a subscription model

### 4.7 Deployment Position

Current decision:

- production deployment architecture is deferred

Working assumption:

- local development and service composition should remain compatible with `docker compose`

Rationale:

- the selected stack already implies multiple runtime concerns, including web UI, API, PostgreSQL, Temporal services, and worker processes
- even without finalizing production topology, the architecture should preserve clean service boundaries and container-friendly startup assumptions

## 5. System Context

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

## 6. Logical Components

### 6.1 Web UI

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
- executor-specific SDK orchestration rules

### 6.2 Application Backend

The backend is the system of record for product semantics.

Primary responsibilities:

- validate user intent
- persist tasks, templates, schedules, and runs
- translate task definitions into Temporal-facing execution commands
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
- how PostgreSQL records and Temporal resources stay synchronized

The backend should own:

- Temporal Schedule creation, update, pause, resume, trigger, and delete commands for recurring tasks
- Workflow start and control commands for one-time or in-flight execution
- translation between product ids and Temporal ids or handles

### 6.3 Scheduling / Durable Execution Layer

This layer is responsible for time-based triggering and reliable progression of execution.

Primary responsibilities:

- host Temporal Schedules for recurring execution timing
- wake jobs at scheduled times
- preserve execution continuity across restarts
- track workflow progress
- support retries or terminal failure states where needed

Temporal-specific responsibilities:

- maintain durable Workflow execution history
- deliver Signals, Updates, and Queries to the correct Workflow when used
- provide Schedule lifecycle operations without redefining product semantics

This layer should not be treated as the product domain model. It supports execution durability, but product state naming and UX semantics remain owned by the backend.

### 6.4 AI Executor Adapter

This component delegates a planned task to an external coding-agent runtime invoked inside a run-scoped working directory. VesperaFlow does not implement an agent runtime and does not call LLM provider APIs directly; it relies on each executor's existing runtime to do that work. See `docs/adr/002-execution-engine-choice.md`.

Primary responsibilities:

- translate task content into a normalized invocation of the configured executor
- invoke the executor inside the run's working directory through its official SDK or CLI transport in VesperaFlow's Worker process
- observe and persist the executor's progress signals when the SDK or CLI transport exposes them
- observe the executor's terminal outcome and translate it to backend-owned run states
- propagate cancellation into the executor using its native cancellation mechanism

By isolating executor logic behind a stable adapter, the system avoids coupling task planning to any single agent runtime or LLM provider.

#### Supported Executors

MVP supports these executors:

- `claude_code` — Anthropic's Claude Code, invoked via the Claude Agent SDK
- `codex` — OpenAI Codex CLI, invoked via non-interactive `codex exec`
- `kimi_code` — Moonshot AI's Kimi Code, invoked via the `kimi` CLI text transport
- `debug_printer` — local runtime simulator that logs the execution snapshot and completes successfully

`opencode` and additional executor integrations are post-MVP candidates.

Executor selection is profile-primary. New task and template flows choose an executor profile that owns the executor kind plus default model/env. MVP still stores the resolved executor on the task so every run can be traced to the executor kind intended when the task was created.

#### Adapter Interface Shape

The adapter is invoked from executor Activities with a small, stable executor-oriented contract:

- Input: an execution snapshot containing `run_id`, the selected executor name, optional executor profile id, normalized instructions, the run's working directory, optional executor-specific parameters, and an idempotency key derived from `run_id`
- Output: a normalized execution outcome containing terminal status (`completed` / `failed`), a short `result_summary`, optional `result_artifact_ref` (path to files written inside the working directory), a terminal-outcome code from the executor, and a `failure_reason` category when not successful
- Cancellation: the adapter must translate an Activity cancellation into the executor's native cancellation mechanism and must not retry after a cancellation signal

Executor-specific details (SDK client construction, CLI process management, event framing, file layout conventions, and the executor's own authentication with its upstream provider) remain inside the adapter and are not exposed to the Workflow. Concrete executor modules may import their SDK at module top level, but those modules must only be reachable from Worker startup or Activity-only paths; package roots, Workflow modules, and lightweight facades must stay SDK-free for Temporal sandbox imports.

#### Non-Goals

- the adapter does not call LLM APIs directly; the executor runtime makes those calls
- the adapter does not implement prompt construction, tool selection, tool calling, memory, or streaming agent logic; those live in the executor runtime
- the adapter does not manage LLM provider credentials; the executor is expected to be authenticated by the user through its supported mechanism before VesperaFlow invokes it

### 6.5 Local Data Store

The local store persists product-facing state that should remain queryable independent of execution history internals.

Primary responsibilities:

- task definitions
- recurring schedule definitions
- template definitions
- run summaries
- view-friendly metadata
- history read-model projections

The local store should preserve the information required to render product views even if the underlying execution system changes later.

## 7. Domain Model

Some early discussions use terms such as `schedule` and `run`. In the formal architecture, the core domain should be normalized into a smaller set of stable concepts.

### 7.1 Core Entities

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

### 7.2 Supporting Concepts

#### Task Mode

- `one_time`
- `recurring`

#### Run State

Backend-owned run states, authoritative in `docs/domain-model.md`:

- `planned`
- `queued`
- `running`
- `completed`
- `failed`
- `canceled`

These are backend semantics. UI columns may group or rename them. `paused` is a `Schedule` state, not a `Run` state, and is surfaced through recurring todo and task detail rather than kanban.

#### View Grouping

Kanban columns should be derived from domain state rather than treated as the source of truth. For MVP, kanban applies only to one-time tasks:

- `Upcoming` maps to `planned`, `queued`, and scheduled future work without an active run
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

## 8. Primary Flows

### 8.1 One-Time Deferred Task Flow

```text
User creates task
  -> Backend validates and stores task
  -> Backend creates single-run schedule
  -> Backend starts or arranges the Temporal execution path
  -> Temporal Workflow waits until planned time or is started for due execution
  -> Workflow invokes Activities for provider work and persistence side effects
  -> Backend-owned records are synchronized from execution progress
  -> UI surfaces result in calendar / kanban / detail view
```

### 8.2 Recurring Task Flow

```text
User creates recurring task
  -> Backend stores task and recurrence rule
  -> Backend creates or updates a linked Temporal Schedule
  -> Temporal Schedule starts each due Workflow run
  -> Workflow executes Activities for provider work and persistence side effects
  -> Backend appends run history and updates recurring read models
  -> UI shows future occurrences and past outcomes
```

### 8.3 Template Reuse Flow

```text
User creates or saves template
  -> Backend stores reusable definition
  -> User starts new task from template
  -> Backend copies template content into a new task
  -> New task becomes independently editable
```

### 8.4 Calendar Flow

```text
UI requests upcoming scheduled work
  -> Backend returns time-oriented task and run projections
  -> UI renders upcoming executions by date/time
  -> User opens an item for details or editing
```

### 8.5 Kanban Flow

```text
UI requests one-time work grouped by execution state
  -> Backend returns one-time task / run summaries with derived status
  -> UI renders cards grouped by product-visible state
  -> User opens a card for details or action
```

### 8.6 Recurring Todo Flow

```text
UI requests recurring tasks
  -> Backend returns recurring task summaries with next run and schedule state
  -> Backend decorates items with latest run outcome where relevant
  -> UI renders a todo-style list of recurring work
  -> User opens an item to inspect, pause, resume, or edit recurrence
```

### 8.7 History Flow

```text
UI requests history view
  -> Backend returns historical run summaries joined with task metadata
  -> UI renders completed and failed runs in reverse chronological order
  -> User opens an item to inspect related task detail
```

## 9. State Ownership

One of the key SA tasks is making ownership explicit.

### 9.1 UI-Owned State

- current filters
- selected view mode
- expanded card or modal state
- temporary form state before save

### 9.2 Backend-Owned State

- task definition truth
- template truth
- schedule truth
- run summary truth
- status mapping rules
- editability rules

### 9.3 Scheduler-Owned State

- trigger timing
- durable workflow progression
- internal retry bookkeeping

### 9.4 Executor-Owned State

State owned by the external executor runtime SDK and its upstream LLM provider; opaque to VesperaFlow:

- executor internal session state, tool-call traces, and any files it writes outside the run working directory
- model-specific logs, provider request/response payloads, and streaming chunks or SDK event streams
- token accounting, rate-limit counters, and cost data

VesperaFlow treats this layer as a black box; the executor's terminal outcome and a short result summary are the only signals the product surfaces.

## 10. Data Boundaries

### 10.1 Product Store Versus Execution Store

The product must not rely exclusively on execution-engine internals for user-facing queries.

Therefore:

- user-facing lists should come from product-controlled records
- execution-engine identifiers should be stored as references, not used as primary user-facing objects
- task and template retrieval should remain available even if execution history is archived or rotated

### 10.2 Execution Progress Synchronization

Execution progress is persisted to PostgreSQL by backend-owned persistence Activities running inside the Worker process. There is no separate event bus between the execution layer and the backend API in MVP; both share the PostgreSQL system of record.

Typical synchronization points persisted as PostgreSQL writes:

- schedule created
- schedule paused or resumed
- run started
- run completed
- run failed
- run canceled

Detailed Activity-level contracts and idempotency rules for these writes are defined in `docs/temporal-architecture.md`.

## 11. Read Models for Core Views

The current product direction strongly implies three primary operational views and one task creation surface. These should be reflected in architecture as explicit read models.

### 11.1 Calendar Read Model

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

### 11.2 Kanban Read Model

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

### 11.3 Recurring Todo Read Model

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

### 11.4 Task Detail Read Model

Purpose:

- show a task definition together with its schedule and recent runs

Required fields:

- task definition
- schedule information
- template origin, if any
- recent run list
- current editable actions

## 12. API Surface Areas

Formal payload design belongs in a separate API specification, but the architecture should define responsibility boundaries.

### 12.1 Task Management Interface

Supports:

- create task
- update task
- delete or cancel task
- retrieve task detail

### 12.2 Schedule Management Interface

Supports:

- create single-run schedule
- create recurring schedule
- pause schedule
- resume schedule
- reschedule future execution

### 12.3 Template Management Interface

Supports:

- create template
- list templates
- update template
- delete template
- instantiate task from template

### 12.4 View Query Interface

Supports:

- fetch calendar items
- fetch one-time kanban groups
- fetch recurring todo items
- fetch run history

### 12.5 Execution Update Interface

Supports:

- receive status updates from execution layer
- push live status updates to UI if needed

## 13. Non-Functional Requirements

### 13.1 Reliability

The system should not miss due executions under normal local operation and restart scenarios.

### 13.2 Recoverability

After local restart, the system should recover:

- active schedules
- pending one-time tasks
- run history references

### 13.3 Observability

The user should be able to inspect:

- what was planned
- what actually ran
- whether it succeeded or failed

Developer-facing observability must make it possible to trace a run from task definition to external execution reference end-to-end.

MVP observability baseline:

- structured JSON logs across API, Worker, and adapter processes
- every log line carries `task_id`, `schedule_id`, `run_id`, and the Temporal `workflow_id` / `run_id` when present
- Activity attempts log start, success, retry, and terminal failure with the same identifiers
- a minimal metrics set is exposed for local introspection: `runs_started_total`, `runs_completed_total`, `runs_failed_total`, `executor_run_latency_seconds`, `schedule_fire_delay_seconds`
- detailed tracing is optional for MVP but the log correlation-ID strategy must not block adding OpenTelemetry later

### 13.4 Security and Secrets

MVP security posture:

- authentication and authorization are intentionally out of scope for the single-local-user MVP, but the domain model must preserve a clean extension point for a future `user_id` association
- VesperaFlow may store executor profile env overrides, including write-only secret env values in the local PostgreSQL database for v1. These values are resolved only inside Worker Activities and must not be logged or serialized into Workflow history.
- Worker Activities may pass explicit executor profile environment values into the executor invocation, but these values must not be logged, serialized into Temporal payloads, or expanded to the full Worker process environment
- task `instruction_source` and executor output may contain sensitive content; they must not be serialized into Temporal Workflow input payloads beyond what is strictly required, and structured logs must not emit full instruction or output bodies at default log levels
- PostgreSQL is assumed to be on trusted local storage for MVP; at-rest encryption is a deployment concern tracked in `docs/adr/004-security-posture.md`

### 13.5 Concurrency and Reconciliation

The system must behave predictably under concurrent edits and partial failure between PostgreSQL and Temporal.

MVP rules:

- mutating API endpoints must support optimistic concurrency via a resource `version` field or `If-Match` header; concurrent writers receive `409 conflict`
- a user-initiated edit, pause, resume, or cancel that cannot be mirrored to Temporal must be rolled back in PostgreSQL and surfaced as `execution_unavailable`
- scheduler-fired runs and user edits that target the same schedule are resolved by the product command path owning the final state; in-flight runs are not retroactively mutated
- PostgreSQL is authoritative for user-visible status; divergence from Temporal is reconciled by backend-owned tooling described in `docs/temporal-architecture.md`

### 13.6 Simplicity of Deployment

The architecture should remain operable by one user on one machine with minimal setup.

## 14. Architecture Decisions to Record Separately

These topics are tracked as ADRs rather than remaining implicit:

- `docs/adr/001-local-first.md` — why the product is local-first (scoped)
- `docs/adr/002-execution-engine-choice.md` — why Temporal is the sole scheduling system and why executor runtimes stay behind Worker adapters
- `docs/adr/003-task-schedule-run-separation.md` — why task, schedule, and run are separate domain objects
- `docs/adr/004-security-posture.md` — MVP secrets handling and future authz extension
- `docs/adr/005-derived-view-states.md` — why kanban state is derived from backend semantics rather than UI-only labels

## 15. Resolved Architecture Questions

These items were previously open and are now architectural decisions for MVP:

- Recurring future occurrences are generated on demand for bounded calendar windows. PostgreSQL persists the parent `Schedule`, completed or in-flight `Run`s, and explicit `OccurrenceOverride`s; it does not eagerly materialize all future recurring occurrences.
- A one-off exception to a recurring occurrence is modeled as `OccurrenceOverride` keyed by `schedule_id` and the original occurrence time. The parent recurring `Schedule` remains unchanged.
- Run detail preserves normalized executor metadata only: executor name, SDK adapter version, terminal status, terminal code or SDK error category, short result summary, artifact references, timestamps, and run working-directory reference. Raw SDK event streams and bulky outputs stay in the run working directory unless a later feature explicitly promotes them.
- Task creation stores both `instruction_source` and `normalized_instruction` as first-class fields. A `Run` stores an immutable execution snapshot so later task edits do not rewrite historical execution intent.
- MVP resolves the executor from the install-level default, optional template default, or task creation request and stores the resolved value on `Task.executor`. Supported MVP values are `claude_code`, `codex`, `kimi_code`, and `debug_printer`.
- The API preflight checks target working-directory access. It also checks `codex` binary availability for `codex` and `kimi` binary availability for `kimi_code`. Codex Worker execution uses `codex exec` in full-permission bypass mode and may pass the executor profile `default_model` through as `--model`; Codex authentication and provider configuration remain owned by the CLI. Claude Agent SDK import is a normal Worker dependency, while authentication/configuration failures are mapped during task execution to actionable product errors such as `executor_not_authenticated`, `executor_misconfigured`, and `executor_workspace_unavailable`.
- Archived tasks remain queryable through the normal task detail endpoint by id. Default active lists exclude them unless `include_archived` is requested.
- The 15-minute recurrence frequency bound is fixed for MVP and is not configurable per deployment.
- The Claude Agent SDK compatibility policy is dependency-lock driven: the Worker pins the validated SDK version and imports it normally instead of reimplementing package-version or optional-import policy at runtime.

## 16. Recommended Next Documents

This architecture document should be followed by:

1. `docs/domain-model.md`
2. `docs/temporal-architecture.md`
3. `docs/functional-spec.md`
4. `docs/api-spec.md`
5. `docs/ux-spec.md`
6. `docs/glossary.md`
7. `docs/adr/001-local-first.md`
8. `docs/adr/002-execution-engine-choice.md`
9. `docs/adr/003-task-schedule-run-separation.md`
10. `docs/adr/004-security-posture.md`
11. `docs/adr/005-derived-view-states.md`
