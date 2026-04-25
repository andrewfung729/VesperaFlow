# VesperaFlow API

FastAPI service for product commands and reads. It owns HTTP API boundaries,
request/response schemas, task route behavior, database sessions, and calls
into the Temporal scheduler adapter.

## Ownership

- Routes live in `src/vesperaflow_api/routes/`.
- API payload schemas live in `src/vesperaflow_api/schemas/`.
- Runtime settings live in `src/vesperaflow_api/settings.py`.
- Temporal Schedule integration lives in `src/vesperaflow_api/temporal_scheduler.py`.
- Product-visible persistence is delegated to `packages/store`.
- Shared domain enums and contracts come from `packages/core`.

The API should not invoke executor SDKs directly. Executor work belongs in
Worker Activities.

## Local Run

From this directory:

```bash
uv run uvicorn vesperaflow_api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

The VS Code task `dev: api` runs the same command.

## Settings

Settings are loaded through `pydantic-settings`. Keep local infrastructure
values aligned with `infra/compose.dev.yaml` and `infra/.env.example`.

## Tests

Run API tests from the repository root:

```bash
uv run pytest apps/api/tests
```

Use fakes for Temporal in route/service tests. Full Temporal behavior belongs
in integration tests or Worker-focused tests.
