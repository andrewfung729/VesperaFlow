# VesperaFlow MVP Progress

_Last updated: 2026-04-27. Update this whenever product scope or implementation
status changes._

This is the implementation truth table for the MVP described in
`docs/requirements.md`, `docs/functional-spec.md`, and `docs/api-spec.md`.
Specs describe the target; this file records what currently exists in the repo
and what remains before the MVP is shippable.

## Update Rules

Update this file when:

- a feature moves between `Not Started`, `Partial`, `Blocked`, or `Done`
- an endpoint, view, model, workflow, or migration lands for an MVP feature
- a feature is intentionally downscoped, deferred, or split
- verification coverage changes for an MVP area
- an active plan completes and changes MVP readiness

Status meanings:

- `Done`: implemented, wired through the expected layers, and covered by tests
- `Partial`: useful slice exists, but some MVP behavior, UI, integration, or
  verification is missing
- `Not Started`: only specs or placeholder fields exist
- `Blocked`: cannot progress until an explicit dependency or decision lands

## Current Summary

VesperaFlow MVP is functionally complete. One-time tasks, history, templates,
recurring lifecycle commands, recurring todo, calendar visibility, and
occurrence overrides are wired through the owning layers. Claude Code executor
preflight, runtime classification, and authenticated live smoke have been
verified on the local stack.

## Feature Progress

| MVP Feature | Status | Current Implementation Evidence | Remaining Gap |
|---|---|---|---|
| Create one-time deferred task | Partial | API route and repository create a task, single-run schedule, planned run, target working directory, and Temporal Schedule; web composer creates one-time tasks and gates Claude Code task creation through executor preflight; an opt-in full-stack `debug_printer` smoke test covers local Postgres, Temporal, API, Worker, and persisted run state. | Need a recorded live success path for the selected production executor. Full-stack smoke stays opt-in and local-only; it will not become a required CI gate for MVP. |
| Create recurring scheduled task | Partial | Store/API now create recurring tasks with one active `recurring_rule` schedule, validate RRULE/timezone inputs, create/update/pause/resume/cancel the matching Temporal Schedule, lazily materialize each schedule-fired occurrence into an idempotent run via `occurrence_key`, expose recurring tasks in the recurring todo view, project recurring occurrences into calendar, and support single-occurrence overrides. Repository, API, replay, web unit, and web smoke coverage exercise the core lifecycle, todo read model, calendar projection, and override commands. The end-to-end path was manually verified on the local stack. | Full-stack smoke stays opt-in and local-only; it will not become a required CI gate for MVP. |
| Review planned and completed work | Partial | Task detail returns task, schedule, latest run, and runs; one-time board groups tasks by status; `/api/v1/views/history` and the web History route show completed/failed runs across tasks with status and execution-mode filters; `/api/v1/views/recurring-todo` and the web recurring todo route show active/paused recurring commitments with latest-run context; `/api/v1/views/calendar` and the web Calendar route show one-time and recurring planned work in a bounded agenda window. Recurring materialized runs use the same run/history model. | Broaden web behavior coverage beyond smoke-level. |
| Separate planning from execution | Partial | One-time task creation stores intent and a planned run before execution; recurring task creation stores the parent definition before Temporal fires, and the first Workflow Activity materializes occurrence runs without DB access in Workflow code. Occurrence overrides are PostgreSQL state, canceled occurrences are skipped by the existing first persistence Activity, and moved later occurrences wait on a Temporal Workflow timer. | Add stronger live integration coverage. |
| Reuse task templates | Done | Template model/table, repository methods, `/api/v1/templates` CRUD/archive/instantiate endpoints, web template management, optional default target directory, and composer prefill flow exist. Creating from a template copies fields onto an independent task while preserving `template_id`; archived templates leave linked tasks readable. | Save-as-template from an existing task is not yet exposed as a shortcut, but direct template management covers the MVP template lifecycle. |
| Calendar view for time-based planning | Done | `occurrence_overrides` storage, `/api/v1/views/calendar`, scoped occurrence update/cancel endpoints, calendar projection tests, and a web Calendar agenda route now cover one-time tasks, active recurring projections, overlap visibility, overrides, skipped occurrences, empty/loading/error states, task-detail linking, and scoped edit entry points. | Future hardening can add richer visual calendar layouts. |
| One-time kanban view | Done | `/api/v1/views/kanban` supports an `include_canceled` query parameter (default `false`) aligned with UX rules; `KanbanBoardView.vue` has a "Show canceled" toggle, loading spinner, global empty state, and per-column empty states. Web/API tests cover the default hidden-canceled and explicit shown-canceled paths. | Future hardening can add drag-and-drop or more advanced filtering, but the MVP kanban lifecycle is wired. |
| Recurring todo view | Done | Store read model lists recurring tasks only, with active schedules sorted by `next_run_at` before paused schedules sorted by recent update; `/api/v1/views/recurring-todo` exposes latest-run context; the web route groups scheduled and paused items, links to task detail, and supports pause/resume from the list. Repository, API, web unit, and Playwright smoke coverage exist. | Future hardening can add richer recurrence copy. |
| History view for run review | Done | Store history query, `/api/v1/views/history`, and `HistoryView.vue` list completed/failed runs in reverse finished order, filter by outcome and execution mode, and link items back to task detail with selected run context. Repository, API, web unit, and Playwright smoke coverage exist. | Recurring runs will appear through the same read model once M3 materializes them. |
| Executor integration | Done | Worker workflow, activities, executor router, debug printer, Claude Agent SDK invocation, API workspace preflight endpoint, and composer preflight UX exist; Claude output artifacts and auth, misconfiguration, workspace, and execution failure classifications are covered with mocked Worker/API/web tests. Authenticated live Claude Code smoke was manually verified on the local stack. | Full-stack smoke stays opt-in and local-only; it will not become a required CI gate for MVP. |
| Temporal production hardening | Partial | One-time and recurring Temporal Schedule client paths exist; repo check enforces Temporal as sole scheduler; `TaskRunWorkflow` has replay coverage for completed, failed, canceled, and pre-execution-canceled paths. | Add rollout/versioning discipline. Live recurring full-stack smoke was manually verified on the local stack. |

