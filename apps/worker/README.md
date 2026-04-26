# VesperaFlow Worker

Temporal Worker process for durable task execution. It registers Workflows and
Activities, connects to Temporal, and invokes configured executor adapters from
Activities.

## Ownership

- Worker startup lives in `src/vesperaflow_worker/main.py`.
- Workflows live in `src/vesperaflow_worker/workflows/`.
- Activities live in `src/vesperaflow_worker/activities/`.
- Executor adapters live in `src/vesperaflow_worker/executors/`.
- Worker settings live in `src/vesperaflow_worker/settings.py`.
- `claude_code` invokes the Python Claude Agent SDK from an Activity, using the
  task's target working directory as SDK `cwd`.

## Temporal Rules

- Workflows coordinate durable execution only.
- Workflows must not access PostgreSQL, disk, network, executor SDKs, random
  values, or wall-clock APIs directly.
- Side effects belong in Activities.
- Payload models that cross Temporal boundaries belong in `packages/core`.
- Keep Workflow, Activity, task queue, Schedule ID, and Workflow ID names stable
  unless a versioning plan exists.
- Keep `vesperaflow_worker/__init__.py`, Workflow modules, and executor package
  facades import-safe for the Temporal sandbox. Concrete executor modules may
  import SDKs at module top level, but those modules must only be imported by
  Worker startup or Activity-only paths.

## Local Run

From this directory:

```bash
uv run vesperaflow-worker
```

The VS Code task `dev: worker` runs the same command.

## Executor Settings

Environment variables use the `VESPERAFLOW_` prefix:

- `VESPERAFLOW_EXECUTOR_ADAPTER`: `auto`, `router`, `debug_printer`, or
  `claude_code`.
- `VESPERAFLOW_CLAUDE_MAX_TURNS`: max Claude Agent SDK turns per run.
- `VESPERAFLOW_CLAUDE_ENV`: optional JSON object of explicit SDK env values.
- `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, and `ANTHROPIC_MODEL`: optional
  Claude SDK env values loaded from the process environment or root `.env`.

The Worker also adds Claude Code subprocess defaults for disabling telemetry,
error reporting, feedback prompts, autoupdates, nonessential traffic, and
flicker, and for enabling the LSP tool and experimental agent teams. Override
those flags, or the `ANTHROPIC_*` values, with `VESPERAFLOW_CLAUDE_ENV` if
needed. These values are never written to Temporal payloads or logs.

Claude Code runs with `permission_mode="bypassPermissions"` and loads
`user`, `project`, and `local` setting sources. It writes full executor output
under the run artifact directory while storing only a short normalized summary
on the run.

## Tests

Run Worker tests from the repository root:

```bash
uv run pytest apps/worker/tests
```

Add replay tests before making non-trivial Workflow control-flow changes.
