# VesperaFlow

VesperaFlow is a local-first planning app for AI work. It lets a user define
one-time or recurring work now, schedule execution for later, and review what
ran through product-visible task, schedule, and run state.

The MVP is built around:

- FastAPI for the product API
- Temporal for durable scheduling and execution
- PostgreSQL for product-visible state
- Vue 3 for the local UI
- External coding-agent runtimes invoked through Worker Activities

## Repository Map

- `apps/api`: FastAPI app and task command/read endpoints.
- `apps/worker`: Temporal Worker, Workflows, Activities, executor adapters.
- `apps/web`: Vue UI, unit tests, and Playwright smoke tests.
- `packages/core`: shared domain enums, contracts, validation, and ID helpers.
- `packages/store`: SQLAlchemy persistence and Alembic migrations.
- `infra`: local Postgres and Temporal stack.
- `docs`: requirements, architecture, ADRs, quality, and implementation plans.

For agent-specific navigation, see `AGENTS.md`. For documentation navigation,
see `docs/README.md`.

## Local Setup

Install Python dependencies through the workspace:

```bash
uv sync
cp .env.example .env
```

Install web dependencies:

```bash
cd apps/web
bun install
```

Start local infrastructure:

```bash
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/compose.dev.yaml up
```

Run API, Worker, and Web together through the VS Code task `dev: all`, or run
the component commands from `.vscode/tasks.json`.

## Checks

Python:

```bash
uv run ruff check .
uv run pytest
```

Web:

```bash
cd apps/web
bun run type-check
bun run lint:check
bun run test:unit:run
bun run test:e2e:smoke
```

Agent-first repo health:

```bash
python scripts/check_agent_repo.py
```
