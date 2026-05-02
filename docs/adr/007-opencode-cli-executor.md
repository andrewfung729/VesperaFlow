---
title: "ADR 007: OpenCode CLI Executor Integration"
status: accepted
date: "2026-05-02"
aligned_architecture: "docs/architecture.md"
aligned_adr: "docs/adr/002-execution-engine-choice.md"
---

# ADR 007: OpenCode CLI Executor Integration

## Status

Accepted for v1.

## Context

OpenCode exposes two plausible automation surfaces:

1. **Non-interactive CLI subprocess** — `opencode run` with JSON event output
2. **ACP server subprocess** — `opencode acp` over stdin/stdout nd-JSON

VesperaFlow already has a CLI adapter boundary for Codex and Kimi Code, plus
profile-based model/env resolution inside the Worker Activity. Adding OpenCode
should not add task/template model columns or move executor configuration into
Temporal Workflow history.

## Decision

Adopt **non-interactive CLI subprocess** as the `opencode` executor
integration:

```text
opencode run --format json --dir <target_working_directory> --dangerously-skip-permissions --title <run_id> [--model <executor_profile.default_model>]
```

- stdin receives the task instruction
- stdout JSON events are persisted to `opencode-events.jsonl`
- stderr is persisted to `opencode-stderr.txt`
- final text output is persisted to `opencode-result.txt`
- cancellation sends `SIGINT`, waits briefly, then kills the process group
- non-zero exits are normalized into the existing executor outcome codes

OpenCode authentication, provider configuration, and model availability remain
owned by the `opencode` CLI. VesperaFlow only checks that the binary exists and
the target workspace is accessible during API preflight.

## Why Not ACP For v1

ACP is a better fit for richer progress and session control, but v1 does not
yet have a shared ACP adapter or product-visible progress model that needs it.
Using `opencode run --format json` matches the existing CLI adapter pattern and
keeps the Worker dependency footprint unchanged.

## Consequences

Positive:

- OpenCode becomes a first-class executor without changing Workflow payloads
- Profile `default_model` works consistently with Codex and Claude Code
- JSON event output is retained as an artifact without bloating Temporal history
- Adapter tests can mock subprocess behavior like Codex and Kimi Code

Negative:

- Requires `opencode` on the Worker host `PATH`
- JSON event shape can drift with CLI releases
- No live model discovery in v1; users rely on profile custom model input

## Follow-up

- Revisit ACP when VesperaFlow adds a shared event/progress model or a second
  executor needs the same ACP client infrastructure
- Add an opt-in OpenCode live smoke runbook once a local authenticated path is
  available
