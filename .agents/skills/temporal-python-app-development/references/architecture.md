# Temporal Application Architecture

Use this reference when designing or reviewing the architecture of a Temporal Python application, before focusing on code.

## Architecture First Pass

Produce these design decisions before implementing:

- Domain boundary: the business process or entity whose state must survive crashes, retries, deploys, and long waits.
- Workflow types: each durable lifecycle, its start input, result, completion conditions, and expected run duration.
- Activities: every external side effect, its idempotency key, timeout, retry policy, heartbeat need, and dependency owner.
- Message APIs: signals, updates, and queries exposed by each workflow.
- Task queues: which worker pool owns each workflow/activity set and why.
- Worker topology: processes, autoscaling unit, concurrency, dependency isolation, graceful shutdown, and deployment cadence.
- Data model: payload models, backward-compatible evolution, search attributes, memo use, and payload size strategy.
- Failure model: expected business failures, retryable technical failures, compensation, cancellation, and stuck workflow recovery.
- Versioning model: patching, worker versioning, replay tests, and migration/drain strategy.
- Observability model: logs, metrics, tracing, search attributes, alerts, dashboards, and operational runbooks.

## Workflow Boundary Heuristics

Make something a workflow when it:

- Represents a durable business lifecycle such as order fulfillment, subscription provisioning, claim processing, KYC review, or model training job orchestration.
- Waits for time, human action, signals, third-party callbacks, retries, or async completion.
- Owns state that must survive service restarts and deploys.
- Coordinates multiple activities or child processes where partial progress matters.
- Needs queryable status or command-style updates while running.

Do not make something a workflow when it:

- Is a single short side effect with no durable coordination need.
- Is a synchronous request/response handler with no long-running state.
- Exists only to group code that could be a normal Python function.
- Would require non-deterministic workflow code to do its main job.

## Common Architecture Patterns

### Process Manager Workflow

Use for a business process with ordered or conditional steps. The workflow owns process state and schedules activities for side effects.

Good fit:

- Payment then fulfillment then notification.
- Provision account, wait for verification, activate service.
- Data export with retries, validation, and completion notification.

Design notes:

- Keep external calls in activities.
- Persist progress in workflow state, not only in external databases.
- Use `ApplicationError` for terminal business failures that should be visible to callers.
- Add compensation activities only for side effects that cannot be made naturally idempotent or reversible elsewhere.

### Entity Workflow

Use for one durable domain object that receives commands over time.

Good fit:

- Shopping cart, cluster manager, device session, document approval, tenant provisioning state.

Design notes:

- Use business-key workflow IDs such as `cart/{cart_id}` or `tenant/{tenant_id}`.
- Use updates for commands that need validation and results.
- Use signals for external facts/events.
- Use queries for current state.
- Use `continue_as_new` to manage long histories, carrying state forward in one serializable object.
- Protect shared state in async handlers with `asyncio.Lock` when awaits can interleave.

### Batch Orchestrator

Use for large fan-out/fan-in work where chunks need independent retries, rate limits, or progress.

Design notes:

- Use activities for small chunks when history size stays reasonable.
- Use child workflows for chunks with their own long lifecycle, cancellation, retries, or visibility.
- Throttle concurrency inside the workflow or by worker/activity concurrency when the downstream system needs protection.
- Continue as new for long batches or sliding windows.

### Polling And Callback Coordination

Prefer callback/event signals when the external system can notify you. Use polling activities when it cannot.

Design notes:

- For polling, use an activity that polls with heartbeats if each poll cycle is long, or a workflow loop with timer plus short activities when waiting must be visible and controllable.
- Avoid tight workflow timer loops for high-cardinality polling. Consider a schedule, external event ingestion, or coarser polling cadence.
- Use stable IDs and idempotent updates when callbacks can arrive more than once or out of order.

### Schedules

Use Temporal schedules for durable recurring starts rather than cron inside application processes.

Design notes:

- Keep scheduled workflow IDs deterministic enough to avoid duplicate period work.
- Decide overlap policy and catch-up semantics.
- Put period boundaries in input models for replayable, testable behavior.

