---
title: "VesperaFlow Glossary"
status: draft
version: "1.0"
aligned_requirements: "docs/requirements.md"
aligned_architecture: "docs/architecture.md"
aligned_domain_model: "docs/domain-model.md"
aligned_temporal_architecture: "docs/temporal-architecture.md"
aligned_functional_spec: "docs/functional-spec.md"
aligned_api_spec: "docs/api-spec.md"
aligned_ux_spec: "docs/ux-spec.md"
---

# VesperaFlow Glossary

This glossary defines the vocabulary used across VesperaFlow documentation. Where the same concept has both a user-facing label and a technical identifier, both are recorded so the mapping is unambiguous.

## Core Domain Terms

### Task

A user-owned unit of planned AI work. The primary object the user creates, edits, reviews, and inspects. A task has an `execution_mode` of `one_time` or `recurring`. See `docs/domain-model.md` §3.2.

### Template

A reusable task blueprint. Templates are not executed directly; they are instantiated into new tasks that become independently editable. See `docs/domain-model.md` §3.1.

### Schedule

The timing contract attached to a task. A `Schedule` has a `schedule_type` of `single_run` (for one-time tasks) or `recurring_rule` (for recurring tasks). See `docs/domain-model.md` §3.3.

### Run

One concrete execution attempt generated from a task and schedule. Runs are append-oriented and preserve history even when the parent task or schedule changes. See `docs/domain-model.md` §3.4.

### Occurrence

A single scheduled firing of a recurring `Schedule`. An occurrence may resolve to a `Run` when it fires, or to an `OccurrenceOverride` if the user edited that specific instance.

### Occurrence Override

A single-instance exception to a recurring `Schedule`. Overrides can reschedule or cancel a specific occurrence without changing the parent rule. See `docs/domain-model.md` §3.5.

### Read Model

A projection built from domain entities for a specific view. Calendar items, kanban cards, recurring todo items, task details, and history items are all read models. Read models are derived, not authoritative. See `docs/architecture.md` §11 and `docs/adr/005-derived-view-states.md`.

## Execution and Scheduling Terms

### Durable Execution

An execution model that survives process restarts and infrastructure failures by persisting the progression of a workflow. Provided in VesperaFlow by Temporal.

### Workflow

A Temporal concept for a durable program that coordinates Activities. VesperaFlow uses one primary short-lived Workflow type, `TaskRunWorkflow`. See `docs/temporal-architecture.md` §3.1.

### Activity

A Temporal concept for a unit of work with side effects. VesperaFlow organizes Activities into persistence Activities, executor Activities, and schedule reconciliation Activities. See `docs/temporal-architecture.md` §5.

### Executor

An external coding-agent runtime that performs the AI work for a task. VesperaFlow invokes the executor inside a run-scoped working directory and does not implement any agent runtime itself. MVP supports SDK-based and CLI-based invocation depending on the executor. See `docs/adr/002-execution-engine-choice.md` and `docs/architecture.md` §6.4.

Supported executor for MVP:

- `claude_code` — Anthropic's Claude Code, via the Claude Agent SDK
- `kimi_code` — Moonshot AI's Kimi Code, via the `kimi` CLI text transport
- `debug_printer` — local runtime simulator for end-to-end workflow testing

`codex`, `opencode`, and additional executor integrations are post-MVP candidates.

### Executor Adapter

The thin VesperaFlow component that invokes an `Executor` by calling into its SDK in-process or spawning its CLI transport, observes progress, captures the terminal outcome, and normalizes it into backend-owned run states. The adapter isolates executor-specific APIs, process handling, and event formats from the rest of the system. Defined in `docs/architecture.md` §6.4 and driven by `execute_agent_run` in `docs/temporal-architecture.md` §5.2.

### Provider (upstream)

The LLM service that an `Executor` talks to when it runs, such as Anthropic for Claude Code or Moonshot AI for Kimi Code. VesperaFlow itself never calls an LLM provider API and never handles provider credentials; those concerns belong entirely to the executor runtime and the user who installed it.

### Temporal Schedule

A Temporal primitive for time-based Workflow triggering. VesperaFlow uses Temporal Schedules for all scheduled work — recurring and one-time deferred alike. Temporal is the sole scheduling system; see `docs/architecture.md` §3.6 and `docs/adr/002-execution-engine-choice.md`.

