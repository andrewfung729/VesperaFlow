# Temporal Python Patterns

Use this reference when implementing or reviewing Temporal Python applications.

## Minimal Production Shape

Separate durable orchestration from side effects:

```python
# activities.py
from dataclasses import dataclass
from temporalio import activity

@dataclass
class ChargeInput:
    order_id: str
    amount_cents: int

@activity.defn
def charge_customer(input: ChargeInput) -> str:
    # External payment call belongs here, not in workflow code.
    return f"payment-for-{input.order_id}"
```

```python
# workflows.py
from dataclasses import dataclass
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import ChargeInput, charge_customer

@dataclass
class OrderInput:
    order_id: str
    amount_cents: int

@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, input: OrderInput) -> str:
        return await workflow.execute_activity(
            charge_customer,
            ChargeInput(input.order_id, input.amount_cents),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
```

```python
# worker.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from temporalio.client import Client
from temporalio.envconfig import ClientConfig
from temporalio.worker import Worker
from .activities import charge_customer
from .workflows import OrderWorkflow

async def main() -> None:
    config = ClientConfig.load_client_connect_config()
    config.setdefault("target_host", "localhost:7233")
    client = await Client.connect(**config)
    with ThreadPoolExecutor(max_workers=20) as activity_executor:
        await Worker(
            client,
            task_queue="orders-v1",
            workflows=[OrderWorkflow],
            activities=[charge_customer],
            activity_executor=activity_executor,
            max_concurrent_activities=20,
        ).run()

if __name__ == "__main__":
    asyncio.run(main())
```

## Determinism

Workflow code must replay to the same commands from history. Avoid:

- `datetime.now()`, `date.today()`, random UUIDs, random numbers, set iteration, network calls, file IO, subprocesses, threads, environment reads, and mutable module globals.
- Blocking calls inside async workflow or async activity code.
- Reordering workflow commands in a way that existing histories will not replay.

Use:

- `workflow.now()` for current workflow time.
- `workflow.info()` for workflow metadata.
- `workflow.logger` for replay-aware logs.
- `workflow.wait()` and `workflow.as_completed()` instead of `asyncio.wait()` and `asyncio.as_completed()`.
- Activities for all external effects.

## Inputs And Payloads

Prefer one model argument even when the SDK permits multiple parameters:

```python
from dataclasses import dataclass

@dataclass
class ResizeImageInput:
    image_id: str
    width: int
    height: int
    format: str = "webp"  # Added later without changing the signature.
```

Use Pydantic v2 by setting the converter on all clients and workers that encode/decode those payloads:

```python
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

client = await Client.connect(
    "localhost:7233",
    namespace="default",
    data_converter=pydantic_data_converter,
)
```

Use custom converters or external storage only when the project has concrete payload needs such as encryption, compression, custom types, or large payload offload. Keep converter config identical across starter clients, workers, test clients, and operational tools.

## Activities

Use synchronous threaded activities for blocking libraries:

```python
from concurrent.futures import ThreadPoolExecutor
from temporalio.worker import Worker

Worker(
    client,
    task_queue="billing",
    workflows=[BillingWorkflow],
    activities=[charge_customer],
    activity_executor=ThreadPoolExecutor(max_workers=50),
    max_concurrent_activities=50,
)
```

Use async activities only when every dependency is async and non-blocking. A blocking call in an async activity can stall the worker event loop.

For long work, heartbeat and resume from heartbeat details:

```python
from temporalio import activity

@activity.defn
def process_records(records: list[str]) -> int:
    processed = 0
    details = activity.info().heartbeat_details
    if details:
        processed = int(details[0])
    for index, _record in enumerate(records[processed:], start=processed):
        activity.heartbeat(index + 1)
    return len(records)
```

Invoke it with a heartbeat timeout:

```python
await workflow.execute_activity(
    process_records,
    records,
    start_to_close_timeout=timedelta(minutes=10),
    heartbeat_timeout=timedelta(seconds=30),
)
```

## Signals, Queries, And Updates

