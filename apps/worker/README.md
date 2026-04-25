# VesperaFlow Worker

Temporal Worker process for durable task execution. It registers Workflows and
Activities, connects to Temporal, and invokes configured executor adapters from
Activities.

## Ownership

- Worker startup lives in `src/vesperaflow_worker/__init__.py`.
- Workflows live in `src/vesperaflow_worker/workflows/`.
- Activities live in `src/vesperaflow_worker/activities/`.
- Executor adapters live in `src/vesperaflow_worker/executors/`.
- Worker settings live in `src/vesperaflow_worker/settings.py`.

## Temporal Rules

- Workflows coordinate durable execution only.
- Workflows must not access PostgreSQL, disk, network, executor SDKs, random
  values, or wall-clock APIs directly.
- Side effects belong in Activities.
- Payload models that cross Temporal boundaries belong in `packages/core`.
- Keep Workflow, Activity, task queue, Schedule ID, and Workflow ID names stable
  unless a versioning plan exists.

## Local Run

From this directory:

```bash
uv run vesperaflow-worker
```

The VS Code task `dev: worker` runs the same command.

## Tests

Run Worker tests from the repository root:

```bash
uv run pytest apps/worker/tests
```

Add replay tests before making non-trivial Workflow control-flow changes.
