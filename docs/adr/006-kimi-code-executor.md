---
title: "ADR 006: Kimi Code Executor Integration"
status: accepted
date: "2026-04-28"
aligned_architecture: "docs/architecture.md"
aligned_adr: "docs/adr/002-execution-engine-choice.md"
---

# ADR 006: Kimi Code Executor Integration

## Status

Accepted for MVP.

## Context

ADR 002 established that VesperaFlow delegates AI execution to external coding-agent runtimes through two integration modes:

- **SDK integration** — import the executor's official SDK and drive it in-process
- **CLI transport** — spawn the executor's official CLI binary with a documented non-interactive mode

Claude Code ships as the Claude Agent SDK (SDK integration). Moonshot AI's `kimi-cli` offers multiple embedding surfaces, ranked by stability and risk:

1. **Non-interactive text CLI subprocess** — `kimi --print --final-message-only --work-dir <dir> --yolo`
2. **ACP server subprocess** — `kimi acp` over stdio, driven via `agent-client-protocol`
3. **In-process embedding** — `from kimi_cli.app import KimiCLI` and iterate `instance.run(...)`
4. **`kimi-sdk` primitives** — `generate()` / `step()` / `Toolset` without file/shell/coding tools

## Decision

Adopt **non-interactive text CLI subprocess** (surface #1) as the `kimi_code` executor integration.

### Why not ACP (surface #2)

ACP is typed and schema-validated, but it is intentionally session-oriented and requires a ~moderate Python dependency (`agent-client-protocol`) in the Worker. It becomes worth its weight once a second ACP-speaking executor is added; until then, the text CLI surface is simpler and matches the existing `ClaudeCodeExecutor` outcome shape with less code.

### Why not in-process embed (surface #3)

`KimiCLI` is the application class, not a stable embedding API. Pulling it into the Worker would drag in `prompt-toolkit`, `rich`, `fastapi`, `uvicorn`, `fastmcp`, `loguru`, `keyring`, `pillow`, and others, significantly expanding the Temporal sandbox surface area. Signal handling, logging, and `setproctitle` would collide with the Worker's own runtime.

### Why not `kimi-sdk` primitives (surface #4)

`kimi-sdk` only provides `generate()` / `step()` / `Toolset`. Building a coding agent on top of it would require VesperaFlow to own prompts, file tools, shell tools, planning, and approvals — exactly what ADR 002 excludes.

### Text CLI specifics

The adapter spawns:

```text
kimi --print --final-message-only --work-dir <target_working_directory> --yolo
```

- `--print` implies `--yolo` (auto-approve), matching the `permission_mode="bypassPermissions"` posture already used for `claude_code`
- `--work-dir` maps onto `ExecutionSnapshot.target_working_directory`
- stdin receives the normalized instruction followed by a newline
- stdout is captured as text and normalized into the run result summary
- stderr is captured into artifacts for diagnostics
- cancellation sends `SIGINT`, waits a short grace, then `SIGKILL` to the process group
- on non-zero exit, the adapter classifies into `executor_not_authenticated`, `executor_not_available`, or `executor_error`
- artifacts `kimi-output.txt` and `kimi-result.json` are written under the run's working directory

Authentication is handled entirely by the `kimi` CLI itself (e.g. OAuth token cache or its own configuration). The worker does not perform any pre-flight auth check and does not inject env vars; the subprocess simply inherits the full parent environment.

## Consequences

Positive:

- Officially supported non-interactive CLI mode
- Architecturally identical transport to today's `claude_code` (subprocess CLI wrapped by SDK)
- Opaque text output; no internal API coupling
- Cancellation = signal/kill + close stdin; same shape already handled
- Worker dependency footprint stays small (just spawn a binary)
- VesperaFlow does not own the agent loop, prompts, or tool-calling logic

Negative:

- Requires `kimi` binary on `PATH` of the Worker host
- CLI text output can drift; the adapter treats stdout as opaque result text and stderr as diagnostic material
- Background-task semantics in kimi (`background.keep_alive_on_exit`) can keep the subprocess alive after the prompt finishes; the adapter enforces its own deadline and terminates the process group
- Same user-trust assumption as Claude Code (`--yolo` / `bypassPermissions`); the executor has broad file-system and shell access in the target working directory

## Follow-up

- Revisit ACP (surface #2) once a second ACP-speaking executor makes the abstraction worth its weight
- Consider per-task knobs (`--model`, `--no-thinking`, `--add-dir`, `--agent-file`, `--mcp-config-file`) driven by config in a future settings pass
