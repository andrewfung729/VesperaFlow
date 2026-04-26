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

VesperaFlow is currently a one-time task vertical slice, not a complete MVP.
The repo supports creating, rescheduling, canceling, listing, viewing, and
executing one-time tasks through the API/store/Temporal Worker shape, with a
Vue composer, one-time board, and task detail view.

The largest MVP gaps are recurring schedules, recurring
todo, calendar, and full Claude Code executor invocation. The codebase already has
strong domain docs for these areas, but most of those surfaces are not yet
implemented.

## Feature Progress

| MVP Feature | Status | Current Implementation Evidence | Remaining Gap |
|---|---|---|---|
| Create one-time deferred task | Partial | API route and repository create a task, single-run schedule, planned run, target working directory, and Temporal Schedule; web composer creates one-time tasks; an opt-in full-stack `debug_printer` smoke test covers local Postgres, Temporal, API, Worker, and persisted run state. | Need clear success path for the selected production executor and required CI/service-container strategy for full-stack smoke. |
| Create recurring scheduled task | Not Started | Core enums and status derivation recognize `recurring`; docs define schedule semantics. API currently rejects recurring create requests as unsupported. | Add recurring models/repositories, API commands, Temporal Schedule creation, pause/resume/update, occurrence materialization, and tests. |
| Review planned and completed work | Partial | Task detail returns task, schedule, latest run, and runs; one-time board groups tasks by status; `/api/v1/views/history` and the web History route show completed/failed runs across tasks with status and execution-mode filters. | Extend history with recurring context after recurring runs land, and continue broadening web behavior coverage. |
| Separate planning from execution | Partial | One-time task creation stores intent and a planned run before execution; reschedule/cancel are supported before run start. | Extend same lifecycle guarantees to recurring tasks, templates, and calendar edits; add stronger integration coverage. |
| Reuse task templates | Done | Template model/table, repository methods, `/api/v1/templates` CRUD/archive/instantiate endpoints, web template management, optional default target directory, and composer prefill flow exist. Creating from a template copies fields onto an independent task while preserving `template_id`; archived templates leave linked tasks readable. | Save-as-template from an existing task is not yet exposed as a shortcut, but direct template management covers the MVP template lifecycle. |
| Calendar view for time-based planning | Not Started | Calendar behavior is specified in product/API/UX docs. | Add calendar read model endpoint, web calendar/agenda view, time-window filtering, overlap handling, and scoped recurring occurrence edit entry point. |
| One-time kanban view | Partial | `/api/v1/views/kanban` and `KanbanBoardView.vue` exist for one-time tasks. | Add stronger filtering/empty/error behavior, hide or filter canceled items per UX rules, and broaden web/API tests. |
| Recurring todo view | Not Started | UX and functional specs define the surface. | Add recurring task read model, pause/resume commands, latest-run context, web view, and tests. |
| History view for run review | Done | Store history query, `/api/v1/views/history`, and `HistoryView.vue` list completed/failed runs in reverse finished order, filter by outcome and execution mode, and link items back to task detail with selected run context. Repository, API, web unit, and Playwright smoke coverage exist. | Recurring runs will appear through the same read model once M3 materializes them. |
| Executor integration | Partial | Worker workflow, activities, executor router, debug printer, and Claude Agent SDK invocation exist; Claude output artifacts and expected SDK failure classifications are covered with mocked Worker tests. | Add live Claude Code smoke coverage, stronger preflight UX, and full-stack execution verification. |
| Temporal production hardening | Partial | One-time Temporal Schedule client and Worker workflow exist; repo check enforces Temporal as sole scheduler; `TaskRunWorkflow` has replay coverage for the completed debug-printer path. | Add recurring schedule behavior, idempotency coverage, more representative replay histories, and rollout/versioning discipline. |

## Layer Readiness

| Layer | Status | Notes |
|---|---|---|
| Domain docs | Done | Requirements, functional spec, domain model, API spec, UX spec, architecture, Temporal architecture, and ADRs exist. |
| Core domain package | Partial | Shared enums, contracts, IDs, validation, status derivation, and template default validation exist; recurring/calendar behavior needs more domain helpers as features land. |
| Store | Partial | Task, schedule, run, and template tables exist, including target working directory, terminal-run history index, template archive support, and copy-on-instantiate repository coverage; occurrence override tables are absent. |
| API | Partial | One-time task, schedule, run, detail, kanban, history, and template CRUD/archive/instantiate endpoints exist; recurring, calendar, and recurring todo endpoints are absent. |
| Worker | Partial | TaskRunWorkflow, activities, debug printer, Claude Agent SDK executor, and import-hygiene regression coverage exist for single-run execution; recurring schedule behavior, replay tests, and live executor integration tests are not complete. |
| Web | Partial | Composer, one-time board, task detail, history, template management, template target-directory prefill, executor selection, and target directory capture exist; calendar and recurring todo views are absent. |
| Verification | Partial | Unit/API/web smoke checks exist; generated facts are present; replay coverage exists for `TaskRunWorkflow`; opt-in full-stack one-time smoke exists for local Postgres/Temporal/API/Worker. | Full-stack smoke is not required in default CI yet, live Claude Code smoke is missing, and deeper web E2E coverage is still needed. |

## Recommended Build Order

1. Harden the one-time vertical slice end to end: local stack runbook, full
   Temporal/Postgres/Worker integration test, debug-printer success path, and
   failure visibility.
2. Add recurring task lifecycle: create, pause, resume, update, and recurring
   Temporal Schedule creation.
3. Add recurring todo and calendar read models after recurring storage and
   schedule behavior are stable.
4. Add a live Claude Code smoke test and preflight UX once the local stack
   success path is stable.

## Current Blockers And Risks

- The MVP scope in docs is broader than the implemented product surface; new
  agents should not assume every specified endpoint or view exists.
- Claude Agent SDK execution is implemented, but live authenticated CLI coverage
  is still missing from automated verification.
- Recurring schedule semantics are well documented but not implemented in the
  store/API/worker/web layers.
- Generated schema/API/Temporal snapshots now exist under `docs/generated/`, but
  they are still manually refreshed.
- Full-stack Temporal smoke is opt-in because it requires local Postgres and
  Temporal services; it is not yet a required CI gate.

## Verification Snapshot

Most recent broad verification recorded on 2026-04-26 during M2 work:

- `python scripts/check_agent_repo.py`
- `uv run ruff check .`
- `uv run pytest` (`38 passed, 1 skipped`)
- `bun run type-check`
- `bun run lint:check`
- `bun run test:unit:run`
- `bun run test:e2e:smoke` (`3 passed`)

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

Notes:

- `uv run pytest` skipped the opt-in full-stack smoke because
  `VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL` was not set.
- The first web lint run failed before e2e created `apps/web/test-results`;
  rerunning `bun run lint:check` after e2e passed.