## Task Queue And Worker Topology

Create a separate task queue when there is a real operational boundary:

- Different team or service owns the worker.
- Different scaling profile or resource type is needed.
- Activities require isolated credentials, network access, CPU/GPU, or large memory.
- A cross-language boundary exists.
- Deployment cadence or versioning policy differs.
- A downstream dependency needs independent rate limiting.

Avoid task queue proliferation for simple module boundaries. Extra queues increase routing, deployment, and operational complexity.

Worker topology checklist:

- Run multiple identical worker replicas for horizontal scale.
- Keep workers stateless apart from local connection pools, clients, and executors.
- Size `ThreadPoolExecutor` and `max_concurrent_activities` together for synchronous activities.
- Keep CPU-heavy work in process pools, external services, or dedicated workers; ensure picklability for process pools.
- Set `graceful_shutdown_timeout` for long activities and make activities observe shutdown/cancellation.
- Isolate risky or slow dependencies into separate activity workers so they cannot starve unrelated workflows.

## IDs, Idempotency, And Deduplication

Design IDs before implementation:

- Workflow ID: business identity for singleton/entity workflows; generated command ID for independent process instances.
- Activity idempotency key: workflow ID plus step name plus business operation ID, or a domain-native key.
- External request ID: pass the idempotency key to payment, email, provisioning, ticketing, and DB mutation systems when supported.
- Callback correlation ID: include workflow ID and run ID only when run-specific correlation is intended; prefer workflow ID for signals that should target the current run after continue-as-new.

Avoid relying on "activity ran only once"; retries, worker crashes, and timeouts can cause repeated attempts.

## Failure And Retry Architecture

Classify failures:

- Transient technical failure: retry with bounded timeout/backoff.
- Terminal business failure: fail with `ApplicationError` or return a domain result.
- Partial side effect: make the next attempt idempotent or add a compensation step.
- Downstream overload: throttle concurrency, use retry backoff, or split task queues.
- Human/manual intervention: keep the workflow waiting with queryable state and signal/update APIs.

Timeout guidance:

- `start_to_close_timeout`: cap one activity attempt.
- `schedule_to_close_timeout`: cap total activity lifecycle including retries and queue delay.
- `heartbeat_timeout`: detect stuck long-running activity attempts and deliver cancellation.
- Workflow run/execution timeout: use sparingly; many Temporal workflows intentionally run for long periods.

## Data And Compatibility

Design payloads as versionable contracts:

- Prefer a single dataclass or Pydantic model input with defaults for newly added fields.
- Avoid positional multi-argument APIs for public workflow/signal/update/activity contracts.
- Keep payloads reasonably small; store large blobs externally and pass references.
- Use search attributes for fields operators need to filter on.
- Use memo for descriptive metadata that does not need indexed search.
- Keep data converter choices consistent across all clients and workers.

## Versioning And Deployment

Before changing workflow logic, answer:

- Are old executions still running?
- Will old histories replay through the new workflow code?
- Is a payload model change backward compatible?
- Do worker deployments need pinned behavior or auto-upgrade behavior?
- Can old and new workers safely poll the same task queue?

Use:

- Patch markers for workflow code branches that must replay both old and new histories.
- Replay tests against exported or listed histories for risky control-flow changes.
- Worker versioning when build-level compatibility needs explicit deployment control.
- New task queues only when the routing/deployment boundary is intentional.

## Architecture Review Template

For architecture answers, provide:

```text
Workflow types:
- Name: responsibility, workflow ID scheme, start input, result, completion condition.

Activities:
- Name/group: side effect, idempotency key, timeout/retry/heartbeat policy.

Messages:
- Signals, updates, queries with purpose and input models.

Task queues and workers:
- Queue names, registered workflows/activities, scaling profile, dependency isolation.

Data and visibility:
- Payload models, search attributes, memo fields, large payload strategy.

Failure handling:
- Retryable failures, terminal business failures, compensation, cancellation, manual recovery.

Versioning and operations:
- Patch/versioning plan, replay tests, deployment rollout, metrics/logs/tracing.
```