## Layer Readiness

| Layer | Status | Notes |
|---|---|---|
| Domain docs | Done | Requirements, functional spec, domain model, API spec, UX spec, architecture, Temporal architecture, and ADRs exist. |
| Core domain package | Partial | Shared enums, contracts, IDs, recurrence validation, occurrence-key helpers, occurrence edit enums, status derivation, and template default validation exist. |
| Store | Partial | Task, schedule, run, template, and occurrence override tables exist, including target working directory, terminal-run history index, recurring run `occurrence_key` idempotency, template archive support, copy-on-instantiate repository coverage, calendar projection, and scoped occurrence overrides. |
| API | Partial | One-time and recurring task lifecycle endpoints, occurrence update/cancel endpoints, schedule/run/detail, kanban with optional canceled visibility, history, recurring todo, calendar, executor preflight, and template CRUD/archive/instantiate endpoints exist. |
| Worker | Partial | TaskRunWorkflow, activities, debug printer, Claude Agent SDK executor, recurring materialization, and import-hygiene/replay coverage exist; authenticated live Claude Code and recurring smoke were manually verified on the local stack. |
| Web | Partial | Composer, one-time board with canceled toggle and empty states, task detail, history, recurring todo, calendar agenda, template management, template target-directory prefill, executor selection, executor preflight visibility, and target directory capture exist. |
| Verification | Partial | Unit/API/web smoke checks exist; generated facts are present; replay coverage exists for `TaskRunWorkflow`; opt-in full-stack one-time smoke exists for local Postgres/Temporal/API/Worker; Playwright covers the MVP navigation path with mocked API data. | Full-stack smoke is intentionally opt-in and local-only; it is not a required CI gate for MVP. |

## Recommended Build Order

MVP is complete. Future work beyond MVP should be planned in new active plans.

## Current Blockers And Risks

- The MVP scope in docs is broader than the implemented product surface; new
  agents should not assume every specified endpoint or view exists.
- Claude Agent SDK execution, runtime classification, and authenticated live
  smoke are implemented and manually verified; they are not yet in automated
  CI coverage.
- Calendar and occurrence override semantics are implemented in the
  store/API/worker/web layers, and the end-to-end recurring path was manually
  verified on the local stack.
- Generated schema/API/Temporal snapshots now exist under `docs/generated/`, but
  they are still manually refreshed.
- Full-stack Temporal smoke is opt-in and local-only; it will not become a
  required CI gate for MVP.

## Verification Snapshot

Most recent broad verification recorded on 2026-04-27 during MVP hardening:

- `bun run type-check`
- `bun run lint:check`
- `bun run test:unit:run` (`24 passed`)
- `bun run test:e2e:smoke` (`6 passed`)
- `python scripts/check_agent_repo.py`
- `uv run ruff check .`
- `uv run pytest` (`61 passed, 1 skipped`)
- `uv run python scripts/generate_agent_facts.py`

Notes:

- `uv run pytest` skipped the opt-in full-stack smoke because
  `VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL` was not set.
- Full-stack smoke (one-time and recurring) was manually verified on the local
  stack. Authenticated live Claude Code smoke was also manually verified.
