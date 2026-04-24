---
title: "VesperaFlow Functional Specification"
status: draft
version: "1.0"
aligned_requirements: "docs/requirements.md"
aligned_architecture: "docs/architecture.md"
aligned_domain_model: "docs/domain-model.md"
---

# VesperaFlow Functional Specification

## 1. Purpose

This document specifies the functional behavior of VesperaFlow for the current MVP.

It defines:

- actors
- preconditions
- main flows
- alternate flows
- business rules
- edge cases

It covers the MVP features that matter most to product behavior:

- one-time deferred tasks
- recurring tasks
- task templates
- calendar view
- one-time kanban view
- recurring todo view
- history view

## 2. Actors

### 2.1 Primary Actor

`User`

An individual planning and reviewing AI work for their own use.

### 2.2 Supporting Actors

`System`

The VesperaFlow application, including backend, schedule orchestration, and execution coordination.

`Executor`

The downstream AI execution provider or adapter used by the system to perform planned work.

## 3. Global Functional Rules

- The user must be able to create work without executing it immediately
- Every saved task must have a visible execution mode: `one-time` or `recurring`
- Template reuse must never overwrite already-created tasks
- Calendar is the time-oriented view of future work
- Kanban is the state-oriented view for one-time tasks
- Recurring tasks are managed through a todo-style list rather than kanban columns
- Historical execution outcomes must remain inspectable after future schedules change
- Recurring task lifecycle remains anchored to schedule state; individual run failures are shown as execution context rather than converting the parent recurring task into a failed task

## 4. Feature: One-Time Deferred Task

### 4.1 Goal

Allow the user to define work now and have it run once at a chosen future time.

### 4.2 Preconditions

- The user is able to access task creation
- The user provides task instructions
- The user selects `one-time` mode
- The user provides a valid future execution time

### 4.3 Main Flow

1. User starts task creation
2. User enters task title or instruction text
3. User selects `one-time` execution mode
4. User chooses a future date and time
5. User saves the task
6. System validates the schedule
7. System creates a task and a single-run schedule
8. System shows the task in upcoming planned work
9. At the scheduled time, system creates or activates the run
10. Executor processes the run
11. System stores the final run outcome
12. User can inspect the outcome later

### 4.4 Alternate Flows

#### A. User edits before execution

1. User opens the scheduled task before the run starts
2. User edits instructions or planned time
3. System validates the changes
4. System updates task and schedule while preserving task identity

#### B. User cancels before execution

1. User opens the scheduled task
2. User cancels future execution
3. System marks the schedule as canceled
4. System removes the task from active upcoming work
5. Historical audit information remains available

#### C. User reschedules after failure

1. User opens a failed one-time task
2. User chooses to retry or reschedule
3. System creates a new future run plan from the existing task definition
4. Task returns to scheduled state

### 4.5 Business Rules

- One-time tasks must have exactly one planned future execution at save time
- One-time tasks may be edited before execution starts
- One-time tasks may be canceled before execution starts
- A completed one-time run must remain visible in history
- Rescheduling after completion or failure must be explicit user action

### 4.6 Edge Cases

- If the user selects a past time, the system must reject save and request a valid future time
- If execution cannot start at the planned time, the run must surface as delayed, queued, or failed rather than disappearing
- If the executor fails mid-run, the task must remain inspectable with a failed outcome

## 5. Feature: Recurring Task

### 5.1 Goal

Allow the user to define repeatable AI work that runs on a continuing cadence.

### 5.2 Preconditions

- The user is able to access task creation
- The user provides task instructions
- The user selects `recurring` mode
- The user provides a valid recurrence rule

### 5.3 Main Flow

1. User starts task creation
2. User enters task title or instruction text
3. User selects `recurring` execution mode
4. User chooses a recurrence pattern
5. User saves the task
6. System validates the recurrence rule
7. System creates a task and recurring schedule
8. System shows the task in planned future work
9. At each due time, system materializes a new run
10. Executor processes each run
11. System stores each run as historical output under the same task
12. User reviews recent and future activity from task detail, calendar, or recurring todo view

### 5.4 Alternate Flows

#### A. User pauses recurring execution

1. User opens the recurring task
2. User pauses the schedule
3. System marks the schedule as paused
4. No further future runs are created while paused

#### B. User resumes recurring execution

1. User opens a paused recurring task
2. User resumes the schedule
3. System reactivates future execution based on the active recurrence rule
4. Task returns to scheduled state

#### C. User updates recurrence

1. User opens the recurring task
2. User changes the recurrence rule
3. System validates the new rule
4. Future occurrences are regenerated or recalculated
5. Existing historical runs remain unchanged

#### D. User edits one recurring occurrence from calendar

