# VesperaFlow MVP Progress

_Last updated: 2026-04-26. Update this whenever product scope or implementation
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

VesperaFlow is not yet a complete MVP, but it now has one-time tasks, history,
templates, recurring lifecycle commands, and recurring todo wired through the
owning layers. The remaining release-critical product surfaces are calendar
visibility, occurrence overrides, and live Claude Code confidence.

The largest MVP gaps are calendar, occurrence overrides, and full Claude Code
executor invocation. The codebase already has strong domain docs for these
areas, but those surfaces are not yet fully implemented.

## Feature Progress

| MVP Feature | Status | Current Implementation Evidence | Remaining Gap |
|---|---|---|---|
| Create one-time deferred task | Partial | API route and repository create a task, single-run schedule, planned run, target working directory, and Temporal Schedule; web composer creates one-time tasks; an opt-in full-stack `debug_printer` smoke test covers local Postgres, Temporal, API, Worker, and persisted run state. | Need clear success path for the selected production executor and required CI/service-container strategy for full-stack smoke. |
| Create recurring scheduled task | Partial | Store/API now create recurring tasks with one active `recurring_rule` schedule, validate RRULE/timezone inputs, create/update/pause/resume/cancel the matching Temporal Schedule, lazily materialize each schedule-fired occurrence into an idempotent run via `occurrence_key`, and expose recurring tasks in the recurring todo view. Repository, API, replay, web unit, and web smoke coverage exercise the core lifecycle and todo read model. | Add calendar projections, occurrence overrides, and live full-stack recurring smoke coverage. |
| Review planned and completed work | Partial | Task detail returns task, schedule, latest run, and runs; one-time board groups tasks by status; `/api/v1/views/history` and the web History route show completed/failed runs across tasks with status and execution-mode filters; `/api/v1/views/recurring-todo` and the web recurring todo route show active/paused recurring commitments with latest-run context. Recurring materialized runs use the same run/history model. | Add calendar context and broaden web behavior coverage. |
| Separate planning from execution | Partial | One-time task creation stores intent and a planned run before execution; recurring task creation stores the parent definition before Temporal fires, and the first Workflow Activity materializes occurrence runs without DB access in Workflow code. | Extend the same guarantees to calendar occurrence edits and add stronger integration coverage. |
| Reuse task templates | Done | Template model/table, repository methods, `/api/v1/templates` CRUD/archive/instantiate endpoints, web template management, optional default target directory, and composer prefill flow exist. Creating from a template copies fields onto an independent task while preserving `template_id`; archived templates leave linked tasks readable. | Save-as-template from an existing task is not yet exposed as a shortcut, but direct template management covers the MVP template lifecycle. |
| Calendar view for time-based planning | Not Started | Calendar behavior is specified in product/API/UX docs. | Add calendar read model endpoint, web calendar/agenda view, time-window filtering, overlap handling, and scoped recurring occurrence edit entry point. |
| One-time kanban view | Partial | `/api/v1/views/kanban` and `KanbanBoardView.vue` exist for one-time tasks. | Add stronger filtering/empty/error behavior, hide or filter canceled items per UX rules, and broaden web/API tests. |
| Recurring todo view | Done | Store read model lists recurring tasks only, with active schedules sorted by `next_run_at` before paused schedules sorted by recent update; `/api/v1/views/recurring-todo` exposes latest-run context; the web route groups scheduled and paused items, links to task detail, and supports pause/resume from the list. Repository, API, web unit, and Playwright smoke coverage exist. | Future hardening can add richer recurrence copy and live full-stack recurring smoke, but the MVP todo lifecycle is wired. |
| History view for run review | Done | Store history query, `/api/v1/views/history`, and `HistoryView.vue` list completed/failed runs in reverse finished order, filter by outcome and execution mode, and link items back to task detail with selected run context. Repository, API, web unit, and Playwright smoke coverage exist. | Recurring runs will appear through the same read model once M3 materializes them. |
| Executor integration | Partial | Worker workflow, activities, executor router, debug printer, and Claude Agent SDK invocation exist; Claude output artifacts and expected SDK failure classifications are covered with mocked Worker tests. | Add live Claude Code smoke coverage, stronger preflight UX, and full-stack execution verification. |
| Temporal production hardening | Partial | One-time and recurring Temporal Schedule client paths exist; repo check enforces Temporal as sole scheduler; `TaskRunWorkflow` has replay coverage for one-time and recurring materialized debug-printer paths. | Add failed/canceled replay histories, live recurring full-stack smoke coverage, and rollout/versioning discipline. |

## Layer Readiness

