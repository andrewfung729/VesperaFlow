"""VesperaFlow Temporal worker entrypoint."""

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)

from vesperaflow_worker.activities import TaskRunActivities
from vesperaflow_worker.executors.factory import build_executor
from vesperaflow_worker.settings import get_settings
from vesperaflow_worker.workflows import TaskRunWorkflow

_pydantic_sandbox_runner = SandboxedWorkflowRunner(
    restrictions=SandboxRestrictions.default.with_passthrough_modules(
        "pydantic_core",
        "pydantic_core._pydantic_core",
        "pydantic_core.core_schema",
    )
)


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    activities = TaskRunActivities(
        database_url=settings.database_url,
        executor=build_executor(
            settings.executor_adapter,
            claude_max_turns=settings.claude_max_turns,
            claude_env=settings.claude_executor_env(),
        ),
        run_workspace_root=settings.run_workspace_root,
    )
    worker = Worker(
        client,
        task_queue=settings.task_queue,
        workflows=[TaskRunWorkflow],
        activities=[
            activities.materialize_run,
            activities.mark_run_queued,
            activities.mark_run_running,
            activities.execute_agent_run,
            activities.mark_run_completed,
            activities.mark_run_failed,
            activities.mark_run_canceled,
            activities.complete_single_run_schedule,
        ],
        workflow_runner=_pydantic_sandbox_runner,
    )
    try:
        await worker.run()
    finally:
        await activities.close()


def main() -> None:
    asyncio.run(run_worker())
