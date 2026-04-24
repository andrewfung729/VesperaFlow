---
title: "VesperaFlow Temporal Architecture"
status: draft
version: "1.0"
aligned_architecture: "docs/architecture.md"
aligned_domain_model: "docs/domain-model.md"
aligned_functional_spec: "docs/functional-spec.md"
aligned_api_spec: "docs/api-spec.md"
---

# VesperaFlow Temporal Architecture

## 1. Purpose

This document defines how VesperaFlow uses Temporal for durable scheduling and execution.

It extends `docs/architecture.md` with Temporal-specific implementation architecture:

- Workflow and Activity boundaries
- Temporal Schedule usage
- task queue and Worker topology
- Workflow ID and Schedule ID conventions
- retry, timeout, heartbeat, and idempotency policy
- PostgreSQL synchronization rules
- deployment, versioning, and replay verification expectations

It does not replace the product domain model. PostgreSQL remains the product system of record for tasks, schedules, runs, templates, occurrence overrides, and user-facing read models.

## 2. Temporal Role In The System

Temporal is the durable execution and scheduling layer.

Temporal owns:

- durable timers and schedule triggering
- Workflow execution history
- Activity retry bookkeeping
- Workflow progress through durable orchestration
- delivery of Signals, Updates, and Queries where explicitly used

Temporal does not own:

- product-visible task truth
- product-visible schedule truth
- run history read models
- UI state names and grouping rules
- template data

The backend owns product commands and translates them into Temporal operations.

## 3. MVP Temporal Model

### 3.1 Workflow Types

MVP should use one primary short-lived Workflow type:

#### `TaskRunWorkflow`

Purpose:

- execute one concrete `Run`
- move product-visible run state through queued, running, and terminal outcomes
- call provider and persistence Activities

Input:

- `run_id`, when the product Run is already materialized
- `task_id`
- `schedule_id`
- `planned_start_at`
- `occurrence_key`, when started by a recurring Temporal Schedule before a product Run exists
- immutable execution snapshot derived from the Task and Schedule at run creation time

Behavior:

1. materialize or load the product Run through a persistence Activity
2. mark the run as `running` through a persistence Activity
3. execute the provider request through a provider Activity
4. persist successful result summary through a persistence Activity
5. persist failed or canceled outcome through a persistence Activity

Rules:

- The Workflow must be short-lived and scoped to one run.
- The Workflow must not read PostgreSQL directly.
- The Workflow must not call the provider directly.
- The Workflow must receive the execution snapshot it needs at start time or through deterministic Activity results.

### 3.2 Deferred One-Time Work

One-time tasks should use Temporal Schedule for MVP consistency unless implementation pressure proves this too heavy.

Model:

- Backend creates `Task`, `Schedule(single_run)`, and a planned `Run`.
- Backend creates a Temporal Schedule that starts `TaskRunWorkflow` at `planned_at`.
- After the run starts, the product schedule transitions toward `completed` or terminal state according to domain rules.

Rationale:

- one-time and recurring time triggers use one Temporal mechanism
- rescheduling maps to Temporal Schedule update
- cancellation maps to Temporal Schedule delete or pause plus product state update
- the system avoids long-sleeping Workflows for future work

### 3.3 Recurring Work

Recurring tasks should use Temporal Schedules.

Model:

- Backend creates `Task`, `Schedule(recurring_rule)`, and a linked Temporal Schedule.
- Each Temporal Schedule action starts one `TaskRunWorkflow`.
- Each started Workflow represents exactly one concrete run occurrence.
- Backend may pre-materialize a `Run`, but the default recurring path may materialize the `Run` as the first idempotent Activity in `TaskRunWorkflow`.

Rules:

- Pause and resume use Temporal Schedule pause and unpause operations.
- Updating the recurrence updates both PostgreSQL schedule truth and the linked Temporal Schedule.
- Canceling the recurring series cancels future Temporal Schedule actions without deleting historical runs.
- `Skip This Occurrence` is represented by `OccurrenceOverride`; it must prevent or no-op the corresponding run without redefining the whole recurring Temporal Schedule.

## 4. Temporal Identity

Temporal identifiers must be derived from product identifiers and remain stable across process restarts.

### 4.1 Schedule IDs

Use:

```text
vesperaflow.schedule.{schedule_id}
```

For one-time schedules and recurring schedules, `schedule_id` is the PostgreSQL product schedule id.

### 4.2 Workflow IDs

Use this pattern when a product `Run` already exists before Workflow start:

