# Codebase Quality

_Last updated: 2026-04-27. Update this whenever a major area improves or
degrades._

Scores: A excellent, B solid, C needs work, D problematic, F broken.

## Update Triggers

Update this file when any of these change:

- a new app, package, integration, or major feature lands
- Workflow, Activity, Schedule, task queue, or executor behavior changes
- a domain score materially improves or regresses
- a known gap is fixed, accepted, or becomes more severe
- MVP progress changes in `docs/MVP_PROGRESS.md`
- CI, structural checks, or required test coverage changes
- an active plan is completed with a meaningful quality impact

## Domain Scores

| Domain | Score | Notes |
|---|---|---|
| `packages/core` | B | Small domain layer with tests, including recurrence validation, occurrence-key helpers, occurrence edit enums, executor preflight contracts, and template default validation. Keep Temporal-import safety explicit. |
| `packages/store` | C | Models and repositories are covered, generated schema docs exist, terminal-run history has a focused query/index, recurring run materialization is idempotent by `occurrence_key`, recurring todo/calendar have derived read models, occurrence overrides are scoped by schedule/original occurrence, and template archive/copy semantics are tested. |
| `apps/api` | C | One-time, recurring lifecycle, occurrence edit/cancel, calendar, recurring todo, history, executor preflight, and template endpoints are tested with a fake scheduler, including template target-directory defaults; broader API contract coverage is still thin. |
| `apps/worker` | C | Workflow and executor structure exists; import hygiene, one-time replay, recurring materialization replay, and Claude Code runtime classification tests are covered, but live recurring stack and authenticated Claude Code coverage are not in place yet. |
| `apps/web` | C | Vue surface has composer, board, detail, history, recurring todo, calendar, template, executor preflight, and MVP navigation smoke coverage; UI behavior coverage is still shallow. |
| `infra` | C | Local Temporal/Postgres stack exists; env handling now uses an example file. |
| `docs` | B | Strong architecture and product docs; navigation, active-plan structure, generated facts, and a local full-stack runbook are now present. |

## Known Gaps

- [ ] Generated DB schema, API route map, Temporal surface, and dependency graph
      exist, but refresh is manual.
- [x] Temporal replay tests cover completed, failed, canceled, and
      pre-execution-canceled representative histories.
- [x] Integration tests requiring the full Postgres/Temporal stack are opt-in and
      local-only; they will not become a required CI gate for MVP.
- [ ] Web E2E coverage includes the MVP navigation path, but remains smoke-level.
- [ ] Calendar, history, and recurring todo latest-run/context paths are
      implemented for materialized recurring runs, but live recurring stack
      coverage is still pending.
- [ ] Templates are implemented for direct management and composer prefill; the
      save-as-template shortcut from an existing task is not yet exposed.
- [ ] No automated PR-opening cleanup loop yet; CI only detects the first set of drift patterns.
- [ ] Package README coverage was added recently and should be kept current as ownership changes.
- [ ] `docs/MVP_PROGRESS.md` now tracks MVP delivery state, but it is manually
  maintained and not yet generated from tests or route/schema snapshots.

## Golden Rules To Protect

- Temporal is the sole scheduler for one-time and recurring work.
- Workflows do not access PostgreSQL, network services, executor SDKs, random
  values, or disk I/O directly.
- Product-visible truth is persisted in PostgreSQL and exposed through backend
  read models.
- Executor credentials and full task instructions must not be written into
  Workflow history or default structured logs.

## Recently Fixed

- 2026-04-25: Added root agent entry point, docs index, active-plan structure,
  package READMEs, repo health check, and CI workflow.
- 2026-04-25: Added docs navigation change map and completed plan record for
  the initial agent-first bootstrap.
- 2026-04-25: Added `docs/MVP_PROGRESS.md` to track current implementation
  status against the documented MVP.
- 2026-04-25: Isolated Worker startup and executor factory imports so Workflow
  sandbox import paths do not load the Claude Agent SDK.
- 2026-04-26: Added generated system fact snapshots, a local full-stack
  one-time runbook, `TaskRunWorkflow` replay coverage, and an opt-in
  Postgres/Temporal/API/Worker smoke test for `debug_printer`.
- 2026-04-26: Added the M1 history read model across store/API/web, including
  status and execution-mode filters, selected-run task detail linking, tests,
  and refreshed generated facts.
- 2026-04-26: Added the M3 recurring lifecycle across store/API/Temporal
  Scheduler/Worker, including lazy occurrence run materialization and replay
  coverage.
- 2026-04-26: Added the M2 template lifecycle across core/store/API/web,
  including archive behavior, copy-on-instantiate semantics, composer prefill,
  tests, and refreshed generated facts.
- 2026-04-26: Added the M4 recurring todo read model across store/API/web,
  including active/paused ordering, latest-run context, pause/resume list
  actions, tests, and refreshed generated API facts.
- 2026-04-26: Added allowlisted Claude Agent SDK environment passthrough in the
  Worker while keeping credentials out of Temporal payloads and logs.
- 2026-04-27: Added the M5 calendar and occurrence override slice across
  store/API/web, including scoped occurrence update/cancel commands, calendar
  projection, generated fact refresh, and repository/API/web smoke coverage.
- 2026-04-27: Added the M6 Claude Code preflight slice across core/API/Worker/web,
  including API workspace preflight, Worker runtime classification, composer
  visibility, documented opt-in live smoke, and broader MVP navigation smoke
  coverage.