1. User selects one recurring occurrence in calendar
2. User chooses to edit the occurrence
3. System prompts whether to apply the change to `only this occurrence` or `this and future`
4. If `only this occurrence` is selected, system creates or updates a single-occurrence override
5. If `this and future` is selected, system updates the parent recurring definition for future occurrences only
6. Past occurrences and finished runs remain unchanged

### 5.5 Business Rules

- Recurring tasks must have exactly one active recurrence definition in MVP
- Pausing a recurring task stops future execution but preserves the task and history
- Resuming a recurring task re-enables future execution without creating a new task
- Editing the recurrence affects future runs only
- Calendar edits for recurring tasks must offer scoped editing behavior similar to common recurring-calendar products
- Historical runs must remain attached to the same task even if recurrence changes

### 5.6 Edge Cases

- If a recurring run fails, that failure must be visible without deleting the recurring schedule
- If a recurrence rule becomes invalid after editing, the change must be rejected
- If multiple future occurrences exist in projection, they must still map back to one recurring task definition

## 6. Feature: Template Management

### 6.1 Goal

Allow the user to save reusable task patterns and instantiate future tasks from them without copying and pasting instructions manually.

### 6.2 Preconditions

- The user has permission to create or edit tasks
- The user has either an existing task or enough input to define a template directly

### 6.3 Main Flow

#### A. Create template directly

1. User opens template management
2. User chooses to create a new template
3. User provides a template name, instructions, and optional defaults
4. System stores the template

#### B. Save template from an existing task

1. User creates or opens a task
2. User chooses `Save as Template`
3. User provides a template name and optional defaults
4. System stores the template

#### C. Create a task from a template

1. User starts new task creation
2. User chooses an existing template
3. System pre-fills a new task from template data
4. User adjusts task-specific details if needed
5. User saves the new task
6. System creates a new independent task linked to the template origin

### 6.4 Alternate Flows

#### A. User edits a template

1. User opens template management
2. User edits template content
3. System saves the updated template
4. Future task creation uses the new template values
5. Existing tasks created from that template remain unchanged

#### B. User deletes or archives a template

1. User opens template management
2. User deletes or archives a template
3. System removes it from active template selection
4. Existing tasks retain their copied content and historical template linkage

### 6.5 Business Rules

- Templates do not execute directly
- A task created from a template becomes independent after creation
- Templates may be created directly without first creating a task
- Template edits apply only to future tasks
- Template deletion must not break historical task detail views

### 6.6 Edge Cases

- If a template's default time settings are no longer desired, the user must still be able to override them during task creation
- If a linked template is archived, tasks created from it must remain fully readable

## 7. Feature: Calendar View

### 7.1 Goal

Allow the user to inspect future AI work through a time-based planning surface.

### 7.2 Preconditions

- At least one one-time or recurring task exists, or the view is empty-state capable

### 7.3 Main Flow

1. User opens calendar view
2. System loads future scheduled work
3. System renders one-time tasks at their planned date and time
4. System renders recurring tasks as future occurrences or projected instances
5. User scans workload by date and time
6. User selects an item to inspect details
7. System opens task detail or a lightweight task preview

### 7.4 Alternate Flows

#### A. Empty state

1. User opens calendar with no planned work
2. System shows an empty state with a path to create a task

#### B. Edit from calendar

1. User selects a calendar item
2. User chooses to edit or reschedule
3. If the item belongs to a recurring task, system prompts whether the change applies to `only this occurrence` or `this and future`
4. System opens the relevant editing flow with the chosen scope

### 7.5 Business Rules

- Calendar shows planned future work, not only historical runs
- One-time tasks appear as single planned entries
- Recurring tasks appear based on future schedule projection
- Recurring task edits from calendar must support scoped changes for single occurrence versus future series
- Selecting a calendar item must resolve to a task-level object the user can inspect or modify

### 7.6 Edge Cases

- If multiple tasks overlap in time, the calendar must still expose each task distinctly
- If a recurring schedule is paused, future projected occurrences should not appear as active planned work
- If a one-time task is canceled, it should no longer appear in default upcoming calendar views

## 8. Feature: One-Time Kanban View

### 8.1 Goal

Allow the user to inspect one-time AI work by current execution state instead of time.

### 8.2 Preconditions

- At least one one-time task or run exists, or the view is empty-state capable

### 8.3 Main Flow

1. User opens kanban view
2. System loads one-time task and run summaries grouped by product-visible state
3. System renders cards in columns such as `Upcoming`, `Running`, `Completed`, and `Failed`
4. User scans the board for work needing attention
5. User opens a card
6. System shows task intent, timing, and latest outcome state

### 8.4 Alternate Flows

#### A. Empty state

