## 1. Contracts, Storage, API, and Save-Time Validation

- [x] 1.1 Add nullable `reasoning_level` string fields to executor profile create/update/response contracts, including blank-to-null normalization, length validation, and tests proving no product-level enum is required.
- [x] 1.2 Add nullable `reasoning_level` to the SQLAlchemy `ExecutorProfile` model and create an Alembic migration for `executor_profiles.reasoning_level`.
- [x] 1.3 Add transient profile validation handoff storage for effective env/secret env values, with expiry and cleanup behavior that prevents abandoned validation secrets from lingering.
- [x] 1.4 Update executor profile repository create/update/default-profile logic to persist, clear, and serialize `reasoning_level` without changing existing null behavior.
- [x] 1.5 Add save-time validation orchestration to executor profile create/update routes so enabled profiles with explicit `default_model` or `reasoning_level` fail closed before commit when validation fails or times out.
- [x] 1.6 Ensure validation payloads and logs contain only handoff ids/non-secret metadata and that API profile responses still expose only `secret_env_keys`, never secret values.
- [x] 1.7 Add or update core, store, and API tests for create/update/list/get, blank-to-null normalization, null defaults, clearing, optimistic concurrency, failed validation, timeout behavior, and transient handoff cleanup.

## 2. Worker Validation, Runtime Config, and Executor Adapters

- [x] 2.1 Add a short profile validation Workflow/Activity path that receives a transient handoff id, loads the effective runtime config, runs a bounded executor adapter probe in a temporary workspace, and returns a structured validation result.
- [x] 2.2 Add `reasoning_level` to `ExecutorRuntimeConfig` and Activity profile resolution while keeping scheduled-run Workflow payloads unchanged.
- [x] 2.3 Add executor adapter probe methods for Claude Code, Codex, OpenCode, Pi, and Debug Printer that use the safest low-cost non-mutating validation command available for each executor.
- [x] 2.4 Map runtime `reasoning_level` in the Pi adapter with `--thinking <value>` and cover validation/execution command construction with tests.
- [x] 2.5 Map runtime `reasoning_level` in the Claude Code adapter through `ClaudeAgentOptions(effort=...)` and cover validation/execution SDK option construction with tests.
- [x] 2.6 Map runtime `reasoning_level` in the Codex adapter through `model_reasoning_effort` configuration and cover validation/execution command construction with tests.
- [x] 2.7 Map runtime `reasoning_level` in the OpenCode adapter through `--variant <value>` and cover validation/execution command construction with tests.
- [x] 2.8 Keep Debug Printer deterministic while preserving `reasoning_level` as metadata-only propagation for tests.
- [x] 2.9 Include stable `executor_model` and `executor_reasoning_level` keys in executor started/terminal run event details, using `null` when unset and excluding env/secret env values.
- [x] 2.10 Add Activity/runtime tests proving unset reasoning passes no executor option, set reasoning is not silently ignored by real adapters, validation uses temporary workspaces, and profile secrets remain out of Temporal payloads and run events.

## 3. CLI, Web, and Documentation

- [x] 3.1 Update the VesperaFlow CLI profile create/update/list formatting and tests to send/display free-form `reasoning_level` and surface fail-closed validation errors clearly.
- [x] 3.2 Update Web API types, executor profile labels, and profile create/edit UI to support free-form reasoning input, unset state, and save-time validation errors.
- [x] 3.3 Update Web unit tests for profile creation/editing, executor profile labels, and API payloads containing `reasoning_level`.
- [x] 3.4 Update `docs/api-spec.md`, `docs/domain-model.md`, and `docs/executor-profiles.md` to document free-form reasoning semantics, save-time validation, transient handoff, runtime adapter mappings, and stable nullable run event metadata keys.
- [x] 3.5 Update any generated facts or README/source-map references that list executor profile fields or executor event metadata.

## 4. Verification

- [x] 4.1 Run `openspec validate add-executor-profile-reasoning-level --strict`.
- [x] 4.2 Run `uv run ruff check .`.
- [x] 4.3 Run `uv run basedpyright`.
- [x] 4.4 Run `uv run pytest`.
- [x] 4.5 Run `uv run --directory packages/store alembic upgrade head` against a local database or migration test harness.
- [x] 4.6 From `apps/web`, run `bun run type-check`, `bun run lint`, and `bun run test:unit:run`.
- [x] 4.7 Run `python scripts/check_agent_repo.py`.
