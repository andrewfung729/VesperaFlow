# Plan: MVP Completion

## Goal

Finish the VesperaFlow MVP described in `docs/requirements.md`,
`docs/functional-spec.md`, and `docs/api-spec.md` without widening scope beyond
local-first planning, Temporal-backed execution, reusable templates, recurring
schedules, calendar visibility, recurring todo, and run history.

The expected user-visible outcome is:

- one-time tasks can be planned, changed, canceled, executed, and reviewed with
  full-stack confidence
- templates can be created, edited, archived, and used to create independent
  tasks
- recurring tasks can be created, paused, resumed, updated, executed by
  Temporal schedules, and inspected from task detail, recurring todo, calendar,
  and history surfaces
- completed and failed runs can be reviewed across tasks
- Claude Code execution has an explicit preflight and at least one documented
  live smoke path

## Current State

`docs/MVP_PROGRESS.md` is the implementation truth table. As of 2026-04-26,
the repo has backend recurring lifecycle support and recurring management
surfaces, but it is not a complete MVP because calendar, occurrence overrides,
recurring creation/edit UI, and release hardening remain incomplete.

Implemented or partially implemented:

- `packages/core` has shared enums, IDs, validation, status derivation,
  recurrence validation, next-occurrence calculation, and occurrence-key
  helpers.
- `packages/store` has Task, Schedule, Run, and Template models/repositories,
  plus recurring schedule commands, recurring run materialization, history, and
  recurring todo read models. OccurrenceOverride tables do not exist yet.
- `apps/api` supports one-time task create/detail/list/reschedule/cancel,
  `/api/v1/views/kanban`, `/api/v1/views/history`, template
  create/list/detail/update/archive/instantiate, and recurring task
  create/update/pause/resume/cancel commands.
- `apps/worker` has `TaskRunWorkflow`, Activities, executor routing,
  `debug_printer`, Claude Agent SDK adapter tests, and recurring run
  materialization support.
- `apps/web` has a one-time-only task composer, one-time kanban board, history
  view, template management, template prefill, task detail view, executor
  selection, target working directory capture, and recurring todo management
  for existing recurring tasks. It does not yet expose recurring task creation
  or recurring schedule editing.
- `infra` has a local Postgres/Temporal compose stack.
- `docs/generated/` has refreshed schema, API route, Temporal surface, and
  dependency graph snapshots.

Major MVP gaps:

- decide whether the opt-in full-stack one-time smoke becomes a CI service test
- live full-stack recurring smoke coverage with local Postgres, Temporal, API,
  Worker, and web
- web composer/detail controls for creating and editing recurring schedules
- calendar read model and web calendar/agenda view
- occurrence override support for scoped recurring edits
- failed/canceled recurring replay histories
- live Claude Code smoke/preflight documentation

## Decisions

- Temporal remains the only scheduler. Do not introduce cron, APScheduler,
  polling loops, app sleeps, or a second delayed-start mechanism.
- PostgreSQL remains authoritative for product-visible task, schedule, run,
  template, occurrence override, and read-model state. Temporal owns durable
  execution history and timers.
- Workflow code stays deterministic and must not import DB, network, SDK,
  randomness, or disk I/O dependencies.
- Executor invocation stays in Activities through executor adapters. The app
  does not call LLM provider APIs directly.
- Build order favors reducing uncertainty before adding breadth:
  one-time full-stack hardening, history, templates, recurring lifecycle,
  recurring todo/calendar, then live Claude Code hardening.
- Recurring parent tasks stay `scheduled` or `paused` at task level; individual
  run failures are shown as latest-run/history context.
- Template edits affect only future task creation and never mutate existing
  tasks created from the template.
- Calendar and recurring todo are backend-derived read models, not independent
  UI-only state.
- Generated docs under `docs/generated/` should be refreshed from code or the
  live metadata and include their regeneration commands.

## Milestones

### M0: Baseline Agent Facts And Full-Stack One-Time Confidence

Purpose: prove the existing vertical slice before building recurring behavior on
top of it.

Progress on 2026-04-26:

- Generated snapshots now exist for DB schema, API routes, Temporal surface, and
  package dependencies.
- `docs/local-full-stack-runbook.md` documents the local Postgres, Temporal,
  API, Worker, and web one-time `debug_printer` smoke path.
- `TaskRunWorkflow` has replay coverage for the completed debug-printer path.
- An opt-in full-stack integration test covers local Postgres, Temporal, API,
  Worker, and persisted terminal run state for `debug_printer`.
