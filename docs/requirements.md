---
title: "VesperaFlow Async Agent Planning and Scheduling"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No clarification markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [ ] Problem is validated by evidence (not assumptions)
- [x] Context -> Problem -> Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No technical implementation details included
- [x] A new team member could understand this PRD
- [x] **MECE: Personas** — each persona is distinct, all user types represented
- [x] **MECE: Journeys** — each journey is a unique path, all paths covered
- [x] **MECE: Features** — no overlapping user stories, no capability gaps
- [x] **MECE: Acceptance Criteria** — each criterion tests a unique condition, all paths covered

---

## Output Schema

### PRD Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| sections | SectionStatus[] | Yes | Status of each PRD section |
| clarificationsRemaining | number | Yes | Count of clarification markers |
| acceptanceCriteria | number | Yes | Total testable acceptance criteria defined |

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

| Name | Status | Detail |
|------|--------|--------|
| Product Overview | COMPLETE | Core problem, value, and target user are defined |
| User Personas | COMPLETE | Primary and secondary personas are distinct |
| User Journey Maps | COMPLETE | One-time and scheduled usage paths are covered |
| Feature Requirements | COMPLETE | Core scope and acceptance criteria are defined and lifecycle semantics are normalized across downstream specs |
| Detailed Feature Specifications | COMPLETE | One-time deferred task is detailed in PRD; remaining features are fully specified in `docs/functional-spec.md` |
| Success Metrics | COMPLETE | Product success and tracking are defined |
| Constraints and Assumptions | COMPLETE | Non-technical boundaries and assumptions are documented |
| Risks and Mitigations | COMPLETE | Key product risks are identified |
| Supporting Research | IN_PROGRESS | Current evidence state is documented honestly, but formal validation is still incomplete |

**PRD Status Report**

- `specId`: `001-async-agent-planning`
- `title`: `VesperaFlow Async Agent Planning and Scheduling`
- `status`: `DRAFT`
- `clarificationsRemaining`: `0`
- `acceptanceCriteria`: `26`

---

## Product Overview

### Vision
VesperaFlow helps an individual plan AI work ahead of time and have it run at the right moment, especially during periods when the user is offline or sleeping, without losing visibility or control.

### Problem Statement
Many LLM model providers gate premium usage through rolling windows such as 5-hour usage limits, while some valuable AI tasks require sustained execution time or should be deferred to off-hours. Today, a user who wants AI to perform meaningful work overnight or during a future availability window must remember to come back at the right time, re-enter instructions manually, and monitor progress by hand. This creates three concrete problems:

1. Valuable subscription time is wasted because the user is not present when the usage window is available.
2. Longer-running tasks are postponed or abandoned because they do not fit the user's active work hours.
3. The user cannot reliably separate planning from execution, so AI work remains reactive instead of intentional.

If this is not solved, the user continues paying for model access but fails to capture the full value of available usage windows, especially for one-time deferred tasks and recurring scheduled work.

### Value Proposition
VesperaFlow gives a user a simple way to decide work now and let AI execute later. Its value is not stronger models; its value is turning AI usage into a planned, time-aware workflow.

Compared with manual prompting, reminders, or ad hoc scripts, VesperaFlow offers:

- A single place to define tasks before the ideal execution window arrives
- Support for both one-time execution and recurring schedules
- Confidence that overnight or off-hours work will still happen as intended
- Clear visibility into what was planned, what ran, and what still needs attention

## User Personas

### Primary Persona: Subscription-Constrained AI Power User
- **Demographics:** Individual knowledge worker, indie maker, operator, or builder; moderate to high technical fluency; regularly uses multiple LLM products
- **Goals:** Maximize the value of paid LLM subscriptions, prepare tasks in advance, and offload execution to times when they are away from the keyboard
- **Pain Points:** Forgets to start tasks when usage windows reopen; cannot stay awake or online to supervise long runs; loses track of what should run once versus repeatedly

### Secondary Personas

### Secondary Persona 1: Busy Solo Operator
- **Demographics:** Small business owner, consultant, or solo founder; low to moderate technical fluency
- **Goals:** Hand routine research, summarization, drafting, or monitoring tasks to AI without building custom automations
- **Pain Points:** Existing automation tools feel too technical; reminders do not execute work; current AI chat tools do not behave like a planned workflow

### Secondary Persona 2: Experiment-Heavy AI Tinkerer
- **Demographics:** Advanced AI user who actively compares providers, prompts, and task types
- **Goals:** Queue multiple tasks, test execution timing, and organize repeatable AI jobs over time
- **Pain Points:** Runs are fragmented across tools; repeated setups are tedious; there is no clean separation between idea capture and later execution

