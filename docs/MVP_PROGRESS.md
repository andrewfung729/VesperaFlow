# VesperaFlow MVP Progress

_Last updated: 2026-04-25. Update this whenever product scope or implementation
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

The largest MVP gaps are recurring schedules, template management, calendar,
history, and full Claude Code executor invocation. The codebase already has
strong domain docs for these areas, but most of those surfaces are not yet
implemented.

## Feature Progress

| MVP Feature | Status | Current Implementation Evidence | Remaining Gap |
|---|---|---|---|
| Create one-time deferred task | Partial | API route and repository create a task, single-run schedule, planned run, target working directory, and Temporal Schedule; web composer creates one-time tasks. | Need full end-to-end verification with local Temporal/Postgres/Worker and clear success path for the selected production executor. |
| Create recurring scheduled task | Not Started | Core enums and status derivation recognize `recurring`; docs define schedule semantics. API currently rejects recurring create requests as unsupported. | Add recurring models/repositories, API commands, Temporal Schedule creation, pause/resume/update, occurrence materialization, and tests. |
| Review planned and completed work | Partial | Task detail returns task, schedule, latest run, and runs; one-time board groups tasks by status. | Add dedicated history read model, richer completed/failed run review, recurring context, and filters. |
| Separate planning from execution | Partial | One-time task creation stores intent and a planned run before execution; reschedule/cancel are supported before run start. | Extend same lifecycle guarantees to recurring tasks, templates, and calendar edits; add stronger integration coverage. |
| Reuse task templates | Not Started | `template_id` exists on tasks and appears in specs. | Add Template model/table, repository, API endpoints, web template management, instantiate flow, archive behavior, and tests. |
| Calendar view for time-based planning | Not Started | Calendar behavior is specified in product/API/UX docs. | Add calendar read model endpoint, web calendar/agenda view, time-window filtering, overlap handling, and scoped recurring occurrence edit entry point. |
| One-time kanban view | Partial | `/api/v1/views/kanban` and `KanbanBoardView.vue` exist for one-time tasks. | Add stronger filtering/empty/error behavior, hide or filter canceled items per UX rules, and broaden web/API tests. |
| Recurring todo view | Not Started | UX and functional specs define the surface. | Add recurring task read model, pause/resume commands, latest-run context, web view, and tests. |
| History view for run review | Not Started | Runs are persisted and task detail lists runs for one task. | Add cross-task history endpoint, filters by outcome/mode, web history view, and tests. |
| Executor integration | Partial | Worker workflow, activities, executor router, debug printer, and Claude Agent SDK invocation exist; Claude output artifacts and expected SDK failure classifications are covered with mocked Worker tests. | Add live Claude Code smoke coverage, stronger preflight UX, and full-stack execution verification. |
| Temporal production hardening | Partial | One-time Temporal Schedule client and Worker workflow exist; repo check enforces Temporal as sole scheduler. | Add replay tests, full-stack integration tests, recurring schedule behavior, idempotency coverage, and rollout/versioning discipline. |

## Layer Readiness

| Layer | Status | Notes |
|---|---|---|
| Domain docs | Done | Requirements, functional spec, domain model, API spec, UX spec, architecture, Temporal architecture, and ADRs exist. |
| Core domain package | Partial | Shared enums, contracts, IDs, validation, and status derivation exist; recurring/template/calendar behavior needs more domain helpers as features land. |
| Store | Partial | Task, schedule, and run tables exist for the vertical slice, including target working directory; template and occurrence override tables are absent from the implementation. |
| API | Partial | One-time task, schedule, run, detail, and kanban endpoints exist; recurring, templates, calendar, recurring todo, and history endpoints are absent. |
| Worker | Partial | TaskRunWorkflow, activities, debug printer, Claude Agent SDK executor, and import-hygiene regression coverage exist for single-run execution; recurring schedule behavior, replay tests, and live executor integration tests are not complete. |
| Web | Partial | Composer, one-time board, task detail, executor selection, and target directory capture exist; templates, calendar, recurring todo, and history views are absent. |
| Verification | Partial | Unit/API/web smoke checks exist; full local stack, replay, and deeper E2E coverage are missing. |

## Recommended Build Order

1. Harden the one-time vertical slice end to end: local stack runbook, full
   Temporal/Postgres/Worker integration test, debug-printer success path, and
   failure visibility.
2. Add history read model next, because existing runs already provide the data
   and it improves trust before adding more scheduling complexity.
3. Add templates, because they are mostly CRUD plus task instantiation and do
   not require recurring schedule semantics.
4. Add recurring task lifecycle: create, pause, resume, update, and recurring
   Temporal Schedule creation.
5. Add recurring todo and calendar read models after recurring storage and
   schedule behavior are stable.
6. Add a live Claude Code smoke test and preflight UX once the local stack
   success path is stable.

## Current Blockers And Risks

- The MVP scope in docs is broader than the implemented product surface; new
  agents should not assume every specified endpoint or view exists.
- Claude Agent SDK execution is implemented, but live authenticated CLI coverage
  is still missing from automated verification.
- Recurring schedule semantics are well documented but not implemented in the
  store/API/worker/web layers.
- Without generated schema/API snapshots under `docs/generated/`, agents still
  need to inspect code to confirm current implementation facts.
- Without a full-stack Temporal test, one-time execution reliability is not yet
  proven mechanically.

## Verification Snapshot

Most recent broad verification recorded during agent-first bootstrap:

- `python scripts/check_agent_repo.py`
- `uv run ruff check .`
- `uv run pytest`
- `bun run type-check`
- `bun run lint:check`
- `bun run test:unit:run`
- `bun run test:e2e:smoke`

After docs-only progress updates, rerun at minimum:

- `python scripts/check_agent_repo.py`
- `git diff --check`