- Use queries for read-only state. They must not mutate workflow state.
- Use signals for fire-and-forget mutation.
- Use updates when the caller needs validation, rejection, or a result.
- Add update validators when rejection should happen before events are written.
- Use `asyncio.Lock` around shared state when handlers can interleave.

Handler completion pattern:

```python
import asyncio
from temporalio import exceptions, workflow

def is_workflow_exit_exception(err: BaseException) -> bool:
    return isinstance(err, (asyncio.CancelledError, exceptions.FailureError))

@workflow.defn
class EntityWorkflow:
    @workflow.run
    async def run(self) -> str:
        try:
            result = await self._run_entity_loop()
            await workflow.wait_condition(workflow.all_handlers_finished)
            return result
        except BaseException as err:
            if is_workflow_exit_exception(err):
                await workflow.wait_condition(workflow.all_handlers_finished)
            raise
```

## Retries And Failures

- Activities retry by default. Set retry policy only when business semantics require a cap, non-retryable types, or custom backoff.
- Make activity side effects idempotent with business keys, request IDs, idempotency tokens, or upsert semantics.
- Raise `ApplicationError(..., non_retryable=True)` for expected non-retryable business failures.
- In workflow code, unexpected exceptions fail the workflow task and keep retrying. This is often correct because a code fix can recover the execution.
- Be cautious with `workflow_failure_exception_types=[Exception]`; it turns ordinary bugs into workflow failures.

## Long-Running Workflows

Use continue-as-new for loops, entity workflows, polling coordinators, and high-message workloads:

```python
@workflow.defn
class CounterWorkflow:
    @workflow.run
    async def run(self, count: int = 0) -> None:
        if count >= 1000:
            workflow.continue_as_new(0)
        await workflow.sleep(1)
        workflow.continue_as_new(count + 1)
```

Carry durable state in a serializable model so the next run receives everything it needs.

## Workflow Changes

Before changing workflow control flow, ask whether currently running histories can replay through the new code.

Use patch markers for staged changes:

```python
if workflow.patched("new-branch"):
    result = await new_path()
else:
    result = await old_path()
```

Later, after all old histories are gone:

```python
workflow.deprecate_patch("new-branch")
result = await new_path()
```

Use worker versioning when deployments need pinned or auto-upgrading behavior across worker builds. Inspect the current SDK API before adding `deployment_config` or `versioning_behavior` because this area evolves.

## Testing

Workflow test with time skipping:

```python
from concurrent.futures import ThreadPoolExecutor
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

async def test_order_workflow() -> None:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        with ThreadPoolExecutor(max_workers=5) as activity_executor:
            async with Worker(
                env.client,
                task_queue="test-orders",
                workflows=[OrderWorkflow],
                activities=[charge_customer],
                activity_executor=activity_executor,
            ):
                result = await env.client.execute_workflow(
                    OrderWorkflow.run,
                    OrderInput(order_id="o1", amount_cents=500),
                    id="order-o1",
                    task_queue="test-orders",
                )
                assert result == "payment-for-o1"
```

Activity unit test:

```python
from temporalio.testing import ActivityEnvironment

def test_activity_heartbeats() -> None:
    env = ActivityEnvironment()
    heartbeats: list[int] = []
    env.on_heartbeat = lambda value: heartbeats.append(value)
    assert env.run(process_records, ["a", "b"]) == 2
    assert heartbeats == [1, 2]
```

Replay test for compatibility:

```python
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

async def test_replay(history_json: str) -> None:
    await Replayer(workflows=[OrderWorkflow]).replay_workflow(
        WorkflowHistory.from_json(history_json)
    )
```

## Production Review

Check these before shipping:

- Workflow IDs are stable and intentional.
- Task queue names are explicit and deployment-owned.
- Activity timeouts and retry policies match the side effect.
- Long-running activities heartbeat and handle cancellation/shutdown.
- Async activities do not block.
- Workflow code has no nondeterministic operations.
- Payload models are backward compatible.
- Data converters match across clients and workers.
- Message handlers cannot interleave corrupt state.
- Long histories continue as new.
- Workflow changes are patched, versioned, or replay-tested.
- Metrics, tracing, and logs are configured in the runtime path used by workers.
