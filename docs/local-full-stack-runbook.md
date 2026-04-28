# Local Full-Stack One-Time Runbook

Use this runbook to verify the current one-time vertical slice with local
Postgres, Temporal, API, Worker, and web services.

## Prerequisites

- Docker is available for the local infrastructure stack.
- Python dependencies are installed through `uv`.
- Web dependencies are installed through `bun` in `apps/web`.

## Start Infrastructure

From the repository root:

```bash
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/compose.dev.yaml up
```

Leave the compose stack running. It provides Postgres and Temporal using the
default settings in `apps/api` and `apps/worker`.

## Apply Database Schema

Apply migrations from the store package:

```bash
cd packages/store
uv run alembic upgrade head
cd ../..
```

## Start API And Worker

In one terminal:

```bash
VESPERAFLOW_DEFAULT_EXECUTOR=debug_printer uv run vesperaflow-api
```

In another terminal:

```bash
VESPERAFLOW_EXECUTOR_ADAPTER=debug_printer uv run vesperaflow-worker
```

## Start Web

From `apps/web`:

```bash
bun run dev
```

Open the dev server URL shown by Vite, create a one-time task scheduled a minute
or two in the future, and select the `debug_printer` executor.

## Expected Result

- API creates a task, schedule, and planned run row.
- Temporal starts `TaskRunWorkflow` at the scheduled time.
- Worker executes the `debug_printer` adapter.
- Task detail eventually shows a completed run with a debug-printer summary.
- The kanban board moves the task from upcoming/running to completed.

## Automated Smoke Path

The opt-in integration smoke test runs the API app and Worker in-process against
a real local Temporal server and Postgres database:

```bash
VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL=postgresql+asyncpg://vespera:password@localhost:15432/vespera \
  uv run pytest tests/integration/test_full_stack_one_time_smoke.py
```

Without `VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL`, the test is skipped during
normal `uv run pytest` runs.

## Claude Code Live Smoke

Claude Code live smoke is opt-in because it uses the developer machine's local
Claude Code installation, authentication state, and selected workspace.
VesperaFlow does not store or print executor credentials.

Start the API and Worker with the Claude executor, then create a one-time task
in the web UI using an existing absolute target directory and the `claude_code`
executor:

```bash
uv run vesperaflow-api
uv run vesperaflow-worker
```

Use a harmless instruction such as asking Claude Code to inspect the repository
and write a short summary into the run output only. Verify task detail reaches a
terminal completed or classified failed state, and inspect the run artifact path
only if you need the raw Claude output.

## Kimi Code Live Smoke

Kimi Code live smoke is opt-in because it uses the developer machine's local
`kimi` CLI installation, authentication state, and selected workspace.
VesperaFlow does not store or print executor credentials.

Prerequisites:

- `kimi` is installed and available on `PATH`.
- Kimi Code is authenticated through `KIMI_API_KEY`, a cached OAuth token, or the
  CLI's supported configuration.
- The target working directory is an existing absolute path.

Start the API and Worker with the Kimi executor, then create a one-time task in
the web UI using the `kimi_code` executor:

```bash
VESPERAFLOW_DEFAULT_EXECUTOR=kimi_code uv run vesperaflow-api
VESPERAFLOW_EXECUTOR_ADAPTER=kimi_code uv run vesperaflow-worker
```

Use a harmless instruction such as asking Kimi Code to inspect the repository and
write a short summary into the run output only. Verify the executor preflight
passes for the selected target directory, then verify task detail reaches a
terminal completed or classified failed state.

Expected successful execution artifacts under the run artifact directory:

- `kimi-output.txt` contains the final text output captured from stdout.
- `kimi-result.json` contains captured stdout and stderr diagnostic fields.

Expected classified failures include `executor_workspace_unavailable`,
`executor_not_available`, `executor_not_authenticated`, and `executor_error`.
