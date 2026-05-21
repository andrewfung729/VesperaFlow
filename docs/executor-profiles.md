# Executor Profiles

Executor profiles are the selection and default surface for task execution.
They bind an executor kind to optional model and environment defaults while
keeping Temporal payloads small and free of credentials.

## Supported Executors

- `debug_printer`: deterministic local adapter for development and smoke tests.
- `claude_code`: Claude Agent SDK adapter invoked from a Worker Activity.
- `codex`: Codex CLI adapter invoked as `codex exec` from a Worker Activity.
- `opencode`: OpenCode CLI adapter invoked as `opencode run --format json`
  from a Worker Activity.
- `kimi_code`: Kimi Code CLI adapter invoked from a Worker Activity.
- `pi`: Pi CLI adapter invoked as `pi --mode json` from a Worker Activity.

## Selection Rules

- New task and template flows should choose an `executor_profile_id`.
- If a request sends only the legacy `executor` field, the API resolves that
  executor's default profile and stores both `Task.executor` and
  `Task.executor_profile_id`.
- A template may provide `default_executor_profile_id`; creating a task from
  that template copies the profile unless the request overrides it.
- There is no install-level executor fallback. Creating an executable task
  without a request executor/profile or template executor/profile is invalid.
- Archived or disabled profiles cannot be used for new tasks, template
  instantiation, preflight, or Worker execution.
- If both `executor` and `executor_profile_id` are provided, they must refer to
  the same executor kind.

## Runtime Resolution

- The API resolves the profile at task/template creation time and persists the
  resolved executor kind on the task snapshot.
- The Worker always routes by `execution_snapshot.executor`. It does not look
  at Worker environment defaults to choose an executor.
- Workflow payloads carry only the resolved executor name and optional profile
  id. Workflows never load profiles or secrets.
- `execute_agent_run` loads the profile from PostgreSQL immediately before
  invoking the adapter.
- Profile `env` and `secret_env` are merged only inside the Activity runtime
  config. Secret values are write-only in API responses and must not be logged,
  stored in run events, or serialized into Temporal history.
- `default_model` is executor-specific. It is passed to Codex as
  `codex exec --model`, to Claude Code as `ANTHROPIC_MODEL`, to OpenCode as
  `opencode run --model`, and to Pi as `pi --model`. Kimi Code and Debug
  Printer ignore it until they support an explicit model override.

## Preflight Rules

- `GET /api/v1/executors/preflight` accepts `executor_profile_id`,
  `executor`, and `target_working_directory`.
- If `executor_profile_id` is present, the profile determines the executor kind.
- Preflight verifies profile usability and target workspace access.
- Claude Code, Codex, OpenCode, Kimi Code, and Pi preflight check workspace
  access but not live SDK/CLI authentication, provider configuration, or model
  availability.
- Live authentication/configuration/model failures are classified during Worker
  execution, not in the API preflight path.

## Artifacts And Output

- The target working directory is the user project being changed by the
  executor.
- The run artifact directory is VesperaFlow-owned storage for executor output.
- Adapters write bulky streams and transcripts to artifacts and return a short
  normalized `result_summary`, `result_artifact_ref`, `terminal_code`, and
  `failure_reason`.
- Pi writes filtered non-streaming audit events to `pi-events.jsonl`, stderr to
  `pi-stderr.txt`, final assistant text to `pi-result.txt`, and Pi session
  files under `pi-sessions/` in the run artifact directory. Full raw Pi JSONL
  event capture is opt-in with `VESPERAFLOW_PI_CAPTURE_RAW_EVENTS=1`, which
  writes capped output to `pi-raw-events.jsonl`.
- Run events may include executor name, profile id, profile name, model, and
  terminal code. They must not include full instructions, full executor output,
  or secret env values.

## Source Map

- API profile routes: `apps/api/src/vesperaflow_api/routes/executor_profiles.py`
- API preflight route: `apps/api/src/vesperaflow_api/routes/executors.py`
- Task/template resolution: `apps/api/src/vesperaflow_api/routes/tasks.py` and
  `apps/api/src/vesperaflow_api/routes/templates.py`
- Repository defaults and validation:
  `packages/store/src/vesperaflow_store/repositories.py`
- Temporal payload contract:
  `packages/core/src/vesperaflow_core/contracts.py`
- Worker runtime resolution:
  `apps/worker/src/vesperaflow_worker/activities/task_run.py`
- Worker routing: `apps/worker/src/vesperaflow_worker/executors/router.py`
- Web labels/defaults: `apps/web/src/lib/executors.ts`