```text
vesperaflow.run.{run_id}
```

`run_id` is the PostgreSQL product run id.

Use this pattern when a recurring Temporal Schedule starts a Workflow before the product `Run` exists:

```text
vesperaflow.occurrence.{schedule_id}.{occurrence_key}
```

`occurrence_key` is a stable key for the scheduled occurrence, such as the planned fire time normalized to UTC.

Rules:

- Retrying or rescheduling a failed one-time task creates a new `Run` and therefore a new Workflow ID.
- Reusing a Workflow ID for a different run is forbidden.
- Duplicate start attempts for the same `run_id` or occurrence key must collapse to, or conflict with, the existing Workflow execution instead of creating duplicate provider calls.
- The first persistence Activity in a schedule-fired recurring Workflow must create or load exactly one `Run` for the `(schedule_id, occurrence_key)` pair.
- If the selected Temporal Schedule implementation cannot provide unique Workflow IDs per occurrence, the system must pre-materialize occurrence Runs and start Workflows by `run_id` instead.

### 4.3 External References

Store Temporal references in product records:

- `Schedule.external_schedule_ref`
- `Run.external_execution_ref`

These references are for tracing and reconciliation, not user-facing identity.

## 5. Activity Groups

### 5.1 Persistence Activities

Persistence Activities write product-visible state to PostgreSQL.

Candidate Activities:

- `materialize_run`
- `mark_run_running`
- `mark_run_completed`
- `mark_run_failed`
- `mark_run_canceled`
- `complete_single_run_schedule`

Rules:

- Every persistence Activity must be idempotent by `run_id` plus target state or by `(schedule_id, occurrence_key)` before a recurring `Run` exists.
- Terminal state writes must be safe to retry.
- State transitions must enforce the domain model state machine.
- Activity results should return the persisted state needed by the Workflow; the Workflow should not inspect the database directly.

### 5.2 Provider Activities

Provider Activities call LLM or agent providers.

Candidate Activities:

- `execute_provider_run`
- `cancel_provider_run` if the provider supports external cancellation

Rules:

- Provider Activities must use an idempotency key when the provider supports one.
- The default provider idempotency key is `run_id`.
- Blocking provider clients should be implemented as synchronous Activities executed by a Worker with a `ThreadPoolExecutor`.
- Async Activities are acceptable only when the provider client is fully non-blocking.

### 5.3 Schedule Reconciliation Activities

Reconciliation Activities inspect and repair divergence between PostgreSQL and Temporal.

Candidate Activities:

- `sync_schedule_reference`
- `reconcile_due_run`
- `reconcile_temporal_schedule_state`

These are not required for the first thin implementation, but the architecture should preserve a place for them.

## 6. Task Queues And Workers

### 6.1 MVP Task Queues

Use one task queue for the first implementation:

```text
vesperaflow-default
```

This queue may run:

- `TaskRunWorkflow`
- persistence Activities
- provider Activities

### 6.2 Split Queue Path

If provider calls become blocking, slow, or resource-heavy, split into:

```text
vesperaflow-workflows
vesperaflow-activities
```

Rules after splitting:

- Workflow Workers register Workflow types only.
- Activity Workers register persistence and provider Activities.
- Provider Activity concurrency is tuned independently from Workflow task execution.

### 6.3 Worker Processes

FastAPI must not host the main Worker runtime.

MVP service processes:

- `web-ui`
- `api`
- `postgres`
- `temporal`
- `worker`

Worker configuration must be explicit:

- task queue name
- registered Workflows
- registered Activities
- Activity executor strategy
- graceful shutdown timeout
- concurrency limits once workload behavior is known

## 7. Retry, Timeout, And Heartbeat Policy

Every Activity execution must define at least one timeout.

### 7.1 Persistence Activity Policy

Recommended defaults:

- `start_to_close_timeout`: short bounded timeout, such as 10 to 30 seconds
- retry: enabled for transient database failures
- non-retryable: validation errors, invalid state transitions, malformed payloads

### 7.2 Provider Activity Policy

Recommended defaults:

- `schedule_to_close_timeout`: end-to-end cap for provider execution
- `start_to_close_timeout`: provider-specific bounded attempt duration
- retry: enabled only when duplicate execution is safe or provider idempotency is available
- non-retryable: user input validation errors, unsupported provider request, provider authentication/configuration errors

Long-running provider Activities should use heartbeat timeout and call `activity.heartbeat()` when progress or cancellation responsiveness matters.

### 7.3 Workflow Failure Policy

