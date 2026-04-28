---
title: "VesperaFlow UX Specification"
status: draft
version: "1.0"
aligned_requirements: "docs/requirements.md"
aligned_architecture: "docs/architecture.md"
aligned_domain_model: "docs/domain-model.md"
aligned_functional_spec: "docs/functional-spec.md"
aligned_api_spec: "docs/api-spec.md"
---

# VesperaFlow UX Specification

## 1. Purpose

This document defines the user experience behavior for the current VesperaFlow MVP.

It focuses on:

- information architecture
- primary user flows
- screen responsibilities
- interaction rules
- empty, loading, and error states
- recurring edit behavior

It does not define:

- visual design system tokens
- implementation details
- backend data models

## 2. UX Principles

### 2.1 Plan First

The product should make it easy to decide work now and execute later. The UI should never force immediate execution as the default mental model.

### 2.2 One Screen, One Mental Model

Each primary view should answer one distinct question:

- `Composer`: what should AI do
- `Calendar`: when will it happen
- `Kanban`: what is happening with one-time work
- `Recurring Todo`: what repeating work is active

### 2.3 Stable Objects, Clear States

Users should always know whether they are looking at:

- a reusable template
- a task definition
- a scheduled occurrence
- a historical run

### 2.4 Scoped Edits Must Be Explicit

Recurring-task edits must clearly distinguish:

- editing one occurrence
- editing this and future occurrences

The UI must not hide this choice.

### 2.5 Low-Fragility Operations

Potentially destructive actions such as cancel, archive, or series-wide edit must require explicit confirmation.

## 3. Primary Navigation

### 3.1 Main Sidebar

MVP navigation:

- `Composer`
- `Calendar`
- `One-Time Board`
- `Recurring Todo`
- `Templates`
- `History`
- `Settings`

Deferred from MVP-primary navigation:

- `Dashboard`
- `Agents`
- `Skills`

### 3.2 Default Landing Behavior

Recommended default landing page:

- `Composer` for first-time or low-data usage
- `Calendar` for returning users with active schedules

If no tasks exist:

- default to `Composer`

## 4. Shared UX Objects

### 4.1 Task Card Summary

Used in:

- calendar detail preview
- one-time kanban cards
- recurring todo items

Minimum content:

- title
- execution mode
- next run time or latest run state
- one primary status label

### 4.2 Task Detail Panel

Can appear as:

- right-side drawer on desktop
- full-screen sheet on mobile

Must include:

- task title
- instruction text
- mode: `one-time` or `recurring`
- current schedule state
- next run or planned time
- recent runs
- allowed actions

### 4.3 Confirmation Modal

Used for:

- cancel one-time task
- cancel recurring schedule
- archive template
- series-wide recurring edit
- single-occurrence cancel

Must include:

- action summary
- object title
- consequence summary
- primary confirm
- secondary cancel

## 5. Composer

### 5.1 Goal

Allow the user to create a task quickly, choose whether it is one-time or recurring, and save it with minimal friction.

### 5.2 Layout

Primary regions:

- task title
- instruction editor
- mode selector
- schedule configuration
- optional template actions
- save actions

### 5.3 Creation Flow

1. User enters title and instructions
2. User chooses `One-Time` or `Recurring`
3. UI updates schedule controls based on mode
4. User chooses date/time or recurrence
5. User saves task
6. UI routes user to the most relevant follow-up state

Recommended follow-up routing:

- one-time task: open task detail or one-time board highlight
- recurring task: open task detail or recurring todo highlight

### 5.4 Mode Selector Rules

Display as segmented control or radio choice:

- `One-Time`
- `Recurring`

Rules:

- default selection may be empty until user chooses, or use `One-Time` if a default is needed
- changing mode after schedule input should warn before incompatible data is cleared

### 5.5 Schedule Inputs

#### One-Time Inputs

- date picker
- time picker
- timezone display

#### Recurring Inputs

- cadence preset or recurrence editor
- next run preview
- timezone display

### 5.6 Primary Actions

- `Save Task`
- `Save as Template`

Optional secondary:

- `Cancel`

### 5.7 Validation Behavior

- inline validation for missing title or instructions
- inline validation for invalid past time
- inline validation for invalid recurrence
- save button disabled only for clearly invalid states

## 6. Templates

### 6.1 Goal

Allow users to create, edit, archive, and reuse templates without copying and pasting task content.

### 6.2 Template List Screen

Must show:

- template name
- short description
- default mode
- updated time
- actions menu

Primary actions:

- `New Template`
- `Use Template`
- `Edit`
- `Archive`

### 6.3 Create Template Flow