1. User opens kanban with no tasks
2. System shows an empty state with a path to create planned work

#### B. Follow-up from failed work

1. User opens a failed card
2. User reviews the failed outcome
3. User chooses to edit, retry, or reschedule as supported by task type

### 8.5 Business Rules

- Kanban columns are derived from backend state and latest relevant execution context
- Only one-time tasks appear in kanban
- A task must appear in only one primary kanban grouping at a time
- The board should prioritize current operational understanding over full historical completeness
- Historical detail belongs in the task detail surface, not on the card face

### 8.6 Edge Cases

- A currently running task must not appear simultaneously in `Upcoming`
- A completed one-time task may appear in `Completed` until archived or filtered out

## 9. Feature: Recurring Todo View

### 9.1 Goal

Allow the user to inspect and manage recurring tasks as ongoing commitments rather than transient board cards.

### 9.2 Preconditions

- At least one recurring task exists, or the view is empty-state capable

### 9.3 Main Flow

1. User opens recurring todo view
2. System loads recurring task summaries
3. System renders each recurring task as a stable list item
4. User reviews recurrence pattern, next run, and current schedule state
5. User opens an item to inspect, edit, pause, or resume the recurring task

### 9.4 Alternate Flows

#### A. Empty state

1. User opens the recurring todo view with no recurring tasks
2. System shows an empty state with a path to create recurring work

#### B. Pause or resume from list

1. User selects a recurring item
2. User pauses or resumes the recurring schedule
3. System updates the schedule state
4. The same recurring item remains visible with updated status

### 9.5 Business Rules

- Only recurring tasks appear in recurring todo view
- Recurring items remain stable over time instead of moving across kanban columns
- Latest run outcome may be shown as context, but recurring work remains anchored to its schedule identity

### 9.6 Edge Cases

- A recurring task with a failed latest run remains in recurring todo view and surfaces the failure as context
- A paused recurring task remains visible and clearly marked as paused

## 10. Shared Detail and Inspection Flow

### 9.1 Goal

Allow the user to inspect any task from any surface and understand:

- what the task is supposed to do
- when it is or was scheduled
- what happened most recently
- what actions are currently available

### 9.2 Main Flow

1. User opens task detail from calendar, kanban, recurring todo view, or task list
2. System shows task definition
3. System shows execution mode
4. System shows current schedule state
5. System shows recent run history
6. System shows available actions based on state

### 9.3 Available Actions by State

- `scheduled`: edit, cancel, reschedule
- `paused`: resume, edit, cancel
- `running`: inspect only, with restricted edits
- `completed`: review, duplicate, reschedule explicitly
- `failed`: inspect, edit, retry, reschedule
- `canceled`: review, duplicate if needed, or archive

## 11. Feature: History View

### 11.1 Goal

Allow the user to review completed and failed runs across one-time and recurring work from one dedicated history surface.

### 11.2 Preconditions

- At least one historical run exists, or the view is empty-state capable

### 11.3 Main Flow

1. User opens history view
2. System loads historical run summaries across tasks
3. System renders runs in reverse chronological order
4. User filters by status, execution mode, or date range as needed
5. User opens a historical item
6. System links the user to related task detail with the selected run context

### 11.4 Alternate Flows

#### A. Empty state

1. User opens history with no completed or failed runs
2. System shows an empty state explaining that completed work will appear here

### 11.5 Business Rules

- History is a derived read model built from run records and task metadata
- Opening history must not mutate task or run state
- Historical runs remain visible even if the parent task or template is later archived

### 11.6 Edge Cases

- If a recurring task remains scheduled after a failed run, the failed run must still appear in history without removing the recurring task from recurring todo view
- If a one-time task is duplicated later, earlier runs must remain associated with the original task identity

## 12. View Consistency Rules

- A task saved successfully must appear consistently across task detail and any relevant calendar or kanban surfaces
- A recurring task saved successfully must appear consistently across task detail, calendar, and recurring todo view
- A completed or failed run saved successfully must appear consistently across task detail and history view
- Calendar and kanban must resolve to the same underlying task identity
- Calendar and recurring todo must resolve to the same underlying recurring task identity
- A schedule change must update all views that depend on timing
- A run status change must update all views that depend on execution state

## 13. Out of Scope for This Functional Spec

- suggested timing recommendations
- passive push notifications or overnight digests
- team approval workflows
- advanced multi-agent composition

## 14. Open Functional Questions

- Should calendar allow direct drag-rescheduling in MVP, or route rescheduling through detail/edit flow only?
- For `only this occurrence`, should MVP allow both time edits and instruction edits, or time edits only?
- Should recurring todo items be grouped by schedule state, due time, or left as a flat list in MVP?
