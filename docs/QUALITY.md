# Codebase Quality

_Last updated: 2026-05-21. Update this whenever a major area improves or
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
| `packages/core` | B | Small domain layer with tests, including recurrence validation, occurrence-key helpers, occurrence edit enums, Codex/OpenCode/Claude/Pi/debug executor contracts, executor preflight contracts, shared API request DTOs, and template default validation. Keep Temporal-import safety explicit. |
| `packages/store` | C | Models and repositories are covered, generated schema docs exist, terminal-run history has a focused query/index, runs snapshot their effective instruction source, recurring run materialization is idempotent by `occurrence_key`, recurring todo/calendar have derived read models, occurrence overrides are scoped by schedule/original occurrence, and template archive/copy semantics are tested. |
| `apps/api` | C | One-time, recurring lifecycle, occurrence edit/cancel, calendar, recurring todo, history, run detail/reader snapshot, executor preflight, and template endpoints are tested with a fake scheduler, including template target-directory defaults; broader API contract coverage is still thin. |
| `apps/cli` | C | Agent-facing API-only CLI covers task creation, task/run reads, run-now, executor preflight, and profile listing with JSON output and mocked HTTP tests. Destructive/versioned commands are intentionally deferred. |
| `apps/worker` | C | Workflow and executor structure exists; import hygiene, one-time replay, recurring materialization replay, structured Worker logging, persisted run event timelines, Claude Code executor tests, Codex CLI JSONL executor tests, OpenCode CLI JSON event executor tests, and Pi CLI JSON executor tests are covered. Authenticated live executor and recurring smokes are opt-in local verification paths; they are not in automated CI coverage. |
| `apps/web` | C | Vue surface has composer, board, detail, history, recurring todo, calendar, template, executor preflight, and MVP navigation smoke coverage; common alert, form, recurrence, status badge, and recurring action patterns are shared; `apps/web/README.md` now captures local conventions. UI behavior coverage is still shallow. |
| `infra` | C | Local Temporal/Postgres stack exists; env handling now uses an example file. |
| `docs` | B | Strong architecture and product docs; navigation, active-plan structure, generated facts, CLI executor ADRs through ADR 007, executor/profile rules, frontend guide, and local full-stack runbooks are now present. |

## Known Gaps

- [x] Generated DB schema, API route map, Temporal surface, and dependency graph
      exist; repo health checks validate their headers and CI regenerates them
      before checking `docs/generated` for drift.
- [x] Worker startup, Activity execution, and run lifecycle now emit structured
      logs or persisted run timeline events with correlation identifiers.
- [x] Temporal replay tests cover completed, failed, canceled, and
      pre-execution-canceled representative histories.
- [x] Integration tests requiring the full Postgres/Temporal stack are opt-in and
      local-only; they will not become a required CI gate for MVP.
- [ ] Web E2E coverage includes the MVP navigation path, but remains smoke-level.
- [ ] Authenticated Claude Code, Codex, OpenCode, and Pi live smokes are opt-in local
      verification paths and are not automated CI gates.
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
- Shared API request DTOs may live in `packages/core`; API response models
  stay in `apps/api` unless they are pure and mapper-free.

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
- 2026-04-26: Added executor profile environment passthrough in the Worker
  while keeping credentials out of Temporal payloads and logs.
- 2026-04-27: Added the M5 calendar and occurrence override slice across
  store/API/web, including scoped occurrence update/cancel commands, calendar
  projection, generated fact refresh, and repository/API/web smoke coverage.
- 2026-04-27: Added the M6 Claude Code preflight slice across core/API/Worker/web,
  including API workspace preflight, Worker runtime classification, composer
  visibility, documented opt-in live smoke, and broader MVP navigation smoke
  coverage.
- 2026-04-27: Introduced basedpyright for static type checking across all Python
  packages, fixed existing type errors in API exception handlers and store
  repository filters, and added it to CI and common commands.
- 2026-04-28: Aligned the then-supported text CLI executor documentation,
  runbook, and executor status notes across architecture, API, Temporal, MVP
  progress, and quality docs.
- 2026-04-29: Added Codex CLI `codex exec` as a first-class executor behind
  the Worker adapter boundary, including API preflight, web selectors, mocked
  Worker/API/web coverage, and refreshed executor documentation.
- 2026-04-29: Consolidated repeated apps/web alert, form, recurrence editor,
  execution/status badge, recurring action, and page state patterns into shared
  components, helpers, and composables.
- 2026-04-30: Updated Codex Worker execution to use full-permission bypass mode;
  Codex model selection now belongs to executor profiles.
- 2026-05-02: Added OpenCode CLI `opencode run --format json` as a
  first-class profile-driven executor, including API preflight, Worker
  artifacts/classification, Web profile model choices, tests, and ADR 007.
- 2026-04-30: Added Worker JSON logs and persisted run event timelines across
  store/API/Worker/web, including Activity correlation metadata and UI timeline
  surfaces.
- 2026-05-02: Removed install-level executor fallbacks from API and Worker
  runtime settings; new tasks now require a request or template
  executor/profile, and the Worker always routes by task snapshot.
- 2026-05-02: Added focused web and executor-profile docs, wired them into
  agent navigation, refreshed generated facts, added deterministic generated
  schema defaults, and made CI fail when regenerated agent facts differ.
- 2026-05-10: Added the `vespera` API-only CLI workspace for agent task
  creation, task/run inspection, run-now, executor preflight, and profile
  listing.
- 2026-05-12: Split run detail and reader web surfaces, routed all history
  items through run detail, and persisted run instruction snapshots across
  one-time, recurring materialized, and recurring run-now paths.
- 2026-05-19: Added Pi CLI JSON mode as a first-class profile-driven executor,
  including core/store/API/Worker/web/CLI coverage, artifacts/classification,
  profile model/env passthrough, ADR 006, and synchronized executor docs.
- 2026-05-21: Changed Pi default event artifacts from full streaming stdout
  capture to filtered non-streaming audit events, with capped raw JSONL capture
  available only through explicit opt-in.
- 2026-05-25: Removed unsupported executor integration from public contracts,
  Worker routing, web selection, executor defaults, and current documentation.
- 2026-05-30: Added executor profile reasoning defaults with save-time Worker
  validation, transient secret handoff storage, adapter propagation, CLI/Web
  surfaces, and stable run event metadata.
