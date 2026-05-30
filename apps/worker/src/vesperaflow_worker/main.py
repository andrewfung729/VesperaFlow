"""VesperaFlow Temporal worker entrypoint."""

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)

from vesperaflow_worker.activities import TaskRunActivities
from vesperaflow_worker.executors.factory import build_executor
from vesperaflow_worker.runtime_logging import configure_worker_logging
from vesperaflow_worker.settings import get_settings
from vesperaflow_worker.workflows import (
    ExecutorProfileValidationWorkflow,
    TaskRunWorkflow,
)

logger = logging.getLogger(__name__)

_pydantic_sandbox_runner = SandboxedWorkflowRunner(
    restrictions=SandboxRestrictions.default.with_passthrough_modules(
        "pydantic_core",
        "pydantic_core._pydantic_core",
        "pydantic_core.core_schema",
    )
)


async def run_worker() -> None:
    try:
        settings = get_settings()
        configure_worker_logging(settings.log_level)
        logger.info("worker.settings.loaded", extra=_settings_log_context(settings))
    except Exception:
        logger.exception("worker.settings.failed")
        raise

    logger.info(
        "worker.temporal.connect.starting",
        extra=_settings_log_context(settings),
    )
    try:
        client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
            data_converter=pydantic_data_converter,
        )
    except Exception:
        logger.exception(
            "worker.temporal.connect.failed",
            extra=_settings_log_context(settings),
        )
        raise
    logger.info(
        "worker.temporal.connect.succeeded",
        extra=_settings_log_context(settings),
    )

    logger.info("worker.executor.build.starting", extra=_settings_log_context(settings))
    try:
        executor = build_executor()
    except Exception:
        logger.exception(
            "worker.executor.build.failed",
            extra=_settings_log_context(settings),
        )
        raise
    logger.info(
        "worker.executor.build.succeeded",
        extra=_settings_log_context(settings),
    )

    activities = TaskRunActivities(
        database_url=settings.database_url,
        executor=executor,
        run_workspace_root=settings.run_workspace_root,
    )
    worker = Worker(
        client,
        task_queue=settings.task_queue,
        workflows=[ExecutorProfileValidationWorkflow, TaskRunWorkflow],
        activities=[
            activities.validate_executor_profile,
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
        logger.info("worker.started", extra=_settings_log_context(settings))
        await worker.run()
    finally:
        logger.info("worker.shutdown.starting", extra=_settings_log_context(settings))
        await activities.close()
        logger.info("worker.shutdown.completed", extra=_settings_log_context(settings))


def main() -> None:
    configure_worker_logging(os.environ.get("VESPERAFLOW_LOG_LEVEL"))
    logger.info("worker.init.starting")
    asyncio.run(run_worker())


def _settings_log_context(settings: object) -> dict[str, object]:
    return {
        "temporal_address": getattr(settings, "temporal_address", None),
        "temporal_namespace": getattr(settings, "temporal_namespace", None),
        "task_queue": getattr(settings, "task_queue", None),
        "run_workspace_root": getattr(settings, "run_workspace_root", None),
    }