- Broad Python and web verification commands passed locally; the full-stack
  smoke remains opt-in and skipped in default `uv run pytest`.
- Remaining M0 work: decide whether the full-stack smoke becomes a CI service
  test and add broader kanban web behavior coverage.

Scope:

- Add generated snapshots:
  - `docs/generated/db-schema.md`
  - `docs/generated/api-routes.md`
  - `docs/generated/temporal-surface.md`
  - optionally `docs/generated/dependency-graph.md`
- Add or document a local full-stack runbook for Postgres, Temporal, API,
  Worker, and web.
- Add an integration test or scripted smoke path that creates a one-time
  `debug_printer` task, lets Temporal start the Workflow, and verifies the run
  reaches a terminal state in PostgreSQL.
- Add Temporal replay coverage for `TaskRunWorkflow`.
- Improve one-time kanban behavior where MVP specs already call out gaps:
  canceled visibility, empty states, error handling, and filters if needed.
- Update `docs/MVP_PROGRESS.md` and `docs/QUALITY.md` after the slice is proven.

Exit criteria:

- one-time task execution is verified across API, store, Temporal, Worker, and
  persisted run state
- generated facts exist and are useful enough for a new agent to inspect current
  system shape without reading migrations and route code first
- broad checks pass

### M1: History Read Model

Purpose: make completed and failed work reviewable before increasing the number
of ways work can execute.

Progress on 2026-04-26:

- Added a derived store history query for completed/failed runs across tasks,
  ordered by `finished_at` descending, with pagination and status, execution
  mode, and finished-window filters.
- Added a terminal-run history index and Alembic migration.
- Added `/api/v1/views/history` matching the documented list envelope and
  history item shape.
- Added a web History route with loading, error, empty, filtered, and linked
  task-detail states; task detail now highlights a selected run from history.
- Added repository, API, web unit, and Playwright smoke coverage for the slice.
- Refreshed generated DB/API snapshots after the endpoint and index landed.

Scope:

- Add store repository query for completed/failed runs across tasks in reverse
  chronological order.
- Add API endpoint matching `docs/api-spec.md` history behavior, including
  pagination and filters for outcome and execution mode.
- Add web history route/view with empty, loading, error, filtered, and linked
  task-detail states.
- Ensure history includes one-time runs now and can include recurring runs once
  M3 lands.
- Add API, repository, web unit, and smoke coverage.
- Update `docs/MVP_PROGRESS.md` when history moves from `Not Started`.

Exit criteria:

- completed and failed one-time runs are visible across tasks
- selecting a history item resolves to task detail
- tests cover empty, filtered, failed, and successful histories

### M2: Templates

Purpose: add reusable task definitions before recurring complexity, because
templates are mostly CRUD plus task instantiation.

Progress on 2026-04-26:

- Added the Template SQLAlchemy model, Alembic migration, repository methods,
  archive behavior, and template default validation.
- Added `/api/v1/templates` create/list/detail/update/archive endpoints and
  `/api/v1/templates/{template_id}/instantiate`.
- Updated one-time task creation so a provided template is validated and can
  supply the default executor and optional target directory while preserving
  `template_id` lineage.
- Added a web Templates route for direct management and a composer prefill flow
  that copies template content and target-directory defaults into an independent
  task draft.
- Added repository, API, web unit, and Playwright smoke coverage for template
  management, archive behavior, and copy-on-instantiate semantics.
- Refreshed generated DB/API snapshots after the template table and endpoints
  landed.

Scope:

- Add Template SQLAlchemy model, migration, repository methods, and archive
  behavior.
- Add core contracts/validation for template defaults where shared across
  API/web.
- Add API endpoints for create/list/detail/update/archive and create task from
  template, aligned with `docs/api-spec.md`.
- Update task creation to copy template fields into the new independent task
  while preserving `template_id` lineage.
- Add web template management and composer prefill flow.
- Add repository/API/web tests proving edits to templates do not mutate existing
  tasks.
- Update generated DB/API snapshots and MVP progress.

Exit criteria:

- templates can be managed directly
- a task can be created from a template and then edited independently
- archived templates disappear from active selection but linked tasks remain
  readable

### M3: Recurring Task Lifecycle And Temporal Schedule Behavior

Purpose: implement the core recurring schedule semantics before dependent read
models.

