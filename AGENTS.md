# VesperaFlow Agent Guide

This file is the repo map for coding agents. Keep it short. Follow links for
details instead of expanding this file into a manual.

## What This Is

VesperaFlow is a local-first app for planning AI work now and executing it later
through Temporal-backed one-time and recurring schedules.

## Repo Layout

- `apps/api`: FastAPI application, task routes, scheduler integration.
- `apps/worker`: Temporal Worker, Workflows, Activities, executor adapters.
- `apps/web`: Vue 3 UI, tests, Playwright smoke coverage.
- `packages/core`: dependency-light domain enums, contracts, validation, IDs.
- `packages/store`: SQLAlchemy models, repositories, Alembic migrations.
- `infra`: local Postgres and Temporal development stack.
- `docs`: product, architecture, API, UX, ADRs, quality, and active plans.
- `tests/integration`: cross-package tests that may need local services.

## Start Here

- Product intent: `docs/requirements.md`
- MVP implementation status: `docs/MVP_PROGRESS.md`
- System architecture: `docs/architecture.md`
- Temporal design: `docs/temporal-architecture.md`
- Domain rules: `docs/domain-model.md`
- API contract: `docs/api-spec.md`
- Documentation index: `docs/README.md`
- Test ownership: `tests/README.md`
- Current quality/debt: `docs/QUALITY.md`
- Active implementation plans: `docs/plans/active/`

## Common Commands

Run from the repository root unless noted.

```bash
uv run ruff check .
uv run pytest
python scripts/check_agent_repo.py
```

Web commands run from `apps/web`:

```bash
bun run type-check
bun run lint:check
bun run test:unit:run
bun run test:e2e:smoke
```

Local infrastructure:

```bash
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/compose.dev.yaml up
```

## Architectural Non-Negotiables

- Temporal is the only scheduler. Do not add cron, APScheduler, polling
  schedulers, application sleep loops, or a second delayed-start mechanism.
- PostgreSQL is authoritative for product-visible task, schedule, run, and read
  model state. Temporal owns durable execution history and timers.
- Workflows must stay deterministic: no direct DB access, network calls, SDK
  imports, randomness, or disk I/O inside Workflow code.
- Executor invocation belongs in Activities through executor adapters. The app
  does not call LLM provider APIs directly.
- Shared domain contracts that cross Temporal boundaries belong in
  `packages/core` and must remain safe for Workflow imports.
- User-facing state is derived from backend semantics, not UI-only labels.

## Before Editing

- Read the active plan if one exists in `docs/plans/active/`.
- Check `docs/QUALITY.md` before copying a local pattern; some patterns may be
  known debt rather than intended style.
- Prefer adding or updating a focused doc when a decision explains future code.
- Add tests in the package that owns the behavior.

## When Adding Features

- Update public contracts in `docs/api-spec.md` when API payloads change.
- Update `docs/MVP_PROGRESS.md` when MVP feature status or delivery order
  changes.
- Update `docs/domain-model.md` when task, schedule, run, or status rules
  change.
- Add or update an ADR for durable architectural decisions.
- Update `docs/QUALITY.md` when an area materially improves or regresses.
