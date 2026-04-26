from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NotRequired, TypedDict, cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from vesperaflow_api.app import create_app
from vesperaflow_api.settings import ApiSettings
from vesperaflow_store import Base, create_engine, create_session_factory
from vesperaflow_store import repositories as repo
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


@dataclass(frozen=True, slots=True)
class ApiTestContext:
    client: AsyncClient
    session_factory: async_sessionmaker


@pytest_asyncio.fixture
async def api_context(tmp_path: Path) -> AsyncIterator[ApiTestContext]:
    app = create_app()
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    app.state.settings = ApiSettings()
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.scheduler = FakeScheduler()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as active_client:
        yield ApiTestContext(client=active_client, session_factory=session_factory)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(api_context: ApiTestContext) -> AsyncIterator[AsyncClient]:
    yield api_context.client


@pytest.mark.asyncio
async def test_create_task_success(client: AsyncClient) -> None:
    response = await client.post("/api/v1/tasks", json=_create_payload())

    assert response.status_code == 201
    body = cast(dict[str, object], response.json()["data"])
    task = cast(dict[str, object], body["task"])
    assert cast(str, task["task_status"]) == "scheduled"
    assert cast(str, task["target_working_directory"]) == str(Path.cwd())
    schedule = cast(dict[str, object], body["schedule"])
    assert cast(str, schedule["external_schedule_ref"]).startswith(
        "vesperaflow.schedule."
    )
    run = cast(dict[str, object], body["run"])
    assert cast(str, run["run_status"]) == "planned"


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
async def test_create_task_rejects_relative_target_directory(
    client: AsyncClient,
) -> None:
    payload = _create_payload()
    payload["target_working_directory"] = "relative/path"

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
    data = cast(dict[str, object], created.json()["data"])
    task = cast(dict[str, object], data["task"])
    schedule = cast(dict[str, object], data["schedule"])

    canceled = await client.post(
        f"/api/v1/tasks/{cast(str, task['task_id'])}/schedule/cancel",
        json={"version": cast(str, schedule["version"])},
    )
    board = await client.get("/api/v1/views/kanban")

    assert canceled.status_code == 200
    assert board.status_code == 200
    columns = cast(dict[str, object], board.json()["data"]["columns"])
    assert len(cast(list[object], columns["canceled"])) == 1


