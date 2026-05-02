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
- call executor and persistence Activities

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
3. execute the agent through an executor Activity using the configured executor SDK
4. persist successful result summary through a persistence Activity
5. persist failed or canceled outcome through a persistence Activity

Rules:

- The Workflow must be short-lived and scoped to one run.
- The Workflow must not read PostgreSQL directly.
- The Workflow must not invoke the executor directly by importing an SDK; all executor invocation runs inside an Executor Activity.
- The Workflow must receive the execution snapshot it needs at start time or through deterministic Activity results.

### 3.2 Deferred One-Time Work

One-time tasks use Temporal Schedule. Temporal is the sole scheduling system in VesperaFlow (see `docs/architecture.md` §3.6); no alternative delayed-start mechanism is used, either outside Temporal or elsewhere inside Temporal such as long-sleep Workflows acting as ad-hoc schedulers.

Model:

- Backend creates `Task`, `Schedule(single_run)`, and a planned `Run`.
- Backend creates one dedicated Temporal Schedule per one-time task that starts `TaskRunWorkflow` at `planned_at`.
- After the run starts, the product schedule transitions toward `completed` or terminal state according to domain rules.

Rationale:

- one-time and recurring time triggers use one Temporal mechanism
- rescheduling maps to Temporal Schedule update
- cancellation maps to Temporal Schedule delete or pause plus product state update
- the system avoids long-sleeping Workflows for future work
- a dedicated Schedule per one-time task keeps reconciliation direct because each product `Schedule` maps to one Temporal Schedule reference

### 3.3 Recurring Work

Recurring tasks use Temporal Schedules. As with deferred one-time work, Temporal is the sole scheduling system; long-sleeping Workflows must not be used as ad-hoc recurring schedulers.

Model:

- Backend creates `Task`, `Schedule(recurring_rule)`, and a linked Temporal Schedule.
- Each Temporal Schedule action starts one `TaskRunWorkflow`.
- Each started Workflow represents exactly one concrete run occurrence.
- Backend may pre-materialize a `Run`, but the default recurring path may materialize the `Run` as the first idempotent Activity in `TaskRunWorkflow`.

Rules:

- Pause and resume use Temporal Schedule pause and unpause operations.
- Updating the recurrence or recurring task run parameters updates both
  PostgreSQL truth and the linked Temporal Schedule action.
- Canceling the recurring series cancels future Temporal Schedule actions without deleting historical runs.
- `Skip This Occurrence` is represented by `OccurrenceOverride`; the corresponding Workflow may still start, but its first persistence Activity must detect the override and complete as a no-op without invoking the executor.

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

`occurrence_key` is the canonical form of the scheduled occurrence's planned fire time. It is defined as:

- the planned fire instant in UTC
- formatted as ISO 8601 basic notation with second precision and a trailing `Z`, using only digits and the characters `T` and `Z` (for example `20260429T010000Z`)
- no colons, no dashes, no fractional seconds, no timezone offsets other than `Z`

This format is frozen for the lifetime of a Temporal Schedule. Changing the format after any Workflow has started would produce conflicting Workflow IDs for the same occurrence and is forbidden without a migration plan.

Rules:

- Retrying or rescheduling a failed one-time task creates a new `Run` and therefore a new Workflow ID.
- Reusing a Workflow ID for a different run is forbidden.
- Duplicate start attempts for the same `run_id` or occurrence key must collapse to, or conflict with, the existing Workflow execution instead of creating duplicate executor invocations.
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

### 5.2 Executor Activities

Executor Activities delegate AI execution to an external coding-agent runtime invoked from a Temporal Activity through its official SDK or CLI transport. SDK dependencies and CLI process management live in Worker startup or Activity-only modules. They must not be reachable through package root, Workflow modules, or any Workflow-reachable facade. VesperaFlow does not call LLM APIs from Workflow or Activity code. See `docs/adr/002-execution-engine-choice.md` and `docs/architecture.md` §6.4.

Supported executor:

- `claude_code` via the Claude Agent SDK
- `codex` via Codex CLI `codex exec --json`
- `kimi_code` via the `kimi` CLI text transport
- `debug_printer` as a local runtime simulator that logs the execution snapshot and returns a completed outcome

`opencode` and additional executor integrations are post-MVP candidates.

Candidate Activities:

- `execute_agent_run` — invoke the executor, wait for terminal outcome, return normalized result
- `cancel_agent_run` — cancel the in-flight executor and wait for it to settle

General rules:

- The default idempotency key for an executor invocation is `run_id`; it is used to name the run's working directory and any on-disk artifacts, so a retried Activity attempt resumes or overwrites the same working directory deterministically.
- Each attempt of `execute_agent_run` must reuse or recreate the same `run_id`-scoped working directory; attempts must not be directed to ephemeral temp paths that disappear between retries.
- Activity timeouts must be large enough to accommodate long-running coding-agent sessions; use `heartbeat_timeout` with regular heartbeats while the executor is active.
- After Activity cancellation propagates to the executor, the Activity must not retry.
- Terminal outcomes are normalized: successful executor completion maps to `completed`; SDK exceptions or non-zero CLI exits map to `failed` with a `failure_reason` category derived from the SDK error type or CLI diagnostics; cancellations map to `canceled`.

Executor integration rules:

