# Claude Code SDK Executor

Status: active
Owner: TBD
Started: 2026-04-25

## Goal

Implement `claude_code` as a real VesperaFlow executor using the Python
`claude-agent-sdk`.

The executor must support unattended scheduled work with full Claude Code
permissions, run inside a user-selected target directory, and preserve normalized
run outcomes for VesperaFlow without exposing raw credentials or bulky SDK
output through Workflow history or default logs.

## Current State

`ClaudeCodeExecutor` is implemented in a dedicated executor module with
top-level Claude Agent SDK imports. The remaining work is operational hardening
around live authenticated runs, full-stack verification, and Temporal sandbox
import hygiene.

Existing working pieces:

- Worker has `TaskRunWorkflow`, `execute_agent_run`, and executor adapter boundary.
- `debug_printer` and fake executors are tested.
- Tasks store selected executor as `claude_code` or `debug_printer`.
- `ExecutionSnapshot.working_directory` exists for run artifact workspace.
- `target_working_directory` exists in task create/read contracts, persistence,
  web create flow, and execution snapshots.
- SDK failure mapping and output artifact handling exist for mocked execution.
- Docs already require SDK execution inside Activities, not Workflows.

Main gaps:

- Worker import hygiene needs to stay protected so Workflow sandbox imports do
  not load the Claude Agent SDK.
- Unit tests cover expected Claude SDK behavior, but not a live CLI smoke run.
- Full-stack verification with local Temporal/Postgres/Worker is still missing.

## Decisions

- Use `ClaudeSDKClient`, not `query()`, so Activity cancellation can interrupt
  the running SDK session.
- Use `permission_mode = "bypassPermissions"` for unattended execution.
- Load Claude settings from `["user", "project", "local"]`.
- Add `target_working_directory` to task create/read contracts and persisted
  task state.
- Require `target_working_directory` to be an existing absolute directory.
- Keep `ExecutionSnapshot.working_directory` as the run artifact directory.
- Add `ExecutionSnapshot.target_working_directory` as Claude Code `cwd`.
- Store only short normalized summaries in DB.
- Write fuller SDK output/transcript artifacts under the run artifact directory.
- Do not log full task instructions, credentials, or full executor output.

## Implementation Plan

1. Add Worker dependency on `claude-agent-sdk` and update the lockfile.

2. Extend domain and persistence contracts:
   - add `target_working_directory` to `Task`
   - add Alembic migration
   - add field to API schemas and responses
   - add field to `ExecutionSnapshot`
   - update Temporal schedule snapshot construction

3. Add validation:
   - API rejects missing, relative, non-existent, or non-directory target paths
   - Worker re-validates target path before invoking SDK
   - invalid target path maps to `executor_workspace_unavailable`

4. Implement `ClaudeCodeExecutor`:
   - create run artifact directory if needed
   - build `ClaudeAgentOptions`
   - run `ClaudeSDKClient` with task instructions
   - collect assistant text and result metadata
   - write detailed output artifacts
   - return normalized `ExecutorOutcome`

5. Harden Temporal import boundaries:
   - keep `vesperaflow_worker/__init__.py` sandbox-safe
   - keep executor package facade SDK-free
   - import concrete executor modules only from Worker startup or factory paths
   - cover package root and Workflow imports with a regression test

6. Add failure mapping:
   - missing CLI -> executor not available terminal code
   - missing SDK package -> Worker deployment/preflight failure
   - auth/login failure -> `executor_not_authenticated`
   - process/JSON/config errors -> `executor_misconfigured`
   - workspace errors -> `executor_workspace_unavailable`
   - cancellation -> `canceled`

7. Update web:
   - task composer requires target directory
   - create request includes `target_working_directory`
   - task detail displays target directory

8. Update docs:
   - `docs/MVP_PROGRESS.md`
   - `docs/api-spec.md`
   - `docs/domain-model.md`
   - `apps/worker/README.md`

## Blockers

None currently. The chosen security posture is intentionally high-trust:
Claude Code runs unattended with bypass permissions in the selected target
directory.

## Verification

Run:

- `uv run ruff check .`
- `uv run pytest`
- `python scripts/check_agent_repo.py`
- `bun run type-check`
- `bun run lint:check`
- `bun run test:unit:run`
- `bun run test:e2e:smoke`

Worker-specific test cases:

- mocked Claude SDK success returns completed outcome
- SDK options include target cwd, bypass permissions, and all setting sources
- missing SDK/CLI/auth/process failures map to expected terminal codes
- invalid workspace fails before SDK invocation
- output artifact is written under run artifact directory
- cancellation interrupts the SDK client
- importing package root and Workflow modules does not import `claude_agent_sdk`

## Next Action

Run the full local verification suite, then add a live authenticated Claude Code
smoke once local Temporal/Postgres/Worker orchestration is ready.