### Occurrence Key

The canonical form of a scheduled occurrence's planned fire time, used inside a Workflow ID when the Workflow is started by a Temporal Schedule before a product `Run` exists. Format: UTC ISO 8601 basic notation with second precision and a trailing `Z` (for example `20260429T010000Z`). See `docs/temporal-architecture.md` §4.2.

### Idempotency Key

A stable key used to make retried work converge on a single effect. VesperaFlow uses `run_id` as the default idempotency key for an executor invocation; a retry of `execute_agent_run` reuses the same `run_id`-scoped working directory so the executor operates against the same on-disk state.

### Materialize (a Run)

To create a `Run` record in PostgreSQL. A recurring occurrence can be materialized eagerly (backend creates the `Run` before the Workflow starts) or lazily (first persistence Activity inside the Workflow creates the `Run`). See `docs/temporal-architecture.md` §5.1.

## Status Vocabulary

### Execution Mode

The task-level decision of whether the task runs once or repeatedly. Values: `one_time`, `recurring`.

### Task Status

A derived projection of the task's current lifecycle state. Values: `scheduled`, `paused`, `running`, `completed`, `failed`, `canceled`, `archived`. Derivation rules are in `docs/domain-model.md` §4.4.

### Schedule Status

The lifecycle of a `Schedule`. Values: `pending`, `active`, `paused`, `completed`, `canceled`.

### Run Status

The lifecycle of a single execution attempt. Values: `planned`, `queued`, `running`, `completed`, `failed`, `canceled`. Authoritative definition in `docs/domain-model.md` §4.3.

### Kanban Column

A visual grouping on the one-time kanban board. Columns are derived from task and run status. Values: `Upcoming`, `Running`, `Completed`, `Failed`. `Canceled` is available as a filter but not a default column. See `docs/ux-spec.md` §8.

## Integrity and Synchronization Terms

### Optimistic Concurrency

A write strategy where each client echoes the observed `version` of a resource; the server rejects writes whose version does not match current state. Used by all mutating endpoints. See `docs/api-spec.md` §4.6.

### Divergence

A state where PostgreSQL and Temporal disagree (for example a PostgreSQL schedule row exists but the matching Temporal Schedule was never created). Divergence is handled by explicit reconciliation rather than silent resynchronization. See `docs/temporal-architecture.md` §9.3.

### Reconciliation

The process of restoring consistency between PostgreSQL and Temporal after a divergence. In MVP this is a manual or admin-tooling operation; automatic reconciliation is a post-MVP consideration.

### Execution Unavailable

An API error code (`execution_unavailable`) returned when a mutating command could not be mirrored from PostgreSQL to Temporal and was rolled back. The client should retry. See `docs/api-spec.md` §4.3.

## User Interface Terms

### Composer

The task creation surface. Lets the user describe AI work, choose one-time or recurring mode, and set a schedule. See `docs/ux-spec.md` §5.

### Calendar

The time-oriented read model and UI that shows future planned work on dates and times. See `docs/ux-spec.md` §7.

### One-Time Kanban Board

The state-oriented read model and UI for one-time tasks, grouped by derived execution state. Recurring tasks are excluded from this surface. See `docs/ux-spec.md` §8.

### Recurring Todo View

The stable management list for recurring tasks, treated as ongoing commitments rather than transient board cards. See `docs/ux-spec.md` §9.

### History

The review surface for completed and failed runs across all tasks, presented in reverse chronological order. See `docs/ux-spec.md` §11.

### Task Detail

The single inspection surface reachable from calendar, kanban, recurring todo, or task list. Shows task definition, schedule, recent runs, and state-dependent actions. See `docs/ux-spec.md` §10.

## Deferred and Out-of-Scope Concepts

### Dashboard

An aggregate overview surface. Deferred from MVP-primary navigation; see `docs/architecture.md` §2.3.

### Agents (UI surface)

A hypothetical surface for composing or configuring multi-agent behavior inside VesperaFlow. Deferred from MVP. This is distinct from the coding-agent runtime VesperaFlow delegates to as an `Executor`; it is not modeled or composed by VesperaFlow, only invoked through the SDK adapter.

### Skills

A surface for managing reusable AI capabilities. Deferred from MVP.
