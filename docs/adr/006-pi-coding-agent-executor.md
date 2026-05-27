---
title: "ADR 006: Pi Coding Agent Executor Integration"
status: accepted
date: "2026-05-19"
aligned_architecture: "docs/architecture.md"
aligned_adr: "docs/adr/002-execution-engine-choice.md"
---

# ADR 006: Pi Coding Agent Executor Integration

## Status

Accepted for v1.

## Context

Pi offers several automation surfaces that could drive scheduled coding work:

1. **CLI JSON mode** — `pi --mode json` as a single-shot subprocess with JSONL events
2. **RPC mode** — `pi --mode rpc` with a long-lived JSONL command protocol
3. **TypeScript SDK** — embed Pi from Node/TypeScript code
4. **Print mode** — `pi --print` with plain text output

VesperaFlow already keeps executor invocation inside Worker Activities and keeps
Temporal Workflows free of SDK imports, subprocesses, network calls, and disk IO.
The Pi integration must preserve that boundary and continue using executor
profiles for runtime model/env selection.

## Decision

Adopt **Pi CLI JSON mode** as the `pi` executor integration:

```text
pi --mode json --session-dir <run_artifact_dir>/pi-sessions [--model <executor_profile.default_model>]
```

- The subprocess `cwd` is `ExecutionSnapshot.target_working_directory`
- stdin receives the task instruction followed by a newline
- filtered non-streaming stdout JSONL audit events are persisted to
  `pi-events.jsonl`
- full raw stdout JSONL capture is opt-in and capped in `pi-raw-events.jsonl`
- stderr is persisted to `pi-stderr.txt`
- extracted final assistant text is persisted to `pi-result.txt`
- Pi session files are stored under `pi-sessions/` inside the run artifact directory
- cancellation sends `SIGINT`, waits briefly, then kills the process group
- missing binary, workspace errors, auth/config/model diagnostics, timeouts, non-zero exits, and assistant `error`/`aborted` stop reasons map to existing executor outcome codes

Pi authentication and provider configuration remain owned by Pi itself. API
preflight stays workspace-only and does not perform live Pi auth/model checks.

## Why Not SDK / RPC / Print For v1

- **TypeScript SDK** would add a Node/TypeScript embedding layer or sidecar to a
  Python Worker, expanding deployment and failure modes beyond a normal executor
  adapter.
- **RPC mode** is useful for richer interactive control, but v1 only needs one
  prompt, final outcome, and durable artifacts. A long-lived command client would
  be more code without changing product-visible behavior.
- **Print mode** is the simplest transport, but it discards structured events and
  weakens failure classification compared with JSON mode.

## Consequences

Positive:

- Pi becomes a first-class executor without Workflow payload or run-status changes
- Structured Pi terminal/audit events are preserved without bloating Temporal
  history or default run artifacts with high-frequency streaming deltas
- Executor profile `default_model` and env/secret values are resolved only at Activity runtime
- Tests can mock subprocess execution like the Codex and OpenCode adapters

Negative:

- Requires the `pi` binary on the Worker host `PATH`
- Pi JSON event shapes can drift with CLI releases, so parsing must stay conservative
- Debugging with full streaming events requires explicit raw capture opt-in
- Auth/model failures surface only after execution starts
- Pi inherits the trust model of a local coding agent running in the selected workspace

## Follow-up

- Revisit RPC mode if VesperaFlow adds live executor progress, steering, or richer session control
- Add a local authenticated Pi smoke runbook once the manual setup path is stable