Expected business failures should become explicit failed run outcomes through persistence Activities.

Unexpected Workflow bugs should fail the Workflow task where possible so fixed Worker code can recover existing executions through replay.

## 8. Runtime Messaging

Backend HTTP APIs remain the public command surface.

MVP does not require user-facing Workflow Queries because user reads come from PostgreSQL read models.

Signals or Updates may be introduced only when a running Workflow needs live control:

- use Signals for asynchronous commands that do not need an immediate computed result
- use Updates for validated commands that need acceptance and optional completion semantics
- use Queries only for read-only diagnostics, not product-facing normal reads

If handlers are added later, Workflow completion must wait for in-flight handlers when they may mutate Workflow state.

## 9. PostgreSQL Synchronization

### 9.1 Source Of Truth

PostgreSQL is authoritative for:

- task definition
- schedule definition
- run status and history
- occurrence overrides
- read model projections

Temporal is authoritative for:

- whether a Workflow has executed a given history
- whether a Temporal Schedule exists and is paused or active at the engine level
- Activity retry history

### 9.2 Write Direction

The preferred MVP write path is:

```text
FastAPI command
  -> PostgreSQL product write
  -> Temporal Schedule or Workflow command
  -> PostgreSQL external reference update
```

Execution progress write path:

```text
TaskRunWorkflow
  -> persistence Activity
  -> PostgreSQL run/schedule state update
```

Rules:

- The Workflow does not write PostgreSQL directly.
- The Workflow calls persistence Activities for state changes.
- Persistence Activities are the only Temporal-side code that mutates product tables.
- Backend read endpoints read PostgreSQL, not Temporal Workflow state.

### 9.3 Divergence Handling

The architecture must tolerate partial failure between PostgreSQL and Temporal.

Required reconciliation cases:

- PostgreSQL schedule exists but Temporal Schedule creation failed
- Temporal Schedule exists but PostgreSQL external reference was not written
- Workflow started but run state remains `queued`
- run terminal Activity succeeded but the API or UI missed the update

Initial MVP may handle reconciliation manually or through admin/dev tooling, but the state model must not make reconciliation impossible.

## 10. Payloads And Determinism

Workflow input payloads should be stable versioned data models.

Rules:

- Avoid passing large provider outputs through Workflow history.
- Store large results in PostgreSQL or provider-specific storage and keep summaries or references in Workflow payloads.
- Use the same data converter for every Temporal client and Worker that touches VesperaFlow payloads.
- If Pydantic v2 models are used for payloads, prefer the Temporal Pydantic data converter consistently.
- Workflow modules must avoid top-level side effects, network calls, disk I/O, randomness, threads, subprocesses, and mutable global state changes.

## 11. Versioning And Deployment

Workflow code changes require Temporal-safe rollout.

Rules:

- Prefer Worker Versioning for Workflow code evolution.
- Use patch markers only for narrow compatibility changes where Worker Versioning is not the chosen mechanism.
- Preserve replay compatibility for existing Workflow histories.
- Keep Workflow, Activity, task queue, Schedule ID, Workflow ID, and payload model names stable unless intentionally versioned.

API-only and Activity-only changes are lower risk, but provider Activity changes must still preserve idempotency and retry semantics.

## 12. Testing And Verification

Temporal implementation work is not complete without Temporal-specific tests.

Required verification once code exists:

- Workflow integration tests using `WorkflowEnvironment.start_time_skipping()` for schedule/timer-heavy behavior where supported
- Activity tests using `ActivityEnvironment` for Activity context, heartbeat, cancellation, and idempotency behavior
- replay tests using `temporalio.worker.Replayer` for representative histories after Workflow control-flow changes
- tests for duplicate Workflow start behavior using stable `run_id`
- tests for pause, resume, reschedule, cancel, and retry command paths

Operational verification:

- a separate Worker entry point can start without FastAPI
- Worker shutdown is graceful
- local `docker compose` can run API, PostgreSQL, Temporal, and Worker together
- developer logs can trace from `task_id` to `schedule_id` to `run_id` to Temporal reference

## 13. Open Questions

- Should one-time tasks continue using Temporal Schedules after MVP, or move to a different delayed-start pattern if operational overhead is too high?
- Should recurring `Skip This Occurrence` prevent the Workflow start, or allow a started Workflow to no-op after checking an occurrence override?
- How much provider result detail should be stored in PostgreSQL versus provider-specific artifact storage?
- When should reconciliation become an automatic background process rather than developer/admin tooling?