@pytest.mark.asyncio
async def test_history_returns_terminal_runs_with_filters(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    completed = await client.post("/api/v1/tasks", json=_create_payload("Completed"))
    failed = await client.post("/api/v1/tasks", json=_create_payload("Failed"))
    planned = await client.post("/api/v1/tasks", json=_create_payload("Planned"))
    completed_data = cast(dict[str, object], completed.json()["data"])
    failed_data = cast(dict[str, object], failed.json()["data"])
    planned_data = cast(dict[str, object], planned.json()["data"])

    async with api_context.session_factory() as session:
        async with session.begin():
            completed_run_id = cast(dict[str, object], completed_data["run"])["run_id"]
            await repo.mark_run_queued(session, run_id=cast(str, completed_run_id))
            await repo.mark_run_running(session, run_id=cast(str, completed_run_id))
            completed_run = await repo.mark_run_completed(
                session,
                run_id=cast(str, completed_run_id),
                result_summary="Done",
            )
            completed_run.finished_at = datetime(2026, 4, 25, 9, 0, tzinfo=UTC)

            failed_run_id = cast(dict[str, object], failed_data["run"])["run_id"]
            await repo.mark_run_queued(session, run_id=cast(str, failed_run_id))
            await repo.mark_run_running(session, run_id=cast(str, failed_run_id))
            failed_run = await repo.mark_run_failed(
                session,
                run_id=cast(str, failed_run_id),
                failure_reason="Executor failed",
            )
            failed_run.finished_at = datetime(2026, 4, 25, 10, 0, tzinfo=UTC)
            planned_run = cast(dict[str, object], planned_data["run"])
            assert planned_run["run_status"] == "planned"

    all_history = await client.get("/api/v1/views/history")
    failed_history = await client.get(
        "/api/v1/views/history",
        params={"status": "failed", "execution_mode": "one_time"},
    )
    empty_history = await client.get(
        "/api/v1/views/history",
        params={"status": "running"},
    )

    assert all_history.status_code == 200
    all_items = cast(list[dict[str, object]], all_history.json()["data"])
    assert all_history.json()["meta"]["total"] == 2
    assert [item["title"] for item in all_items] == ["Failed", "Completed"]
    assert all_items[0]["failure_reason"] == "Executor failed"
    assert all_items[1]["result_summary"] == "Done"

    assert failed_history.status_code == 200
    failed_items = cast(list[dict[str, object]], failed_history.json()["data"])
    assert failed_history.json()["meta"]["total"] == 1
    assert failed_items[0]["run_status"] == "failed"

    assert empty_history.status_code == 200
    assert empty_history.json()["data"] == []


@pytest.mark.asyncio
async def test_template_lifecycle_and_instantiation_copy_fields(
    client: AsyncClient,
) -> None:
    created = await client.post("/api/v1/templates", json=_template_payload())
    assert created.status_code == 201
    template = cast(dict[str, object], created.json()["data"])
    template_id = cast(str, template["template_id"])

    instantiated = await client.post(
        f"/api/v1/templates/{template_id}/instantiate",
        json={
            "target_working_directory": str(Path.cwd()),
            "schedule": {
                "schedule_type": "single_run",
                "planned_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        },
    )
    assert instantiated.status_code == 201
    bundle = cast(dict[str, object], instantiated.json()["data"])
    task = cast(dict[str, object], bundle["task"])
    task_id = cast(str, task["task_id"])
    assert task["title"] == "Template Task"
    assert task["instruction_source"] == "Original template instructions"
    assert task["target_working_directory"] == str(Path.cwd())
    assert task["template_id"] == template_id
    assert task["executor"] == "debug_printer"

    updated = await client.patch(
        f"/api/v1/templates/{template_id}",
        json={
            "version": template["version"],
            "name": "Updated template",
            "description": None,
            "instruction_source": "Updated template instructions",
            "default_task_title": "Updated Task",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["description"] is None
    detail = await client.get(f"/api/v1/tasks/{task_id}/detail")
    detail_task = cast(dict[str, object], detail.json()["data"]["task"])
    assert detail_task["title"] == "Template Task"
    assert detail_task["instruction_source"] == "Original template instructions"

    active = await client.get("/api/v1/templates")
    assert active.status_code == 200
    assert active.json()["meta"]["total"] == 1

    updated_template = cast(dict[str, object], updated.json()["data"])
    archived = await client.post(
        f"/api/v1/templates/{template_id}/archive",
        json={"version": updated_template["version"]},
    )
    assert archived.status_code == 200
    active_after_archive = await client.get("/api/v1/templates")
    all_after_archive = await client.get(
        "/api/v1/templates", params={"include_archived": True}
    )
    assert active_after_archive.json()["meta"]["total"] == 0
    assert all_after_archive.json()["meta"]["total"] == 1
    assert (await client.get(f"/api/v1/tasks/{task_id}/detail")).status_code == 200


@pytest.mark.asyncio
async def test_create_task_with_template_uses_template_default_executor(
    client: AsyncClient,
) -> None:
    created = await client.post("/api/v1/templates", json=_template_payload())
    template = cast(dict[str, object], created.json()["data"])
    payload = _create_payload()
    payload["template_id"] = cast(str, template["template_id"])
    del payload["executor"]

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 201
    task = response.json()["data"]["task"]
    assert task["template_id"] == template["template_id"]
    assert task["executor"] == "debug_printer"


@pytest.mark.asyncio
async def test_template_default_target_directory_can_create_task(
    client: AsyncClient,
) -> None:
    payload = _template_payload()
    payload["default_target_working_directory"] = str(Path.cwd())
    created = await client.post("/api/v1/templates", json=payload)
    template = cast(dict[str, object], created.json()["data"])

    instantiated = await client.post(
        f"/api/v1/templates/{template['template_id']}/instantiate",
        json={
            "schedule": {
                "schedule_type": "single_run",
                "planned_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        },
    )

    assert instantiated.status_code == 201
    task = instantiated.json()["data"]["task"]
    assert task["target_working_directory"] == str(Path.cwd())

    direct_payload = _create_payload()
    direct_payload["template_id"] = cast(str, template["template_id"])
    del direct_payload["target_working_directory"]
    direct = await client.post("/api/v1/tasks", json=direct_payload)

    assert direct.status_code == 201
    assert direct.json()["data"]["task"]["target_working_directory"] == str(Path.cwd())


class _SchedulePayload(TypedDict):
    schedule_type: str
    planned_at: str


class _CreatePayload(TypedDict):
    title: str
    instruction_source: str
    target_working_directory: NotRequired[str]
    execution_mode: str
    executor: NotRequired[str]
    template_id: NotRequired[str | None]
    schedule: _SchedulePayload


def _create_payload(title: str = "Overnight research") -> _CreatePayload:
    return {
        "title": title,
        "instruction_source": "Find relevant updates.",
        "target_working_directory": str(Path.cwd()),
        "execution_mode": "one_time",
        "executor": "claude_code",
        "template_id": None,
        "schedule": {
            "schedule_type": "single_run",
            "planned_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    }


def _template_payload() -> dict[str, object]:
    return {
        "name": "Research template",
        "description": "Reusable research",
        "instruction_source": "Original template instructions",
        "default_task_title": "Template Task",
        "default_target_working_directory": None,
        "default_execution_mode": "one_time",
        "default_schedule_config": {
            "schedule_type": "single_run",
            "planned_at": None,
            "recurrence_rule": None,
            "recurrence_timezone": None,
        },
        "default_executor": "debug_printer",
    }