1. User opens `Templates`
2. User clicks `New Template`
3. User fills in name, description, instructions, and optional defaults
4. User saves
5. Template appears in list

### 6.4 Save Task as Template Flow

1. User opens task detail or composer
2. User clicks `Save as Template`
3. Modal asks for template name and optional description
4. User confirms
5. Template is created

### 6.5 Use Template Flow

1. User starts new task creation
2. User chooses template
3. Composer pre-fills from template
4. User edits task-specific values
5. Saving creates a task, not a template mutation

### 6.6 Editing Rules

- editing a template never edits existing tasks
- archived templates are hidden from default selection lists
- archived templates remain viewable in history or filtered template list

## 7. Calendar

### 7.1 Goal

Provide a time-based planning surface for both one-time tasks and recurring occurrences.
The primary calendar surface supports day, week, and month views.

### 7.2 Calendar Content Rules

Display:

- future one-time scheduled tasks
- future recurring projected occurrences
- recurring occurrence overrides

One-time tasks and recurring occurrences appear together in the same calendar grid.
They must be differentiated visually, not separated into independent tabs.

Hide by default:

- canceled one-time tasks
- paused recurring future occurrences
- historical runs

### 7.3 Calendar Item Differentiation

Each calendar item should visually indicate:

- one-time versus recurring
- current state
- whether the item is an overridden occurrence

Recommended indicators:

- icon or badge for recurring
- lighter or distinct badge for paused or inactive context
- small marker for overridden instance

### 7.4 Calendar Interaction

Primary interactions:

- switch between day, week, and month calendar views
- move to the previous period, next period, or today
- click item to open a modal detail preview
- open full detail from preview
- edit or reschedule from preview
- click an empty day or time slot to open a modal for creating a one-time task at that slot

Week and day views should compress hour rows where the entire row has no tasks,
while keeping empty cells interactive for task creation.

MVP decision:

- do not support drag-and-drop editing in first release
- route all edits through explicit edit actions

### 7.5 Recurring Edit Scope Modal

When a user edits a recurring calendar item, the system must show a scope picker before entering the edit form.

Recommended modal title:

- `Edit Recurring Task`

Recommended question:

- `Do you want to update only this occurrence, or this and future occurrences?`

Options:

- `Only This Occurrence`
- `This and Future`
- `Cancel`

Behavior:

- `Only This Occurrence` creates or updates an occurrence override and may edit the occurrence time, instructions, or both
- `This and Future` updates the recurring definition for future occurrences

### 7.6 Recurring Cancel Scope Modal

When canceling from calendar on a recurring item:

- default scope should be `Only This Occurrence` when the user is acting on one projected instance
- a separate destructive action may allow `Cancel Series`
- temporary suspension of the recurring definition should use `Pause`, not `Cancel`

Recommended labels:

- `Skip This Occurrence`
- `Pause or Cancel Series`

### 7.7 Calendar Empty State

If no planned work exists:

- show message: `No upcoming AI work scheduled`
- show CTA: `Create Task`

## 8. One-Time Kanban Board

### 8.1 Goal

Provide an operational board for one-time work only.

### 8.2 Scope Rules

The board must exclude recurring tasks entirely.

Columns:

- `Upcoming`
- `Running`
- `Completed`
- `Failed`

Optional future column:

- `Canceled`

### 8.3 Card Content

Each card should show:

- title
- planned time or latest execution time
- primary status
- short result summary if completed or failed

### 8.4 Card Actions

From card or card detail:

- open task detail
- edit task if allowed
- reschedule
- retry failed one-time task
- cancel upcoming one-time task

### 8.5 Board Behavior

- a task appears in only one column at a time
- cards move between columns based on backend state
- no manual drag between columns in MVP
- completed cards remain visible in the `Completed` column until the user archives them or applies a filter

### 8.6 Board Empty State

If no one-time tasks exist:

- show message: `No one-time tasks yet`
- show CTA: `Create One-Time Task`

## 9. Recurring Todo View

### 9.1 Goal

Provide a stable management list for recurring tasks.

### 9.2 Why It Is Not Kanban

Recurring tasks represent ongoing commitments rather than transient execution cards. The UX should keep them stable and list-oriented.

### 9.3 Item Content

Each recurring item should show:

- title
- recurrence summary in plain language
- next run time
- schedule state: `Scheduled` or `Paused`
- latest outcome summary if relevant

### 9.4 Item Actions

- open task detail
- edit recurring definition
- pause
- resume
- cancel series

### 9.5 Grouping And Sort

Default grouping:

- `Scheduled`
- `Paused`

Default sort:

