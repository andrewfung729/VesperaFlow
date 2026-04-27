import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker
from vesperaflow_api.app import create_app
from vesperaflow_api.dependencies import set_app_state
from vesperaflow_api.settings import ApiSettings
from vesperaflow_api.temporal_scheduler import TemporalScheduler
from vesperaflow_core import ExecutorName
from vesperaflow_store import Base, create_engine, create_session_factory
from vesperaflow_worker.activities import TaskRunActivities
from vesperaflow_worker.executors.debug import DebugPrinterExecutor
from vesperaflow_worker.main import _pydantic_sandbox_runner
from vesperaflow_worker.workflows import TaskRunWorkflow

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_one_time_debug_printer_reaches_terminal_state(
    tmp_path: Path,
) -> None:
    database_url = os.getenv("VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL")
    if database_url is None:
        pytest.skip("set VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL to run")

    settings = ApiSettings(
        database_url=database_url,
        default_executor=ExecutorName.DEBUG_PRINTER,
        run_workspace_root=str(tmp_path / "runs"),
    )
    engine = create_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    scheduler = TemporalScheduler(settings)
    await scheduler.connect()
    temporal_client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    activities = TaskRunActivities(
        database_url=settings.database_url,
        executor=DebugPrinterExecutor(),
        run_workspace_root=settings.run_workspace_root,
    )

    app = create_app()
    set_app_state(settings, create_session_factory(engine), scheduler)

    try:
        async with Worker(
            temporal_client,
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
        ):
            async with _api_client(app) as client:
                created = await client.post(
                    "/api/v1/tasks",
                    json=_create_payload(tmp_path),
                )
                assert created.status_code == 201, created.text
                body: dict[str, Any] = created.json()["data"]
                task: dict[str, Any] = body["task"]
                detail = await _wait_for_terminal_run(
                    client, task["task_id"]
                )
    finally:
        await activities.close()
        await engine.dispose()

    latest_run: dict[str, Any] = detail["latest_run"]
    schedule: dict[str, Any] = detail["schedule"]
    assert detail["task"]["task_status"] == "completed"
    assert latest_run["run_status"] == "completed"
    assert latest_run["result_summary"].startswith("Debug printer completed run")
    assert schedule["schedule_status"] == "completed"


def _api_client(app: Any) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _create_payload(tmp_path: Path) -> dict[str, Any]:
    return {
        "title": "Full-stack debug printer smoke",
        "instruction_source": "Print the workflow input for the local smoke test.",
        "target_working_directory": str(tmp_path),
        "execution_mode": "one_time",
        "executor": "debug_printer",
        "schedule": {
            "schedule_type": "single_run",
            "planned_at": (datetime.now(UTC) + timedelta(seconds=8)).isoformat(),
        },
    }


async def _wait_for_terminal_run(
    client: AsyncClient,
    task_id: str,
) -> dict[str, Any]:
    deadline = datetime.now(UTC) + timedelta(seconds=45)
    terminal = {"completed", "failed", "canceled"}
    while datetime.now(UTC) < deadline:
        response = await client.get(f"/api/v1/tasks/{task_id}/detail")
        assert response.status_code == 200, response.text
        detail: dict[str, Any] = response.json()["data"]
        latest_run = detail["latest_run"]
        if isinstance(latest_run, dict) and latest_run["run_status"] in terminal:
            return detail
        await asyncio.sleep(1)
    raise AssertionError("run did not reach a terminal state within 45 seconds")
