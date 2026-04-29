# Codex CLI Executor Plan

Date: 2026-04-29

## Goal

Add `codex` as a first-class executor that runs through Codex CLI
non-interactive `codex exec` from Worker Activities, without changing Temporal
Workflow orchestration.

## Scope

- Add `ExecutorName.CODEX` to shared domain contracts and generated/web types.
- Add a Worker `CodexExecutor` CLI adapter behind the existing executor adapter
  boundary.
- Route `codex` through `ExecutorRouter` and `build_executor("auto")`.
- Add shallow API preflight for target workspace and `codex` binary
  availability.
- Expose Codex in web executor selectors and preflight gating.
- Update docs and generated facts as source-of-truth references.

## Guardrails

- Keep Codex-specific imports out of Workflow modules and package roots.
- Do not serialize Codex credentials, config, full prompts, or full runtime
  output into Temporal payloads, logs, or database fields.
- Treat Codex CLI as a black-box runtime; do not depend on internal Codex
  implementation details.
- Do not add schedulers, polling loops, or delayed-start mechanisms.

## Verification

- Worker executor unit tests for factory, router, workspace validation, missing
  binary, success artifacts, nonzero/auth failure classification, JSONL
  `turn.failed`, cancellation, and import hygiene.
- API tests for preflight and task/template payload acceptance.
- Web tests for selector visibility and `executor=codex` preflight requests.
- Run targeted Python and web checks, then refresh generated facts.
