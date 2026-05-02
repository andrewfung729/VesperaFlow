---
title: "ADR 002: Execution Engine and Executor Choice"
status: accepted
date: "2026-04-24"
aligned_architecture: "docs/architecture.md"
aligned_temporal_architecture: "docs/temporal-architecture.md"
---

# ADR 002: Execution Engine and Executor Choice

## Status

Accepted for MVP.

## Context

VesperaFlow needs two separate capabilities:

1. Durable scheduling and execution for one-time deferred tasks and recurring runs
2. A concrete way to perform the AI work at execution time

### Scheduling and Durable Execution

Candidates considered:

- simple `cron` or in-process schedulers (APScheduler, Celery beat)
- a durable execution engine (Temporal, Cadence)
- a homegrown scheduler backed by PostgreSQL

Durable execution is a core capability rather than a peripheral background job. It must survive process restarts, support retries and replay, coordinate long-running external executions, and allow recurring schedules to be paused, resumed, and updated without losing history.

### Executor (AI Work Runtime)

Candidates considered:

- direct LLM API integration (Anthropic Messages API, OpenAI Chat Completions, etc.) combined with a VesperaFlow-implemented tool-calling agent loop
- delegation to an existing coding-agent runtime through its official SDK invoked in-process from a Temporal Activity
- delegation to an existing coding-agent runtime through its CLI binary invoked as a subprocess from a Temporal Activity
- delegation to a hosted agent service with its own orchestration

Building and maintaining an agent runtime is a substantial product in its own right: prompt construction, tool selection, tool invocation, memory, streaming, safety controls, model pinning, rate-limit handling, cost accounting. These are solved and continuously improved by the existing coding-agent ecosystem and its SDKs. Reimplementing them inside VesperaFlow would duplicate work and lag behind upstream.

SDK integration gives VesperaFlow structured, typed event streams, first-class cancellation, and cleaner dependency management than shelling out to a binary. CLI integration is also supported when an executor exposes its stable automation surface through the official CLI rather than a Python SDK; the adapter must still normalize cancellation, logging, artifacts, and error classification behind the same executor contract.

Users who benefit from VesperaFlow already have subscriptions and configured credentials for at least one coding-agent runtime. Delegating execution to that runtime means VesperaFlow never handles provider credentials, never maintains prompt scaffolding, and inherits whatever capability upgrades the SDK ships.

## Decision

### Durable Execution and Scheduling

Adopt Temporal as the sole durable execution and scheduling engine. Use the Temporal Python SDK to stay aligned with the FastAPI backend.

Temporal is the only time-based triggering mechanism in VesperaFlow. All scheduling — recurring runs, one-time deferred runs, retries with backoff, and any future time-based behavior — is implemented through Temporal Schedules, Temporal timers, and Workflow control flow.

Explicitly not permitted, either at MVP or as a fallback:

- operating-system `cron` or `at` jobs
- in-process schedulers such as APScheduler, Celery beat, or RQ scheduled jobs
- PostgreSQL-backed polling schedulers, `LISTEN/NOTIFY` schedulers, or triggers that fire application logic on time
- application-level delay queues, `asyncio.sleep` loops, or sidecar timers
- hybrid models that route some triggers through Temporal and others through a secondary scheduler

If Temporal cannot express a future scheduling requirement cleanly, the answer is to solve it inside Temporal or to drop the requirement, not to introduce a second scheduler.

### Executor

VesperaFlow will not implement an AI agent runtime. VesperaFlow will not call LLM APIs directly. All AI execution is delegated to an external coding-agent runtime invoked from a Temporal Activity.

MVP supports two integration modes at the adapter layer:

- **SDK integration**: VesperaFlow imports the executor's official SDK into the Worker process and drives the agent through that SDK. Progress events, tool-call traces, cancellation tokens, and typed terminal outcomes come from the SDK.
- **CLI transport**: VesperaFlow spawns the executor's official CLI binary in a documented non-interactive mode. This is architecturally equivalent to SDK integration—VesperaFlow does not own the agent loop, prompts, or tool-calling logic—and is used when an executor's stable official transport is the CLI rather than an in-process SDK.

Supported executors for MVP:

- `claude_code` — Anthropic's Claude Code, via the Claude Agent SDK (SDK integration)
- `codex` — OpenAI Codex CLI, via non-interactive `codex exec` CLI transport
- `kimi_code` — Moonshot AI's Kimi Code, via the `kimi` CLI non-interactive text transport
- `debug_printer` — local runtime simulator for end-to-end workflow testing

`opencode` and additional executor integrations are post-MVP candidates. The `Executor Adapter` interface defined in `docs/architecture.md` §6.4 remains narrow enough to add them later without changing task, schedule, or run ownership. For MVP, the adapter guarantees the executor:

- accepts VesperaFlow's normalized instructions
- performs the AI work against its own configured upstream LLM provider
- writes output artifacts into the run's working directory
- reports terminal success or failure through a normalized outcome
- supports cancellation through its native mechanism (SDK cancel token or process signal)

Executor and integration-mode selection:

- executor profiles are the primary selection/default surface; they bind executor kind to optional model/env defaults
- templates may optionally declare a default executor profile or legacy default executor
- task creation must provide an executor/profile directly or inherit one from a template; there is no install-level executor fallback
- if a request sends only the legacy `executor` field, the API resolves that executor's default profile and persists both the profile id and resolved executor
- the domain model stores the resolved executor on `Task.executor` for traceability and future multi-executor support, while `Task.executor_profile_id` records the profile that supplied model/env defaults
- integration mode is selected by the executor adapter and is not configurable per task in MVP
- profile defaults are stored in PostgreSQL, not Worker environment configuration
- per-task UI selection is profile-primary and can choose between enabled supported executor profiles
- the Claude Agent SDK dependency pin and lockfile are the source of truth for the validated SDK version; runtime preflight verifies importability and optional live execution instead of reimplementing version policy
- one-time deferred tasks use one dedicated Temporal Schedule per product `Schedule`; VesperaFlow does not use a shared dispatcher Schedule for MVP

## Consequences

Positive:

- durable execution, retries, and recurring scheduling are handled by a mature engine rather than invented
- recurring schedules map cleanly to Temporal Schedules
- VesperaFlow does not maintain any prompt engineering, tool-calling loop, or model-specific code
- VesperaFlow never holds LLM provider credentials; each executor authenticates itself against its upstream service
- the user keeps using the coding-agent capabilities and subscriptions they already rely on
- capability improvements in the executor runtime flow through to VesperaFlow with minimal adapter changes
- SDK integration gives better observability and cancellation than subprocess integration

Negative:

- MVP gains a nontrivial operational component (Temporal server) that must run locally
- Workflow code must follow determinism rules and versioning discipline
- VesperaFlow depends on the presence and correct local installation of the supported executor runtime
- cancellation, timeout, and output semantics vary by executor and must conform to the normalized adapter contract
- importing a third-party agent SDK in-process couples the Worker's Python dependency graph to that SDK's version; the adapter must isolate this coupling
- observability of the agent's internal behavior is limited to what the SDK surfaces; VesperaFlow cannot inspect provider API calls directly
