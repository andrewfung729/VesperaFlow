# Executor Profiles

Executor profiles are the selection and default surface for task execution.
They bind an executor kind to optional model, reasoning, and environment
defaults while keeping Temporal payloads small and free of credentials.

## Supported Executors

- `debug_printer`: deterministic local adapter for development and smoke tests.
- `claude_code`: Claude Agent SDK adapter invoked from a Worker Activity.
- `codex`: Codex CLI adapter invoked as `codex exec` from a Worker Activity.
- `opencode`: OpenCode CLI adapter invoked as `opencode run --format json`
  from a Worker Activity.
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
  `opencode run --model`, and to Pi as `pi --model`. Debug Printer ignores it.
- `reasoning_level` is nullable free-form executor-specific text. Blank input
  normalizes to `null`; `null` means the executor uses its own default. There is
  no VesperaFlow product enum for reasoning values.
- Non-null `reasoning_level` maps to executor controls at runtime: Pi
  `--thinking <value>`, Claude Code `ClaudeAgentOptions(effort=<value>)`, Codex
  `-c model_reasoning_effort="<value>"`, and OpenCode `--variant <value>`.
  Debug Printer keeps deterministic execution and treats the value as metadata.

## Save-Time Validation

- Creating an enabled profile with explicit `default_model` or `reasoning_level`
  runs a live validation probe before the profile is persisted.
- Updating an enabled profile validates before mutation when `default_model`,
  `reasoning_level`, `env`, or `secret_env` changes and the effective model or
  reasoning value is explicit. Enabling a previously disabled explicit profile
  also validates before mutation.
- Validation fails closed. Unsupported model/reasoning, missing executor,
  authentication/configuration failures, or timeout reject the save and leave the
  active profile unchanged.
- The API writes effective plain env and secret env values to a short-lived
  transient handoff row and starts a short Temporal validation Workflow with only
  the handoff id, executor, model, and reasoning metadata.
- The validation Activity loads the handoff, runs the adapter probe in a
  VesperaFlow-owned temporary workspace, and deletes the handoff. API cleanup is
  also attempted if validation fails or times out before the Activity consumes
  the handoff.

## Preflight Rules

- `GET /api/v1/executors/preflight` accepts `executor_profile_id`,
  `executor`, and `target_working_directory`.
- If `executor_profile_id` is present, the profile determines the executor kind.
- Preflight verifies profile usability and target workspace access.
- Claude Code, Codex, OpenCode, and Pi preflight check workspace
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
- Run events include executor name, profile id, nullable profile name,
  `executor_model`, `executor_reasoning_level`, and terminal metadata. They must
  not include full instructions, full executor output, env values, or secret env
  values.

## Source Map

- API profile routes: `apps/api/src/vesperaflow_api/routes/executor_profiles.py`
- API preflight route: `apps/api/src/vesperaflow_api/routes/executors.py`
- Task/template resolution: `apps/api/src/vesperaflow_api/routes/tasks.py` and
  `apps/api/src/vesperaflow_api/routes/templates.py`
- Repository defaults, transient handoff storage, and validation cleanup:
  `packages/store/src/vesperaflow_store/repositories.py`
- Temporal payload contract:
  `packages/core/src/vesperaflow_core/contracts.py`
- Validation Workflow: `apps/worker/src/vesperaflow_worker/workflows/profile_validation.py`
- Worker runtime resolution and validation Activity:
  `apps/worker/src/vesperaflow_worker/activities/task_run.py`
- Worker routing: `apps/worker/src/vesperaflow_worker/executors/router.py`
- Web labels/defaults: `apps/web/src/lib/executors.ts`