| Layer | Status | Notes |
|---|---|---|
| Domain docs | Done | Requirements, functional spec, domain model, API spec, UX spec, architecture, Temporal architecture, and ADRs exist. |
| Core domain package | Partial | Shared enums, contracts, IDs, recurrence validation, occurrence-key helpers, status derivation, and template default validation exist; calendar/override behavior needs more domain helpers as features land. |
| Store | Partial | Task, schedule, run, and template tables exist, including target working directory, terminal-run history index, recurring run `occurrence_key` idempotency, template archive support, and copy-on-instantiate repository coverage; occurrence override tables are absent. |
| API | Partial | One-time and recurring task lifecycle endpoints, schedule/run/detail, kanban, history, recurring todo, and template CRUD/archive/instantiate endpoints exist; calendar endpoints are absent. |
| Worker | Partial | TaskRunWorkflow, activities, debug printer, Claude Agent SDK executor, recurring materialization, and import-hygiene/replay coverage exist; live executor integration tests are not complete. |
| Web | Partial | Composer, one-time board, task detail, history, recurring todo, template management, template target-directory prefill, executor selection, and target directory capture exist; calendar views are absent. |
| Verification | Partial | Unit/API/web smoke checks exist; generated facts are present; replay coverage exists for `TaskRunWorkflow`; opt-in full-stack one-time smoke exists for local Postgres/Temporal/API/Worker. | Full-stack smoke is not required in default CI yet, live Claude Code smoke is missing, and deeper web E2E coverage is still needed. |

## Recommended Build Order

1. Harden the one-time vertical slice end to end: local stack runbook, full
   Temporal/Postgres/Worker integration test, debug-printer success path, and
   failure visibility.
2. Add calendar read models and occurrence overrides after recurring storage,
   schedule behavior, and recurring todo are stable.
3. Add a live Claude Code smoke test and preflight UX once the local stack
   success path is stable.

## Current Blockers And Risks

- The MVP scope in docs is broader than the implemented product surface; new
  agents should not assume every specified endpoint or view exists.
- Claude Agent SDK execution is implemented, but live authenticated CLI coverage
  is still missing from automated verification.
- Calendar and occurrence override semantics are well documented but not
  implemented in the store/API/worker/web layers.
- Generated schema/API/Temporal snapshots now exist under `docs/generated/`, but
  they are still manually refreshed.
- Full-stack Temporal smoke is opt-in because it requires local Postgres and
  Temporal services; it is not yet a required CI gate.

## Verification Snapshot

Most recent broad verification recorded on 2026-04-26 during M4 work:

- `bun run type-check`
- `bun run lint:check`
- `bun run test:unit:run`
- `bun run test:e2e:smoke` (`4 passed`)
- `python scripts/check_agent_repo.py`
- `uv run ruff check .`
- `uv run pytest` (`45 passed, 1 skipped`)

M0 additions on 2026-04-26:

- `uv run python scripts/generate_agent_facts.py`
- `uv run pytest apps/worker/tests/test_workflow_replay.py`
- Opt-in: `VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL=... uv run pytest tests/integration/test_full_stack_one_time_smoke.py`

M1 additions on 2026-04-26:

- `uv run pytest packages/store/tests/test_repositories.py apps/api/tests/test_tasks_api.py`
- `bun run type-check`
- `bun run test:unit:run`
- `bun run lint:check`

M2 additions on 2026-04-26:

- `uv run python scripts/generate_agent_facts.py`
- `uv run pytest packages/store/tests/test_repositories.py`
- `uv run pytest apps/api/tests/test_tasks_api.py`
- `bun run test:unit:run`
- `bun run type-check`
- `bun run lint:check`

M4 additions on 2026-04-26:

- `uv run python scripts/generate_agent_facts.py`
- `uv run pytest packages/store/tests/test_repositories.py apps/api/tests/test_tasks_api.py`
- `uv run ruff check packages/store/src/vesperaflow_store/repositories.py packages/store/tests/test_repositories.py apps/api/src/vesperaflow_api/routes/views.py apps/api/src/vesperaflow_api/schemas/views.py apps/api/tests/test_tasks_api.py`
- `python scripts/check_agent_repo.py`
- `uv run ruff check .`
- `uv run pytest` (`45 passed, 1 skipped`)
- `bun run test:unit:run`
- `bun run type-check`
- `bun run lint:check`
- `bun run test:e2e:smoke`

Notes:

- `uv run pytest` skipped the opt-in full-stack smoke because
  `VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL` was not set.
- The first web lint run failed before e2e created `apps/web/test-results`;
  rerunning `bun run lint:check` after e2e passed.