### MECE Check: Personas
- [x] Each persona has distinct goals and pain points (no overlap)
- [x] All user types who interact with this feature are represented (no gaps)

## User Journey Maps

### Primary User Journey: Plan Tonight, Run While I Sleep
1. **Awareness:** The user realizes they have work that could be done by AI overnight, but their model access window or personal schedule makes immediate execution inconvenient.
2. **Consideration:** They compare doing it now manually, setting a reminder, or writing a custom automation. They care most about reliability, low setup friction, and being able to review outcomes the next morning.
3. **Adoption:** They choose VesperaFlow because they can define the task once, assign when it should run, and trust that it will execute without them being present.
4. **Usage:** They write a task, choose one-time or recurring execution, review the plan, and leave it unattended. Later they review status and results.
5. **Retention:** They come back because planned execution saves active time, increases subscription utilization, and reduces the mental load of remembering future AI work.

### Secondary User Journeys

### Secondary Journey 1: Capture Now, Schedule for the Next Available Window
1. **Awareness:** The user hits a provider usage limit and cannot run the task immediately.
2. **Consideration:** They choose between relying on memory later or storing the task now for future execution.
3. **Adoption:** They use VesperaFlow to capture the task while the intent is fresh.
4. **Usage:** They assign the next suitable time window and leave the task pending.
5. **Retention:** They keep using the product because they no longer lose task intent while waiting for usage to reset.

### Secondary Journey 2: Set and Forget a Recurring AI Routine
1. **Awareness:** The user notices a repeated task that should happen on a cadence, such as morning summaries or nightly synthesis.
2. **Consideration:** They compare manual repetition with a recurring setup.
3. **Adoption:** They configure a recurring version because it reduces repeated prompting.
4. **Usage:** They periodically review outcomes, tweak instructions, or pause the schedule.
5. **Retention:** They stay because repeated AI work becomes habitual and dependable.

### MECE Check: Journeys
- [x] Each journey describes a distinct path (no two journeys cover the same actions for the same persona)
- [x] All primary, secondary, and error/recovery paths are mapped (no gaps)
- [x] Every persona has at least one journey

## Feature Requirements

### Must Have Features
The first release must make it possible for a single user to define AI work ahead of time, assign when it should execute, and understand what happened afterward.

#### Feature 1: Create a One-Time Deferred Task
- **User Story:** As a user, I want to define a task now and have it run once at a later time so that I can use future availability windows without staying present.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a user has described a task, When they choose a future execution time and save it, Then the task appears as a pending one-time run with that scheduled time
  - [x] Given a one-time task is scheduled, When its execution time passes, Then the task changes from pending to executed or failed with a visible outcome state
  - [x] Given a user changes their mind before execution, When they cancel the one-time task, Then it will no longer run and remains visible as canceled or removed from active plans

#### Feature 2: Create a Recurring Scheduled Task
- **User Story:** As a user, I want to define a recurring AI task so that routine work happens on a predictable cadence without repeated setup.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a user has described a task, When they choose a recurring cadence and save it, Then the task appears as an active recurring schedule
  - [x] Given a recurring schedule exists, When the next run time arrives, Then a new run is created and its status becomes visible to the user
  - [x] Given a recurring schedule is active, When the user pauses or resumes it, Then future runs stop or restart without deleting the task definition

#### Feature 3: Review Planned and Completed Work
- **User Story:** As a user, I want to see what is queued, what is running, and what has completed so that I can trust the system and follow up only when needed.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given the user has multiple tasks, When they open the product, Then they can distinguish pending, running, completed, failed, and paused work
  - [x] Given a task has already run, When the user opens its details, Then they can see the original intent, execution timing, and resulting outcome state
  - [x] Given a task fails, When the user reviews it, Then they can clearly identify that it did not complete successfully

#### Feature 4: Separate Planning from Execution
- **User Story:** As a user, I want to capture and organize future AI work even when it cannot run immediately so that I do not lose intent during busy hours or provider lockouts.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given the user cannot or does not want to execute immediately, When they save a task with a future schedule instead of running it now, Then the task remains available for review, editing, or cancelation before execution begins
  - [x] Given a saved task exists, When the user edits its instructions before it runs, Then the updated plan is used for future execution
  - [x] Given a user is deciding between one-time and recurring behavior, When they review the task setup, Then the difference between the two modes is explicit and understandable

#### Feature 5: Reuse Task Templates
- **User Story:** As a user, I want to save reusable task patterns so that I can quickly create common one-time or recurring jobs without copying and pasting instructions each time.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a user wants to define a reusable task pattern directly, When they create a template from template management, Then the template can be saved without first creating a live task
  - [x] Given a user has created a useful task setup, When they save it as a template, Then they can reuse it later without rewriting the full task
  - [x] Given one or more templates exist, When the user creates a new task, Then they can start from a template instead of starting from scratch
  - [x] Given a template is outdated, When the user edits or deletes it, Then future tasks reflect that change without altering already-created tasks

