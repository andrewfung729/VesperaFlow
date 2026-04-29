# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Authoritative Agent Doc

`AGENTS.md` is the canonical repo map. `docs/README.md` has the full documentation index,
including a "Change Map" table for when changing X requires updating Y.

Before resuming unfinished work, read `docs/plans/active/`. Before copying a local pattern,
read `docs/QUALITY.md` — some patterns are known debt, not intended style.

## Workspace Shape

Python uv workspace (Python ≥ 3.13) with four packages:

- `apps/api` — FastAPI
- `apps/worker` — Temporal Worker
- `packages/core` — domain contracts
- `packages/store` — SQLAlchemy + Alembic

Vue 3 web app at `apps/web` is managed by Bun, not uv.

## Common Commands

Run from repo root unless noted.

```bash
# Python
uv sync
uv run ruff check .
uv run pytest

# Per-package tests
uv run pytest packages/core/tests
uv run pytest packages/store/tests
uv run pytest apps/api/tests
uv run pytest apps/worker/tests
uv run pytest tests/integration

# Agent-repo health check (also runs in CI)
python scripts/check_agent_repo.py

# DB migrations
uv run --directory packages/store alembic upgrade head
uv run --directory packages/store alembic revision --autogenerate -m "msg"

# Web (run from apps/web)
bun install
bun run dev
bun run type-check
bun run lint:check
bun run test:unit:run
bun run test:e2e:smoke

# Local infra
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/compose.dev.yaml up
```

VS Code task `dev: all` runs api, worker, and web in parallel (see `.vscode/tasks.json`).

## Architectural Non-Negotiables

These are the rules Claude Code is most likely to violate by writing plausible-looking code.

**Temporal is the only scheduler.** No cron, APScheduler, Celery beat, or
`asyncio.sleep`-based delay loops. Enforced by `FORBIDDEN_SCHEDULER_PATTERNS` in
`scripts/check_agent_repo.py`.

**PostgreSQL owns product-visible state.** Task, schedule, run, and read model state
lives in Postgres. Temporal owns durable execution history and timers only.

**Workflow code must be deterministic.** No DB access, network calls, executor SDK
imports, randomness, wall-clock APIs, or disk I/O inside
`apps/worker/src/vesperaflow_worker/workflows/`. Side effects belong in Activities.

**Executor SDK calls belong in Worker Activities.** Claude Agent SDK and other executor
SDK calls live in `apps/worker/src/vesperaflow_worker/executors/`. The API layer never
invokes executor SDKs directly.

**Cross-boundary contracts belong in `packages/core`.** Anything that crosses a
Workflow/Activity boundary must be dependency-light and Temporal-sandbox safe.

**UI states derive from backend semantics.** No UI-only labels; see ADR 005.

## Where to Look for What

| Topic | File |
|---|---|
| Domain rules | `docs/domain-model.md` |
| Temporal design | `docs/temporal-architecture.md` |
| API contract | `docs/api-spec.md` |
| ADRs | `docs/adr/` |
| MVP status | `docs/MVP_PROGRESS.md` |
| Test ownership | `tests/README.md` |
| Change map | `docs/README.md` |