- `Scheduled` group first, sorted by `next_run_at` ascending
- `Paused` group second, sorted by most recently updated first

### 9.6 Failure Presentation

If the latest recurring run failed:

- keep the item in recurring todo view
- surface failure as a contextual badge or secondary status
- do not move it to the one-time kanban board

### 9.7 Empty State

If no recurring tasks exist:

- show message: `No recurring tasks yet`
- show CTA: `Create Recurring Task`

## 10. Task Detail

### 10.1 Goal

Provide one place to understand what the task is, when it runs, what happened recently, and what actions are available.

### 10.2 Sections

Recommended section order:

1. Header
2. Schedule summary
3. Instruction content
4. Recent runs
5. Template origin
6. Available actions

### 10.3 Header

Must show:

- task title
- mode badge
- status badge

### 10.4 Actions by Mode

#### One-Time

- edit
- reschedule
- cancel
- retry after failure
- duplicate

#### Recurring

- edit recurrence
- pause
- resume
- cancel series

### 10.5 Detail Entry Context

If opened from calendar on a recurring occurrence:

- detail should retain occurrence context
- UI should show the selected occurrence time
- edits should preserve the selected edit scope

## 11. History

### 11.1 Goal

Provide a low-friction way to review completed and failed runs over time.

### 11.2 Minimum Content

- task title
- run timestamp
- run status
- short summary
- link to task detail

### 11.3 Filters

- status
- mode
- date range

## 12. Shared States

### 12.1 Loading States

- use skeletons for list and board surfaces
- use spinner only for short blocking actions
- preserve previous data when refreshing if possible

### 12.2 Empty States

Every primary screen should include:

- concise explanation
- one primary CTA

### 12.3 Error States

User-visible errors should:

- say what failed
- say whether data was saved or not
- provide recovery action when possible

Examples:

- `Could not save task`
- `Could not update recurring schedule`
- `Could not load calendar items`

### 12.4 Success Feedback

Use lightweight toasts or inline confirmations for:

- task saved
- template created
- recurrence updated
- occurrence override created
- task canceled

## 13. Mobile and Responsive Behavior

### 13.1 Navigation

- sidebar becomes bottom nav or drawer
- primary views remain first-level destinations

### 13.2 Task Detail

- use full-screen sheet instead of side drawer

### 13.3 Board and List Behavior

- kanban may collapse into horizontally scrollable columns
- recurring todo remains a vertical list
- calendar keeps day/week/month navigation but may show an agenda-oriented item list on smaller screens

## 14. Accessibility

Minimum expectations:

- keyboard navigable primary flows
- visible focus states
- sufficient color contrast
- status not conveyed by color alone
- modals trap focus correctly

## 15. Copy Guidance

Prefer literal, low-ambiguity labels:

- `One-Time`
- `Recurring`
- `Upcoming`
- `Running`
- `Completed`
- `Failed`
- `Pause`
- `Resume`
- `Scheduled`
- `Skip This Occurrence`
- `Cancel Series`
- `Save as Template`
- `Only This Occurrence`
- `This and Future`

Avoid overly technical internal labels in the UI:

- avoid exposing `schedule_type`
- avoid exposing `occurrence_override`
- avoid exposing backend workflow ids in normal user flows

### 15.1 Label ↔ API Enum Mapping

The frontend is responsible for translating backend enum values into user-visible labels. Mapping is authoritative against `docs/api-spec.md` and `docs/domain-model.md`.

| Backend value | UI label | Used for |
|---|---|---|
| `one_time` | `One-Time` | execution mode selector, badges |
| `recurring` | `Recurring` | execution mode selector, badges |
| `single_run` | hidden from UI | internal schedule classification |
| `recurring_rule` | hidden from UI | internal schedule classification |
| `scheduled` | `Scheduled` | task status badge, kanban `Upcoming` column, recurring todo state |
| `paused` | `Paused` | recurring todo state |
| `running` | `Running` | kanban column, task status badge |
| `completed` | `Completed` | kanban column, history filter |
| `failed` | `Failed` | kanban column, history filter |
| `canceled` | `Canceled` | history filter, hidden from default board |
| `archived` | `Archived` | filtered views only |
| `planned` (run) | `Scheduled` | recent runs list; not shown as a separate kanban column |
| `queued` (run) | `Scheduled` | recent runs list; grouped under `Upcoming` on the board |

Rules:

- run-level `planned` and `queued` states collapse into the user-facing `Scheduled` label
- `paused` appears only on recurring surfaces; it must not appear on the one-time kanban board
- `Canceled` is filter-only on the board and always visible in history
