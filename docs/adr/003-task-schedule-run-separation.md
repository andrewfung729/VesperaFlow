---
title: "ADR 003: Separate Task, Schedule, and Run as Distinct Domain Objects"
status: accepted
date: "2026-04-24"
aligned_domain_model: "docs/domain-model.md"
aligned_architecture: "docs/architecture.md"
---

# ADR 003: Separate Task, Schedule, and Run as Distinct Domain Objects

## Status

Accepted.

## Context

Early product discussions conflated the user's planned work with the schedule it runs on and the execution attempts it produces. Modeling all three as a single record is simpler initially but breaks down when:

- a one-time task is canceled after its schedule is set but before it executes
- a recurring task generates many runs and the user expects historical visibility independent of the current recurrence rule
- a single recurring occurrence is edited or skipped without affecting the parent series
- execution state transitions asynchronously from user edits

## Decision

Model three distinct aggregates:

- `Task` \u2014 user-owned unit of planned AI work, with an execution mode (`one_time` or `recurring`)
- `Schedule` \u2014 when the task runs; `single_run` or `recurring_rule`
- `Run` \u2014 a concrete execution attempt, append-oriented

Introduce `OccurrenceOverride` as a first-class exception to a recurring `Schedule`, rather than mutating the parent rule or creating a new task.

`task_status` is a derived projection over the `Schedule` status and the latest `Run` status, not an independently writable column.

One-time deferred tasks use one dedicated Temporal Schedule per product `Schedule`. Recurring occurrences are not eagerly materialized into future `Run` records; they are projected for calendar windows and materialized when execution actually starts. `OccurrenceOverride` supports both time and instruction edits in MVP.

## Consequences

Positive:

- each lifecycle (planning, timing, execution) evolves independently without cross-pollution
- recurring tasks can keep their history even when the rule changes
- single-occurrence edits do not require cloning the whole series
- state machines stay tractable because each entity has a narrow responsibility

Negative:

- more tables and more relationships than a single-record design
- derived task status requires a recompute path after every persistence Activity
- API clients must reason about three linked objects instead of one
