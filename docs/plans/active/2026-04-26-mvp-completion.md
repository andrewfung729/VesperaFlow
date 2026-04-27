# Plan: MVP Completion — M6 Release Hardening

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

M0 through M5 are complete and archived in
`docs/plans/completed/2026-04-26-mvp-m0-m5.md`.

M6 is nearly complete. The remaining work before closing this active plan:

- active plan closure and final doc refresh

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
- Full-stack smoke stays opt-in and local-only; it will not become a required
  CI gate for MVP.

## Milestones

### M6: Claude Code Preflight And MVP Release Hardening

Purpose: finish executor confidence and release-readiness checks after the
product surfaces are connected.

Progress on 2026-04-27:

- Added shared executor preflight contracts and an API
  `/api/v1/executors/preflight` endpoint for lightweight Claude Code
  workspace checks.
- Kept Claude Agent SDK import as a normal Worker dependency and mapped runtime
  unauthenticated, misconfigured, workspace unavailable, and executor
  unavailable outcomes through task execution.
- Added composer visibility and submit-time gating for Claude Code preflight.
- Documented the opt-in live Claude Code smoke path in the local full-stack
  runbook.
- Expanded Playwright smoke coverage to navigate composer, kanban, task detail,
  history, templates, recurring todo, and calendar with mocked API data.
- Manually verified authenticated live Claude Code smoke on the local stack.
- Full-stack smoke (one-time and recurring) manually verified on the local
  stack; stays opt-in and local-only, not a required CI gate.
- Failed and canceled replay histories are now covered.
- Improved one-time kanban web behavior: added `include_canceled` query
  parameter (default `false`), "Show canceled" toggle, loading spinner, and
  global empty state. Updated web and API tests.
- Ran broad verification; all checks pass locally.
- Remaining M6 work: close or split this active plan.

Scope:

- Add an explicit Claude Code workspace preflight path and keep authentication
  or runtime configuration failures on the normal execution path.
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
- Improve one-time kanban behavior where MVP specs already call out gaps:
  canceled visibility, empty states, error handling, and filters.

Exit criteria:

- MVP surfaces are implemented and tested at the owning layers
- executor setup failures are visible and classified
- broad verification passes locally and in CI
- docs accurately describe what shipped

## Next Actions

1. Close this active plan and move it to `docs/plans/completed/`.

## Blockers

- Full-stack tests require local Postgres and Temporal services and remain
  opt-in for local development only; they will not run as required CI checks.
- Live Claude Code smoke coverage depends on a developer machine with the SDK
  installed, authenticated, and allowed to operate in the target workspace.

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
