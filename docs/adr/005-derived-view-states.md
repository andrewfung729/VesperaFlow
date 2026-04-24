---
title: "ADR 005: Kanban and Read-Model States Are Derived, Not UI-Owned"
status: accepted
date: "2026-04-24"
aligned_architecture: "docs/architecture.md"
aligned_domain_model: "docs/domain-model.md"
aligned_ux_spec: "docs/ux-spec.md"
---

# ADR 005: Kanban and Read-Model States Are Derived, Not UI-Owned

## Status

Accepted.

## Context

Operational boards like kanban are tempting to model as first-class UI state: a column label becomes a field on the card, and moving a card changes the label. This works for ticket trackers where humans drive all transitions but breaks in VesperaFlow because:

- most transitions are driven by the scheduler or the provider, not the user
- a single task can appear on calendar, kanban, recurring todo, and history simultaneously
- run outcomes must be preserved in history even when the user hides the card
- recurring tasks represent ongoing commitments and do not map naturally to transient columns

If column labels were authoritative, reconciling scheduler updates with user drag actions would require extra conflict resolution, and the same task in two different views could disagree with itself.

## Decision

All operational view states (kanban columns, recurring-todo groupings, calendar occurrence states, history filters) are **derived read models** computed from backend-owned domain state. They are never the source of truth.

Concrete rules:

- kanban columns are derived from `task_status` and latest `run_status`
- recurring todo state is derived from `schedule_status`
- calendar occurrences are derived from `Schedule` plus `OccurrenceOverride`
- history items are derived from `Run` records joined with task metadata
- drag-and-drop between kanban columns is not supported in MVP because it would imply UI-owned state

## Consequences

Positive:

- views stay consistent without cross-view synchronization logic
- scheduler-driven transitions and user-driven transitions use the same write paths
- historical and operational views cannot diverge because they read the same underlying truth

Negative:

- the UI cannot express "move this card" as a first-class action; it must route through an explicit domain command (for example reschedule or cancel)
- every new view requires a read-model contract rather than just a UI store change
- drag-and-drop UX, if desired later, must be wired through domain commands rather than pure UI state
- calendar drag-to-reschedule and kanban drag are not part of MVP; if either is added later, it must call the same domain command endpoints as explicit edit actions rather than creating UI-owned state