Progress on 2026-04-26:

- Added recurring RRULE/timezone validation, next-occurrence calculation, and
  occurrence-key helpers in `packages/core`.
- Added recurring task repository commands for create, update, pause, resume,
  cancel, and idempotent run materialization keyed by `(schedule_id,
  occurrence_key)`.
- Added `runs.occurrence_key` and the unique schedule/occurrence constraint.
- Added API support for recurring task create, update, pause, resume, and cancel
  commands with rollback around Temporal Schedule mutations.
- Extended `TemporalScheduler` to create, update, pause, resume, and delete
  recurring Temporal Schedules with a short catch-up window to avoid backfilling
  missed paused occurrences.
- Extended `TaskRunWorkflow` so recurring schedule-fired runs materialize the
  product run in the first persistence Activity before executor invocation while
  preserving the old one-time replay command shape.
- Added core, repository, API, and one-time/recurring replay tests. Remaining M3
  hardening is live full-stack recurring smoke coverage, failed/canceled replay
  histories, and a web creation/editing surface for recurring schedules.

Scope:

- Extend core validation for `ExecutionMode.RECURRING` with
  `ScheduleType.RECURRING_RULE`, `recurrence_rule`, and
  `recurrence_timezone`.
- Add store support for recurring schedules and one-active-schedule invariant.
- Add API create/update/pause/resume/cancel endpoints for recurring tasks.
- Add web composer/detail support for creating and editing recurring schedules,
  including execution mode selection, RRULE/timezone capture, and validation
  feedback.
- Extend `TemporalScheduler` to create, pause, resume, update, and cancel
  recurring Temporal Schedules.
- Decide and implement the recurring run materialization boundary:
  the product run row must exist before or at Workflow start, and the chosen
  approach must keep Workflow code deterministic.
- Add idempotency and rollback handling around PostgreSQL writes and Temporal
  Schedule mutations.
- Add unit, API, repository, Temporal integration, and replay tests for create,
  pause, resume, update, cancel, missed occurrences during pause, and failed run
  visibility.
- Keep recurrence parsing/evaluation in Activity/API/store-safe code, never in
  Workflow code unless it is deterministic and dependency-safe.
- Update generated snapshots and MVP progress.

Exit criteria:

- recurring tasks can be created from the web UI and generate visible runs on
  schedule
- pause prevents future runs and resume does not backfill missed occurrences
- recurring task-level status remains stable while run outcomes appear in run
  history/latest-run context
- Temporal remains the only timing mechanism

### M4: Recurring Todo

Purpose: expose recurring work as ongoing commitments, separate from one-time
kanban.

Progress on 2026-04-26:

- Added a derived store recurring todo read model that returns recurring tasks
  only, with active schedules sorted by `next_run_at` before paused schedules
  sorted by recent schedule update.
- Included latest-run context in recurring todo items while keeping parent
  recurring tasks in scheduled or paused task states.
- Added `/api/v1/views/recurring-todo` with status, paused inclusion,
  pagination, and latest outcome fields.
- Added the web Recurring Todo route, primary navigation entry, grouped
  scheduled/paused tables, task-detail linking, and pause/resume list actions.
- Added repository, API, web unit, and Playwright smoke coverage, and refreshed
  generated API route facts.

Scope:

- Add backend recurring todo read model:
  active scheduled items first by `next_run_at`, then paused items by
  `updated_at`.
- Include latest run outcome as context without converting the parent recurring
  task to failed/completed.
- Add API endpoint and web recurring todo route/view.
- Support pause/resume from the list where the API has already landed in M3.
- Add repository/API/web tests and smoke coverage.
- Update generated snapshots and MVP progress.

Exit criteria:

- only recurring tasks appear in recurring todo
- active and paused recurring tasks sort and display according to
  `docs/functional-spec.md`
- latest failure is visible while the recurring task remains manageable

### M5: Calendar And Occurrence Overrides

Purpose: give the user time-based planning visibility and scoped recurring edit
behavior.

Progress on 2026-04-27:

- Added `OccurrenceOverride` storage, Alembic migration, shared occurrence edit
  enums, and repository commands for single-occurrence update/cancel.
- Added a bounded calendar read model that projects one-time planned runs and
  active recurring future occurrences, applies active overrides, hides skipped
  occurrences, hides paused recurring schedules, and hides canceled one-time
  work by default.
