# VesperaFlow Worker

Temporal Worker process for durable task execution. It registers Workflows and
Activities, connects to Temporal, and routes each run to the executor adapter
recorded on the task snapshot.

## Ownership

- Worker startup lives in `src/vesperaflow_worker/main.py`.
- Workflows live in `src/vesperaflow_worker/workflows/`.
- Activities live in `src/vesperaflow_worker/activities/`.
- Executor adapters live in `src/vesperaflow_worker/executors/`.
- Worker settings live in `src/vesperaflow_worker/settings.py`.
- `claude_code` invokes the Python Claude Agent SDK from an Activity, using the
  task's target working directory as SDK `cwd`.
- `codex` invokes Codex CLI through non-interactive `codex exec --json` from an
  Activity, using the task's target working directory as CLI `cwd`.
- `opencode` invokes OpenCode CLI through non-interactive
  `opencode run --format json` from an Activity, using the task's target
  working directory as CLI `--dir`.

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

## Executor Runtime

The Worker always routes by the executor recorded on each task snapshot. It also
adds Claude Code subprocess defaults for disabling telemetry,
error reporting, feedback prompts, autoupdates, nonessential traffic, and
flicker, and for enabling the LSP tool and experimental agent teams. Executor
profile env and secret env values are loaded from PostgreSQL inside the
Activity immediately before invocation. These values are never written to
Temporal payloads or logs.

Claude Code runs with `permission_mode="bypassPermissions"` and loads
`user`, `project`, and `local` setting sources. It writes full executor output
under the run artifact directory while storing only a short normalized summary
on the run.

Codex runs via the `codex` CLI in non-interactive exec mode with `--json`,
`--output-last-message`, `--skip-git-repo-check`, `-C <target>`, optional
profile `default_model` as `--model`, full-permission bypass, and stdin prompt
input. It requires the `codex` binary to be on `PATH` and
authenticated/configured through Codex CLI itself. It writes
`codex-last-message.txt`, `codex-events.jsonl`, and `codex-stderr.txt` under
the run artifact directory.

OpenCode runs via the `opencode` CLI in non-interactive run mode with
`--format json`, `--dir <target>`, `--dangerously-skip-permissions`,
`--title <run_id>`, optional profile `default_model` as `--model`, and stdin
prompt input. It requires the `opencode` binary to be on `PATH` and
authenticated/configured through OpenCode itself. It writes
`opencode-events.jsonl`, `opencode-stderr.txt`, and `opencode-result.txt`
under the run artifact directory.

## Tests

Run Worker tests from the repository root:

```bash
uv run pytest apps/worker/tests
```

Add replay tests before making non-trivial Workflow control-flow changes.