- SDK-based Executor Activities are async Activities that `await` the SDK's entrypoint; they run on the Worker's async event loop.
- CLI-based Executor Activities spawn the official CLI binary in a run-scoped working directory and capture stdout/stderr into artifacts.
- Activity cancellation is propagated into the executor through the SDK's native cancellation token, context cancellation, `asyncio.CancelledError`, or process signal handling as the executor documents.
- Concrete executor modules may import their SDK dependencies at module top level, but only if those modules are unreachable from Workflow imports.
- Executor profile resolution happens in `execute_agent_run`, not in Workflow code. Workflow payloads carry only the profile id; Activity code loads profile model/env values from PostgreSQL immediately before invoking the adapter.
- The SDK client instance or CLI subprocess is constructed inside the Activity execution path, not at module import time; Activity retries must not reuse stale runtime state across attempts.
- The adapter must not rely on SDK or CLI internals beyond the stable documented API; coupling to internal types is forbidden.

Secrets handling rules for Executor Activities:

- VesperaFlow stores executor profile secret env values in PostgreSQL for the local-first v1, but API/UI responses expose only secret keys. Secret values must not be written to structured logs, run events, or Temporal Workflow history.
- the Worker may pass explicit executor profile environment settings, such as Claude SDK env values, into the executor process environment; it must not pass the full Worker environment
- the Worker may also pass non-secret Claude Code runtime flags for disabling telemetry, error reporting, feedback prompts, autoupdates, nonessential traffic, and flicker, and for enabling local executor capabilities such as the LSP tool
- Codex authentication and provider configuration are handled by the `codex` CLI itself, such as through ChatGPT login, API-key setup, or CLI-supported configuration; the Worker may pass the executor profile `default_model` as the `codex exec --model` value, and the API preflight checks binary and workspace availability but does not perform live auth checks
- Kimi Code authentication is handled by the `kimi` CLI itself, such as through its OAuth token cache, API key environment, or CLI-supported configuration; the API preflight checks binary and workspace availability but does not perform live auth checks
- Workflow inputs, Activity inputs, and Activity return values must not contain credential material
- structured logs emitted by Executor Activities must not include full instruction bodies or full executor output at default log levels; short summaries and terminal outcome codes are sufficient for product-level observability
- rotating an executor's provider credential is a user-side operation that does not require rewriting any existing Workflow history

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
- executor Activities

### 6.2 Split Queue Path

If executor invocations become blocking, slow, or resource-heavy, split into:

```text
vesperaflow-workflows
vesperaflow-activities
```

Rules after splitting:

- Workflow Workers register Workflow types only.
- Activity Workers register persistence and executor Activities.
- Executor Activity concurrency is tuned independently from Workflow task execution.

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

### 7.2 Executor Activity Policy

Recommended defaults:

- `schedule_to_close_timeout`: end-to-end cap for a single executor invocation
- `start_to_close_timeout`: executor-specific bounded attempt duration
- retry: enabled only when duplicate execution is safe; default executor idempotency is keyed by `run_id` and the run's working directory
- non-retryable: user input validation errors, unknown executor, missing or unauthenticated executor SDK, unsupported executor version, inaccessible run working directory

Long-running Executor Activities should use heartbeat timeout and call `activity.heartbeat()` while the executor is active to keep cancellation responsive.

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

MVP reconciliation is manual or admin/dev-tooling driven. Automatic background reconciliation is post-MVP because command-path rollback and explicit divergence records are sufficient for a single-user local release.

Command-path failure rules:

- if a mutating API command cannot mirror its PostgreSQL write to the corresponding Temporal Schedule or Workflow command, the API must roll the PostgreSQL write back and return `execution_unavailable`
- if rollback itself fails, the backend must persist a reconciliation record marking the PostgreSQL row as `divergent` and surface the divergence in admin tooling; the user-facing API still returns `execution_unavailable`
- read endpoints must remain available during divergence; they return the last authoritative PostgreSQL state

## 10. Payloads And Determinism

Workflow input payloads should be stable versioned data models.

Rules:

- Avoid passing large executor outputs through Workflow history.
- Store large results in PostgreSQL, or in the run's on-disk working directory referenced by `result_artifact_ref`, and keep short summaries in Workflow payloads.
- Workflow inputs and outputs must not carry executor credentials, since VesperaFlow does not handle them in the first place.
- Use the same data converter for every Temporal client and Worker that touches VesperaFlow payloads.
- If Pydantic v2 models are used for payloads, prefer the Temporal Pydantic data converter consistently.
- Workflow modules must avoid top-level side effects, network calls, disk I/O, randomness, threads, and mutable global state changes.

## 11. Versioning And Deployment

Workflow code changes require Temporal-safe rollout.

Rules:

- Prefer Worker Versioning for Workflow code evolution.
- Use patch markers only for narrow compatibility changes where Worker Versioning is not the chosen mechanism.
- Preserve replay compatibility for existing Workflow histories.
- Keep Workflow, Activity, task queue, Schedule ID, Workflow ID, and payload model names stable unless intentionally versioned.

API-only and Activity-only changes are lower risk, but Executor Activity changes must still preserve idempotency and retry semantics.

Claude Agent SDK compatibility policy:

- The Worker dependency pin and lockfile are the source of truth for the validated SDK version.
- API preflight verifies workspace access; live SDK behavior is verified through the normal task execution path.
- SDK upgrades should update the dependency pin, lockfile, adapter tests, and live smoke record together.

CLI executor compatibility policy:

- Codex uses `codex exec --json --output-last-message --skip-git-repo-check -C <target> [--model <executor_profile.default_model>] --dangerously-bypass-approvals-and-sandbox -` from a Worker Activity.
- CLI adapters capture stdout/stderr and executor-owned summary artifacts under the run artifact directory instead of passing bulky streams through Workflow history.
- CLI version or transport changes should update adapter tests, docs, and any local live smoke record together.

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