#### Feature 6: Calendar View for Time-Based Planning
- **User Story:** As a user, I want a calendar view of planned and recurring AI work so that I can understand when tasks will run and adjust my schedule visually.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given the user has one-time or recurring tasks, When they open the calendar view, Then they can see upcoming executions placed on dates or times
  - [x] Given a task appears on the calendar, When the user selects it, Then they can view its basic details and execution mode
  - [x] Given the user reviews the calendar, When multiple tasks are scheduled close together, Then the time overlap is visible without opening each task individually
  - [x] Given the user edits a recurring task from calendar, When the system detects a recurring series, Then it must let the user choose whether the change applies to only that occurrence or to future occurrences as well

#### Feature 7: Todo and Kanban Views for Work Management
- **User Story:** As a user, I want one-time tasks shown in a kanban board by execution state and recurring tasks shown in a todo-style list so that each kind of work is managed in the most intuitive way.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given the user has one-time tasks in different states, When they open the kanban view, Then only one-time tasks are grouped by visible execution status
  - [x] Given the user has recurring tasks, When they open the todo-style recurring view, Then recurring tasks appear as list items with their next run information and current schedule state
  - [x] Given a one-time task changes status over time, When the user revisits the kanban view, Then the task appears in the correct status column
  - [x] Given the user wants to inspect a task from either view, When they open an item, Then they can access its task intent and current or upcoming execution state

#### Feature 8: History View for Run Review
- **User Story:** As a user, I want one place to review completed and failed runs across tasks so that I can quickly understand what happened while I was away.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given one or more runs have completed, When the user opens history, Then they can review runs across tasks in reverse chronological order
  - [x] Given history contains different result types, When the user filters by outcome or mode, Then matching runs remain visible without changing the underlying task records
  - [x] Given a run in history is selected, When the user opens it, Then they can reach the related task detail and understand the run outcome in context

### Should Have Features

No additional should-have features are required for the first draft beyond the must-have set. Future prioritization can revisit automation guidance and passive result delivery after core planning and visibility workflows are proven.

### Could Have Features

#### Feature 9: Suggest Suitable Execution Timing
- **User Story:** As a user, I want help choosing when a task should run so that I can better align work with my expected availability or subscription windows.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given the user is scheduling a task, When they reach the timing step, Then the product can suggest one or more suitable execution times with a plain-language explanation
  - [x] Given a suggestion is shown, When the user accepts or ignores it, Then the final schedule always remains under user control

#### Feature 10: Notify the User of Overnight Results
- **User Story:** As a user, I want a concise summary of what happened while I was away so that I can quickly decide what needs follow-up.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given one or more tasks completed while the user was away, When they next check the product, Then they can see a summary grouped by outcome state
  - [x] Given some tasks failed or need attention, When the user views the summary, Then those items are visually distinguishable from successful runs

### Won't Have (This Phase)
- Multi-user collaboration or shared workspaces
- Enterprise approval chains or team governance
- Complex agent building or developer-facing automation tooling
- Deep provider cost optimization or cross-provider arbitrage
- Fully autonomous decision-making without user-defined task intent

### MECE Check: Features
- [x] No two user stories describe the same capability (no overlap across MoSCoW categories)
- [x] All capabilities needed to solve the problem for every persona are present (no gaps)
- [x] Every feature has testable acceptance criteria
- [x] "Won't Have" explicitly accounts for capabilities that could be confused with in-scope features

## Detailed Feature Specifications

The PRD documents a single illustrative feature in detail here to anchor the product-level description. Full per-feature functional behavior, main flows, alternate flows, business rules, and edge cases for every feature above are specified in `docs/functional-spec.md`.

### Feature: Create a One-Time Deferred Task
**Description:** This feature allows the user to describe a piece of AI work now, decide that it should happen later, and leave it in a planned state until its execution time arrives. It is the clearest expression of the product's value because it converts immediate intent into deferred execution.

**User Flow:**
1. User writes the task they want AI to perform
2. System asks whether it should run once or recur
3. User selects one-time execution and assigns a future time
4. System stores the task as planned work and shows it in the upcoming queue
5. User later returns to review whether it ran successfully

**Business Rules:**
- Rule 1: A one-time task must have exactly one future execution time at the moment it is saved
- Rule 2: A one-time task must remain editable until execution begins
- Rule 3: After execution, the task should be preserved in history even though it is no longer an active future plan
- Rule 4: A canceled one-time task must not trigger execution

