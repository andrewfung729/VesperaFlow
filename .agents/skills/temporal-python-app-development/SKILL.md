---
name: temporal-python-app-development
description: Best-practice guidance for architecting, designing, implementing, reviewing, and testing Temporal Python SDK applications. Use when Codex is asked to design Temporal app architecture, choose workflow boundaries, model long-running business processes or entity workflows, plan task queues and worker topology, define activity and retry strategy, build or modify Python workflows, activities, workers, clients, signals, queries, updates, schedules, payload converters, workflow versioning, sandbox configuration, replay tests, or production-readiness checks for Python Temporal apps.
---

# Temporal Python App Development

## Core Workflow

1. Start at the business process boundary: identify the durable outcome, owner entity, external systems, latency needs, and human or async waiting points.
2. Choose workflow boundaries before coding: use workflows for durable orchestration and state; use activities for IO, CPU work, network calls, DB calls, and non-deterministic operations.
3. Design task queues, workers, idempotency keys, retry policy, timeout policy, payload models, and versioning strategy before adding SDK calls.
4. Inspect the app's current `temporalio` version, project layout, worker/client entry points, deployment model, and operational constraints before changing code.
5. Prefer type-safe SDK calls with workflow/activity method references. Use string names only for cross-language calls, dynamic dispatch, or legacy compatibility.
6. Add or update tests with `WorkflowEnvironment`, `ActivityEnvironment`, and replay checks when behavior or workflow history compatibility can change.
7. Review determinism, idempotency, timeouts, retries, cancellation, payload size, observability, worker shutdown, and deployment rollout before calling the work complete.

For architecture design, read [references/architecture.md](references/architecture.md) when the task involves system design, workflow boundaries, task queues, worker topology, versioning, multi-service coordination, or production rollout.

For implementation patterns and examples, read [references/python-patterns.md](references/python-patterns.md) when the task involves nontrivial workflow code, activity execution, message handlers, test design, or code-level production hardening.

## Architecture Rules

- Treat workflows as durable domain objects or durable process managers, not as request handlers.
- Prefer fewer, meaningful workflow types aligned to business lifecycles over many tiny workflows that only wrap single activities.
- Use child workflows when a sub-process needs independent lifecycle, cancellation, retries, visibility, or ownership. Use activities for ordinary side effects.
- Use signals for external events, updates for command-style interactions that need validation/results, and queries for read-only state.
- Design workflow IDs from business identity where duplicate starts must collapse to the same execution.
- Separate task queues by ownership, scaling profile, dependency isolation, deployment cadence, or language boundary. Do not create task queues merely as folders for code organization.
- Keep worker processes horizontally scalable and stateless except for registered activity dependencies such as DB pools or API clients.
- Design every external side effect with idempotency before relying on Temporal retries.
- Plan workflow evolution up front: payload compatibility, patch markers, worker versioning, replay testing, and safe draining of old executions.
- Make observability part of the architecture: search attributes for business lookup, metrics for worker health and activity latency, logs for replay-safe workflow events, and tracing around client/activity boundaries.

## Design Rules

- Keep workflow files boring: no top-level side effects, no network or disk IO, no randomness, no threads, no subprocesses, no global mutable state mutation.
- Use workflow-safe APIs: `workflow.now()` for workflow time, `asyncio.sleep()` or `workflow.sleep()` for timers, `workflow.wait_condition()` for state waits, and `workflow.wait()` / `workflow.as_completed()` instead of the nondeterministic `asyncio` variants.
- Put external calls in activities. Make activities idempotent or safely retryable because retries are normal.
- Configure at least one activity timeout, usually `start_to_close_timeout` for bounded work and `schedule_to_close_timeout` for an end-to-end cap.
- Add `heartbeat_timeout` and call `activity.heartbeat()` for long-running non-local activities so cancellation and retry progress work.
- Use `ApplicationError` for expected business failures that should fail the workflow/update visibly. Let unexpected workflow bugs fail the workflow task so fixed code can recover the execution.
- Treat signal and update handlers as concurrent tasks. Protect shared workflow state with `asyncio.Lock` or design handlers to be idempotent and commutative.
- Before completing, failing, cancelling, or continuing-as-new a workflow with async handlers, wait for `workflow.all_handlers_finished` when handlers may still be running.
- Use `workflow.continue_as_new()` to cap history growth for long-running loops or entity workflows.
- Use `workflow.patched()` / `workflow.deprecate_patch()` or worker versioning when changing workflow logic that existing histories may replay through.

## Worker And Client Rules

- Create workers with explicit task queue names and register only the workflows/activities that queue should run.
- Provide a `ThreadPoolExecutor` for synchronous activities; prefer threaded activities for blocking IO and async activities only when they never block the event loop.
- Tune worker concurrency deliberately for production: `max_concurrent_activities`, workflow task concurrency, poller behavior, cache size, and `graceful_shutdown_timeout`.
- Use the same data converter on every client and worker that touches the same payloads. Prefer the Pydantic data converter when using Pydantic v2 models.
- Pass through deterministic third-party modules used by workflow files via `workflow.unsafe.imports_passed_through()` or `SandboxedWorkflowRunner` restrictions. Avoid disabling the sandbox except for a narrow, justified case.
- Put Temporal connection settings in environment/config (`ClientConfig.load_client_connect_config()` is used in Temporal samples) rather than hard-coding Cloud credentials or endpoints.

## Verification Checklist

- For architecture tasks, provide a concise design with workflow types, activity groups, task queues, worker processes, workflow IDs, message APIs, retry/timeout policy, versioning plan, and failure-mode notes.
- Run the project's existing tests and type checks when available.
- Add a workflow integration test with `WorkflowEnvironment.start_time_skipping()` for timers, sleeps, retries, and timeout-heavy logic when the platform supports it.
- Add an `ActivityEnvironment` unit test for activity heartbeat, cancellation, worker shutdown, and activity context usage.
- Replay representative histories with `temporalio.worker.Replayer` after workflow-control-flow changes.
- Check that every started workflow has stable workflow IDs or an explicit ID reuse/conflict policy appropriate to the use case.
- Check that task queues, workflow names, activity names, and payload model names are stable across deployments unless intentionally versioned.

## Source Material

This skill was distilled from local clones of:

- `~/github-kb/temporalio/sdk-python`
- `~/github-kb/temporalio/samples-python`

When exact API signatures matter, inspect the installed package or these local repositories instead of relying only on memory.
