## 1. Core contracts and storage

- [x] 1.1 Add `ExecutorName.PI = "pi"` and update core contract/validation tests that enumerate executor names.
- [x] 1.2 Add Pi to default executor profile seeding in `packages/store` and cover idempotent default profile creation for `pi`.
- [x] 1.3 Verify task, template, and executor-profile repository paths accept and persist `pi` without schema changes.

## 2. Worker Pi adapter

- [x] 2.1 Add `apps/worker/src/vesperaflow_worker/executors/pi.py` with workspace validation, binary lookup, artifact paths, bounded subprocess environment construction, and command args for `pi --mode json --session-dir <artifact-dir>/pi-sessions`.
- [x] 2.2 Implement Pi subprocess execution with task instructions sent on stdin, stdout/stderr captured to artifacts, final assistant text extraction from JSON events, and `pi-result.txt` summary writing.
- [x] 2.3 Implement Pi failure classification for missing binary, invalid workspace, assistant `error`/`aborted` stop reasons, non-zero exits, auth/config/model diagnostics, timeout, and unknown executor errors.
- [x] 2.4 Implement cancellation handling that interrupts the Pi process group, kills it after a grace period, writes available artifacts, and returns a canceled `ExecutorOutcome` without retrying the canceled attempt.
- [x] 2.5 Register the Pi adapter in the executor factory/router and add router coverage for `pi` snapshots.
- [x] 2.6 Add mocked Worker executor tests for Pi success, artifact creation, `default_model` passthrough, profile env/secret passthrough without logging secrets, missing binary, non-zero/auth failure, timeout, and cancellation.

## 3. API, CLI, and Web surfaces

- [x] 3.1 Update API validation/preflight coverage so task creation, template defaults, executor profile CRUD, and `/api/v1/executors/preflight` accept `pi` and preserve existing workspace-only preflight semantics.
- [x] 3.2 Update `apps/web/src/api.ts`, executor registry/options, profile fixtures, and unit tests so Pi appears with label `Pi` and model selection support.
- [x] 3.3 Update CLI tests/README fixtures for executor preflight and profile listing with `pi`.

## 4. Documentation and generated facts

- [x] 4.1 Add an ADR for the Pi executor decision, documenting JSON CLI mode over SDK/RPC/print alternatives.
- [x] 4.2 Update `docs/executor-profiles.md`, `docs/architecture.md`, `docs/temporal-architecture.md`, and `docs/api-spec.md` with Pi selection, preflight, runtime, artifact, model, env, auth, and failure behavior.
- [x] 4.3 Update `docs/MVP_PROGRESS.md`, `docs/QUALITY.md`, and any local smoke/runbook notes affected by the supported executor list.
- [x] 4.4 Regenerate generated facts with `uv run python scripts/generate_agent_facts.py`.

## 5. Verification

- [x] 5.1 Run focused Python tests for core/store/API/Worker executor behavior.
- [x] 5.2 Run `uv run ruff check .`, `uv run basedpyright`, `uv run pytest`, and `python scripts/check_agent_repo.py` from the repo root.
- [x] 5.3 Run web checks from `apps/web`: `bun run type-check`, `bun run lint`, and `bun run test:unit:run`.
- [x] 5.4 Optional local authenticated Pi smoke not run in this session; required manual setup notes are recorded in `docs/local-full-stack-runbook.md`.
