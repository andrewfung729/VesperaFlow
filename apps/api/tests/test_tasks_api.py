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
        self.paused: list[str] = []
        self.resumed: list[str] = []

    async def create_one_time_schedule(
        self, *, task: Task, schedule: ProductSchedule, run: Run | None
    ) -> str:
        _ = task, run
        self.created.append(schedule.schedule_id)
        return f"vesperaflow.schedule.{schedule.schedule_id}"

    async def replace_one_time_schedule(
        self, *, task: Task, schedule: ProductSchedule, run: Run | None
    ) -> str:
        _ = task, run
        self.deleted.append(schedule.schedule_id)
        return await self.create_one_time_schedule(
            task=task, schedule=schedule, run=run
        )

    async def create_recurring_schedule(
        self, *, task: Task, schedule: ProductSchedule, run: Run | None = None
    ) -> str:
        _ = task, run
        self.created.append(schedule.schedule_id)
        return f"vesperaflow.schedule.{schedule.schedule_id}"

    async def replace_recurring_schedule(
        self, *, task: Task, schedule: ProductSchedule
    ) -> str:
        _ = task
        self.deleted.append(schedule.schedule_id)
        self.created.append(schedule.schedule_id)
        return f"vesperaflow.schedule.{schedule.schedule_id}"

    async def pause_schedule(self, schedule_id: str) -> None:
        self.paused.append(schedule_id)

    async def resume_schedule(self, schedule_id: str) -> None:
        self.resumed.append(schedule_id)

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
async def test_recurring_task_lifecycle(api_context: ApiTestContext) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_recurring_payload())

    assert created.status_code == 201
    data = cast(dict[str, object], created.json()["data"])
    task = cast(dict[str, object], data["task"])
    schedule = cast(dict[str, object], data["schedule"])
    assert task["execution_mode"] == "recurring"
    assert task["task_status"] == "scheduled"
    assert data["run"] is None
    assert schedule["schedule_type"] == "recurring_rule"
    assert schedule["next_run_at"] is not None

    updated = await client.patch(
        f"/api/v1/tasks/{task['task_id']}/schedule",
        json={
            "version": schedule["version"],
            "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;BYHOUR=8;BYMINUTE=30",
            "recurrence_timezone": "Asia/Hong_Kong",
        },
    )
    assert updated.status_code == 200
    updated_schedule = cast(dict[str, object], updated.json()["data"]["schedule"])
    assert updated_schedule["recurrence_rule"] == (
        "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;BYHOUR=8;BYMINUTE=30"
    )

    paused = await client.post(
        f"/api/v1/tasks/{task['task_id']}/schedule/pause",
        json={"version": updated_schedule["version"]},
    )
    assert paused.status_code == 200
    paused_data = cast(dict[str, object], paused.json()["data"])
    paused_task = cast(dict[str, object], paused_data["task"])
    paused_schedule = cast(dict[str, object], paused_data["schedule"])
    assert paused_task["task_status"] == "paused"
    assert paused_schedule["schedule_status"] == "paused"
    assert paused_schedule["next_run_at"] is None

    resumed = await client.post(
        f"/api/v1/tasks/{task['task_id']}/schedule/resume",
        json={"version": paused_schedule["version"]},
    )
    assert resumed.status_code == 200
    resumed_schedule = cast(dict[str, object], resumed.json()["data"]["schedule"])
    assert resumed.json()["data"]["task"]["task_status"] == "scheduled"
    assert resumed_schedule["schedule_status"] == "active"
    assert resumed_schedule["next_run_at"] is not None

    canceled = await client.post(
        f"/api/v1/tasks/{task['task_id']}/schedule/cancel",
        json={"version": resumed_schedule["version"]},
    )
    assert canceled.status_code == 200
    assert canceled.json()["data"]["task"]["task_status"] == "canceled"
    assert canceled.json()["data"]["schedule"]["schedule_status"] == "canceled"


@pytest.mark.asyncio
async def test_recurring_todo_returns_recurring_items_with_latest_outcome(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    active = await client.post("/api/v1/tasks", json=_recurring_payload("Active daily"))
    paused = await client.post("/api/v1/tasks", json=_recurring_payload("Paused daily"))
    one_time = await client.post("/api/v1/tasks", json=_create_payload("One-time"))
    active_data = cast(dict[str, object], active.json()["data"])
    paused_data = cast(dict[str, object], paused.json()["data"])
    active_task = cast(dict[str, object], active_data["task"])
    active_schedule = cast(dict[str, object], active_data["schedule"])
    paused_task = cast(dict[str, object], paused_data["task"])
    paused_schedule = cast(dict[str, object], paused_data["schedule"])

    paused_response = await client.post(
        f"/api/v1/tasks/{paused_task['task_id']}/schedule/pause",
        json={"version": paused_schedule["version"]},
    )
    assert paused_response.status_code == 200
    assert one_time.status_code == 201

    planned_start_at = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
    async with api_context.session_factory() as session:
        async with session.begin():
            schedule = await repo.get_schedule(
                session,
                cast(str, active_schedule["schedule_id"]),
            )
            schedule.next_run_at = planned_start_at
            materialized = await repo.materialize_run(
                session,
                payload_task_id=cast(str, active_task["task_id"]),
                payload_schedule_id=cast(str, active_schedule["schedule_id"]),
                payload_run_id=None,
                planned_start_at=planned_start_at,
                occurrence_key=None,
                workflow_id="vesperaflow-recurring-workflow",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            await repo.mark_run_queued(session, run_id=materialized.run_id)
            await repo.mark_run_running(session, run_id=materialized.run_id)
            await repo.mark_run_failed(
                session,
                run_id=materialized.run_id,
                failure_reason="Executor failed",
            )
            schedule.next_run_at = planned_start_at

    todo = await client.get("/api/v1/views/recurring-todo")
    active_only = await client.get(
        "/api/v1/views/recurring-todo",
        params={"include_paused": False},
    )

    assert todo.status_code == 200
    items = cast(list[dict[str, object]], todo.json()["data"])
    assert todo.json()["meta"]["total"] == 2
    assert [item["title"] for item in items] == ["Active daily", "Paused daily"]
    assert items[0]["schedule_status"] == "active"
    assert items[0]["task_status"] == "scheduled"
    assert items[0]["latest_run_outcome"] == "failed"
    assert items[0]["failure_reason"] == "Executor failed"
    assert items[1]["schedule_status"] == "paused"
    assert active_only.json()["meta"]["total"] == 1
    assert active_only.json()["data"][0]["title"] == "Active daily"


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
    planned_at: NotRequired[str]
    recurrence_rule: NotRequired[str]
    recurrence_timezone: NotRequired[str]


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


def _recurring_payload(title: str = "Daily research") -> _CreatePayload:
    return {
        "title": title,
        "instruction_source": "Find relevant updates.",
        "target_working_directory": str(Path.cwd()),
        "execution_mode": "recurring",
        "executor": "debug_printer",
        "template_id": None,
        "schedule": {
            "schedule_type": "recurring_rule",
            "recurrence_rule": "RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
            "recurrence_timezone": "Asia/Hong_Kong",
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
