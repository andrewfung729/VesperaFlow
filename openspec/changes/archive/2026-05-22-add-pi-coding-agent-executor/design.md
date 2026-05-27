## Context

VesperaFlow executor selection is profile-primary. The API stores the resolved executor kind and optional `executor_profile_id` on each task, Temporal Workflow payloads carry only that snapshot, and `execute_agent_run` resolves profile model/env values inside a Worker Activity before routing to an executor adapter. Existing CLI executors (`codex`, `opencode`) spawn official binaries from Activity-only modules, capture bulky output under the run artifact directory, and return a small normalized `ExecutorOutcome`.

Pi is a local terminal coding harness. It supports single-shot print/JSON mode, RPC mode, and a TypeScript SDK. For a Python Temporal Worker, the CLI process boundary matches the current executor adapter architecture best and keeps Pi's Node/TypeScript dependency graph out of Workflow imports and Python package roots.

## Goals / Non-Goals

**Goals:**

- Add `pi` as a supported executor kind without changing Temporal Workflow payload shape or run state semantics.
- Execute Pi only inside Worker Activities, with the target project as the subprocess working directory.
- Preserve executor-profile behavior: profile usability checks in API/Activity paths, `default_model` as the Pi model selector, and profile env/secret values resolved only at Activity runtime.
- Capture Pi event streams, stderr, final text, and session files as run artifacts while returning only a short summary/reference through Temporal.
- Keep API/Web/CLI labels, docs, tests, and generated facts aligned with the new executor list.

**Non-Goals:**

- Build a Pi SDK bridge or TypeScript service inside VesperaFlow.
- Add Pi-specific task columns, schedule behavior, run statuses, or a new Temporal task queue.
- Implement live Pi authentication/model validation in API preflight.
- Expose Pi streaming/tool events as first-class product progress beyond persisted run artifacts and existing run events.
- Manage Pi provider credentials directly; users configure Pi through Pi's own auth/config files or executor profile environment values.

## Decisions

### Use Pi CLI JSON mode from an Activity

Invoke the official `pi` binary in headless JSON mode from a new Worker adapter. The subprocess runs with `cwd` set to `ExecutionSnapshot.target_working_directory`, receives the task instruction through stdin, and writes stdout JSON lines, stderr, extracted final assistant text, and Pi session files under `ExecutionSnapshot.working_directory`.

Alternatives considered:

- **Pi TypeScript SDK**: type-safe and direct, but it would require embedding Node/TypeScript runtime concerns into the Python Worker or adding a sidecar service. That is a larger architecture change than a new executor adapter.
- **Pi RPC mode**: avoids command-line prompts and supports richer control, but it requires a long-running JSONL command client and extension UI response handling. JSON single-shot mode already supports piped stdin and event output, which is sufficient for v1.
- **Pi text print mode**: simplest, but it loses structured event artifacts and makes failure classification weaker.

### Keep Workflow and executor contracts unchanged

Add a new `ExecutorName.PI = "pi"` enum member and route it in `ExecutorRouter`. `ExecutionSnapshot`, `TaskRunInput`, and `ExecutorOutcome` stay unchanged. Existing persistence Activities and run-event writing continue to work because they already key off the executor enum and normalized outcome.

Alternatives considered:

- Add Pi-specific payload fields for thinking level, session behavior, or tool options. This is deferred because executor profiles already provide `default_model` and env, and the existing contract intentionally keeps Workflow payloads small.

### Map executor profiles to Pi CLI options and environment

Use `runtime_config.default_model` as `pi --model <value>`. Users can use Pi's provider/model patterns, including provider prefixes and optional thinking shorthand supported by Pi. Merge executor profile env and secret env only inside the Activity subprocess environment. Add non-secret defaults to reduce nonessential startup traffic, such as `PI_SKIP_VERSION_CHECK=1` and `PI_TELEMETRY=0`, unless the profile overrides them.

The adapter should pass a bounded process environment containing the values Pi and child tools need (`PATH`, `HOME`, shell/user/locale/temp variables, Pi-specific env, and executor-profile env) rather than writing secrets to logs, run events, or Temporal payloads.

Alternatives considered:

- Add a first-class `thinking_level` profile field. Deferred until multiple executors need a shared reasoning-control contract.
- Depend only on Pi global config and ignore profile env. Rejected because VesperaFlow executor profiles are the existing surface for runtime env/secrets.

### Reuse current API preflight semantics

API preflight for Pi validates that the selected profile is usable and the target working directory is an existing absolute directory. It does not perform live Pi auth, provider, model, package, or extension checks. Missing `pi`, auth failures, model/provider errors, and startup/configuration failures are normalized during Worker execution.

Alternatives considered:

- Run `pi --list-models` or a live prompt in preflight. Rejected because current executor preflight intentionally avoids live auth/provider checks and because preflight should remain fast and side-effect-light.

### Artifact and outcome policy

The adapter writes Pi artifacts under the run artifact directory, for example `pi-events.jsonl`, `pi-stderr.txt`, `pi-result.txt`, and a Pi session directory. Successful runs return `completed`, `pi_completed`, the final assistant text summary, and the result artifact reference. Assistant stop reasons of `error`/`aborted`, non-zero exits, missing binary, auth/configuration diagnostics, workspace errors, and timeouts map to the existing executor terminal codes where possible.

Cancellation follows the CLI executor pattern: Activity cancellation sends `SIGINT` to the process group, waits briefly, then sends `SIGKILL` if needed, and returns a canceled executor outcome without retrying the canceled attempt.

## Risks / Trade-offs

- Pi JSON event shapes can change between releases → Keep parsing conservative, preserve raw stdout as an artifact, and classify unknown event shapes by process exit and assistant stop reason.
- Pi project extensions and skills can execute arbitrary local code → Run only in the user-selected target workspace and document that Pi execution inherits Pi's trust model; do not inject VesperaFlow-specific extensions.
- Authentication failures may appear only after the Worker starts a run → Preserve the current executor policy by surfacing `executor_not_authenticated` or `executor_misconfigured` on the run outcome.
- Long-running Pi sessions can outlive Activity cancellation if child processes detach → Start a subprocess process group, send interrupt/kill on cancellation, and rely on Temporal Activity heartbeat timeout for stuck attempts.
- Adding an enum value can miss one of the UI/API/docs lists → Add focused tests and regenerate generated facts as part of implementation.

## Migration Plan

1. Add the new executor enum value and seed/default profile mapping in code.
2. Add the Pi adapter, route it in the Worker factory/router, and cover adapter behavior with mocked subprocess tests.
3. Update API/Web/CLI validation and labels.
4. Update docs and generated facts.
5. Run unit/static checks and an optional local smoke with an authenticated `pi` installation.

Rollback is code-only: disable or remove Pi profiles if created locally, revert the enum/router/adapter/UI/docs changes, and leave existing tasks for other executors untouched. Because executor columns are string-backed and no Temporal payload shape changes, no database schema rollback is expected.

## Open Questions

- Should v1 expose a profile-level Pi tool allowlist (`--tools`) or rely on Pi project/user settings? Default: rely on Pi settings.
- Should VesperaFlow provide a documented optional live Pi smoke command in the runbook? Default: yes, but not as an automated CI gate.
