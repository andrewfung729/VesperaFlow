from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from vesperaflow_api.app import create_app
from vesperaflow_api.settings import ApiSettings
from vesperaflow_store import Base, create_engine, create_session_factory
from vesperaflow_store.models import Run, Task
from vesperaflow_store.models import Schedule as ProductSchedule


class FakeScheduler:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.deleted: list[str] = []

    async def create_one_time_schedule(
        self, *, task: Task, schedule: ProductSchedule, run: Run
    ) -> str:
        _ = task, run
        self.created.append(schedule.schedule_id)
        return f"vesperaflow.schedule.{schedule.schedule_id}"

    async def replace_one_time_schedule(
        self, *, task: Task, schedule: ProductSchedule, run: Run
    ) -> str:
        _ = task, run
        self.deleted.append(schedule.schedule_id)
        return await self.create_one_time_schedule(
            task=task, schedule=schedule, run=run
        )

    async def delete_schedule(self, schedule_id: str) -> None:
        self.deleted.append(schedule_id)


@pytest_asyncio.fixture
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    app = create_app()
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    app.state.settings = ApiSettings()
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.scheduler = FakeScheduler()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as active_client:
        yield active_client
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_task_success(client: AsyncClient) -> None:
    response = await client.post("/api/v1/tasks", json=_create_payload())

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["task"]["task_status"] == "scheduled"
    assert body["schedule"]["external_schedule_ref"].startswith("vesperaflow.schedule.")
    assert body["run"]["run_status"] == "planned"


@pytest.mark.asyncio
async def test_create_task_accepts_debug_printer_executor(
    client: AsyncClient,
) -> None:
    payload = _create_payload()
    payload["executor"] = "debug_printer"

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 201
    assert response.json()["data"]["task"]["executor"] == "debug_printer"


@pytest.mark.asyncio
async def test_create_task_rejects_past_time(client: AsyncClient) -> None:
    payload = _create_payload()
    payload["schedule"]["planned_at"] = (
        datetime.now(UTC) - timedelta(minutes=5)
    ).isoformat()

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_create_task_rejects_recurring_as_unsupported(
    client: AsyncClient,
) -> None:
    payload = _create_payload()
    payload["execution_mode"] = "recurring"

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "unsupported_operation"


@pytest.mark.asyncio
async def test_cancel_task_updates_kanban(client: AsyncClient) -> None:
    created = await client.post("/api/v1/tasks", json=_create_payload())
    data = created.json()["data"]

    canceled = await client.post(
        f"/api/v1/tasks/{data['task']['task_id']}/schedule/cancel",
        json={"version": data["schedule"]["version"]},
    )
    board = await client.get("/api/v1/views/kanban")

    assert canceled.status_code == 200
    assert board.status_code == 200
    assert len(board.json()["data"]["columns"]["canceled"]) == 1


class _SchedulePayload(TypedDict):
    schedule_type: str
    planned_at: str


class _CreatePayload(TypedDict):
    title: str
    instruction_source: str
    execution_mode: str
    executor: str
    schedule: _SchedulePayload


def _create_payload() -> _CreatePayload:
    return {
        "title": "Overnight research",
        "instruction_source": "Find relevant updates.",
        "execution_mode": "one_time",
        "executor": "claude_code",
        "schedule": {
            "schedule_type": "single_run",
            "planned_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    }