- Extended recurring run materialization so a canceled occurrence override
  creates a canceled run and returns before executor invocation through the
  existing Workflow no-op path; active instruction/time overrides are applied in
  the first persistence Activity, and moved later occurrences wait on a Temporal
  Workflow timer before executor invocation.
- Added `/api/v1/views/calendar`,
  `/api/v1/tasks/{task_id}/occurrences/update`, and
  `/api/v1/tasks/{task_id}/occurrences/cancel`.
- Added the web Calendar agenda route, primary navigation entry, overlap
  visibility, task-detail linking with occurrence context, scoped edit panel,
  and skip-this-occurrence action.
- Added repository, API, web client, and Playwright smoke coverage, and
  refreshed generated schema/API/Temporal/dependency snapshots.

Scope:

- Add OccurrenceOverride model, migration, repository methods, and API schemas.
- Add calendar read model endpoint bounded by `from` and `to`.
- Project one-time scheduled runs and recurring future occurrences in the
  requested time window.
- Hide canceled one-time tasks and paused recurring future occurrences from the
  default upcoming calendar view.
- Add scoped edit commands:
  - `this_occurrence_only` creates or updates an occurrence override
  - `this_and_future` updates the parent recurring task/schedule for future
    occurrences
- Add web calendar or agenda view with overlap visibility, empty/loading/error
  states, task-detail linking, and scoped edit entry points.
- Add tests for window bounds, timezone handling, overlap exposure, paused
  recurring schedules, canceled one-time tasks, and scoped recurring edits.
- Update generated snapshots and MVP progress.

Exit criteria:

- upcoming one-time and recurring work is visible in a calendar/agenda window
- recurring scoped edits preserve historical runs and do not mutate past
  occurrences
- calendar and recurring todo resolve to the same recurring task identity

### M6: Claude Code Preflight And MVP Release Hardening

Purpose: finish executor confidence and release-readiness checks after the
product surfaces are connected.

Scope:

- Add an explicit Claude Code preflight path that classifies SDK missing,
  unauthenticated, misconfigured, workspace unavailable, and execution
  unavailable failures.
- Add web/API visibility for executor unavailability before or during task
  creation where practical.
- Add a documented live Claude Code smoke path that is opt-in and safe for local
  developer credentials.
- Expand web E2E smoke to cover the MVP navigation path:
  composer, kanban, history, templates, recurring todo, calendar, and task
  detail.
- Re-run and update all generated snapshots.
- Move completed plan slices to `docs/plans/completed/` or split this plan into
  smaller completed records as milestones land.
- Update `docs/MVP_PROGRESS.md`, `docs/QUALITY.md`, and any API/domain docs
  that changed during implementation.

Exit criteria:

- MVP surfaces are implemented and tested at the owning layers
- executor setup failures are visible and classified
- broad verification passes locally and in CI
- docs accurately describe what shipped

## Next Actions

1. Decide whether the opt-in full-stack smoke should become a CI service test or
   remain local-only until recurring full-stack behavior lands.
2. Add live full-stack recurring smoke coverage with local Postgres, Temporal,
   API, Worker, and web.
3. Start M6 Claude Code preflight and release hardening.
4. Improve one-time kanban web behavior where MVP specs already call out gaps.

## Blockers

- Full-stack tests require local Postgres and Temporal services. CI may need a
  service container strategy before these can become required checks.
- Live Claude Code smoke coverage depends on a developer machine with the SDK
  installed, authenticated, and allowed to operate in the target workspace.
- Calendar recurrence projection needs a deterministic, timezone-aware recurrence
  implementation that matches `docs/domain-model.md` DST and missed-occurrence
  rules.

## Verification

Run from the repository root unless noted:

```bash
python scripts/check_agent_repo.py
uv run ruff check .
uv run pytest
```

Run from `apps/web`:

```bash
bun run type-check
bun run lint:check
bun run test:unit:run
bun run test:e2e:smoke
```

Feature-specific verification to add as milestones land:

- full-stack one-time `debug_printer` execution against local Postgres and
  Temporal
- Temporal replay test for every Workflow shape change
- repository/API/web tests for template independence and archive behavior
- recurring Temporal Schedule integration tests for create, pause, resume,
  update, cancel, and missed occurrences
- recurring todo read-model tests for status grouping and latest-run context
- calendar projection and occurrence override tests for timezone, overlap,
  paused/canceled filtering, and scoped edits
- opt-in live Claude Code smoke test with documented prerequisites