**Edge Cases:**
- Scenario 1: The user schedules a task for a time that is already in the past -> Expected: the product blocks save or asks the user to choose a valid future time
- Scenario 2: The user forgets what the task was meant to do before it runs -> Expected: the product preserves the original task intent in a readable form
- Scenario 3: The task fails overnight -> Expected: the user can clearly identify failure the next time they review the product

### Other Features

Features 2 through 10 (recurring task, review, planning/execution separation, templates, calendar, kanban, todo, history, suggested timing, overnight notifications) are captured in full behavioral detail in `docs/functional-spec.md`. The PRD intentionally does not duplicate that content.

## Success Metrics

### Key Performance Indicators
- **Adoption:** At least 60% of newly active users create at least one planned task within their first two sessions
- **Engagement:** At least 40% of active users create either one additional one-time task or one recurring task each week
- **Quality:** At least 85% of scheduled runs reach a terminal visible state without the user needing to manually check during execution
- **Business Impact:** Users report that VesperaFlow helps them reclaim at least 3 AI task starts per week that would otherwise have been delayed, forgotten, or skipped

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `task_created` | task_type, created_at, scheduled_for, recurring_flag | Measure adoption of planned AI work |
| `task_edited` | task_id, edited_before_run, task_type | Measure how often planning evolves before execution |
| `task_canceled` | task_id, task_type, time_before_run | Measure abandonment and planning friction |
| `run_started` | task_id, task_type, start_time, planned_vs_actual_delta | Measure execution reliability |
| `run_completed` | task_id, outcome_state, completion_time | Measure successful unattended completion |
| `run_failed` | task_id, failure_state, completion_time | Measure failure patterns and product trust |
| `schedule_paused_or_resumed` | task_id, action, recurring_flag | Measure recurring schedule management |
| `results_viewed` | task_id, time_since_completion, outcome_state | Measure whether completed work is actually reviewed |

---

## Constraints and Assumptions

### Constraints
- The first phase is optimized for individual use, not teams
- The product must stay understandable to users who think in tasks and time, not in automation logic
- The initial scope must solve planning and visibility before expanding into advanced autonomy
- The product should be useful even if future users rely on different LLM providers with different usage windows, but MVP validates the loop with Claude Code first
- The product does not implement its own AI agent runtime and does not call LLM APIs directly; MVP orchestrates the user's existing Claude Code runtime through the Claude Agent SDK, which must already be installed and authenticated on the host. See `docs/adr/002-execution-engine-choice.md`.

### Assumptions
- Users already know what kinds of AI work they want to delegate, even if they do not know how to automate it
- A meaningful number of users experience provider access limits or timing mismatches severe enough to change their behavior
- Users are comfortable trusting planned AI work as long as they retain clear visibility and control
- Users value a mix of one-time and recurring tasks rather than only one mode

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Users may not trust unattended AI execution | High | Medium | Emphasize visibility, clear status states, and easy review of outcomes |
| The problem may feel niche if framed only around 5-hour windows | High | Medium | Position the product around deferred AI work broadly, with subscription windows as a strong motivating use case |
| Users may confuse task planning with full workflow automation | Medium | High | Keep positioning focused on planning, scheduling, and review rather than complex autonomous systems |
| Users may expect perfect results from long-running AI tasks | Medium | Medium | Set expectations around visibility and follow-up rather than guaranteed quality of task outcomes |

## Product Decisions

- First release positioning is deferred AI work anytime the user is offline or away. Overnight execution remains the strongest example, not the only story.
- Run review should show enough detail to build confidence without exposing executor internals: terminal outcome, short result summary, timestamps, failure category when relevant, and artifact links.
- Schedule recommendations are post-launch. MVP requires user-controlled scheduling only.
- Onboarding examples should use a mixed set of task categories, led by research, drafting, and summarization. Monitoring examples are secondary because they can imply broader autonomous behavior than MVP intends.

---

## Supporting Research

### Competitive Analysis
Current alternatives appear fragmented across four categories:

- General chat interfaces are strong for immediate execution but weak for future planning
- Reminder and calendar tools help users remember but do not execute AI work
- Script-based automation can execute later but is too technical for many target users
- Generic task managers track intent but are detached from AI execution outcomes

This suggests an opportunity for a product centered on planned AI work rather than either chat or developer automation.

### User Research
No formal user research has been completed yet. The current PRD is based on the founder hypothesis that AI power users experience repeated frustration around timing, subscription windows, and unattended execution. This needs validation through user interviews and lightweight usage testing.

### Market Data
No formal market sizing has been completed yet. The strongest directional signal is behavioral: more users are integrating paid LLM tools into daily work, and usage limits or time-bound access windows create scheduling friction that traditional chat interfaces do not solve.
