# Codebase Quality

_Last updated: 2026-04-25. Update this whenever a major area improves or
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
| `packages/core` | B | Small, dependency-light domain layer with tests. Keep Temporal-import safety explicit. |
| `packages/store` | C | Models and repositories are covered, but generated schema docs are missing. |
| `apps/api` | C | Vertical slice is tested with a fake scheduler; broader API contract coverage is still thin. |
| `apps/worker` | C | Workflow and executor structure exists; replay and Temporal environment tests are not in place yet. |
| `apps/web` | C | Vue surface has unit and Playwright scaffolding; UI behavior coverage is still shallow. |
| `infra` | C | Local Temporal/Postgres stack exists; env handling now uses an example file. |
| `docs` | B | Strong architecture and product docs; navigation and active-plan structure are now present. |

## Known Gaps

- [ ] No generated DB schema, API route map, or dependency graph under `docs/generated/`.
- [ ] Temporal replay tests are not yet implemented for Workflow evolution.
- [ ] Integration tests requiring the full Postgres/Temporal stack are only scaffolded.
- [ ] Web E2E coverage is still smoke-level.
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
