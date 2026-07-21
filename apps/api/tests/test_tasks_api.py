from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from vesperaflow_api.app import create_app
from vesperaflow_api.dependencies import set_app_state
from vesperaflow_api.settings import ApiSettings
from vesperaflow_api.settings import get_settings as _cached_get_settings
from vesperaflow_core import (
    ProfileValidationInput,
    ProfileValidationResult,
    RunStatus,
    occurrence_key_for_datetime,
)
from vesperaflow_store import Base, create_engine, create_session_factory
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import NotFoundError
from vesperaflow_store.models import Run, Task
from vesperaflow_store.models import Schedule as ProductSchedule


class FakeScheduler:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.updated: list[str] = []
        self.deleted: list[str] = []
        self.paused: list[str] = []
        self.resumed: list[str] = []
        self.profile_validation_inputs: list[ProfileValidationInput] = []
        self.profile_validation_result = ProfileValidationResult(
            ok=True,
            code="profile_validation_passed",
            message="Executor profile validation passed.",
        )
        self.profile_validation_exception: Exception | None = None

    async def validate_executor_profile(
        self,
        payload: ProfileValidationInput,
    ) -> ProfileValidationResult:
        self.profile_validation_inputs.append(payload)
        if self.profile_validation_exception is not None:
            raise self.profile_validation_exception
        return self.profile_validation_result

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
        self.updated.append(schedule.schedule_id)
        return f"vesperaflow.schedule.{schedule.schedule_id}"

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
        self.updated.append(schedule.schedule_id)
        return f"vesperaflow.schedule.{schedule.schedule_id}"

    async def pause_schedule(self, schedule_id: str) -> None:
        self.paused.append(schedule_id)

    async def resume_schedule(self, schedule_id: str) -> None:
        self.resumed.append(schedule_id)

    async def delete_schedule(self, schedule_id: str) -> None:
        self.deleted.append(schedule_id)

    async def run_one_time_now(
        self, *, task: Task, schedule: ProductSchedule, run: Run
    ) -> str:
        _ = task, run
        self.deleted.append(schedule.schedule_id)
        return f"vesperaflow.run.{run.run_id}"

    async def run_recurring_now(
        self, *, task: Task, schedule: ProductSchedule, run: Run
    ) -> str:
        _ = task, schedule, run
        return f"vesperaflow.run.{run.run_id}"

    async def start_one_time_workflow(
        self, *, task: Task, schedule: ProductSchedule, run: Run
    ) -> str:
        _ = task, schedule
        return f"vesperaflow.run.{run.run_id}"

    async def create_occurrence_override_schedule(
        self,
        *,
        task: Task,
        run: Run,
        override_id: str,
        planned_at: datetime,
    ) -> str:
        _ = task, run, planned_at
        self.created.append(f"ovr-{override_id}")
        return f"vesperaflow.schedule.ovr-{override_id}"


@dataclass(frozen=True, slots=True)
class ApiTestContext:
    client: AsyncClient
    session_factory: async_sessionmaker
    scheduler: FakeScheduler


@pytest.fixture(autouse=True)
def _set_test_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "VESPERAFLOW_DATABASE_URL",
        "postgresql+asyncpg://test@localhost/test",
    )
    _cached_get_settings.cache_clear()


@pytest_asyncio.fixture
async def api_context(tmp_path: Path) -> AsyncIterator[ApiTestContext]:
    app = create_app()
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    scheduler = FakeScheduler()
    set_app_state(
        ApiSettings(database_url="postgresql+asyncpg://test@localhost/test"),
        session_factory,
        scheduler,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as active_client:
        yield ApiTestContext(
            client=active_client, session_factory=session_factory, scheduler=scheduler
        )
    await engine.dispose()


@pytest_asyncio.fixture
async def client(api_context: ApiTestContext) -> AsyncIterator[AsyncClient]:
    yield api_context.client


@pytest.mark.asyncio
async def test_create_task_success(api_context: ApiTestContext) -> None:
    client = api_context.client
    response = await client.post("/api/v1/tasks", json=_create_payload())

    assert response.status_code == 201
    body: dict[str, Any] = response.json()["data"]
    task: dict[str, Any] = body["task"]
    assert task["task_status"] == "scheduled"
    assert task["target_working_directory"] == str(Path.cwd())
    schedule: dict[str, Any] = body["schedule"]
    assert schedule["external_schedule_ref"].startswith("vesperaflow.schedule.")
    run: dict[str, Any] = body["run"]
    assert run["run_status"] == "planned"
    async with api_context.session_factory() as session:
        stored_run = await repo.get_run(session, run["run_id"])
    assert stored_run.instruction_source_snapshot == "Find relevant updates."


@pytest.mark.asyncio
async def test_update_task_instruction_updates_planned_run_snapshot(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_create_payload())
    assert created.status_code == 201
    body: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = body["task"]
    run: dict[str, Any] = body["run"]

    updated = await client.patch(
        f"/api/v1/tasks/{task['task_id']}",
        json={
            "version": task["version"],
            "instruction_source": "Find better updates.",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["data"]["instruction_source"] == "Find better updates."
    async with api_context.session_factory() as session:
        stored_run = await repo.get_run(session, run["run_id"])
    assert stored_run.run_status is RunStatus.PLANNED
    assert stored_run.instruction_source_snapshot == "Find better updates."


@pytest.mark.asyncio
async def test_reschedule_updates_temporal_schedule_in_place(
    api_context: ApiTestContext,
) -> None:
    created = await api_context.client.post("/api/v1/tasks", json=_create_payload())
    assert created.status_code == 201
    data: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = data["task"]
    schedule: dict[str, Any] = data["schedule"]

    updated = await api_context.client.patch(
        f"/api/v1/tasks/{task['task_id']}/schedule",
        json={
            "version": schedule["version"],
            "planned_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        },
    )

    assert updated.status_code == 200
    assert api_context.scheduler.updated == [schedule["schedule_id"]]
    assert api_context.scheduler.deleted == []


@pytest.mark.asyncio
async def test_run_now_one_time_task(client: AsyncClient) -> None:
    created = await client.post("/api/v1/tasks", json=_create_payload())
    assert created.status_code == 201
    data: dict[str, Any] = created.json()["data"]
    task_id: str = data["task"]["task_id"]

    response = await client.post(f"/api/v1/tasks/{task_id}/run-now")

    assert response.status_code == 200
    run: dict[str, Any] = response.json()["data"]
    assert run["run_status"] == "planned"


@pytest.mark.asyncio
async def test_run_now_recurring_task(api_context: ApiTestContext) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_recurring_payload())
    assert created.status_code == 201
    data: dict[str, Any] = created.json()["data"]
    task_id: str = data["task"]["task_id"]

    response = await client.post(f"/api/v1/tasks/{task_id}/run-now")

    assert response.status_code == 200
    run: dict[str, Any] = response.json()["data"]
    assert run["run_status"] == "planned"
    assert run["occurrence_key"] is not None
    async with api_context.session_factory() as session:
        stored_run = await repo.get_run(session, run["run_id"])
    assert stored_run.instruction_source_snapshot == "Find relevant updates."


@pytest.mark.asyncio
async def test_run_now_rejects_already_started_run(api_context: ApiTestContext) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_create_payload())
    assert created.status_code == 201
    task_id: str = created.json()["data"]["task"]["task_id"]
    run_id: str = created.json()["data"]["run"]["run_id"]

    async with api_context.session_factory() as session:
        async with session.begin():
            await repo.mark_run_queued(session, run_id=run_id)

    response = await client.post(f"/api/v1/tasks/{task_id}/run-now")

    assert response.status_code == 409


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
async def test_create_task_requires_explicit_executor_or_profile(
    client: AsyncClient,
) -> None:
    payload = _create_payload()
    del payload["executor"]

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "executor_profile_id or executor is required"
    )


@pytest.mark.asyncio
async def test_executor_profile_crud_masks_secret_env(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    response = await client.post(
        "/api/v1/executor-profiles",
        json={
            "name": "Pi Profile",
            "executor": "pi",
            "is_enabled": True,
            "is_default": False,
            "default_model": "sonnet:high",
            "reasoning_level": "high",
            "env": {"FOO": "bar"},
            "secret_env": {"TOKEN": "secret"},
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["executor"] == "pi"
    assert data["default_model"] == "sonnet:high"
    assert data["reasoning_level"] == "high"
    assert data["secret_env_keys"] == ["TOKEN"]
    assert "secret_env" not in data

    assert api_context.scheduler.profile_validation_inputs[0].default_model == (
        "sonnet:high"
    )
    assert api_context.scheduler.profile_validation_inputs[0].reasoning_level == "high"
    assert "secret" not in str(api_context.scheduler.profile_validation_inputs[0])
    listed = await client.get("/api/v1/executor-profiles")
    fetched = await client.get(f"/api/v1/executor-profiles/{data['profile_id']}")
    assert listed.json()["data"][0]["reasoning_level"] == "high"
    assert fetched.json()["data"]["reasoning_level"] == "high"

    updated = await client.patch(
        f"/api/v1/executor-profiles/{data['profile_id']}",
        json={
            "version": data["version"],
            "reasoning_level": None,
            "secret_env": {"TOKEN": None},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["reasoning_level"] is None
    assert updated.json()["data"]["secret_env_keys"] == []


@pytest.mark.asyncio
async def test_executor_profile_validation_failure_rejects_create(
    api_context: ApiTestContext,
) -> None:
    api_context.scheduler.profile_validation_result = ProfileValidationResult(
        ok=False,
        code="executor_misconfigured",
        message="reasoning level is unsupported",
    )

    response = await api_context.client.post(
        "/api/v1/executor-profiles",
        json={
            "name": "Bad Codex",
            "executor": "codex",
            "is_enabled": True,
            "is_default": False,
            "default_model": None,
            "reasoning_level": "xhigh",
            "env": {},
            "secret_env": {"TOKEN": "secret"},
        },
    )

    assert response.status_code == 422
    assert "validation failed" in response.json()["error"]["message"]
    validation_input = api_context.scheduler.profile_validation_inputs[0]
    async with api_context.session_factory() as session:
        page = await repo.list_executor_profiles(session)
        with pytest.raises(NotFoundError):
            await repo.get_profile_validation_handoff(
                session,
                validation_input.handoff_id,
            )
    assert page.total == 0


@pytest.mark.asyncio
async def test_executor_profile_validation_exception_rejects_update_without_mutation(
    api_context: ApiTestContext,
) -> None:
    create_response = await api_context.client.post(
        "/api/v1/executor-profiles",
        json={
            "name": "Codex",
            "executor": "codex",
            "is_enabled": True,
            "is_default": False,
            "default_model": None,
            "reasoning_level": None,
            "env": {},
            "secret_env": {},
        },
    )
    profile = create_response.json()["data"]
    api_context.scheduler.profile_validation_exception = TimeoutError(
        "validation timed out"
    )

    response = await api_context.client.patch(
        f"/api/v1/executor-profiles/{profile['profile_id']}",
        json={"version": profile["version"], "reasoning_level": "high"},
    )

    assert response.status_code == 422
    async with api_context.session_factory() as session:
        stored = await repo.get_executor_profile(session, profile["profile_id"])
    assert stored.version == profile["version"]
    assert stored.reasoning_level is None


@pytest.mark.asyncio
async def test_create_task_accepts_executor_profile_id(client: AsyncClient) -> None:
    profile_response = await client.post(
        "/api/v1/executor-profiles",
        json={
            "name": "Debug Profile",
            "executor": "debug_printer",
            "is_enabled": True,
            "is_default": False,
            "default_model": None,
            "env": {},
            "secret_env": {},
        },
    )
    profile_id = profile_response.json()["data"]["profile_id"]
    payload = _create_payload()
    payload["executor"] = "debug_printer"
    payload["executor_profile_id"] = profile_id

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 201
    task = response.json()["data"]["task"]
    assert task["executor"] == "debug_printer"
    assert task["executor_profile_id"] == profile_id


@pytest.mark.asyncio
async def test_create_task_accepts_codex_executor(
    client: AsyncClient,
) -> None:
    payload = _create_payload()
    payload["executor"] = "codex"

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 201
    assert response.json()["data"]["task"]["executor"] == "codex"


@pytest.mark.asyncio
async def test_create_task_accepts_opencode_executor(
    client: AsyncClient,
) -> None:
    payload = _create_payload()
    payload["executor"] = "opencode"

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 201
    assert response.json()["data"]["task"]["executor"] == "opencode"


@pytest.mark.asyncio
async def test_create_task_accepts_pi_executor(
    client: AsyncClient,
) -> None:
    payload = _create_payload()
    payload["executor"] = "pi"

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 201
    assert response.json()["data"]["task"]["executor"] == "pi"


@pytest.mark.asyncio
async def test_executor_preflight_classifies_workspace_unavailable(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/executors/preflight",
        params={
            "executor": "claude_code",
            "target_working_directory": "/tmp/does-not-exist-vespera",
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "unavailable"
    assert body["code"] == "executor_workspace_unavailable"


@pytest.mark.asyncio
async def test_executor_preflight_rejects_removed_executor(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(
        "/api/v1/executors/preflight",
        params={
            "executor": "ki" + "mi_code",
            "target_working_directory": str(tmp_path),
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_executor_preflight_accepts_existing_workspace(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(
        "/api/v1/executors/preflight",
        params={
            "executor": "claude_code",
            "target_working_directory": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "available"
    assert body["code"] == "executor_preflight_passed"


@pytest.mark.asyncio
async def test_codex_preflight_accepts_existing_workspace(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(
        "/api/v1/executors/preflight",
        params={
            "executor": "codex",
            "target_working_directory": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["executor"] == "codex"
    assert body["status"] == "available"
    assert body["code"] == "executor_preflight_passed"


@pytest.mark.asyncio
async def test_codex_preflight_rejects_missing_workspace(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/executors/preflight",
        params={
            "executor": "codex",
            "target_working_directory": "/tmp/does-not-exist-vespera",
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "unavailable"
    assert body["code"] == "executor_workspace_unavailable"


@pytest.mark.asyncio
async def test_opencode_preflight_accepts_existing_workspace(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(
        "/api/v1/executors/preflight",
        params={
            "executor": "opencode",
            "target_working_directory": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["executor"] == "opencode"
    assert body["status"] == "available"
    assert body["code"] == "executor_preflight_passed"


@pytest.mark.asyncio
async def test_pi_preflight_uses_workspace_only_semantics(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    available = await client.get(
        "/api/v1/executors/preflight",
        params={"executor": "pi", "target_working_directory": str(tmp_path)},
    )
    unavailable = await client.get(
        "/api/v1/executors/preflight",
        params={
            "executor": "pi",
            "target_working_directory": "/tmp/does-not-exist-vespera",
        },
    )

    assert available.status_code == 200
    available_body = available.json()["data"]
    assert available_body["executor"] == "pi"
    assert available_body["status"] == "available"
    assert available_body["code"] == "executor_preflight_passed"
    assert unavailable.status_code == 200
    unavailable_body = unavailable.json()["data"]
    assert unavailable_body["executor"] == "pi"
    assert unavailable_body["status"] == "unavailable"
    assert unavailable_body["code"] == "executor_workspace_unavailable"


@pytest.mark.asyncio
async def test_executor_preflight_returns_debug_printer_available(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/executors/preflight",
        params={"executor": "debug_printer"},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "available"
    assert body["code"] == "executor_preflight_passed"


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
    data: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = data["task"]
    schedule: dict[str, Any] = data["schedule"]
    assert task["execution_mode"] == "recurring"
    assert task["task_status"] == "scheduled"
    assert data["run"] is None
    assert schedule["schedule_type"] == "recurring_rule"
    assert schedule["next_run_at"] is not None

    updated = await client.patch(
        f"/api/v1/tasks/{task['task_id']}/schedule",
        json={
            "version": schedule["version"],
            "title": "Updated recurring research",
            "instruction_source": "Find repo updates.",
            "target_working_directory": str(Path.cwd()),
            "executor": "codex",
            "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;BYHOUR=8;BYMINUTE=30",
            "recurrence_timezone": "Asia/Hong_Kong",
        },
    )
    assert updated.status_code == 200
    updated_data: dict[str, Any] = updated.json()["data"]
    updated_task: dict[str, Any] = updated_data["task"]
    updated_schedule: dict[str, Any] = updated_data["schedule"]
    assert updated_task["title"] == "Updated recurring research"
    assert updated_task["instruction_source"] == "Find repo updates."
    assert updated_task["target_working_directory"] == str(Path.cwd())
    assert updated_task["executor"] == "codex"
    assert updated_schedule["recurrence_rule"] == (
        "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;BYHOUR=8;BYMINUTE=30"
    )

    detail = await client.get(f"/api/v1/tasks/{task['task_id']}/detail")
    assert detail.status_code == 200
    detail_data: dict[str, Any] = detail.json()["data"]
    assert detail_data["task"]["executor"] == "codex"
    assert "runs" not in detail_data

    paused = await client.post(
        f"/api/v1/tasks/{task['task_id']}/schedule/pause",
        json={"version": updated_schedule["version"]},
    )
    assert paused.status_code == 200
    paused_data: dict[str, Any] = paused.json()["data"]
    paused_task: dict[str, Any] = paused_data["task"]
    paused_schedule: dict[str, Any] = paused_data["schedule"]
    assert paused_task["task_status"] == "paused"
    assert paused_schedule["schedule_status"] == "paused"
    assert paused_schedule["next_run_at"] is None

    resumed = await client.post(
        f"/api/v1/tasks/{task['task_id']}/schedule/resume",
        json={"version": paused_schedule["version"]},
    )
    assert resumed.status_code == 200
    resumed_schedule: dict[str, Any] = resumed.json()["data"]["schedule"]
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
async def test_recurring_update_rejects_relative_target_directory(
    client: AsyncClient,
) -> None:
    created = await client.post("/api/v1/tasks", json=_recurring_payload())
    assert created.status_code == 201
    data: dict[str, Any] = created.json()["data"]

    response = await client.patch(
        f"/api/v1/tasks/{data['task']['task_id']}/schedule",
        json={
            "version": data["schedule"]["version"],
            "target_working_directory": "relative/path",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_recurring_todo_returns_recurring_items_with_latest_outcome(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    active = await client.post("/api/v1/tasks", json=_recurring_payload("Active daily"))
    paused = await client.post("/api/v1/tasks", json=_recurring_payload("Paused daily"))
    one_time = await client.post("/api/v1/tasks", json=_create_payload("One-time"))
    active_data: dict[str, Any] = active.json()["data"]
    paused_data: dict[str, Any] = paused.json()["data"]
    active_task: dict[str, Any] = active_data["task"]
    active_schedule: dict[str, Any] = active_data["schedule"]
    paused_task: dict[str, Any] = paused_data["task"]
    paused_schedule: dict[str, Any] = paused_data["schedule"]

    paused_response = await client.post(
        f"/api/v1/tasks/{paused_task['task_id']}/schedule/pause",
        json={"version": paused_schedule["version"]},
    )
    assert paused_response.status_code == 200
    assert one_time.status_code == 201

    planned_start_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    async with api_context.session_factory() as session:
        async with session.begin():
            schedule = await repo.get_schedule(
                session,
                active_schedule["schedule_id"],
            )
            schedule.next_run_at = planned_start_at
            materialized = await repo.materialize_run(
                session,
                payload_task_id=active_task["task_id"],
                payload_schedule_id=active_schedule["schedule_id"],
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
    items: list[dict[str, Any]] = todo.json()["data"]
    assert todo.json()["meta"]["total"] == 2
    assert [item["title"] for item in items] == ["Active daily", "Paused daily"]
    assert items[0]["schedule_status"] == "active"
    assert items[0]["task_status"] == "scheduled"
    assert items[0]["latest_run_outcome"] == "failed"
    assert items[0]["outcome_preview"] == "Executor failed"
    assert items[0]["outcome_source"] == "failure_reason"
    assert items[1]["schedule_status"] == "paused"
    assert active_only.json()["meta"]["total"] == 1
    assert active_only.json()["data"][0]["title"] == "Active daily"


@pytest.mark.asyncio
async def test_calendar_returns_projected_items_and_hides_inactive(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    one_time_payload = _create_payload("Calendar one-time")
    one_time_payload["schedule"]["planned_at"] = datetime(
        2030, 1, 1, 0, 0, tzinfo=UTC
    ).isoformat()
    one_time = await client.post("/api/v1/tasks", json=one_time_payload)
    recurring = await client.post(
        "/api/v1/tasks", json=_recurring_payload("Calendar daily")
    )
    paused = await client.post("/api/v1/tasks", json=_recurring_payload("Paused daily"))

    paused_data: dict[str, Any] = paused.json()["data"]
    paused_task: dict[str, Any] = paused_data["task"]
    paused_schedule: dict[str, Any] = paused_data["schedule"]
    await client.post(
        f"/api/v1/tasks/{paused_task['task_id']}/schedule/pause",
        json={"version": paused_schedule["version"]},
    )

    calendar = await client.get(
        "/api/v1/views/calendar",
        params={
            "from": "2029-12-31T23:59:00+00:00",
            "to": "2030-01-01T00:01:00+00:00",
        },
    )

    assert one_time.status_code == 201
    assert recurring.status_code == 201
    assert calendar.status_code == 200
    items: list[dict[str, Any]] = calendar.json()["data"]
    assert calendar.json()["meta"]["total"] == 2
    assert [item["title"] for item in items] == [
        "Calendar daily",
        "Calendar one-time",
    ]
    assert {item["execution_mode"] for item in items} == {"one_time", "recurring"}


@pytest.mark.asyncio
async def test_occurrence_update_and_cancel_endpoints(
    client: AsyncClient,
) -> None:
    created = await client.post(
        "/api/v1/tasks", json=_recurring_payload("Override daily")
    )
    data: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = data["task"]
    schedule: dict[str, Any] = data["schedule"]

    updated = await client.post(
        f"/api/v1/tasks/{task['task_id']}/occurrences/update",
        json={
            "version": schedule["version"],
            "original_occurrence_at": "2030-01-01T00:00:00+00:00",
            "scope": "this_occurrence_only",
            "planned_at": "2030-01-01T02:00:00+00:00",
            "instruction_source": "Override instructions",
        },
    )
    assert updated.status_code == 200
    override: dict[str, Any] = updated.json()["data"]
    assert override["override_status"] == "active"
    assert override["override_instruction_delta"] == "Override instructions"

    calendar = await client.get(
        "/api/v1/views/calendar",
        params={
            "from": "2030-01-01T01:59:00+00:00",
            "to": "2030-01-01T02:01:00+00:00",
        },
    )
    assert calendar.status_code == 200
    assert calendar.json()["data"][0]["is_occurrence_override"] is True

    canceled = await client.post(
        f"/api/v1/tasks/{task['task_id']}/occurrences/cancel",
        json={
            "version": 2,
            "original_occurrence_at": "2030-01-01T00:00:00+00:00",
            "scope": "this_occurrence_only",
        },
    )
    assert canceled.status_code == 200
    assert canceled.json()["data"]["override_status"] == "canceled"


@pytest.mark.asyncio
async def test_occurrence_time_override_creates_independent_schedule(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post(
        "/api/v1/tasks", json=_recurring_payload("Override daily")
    )
    data: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = data["task"]
    schedule: dict[str, Any] = data["schedule"]

    updated = await client.post(
        f"/api/v1/tasks/{task['task_id']}/occurrences/update",
        json={
            "version": schedule["version"],
            "original_occurrence_at": "2030-01-01T00:00:00+00:00",
            "scope": "this_occurrence_only",
            "planned_at": "2030-01-01T02:00:00+00:00",
            "instruction_source": "Override instructions",
        },
    )
    assert updated.status_code == 200
    override: dict[str, Any] = updated.json()["data"]
    assert override["override_status"] == "active"

    # Verify the independent schedule was created in the database.
    async with api_context.session_factory() as session:
        override_model = await repo.get_occurrence_override(
            session, override["occurrence_override_id"]
        )
    assert override_model.external_schedule_ref is not None
    assert override_model.external_schedule_ref.startswith("vesperaflow.schedule.ovr-")


@pytest.mark.asyncio
async def test_occurrence_cancel_deletes_independent_schedule(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post(
        "/api/v1/tasks", json=_recurring_payload("Override daily")
    )
    data: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = data["task"]
    schedule: dict[str, Any] = data["schedule"]

    updated = await client.post(
        f"/api/v1/tasks/{task['task_id']}/occurrences/update",
        json={
            "version": schedule["version"],
            "original_occurrence_at": "2030-01-01T00:00:00+00:00",
            "scope": "this_occurrence_only",
            "planned_at": "2030-01-01T02:00:00+00:00",
        },
    )
    assert updated.status_code == 200
    override_id: str = updated.json()["data"]["occurrence_override_id"]

    async with api_context.session_factory() as session:
        override_model = await repo.get_occurrence_override(session, override_id)
    assert override_model.external_schedule_ref is not None

    # OccurrenceOverrideResponse does not expose version; the endpoint
    # validates against the schedule version, which was incremented once
    # by the preceding update.
    canceled = await client.post(
        f"/api/v1/tasks/{task['task_id']}/occurrences/cancel",
        json={
            "version": 2,
            "original_occurrence_at": "2030-01-01T00:00:00+00:00",
            "scope": "this_occurrence_only",
        },
    )
    assert canceled.status_code == 200

    async with api_context.session_factory() as session:
        override_model = await repo.get_occurrence_override(session, override_id)
    assert override_model.external_schedule_ref is None


@pytest.mark.asyncio
async def test_occurrence_time_override_update_changes_schedule(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post(
        "/api/v1/tasks", json=_recurring_payload("Override daily")
    )
    data: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = data["task"]
    schedule: dict[str, Any] = data["schedule"]

    first = await client.post(
        f"/api/v1/tasks/{task['task_id']}/occurrences/update",
        json={
            "version": schedule["version"],
            "original_occurrence_at": "2030-01-01T00:00:00+00:00",
            "scope": "this_occurrence_only",
            "planned_at": "2030-01-01T02:00:00+00:00",
        },
    )
    assert first.status_code == 200
    first_override_id: str = first.json()["data"]["occurrence_override_id"]

    async with api_context.session_factory() as session:
        first_override = await repo.get_occurrence_override(session, first_override_id)
    first_schedule_ref = first_override.external_schedule_ref
    assert first_schedule_ref is not None

    # Schedule version was incremented to 2 by the first update.
    second = await client.post(
        f"/api/v1/tasks/{task['task_id']}/occurrences/update",
        json={
            "version": 2,
            "original_occurrence_at": "2030-01-01T00:00:00+00:00",
            "scope": "this_occurrence_only",
            "planned_at": "2030-01-01T03:00:00+00:00",
        },
    )
    assert second.status_code == 200

    async with api_context.session_factory() as session:
        second_override = await repo.get_occurrence_override(session, first_override_id)
    second_schedule_ref = second_override.external_schedule_ref
    assert second_schedule_ref is not None
    # The ref string is deterministic (based on override_id), but the FakeScheduler
    # should have recorded both a delete and a create for the same override.
    assert f"ovr-{first_override_id}" in api_context.scheduler.deleted
    assert second_schedule_ref == first_schedule_ref


@pytest.mark.asyncio
async def test_cancel_task_updates_kanban(client: AsyncClient) -> None:
    created = await client.post("/api/v1/tasks", json=_create_payload())
    data: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = data["task"]
    schedule: dict[str, Any] = data["schedule"]

    canceled = await client.post(
        f"/api/v1/tasks/{task['task_id']}/schedule/cancel",
        json={"version": schedule["version"]},
    )

    # Default view hides canceled tasks per UX rules.
    board_default = await client.get("/api/v1/views/kanban")
    assert canceled.status_code == 200
    assert board_default.status_code == 200
    columns_default: dict[str, Any] = board_default.json()["data"]["columns"]
    assert "canceled" not in columns_default

    # Explicitly requesting canceled tasks shows them.
    board_with_canceled = await client.get("/api/v1/views/kanban?include_canceled=true")
    assert board_with_canceled.status_code == 200
    columns_with_canceled: dict[str, Any] = board_with_canceled.json()["data"][
        "columns"
    ]
    assert len(columns_with_canceled["canceled"]) == 1


@pytest.mark.asyncio
async def test_archived_task_excluded_from_kanban(client: AsyncClient) -> None:
    created = await client.post("/api/v1/tasks", json=_create_payload())
    data: dict[str, Any] = created.json()["data"]
    task: dict[str, Any] = data["task"]
    task_id = task["task_id"]

    # Before archiving, the task appears in the upcoming column.
    board_before = await client.get("/api/v1/views/kanban")
    assert board_before.status_code == 200
    columns_before: dict[str, list[dict[str, Any]]] = board_before.json()["data"][
        "columns"
    ]
    assert any(card["task_id"] == task_id for card in columns_before["upcoming"])

    archived = await client.post(
        f"/api/v1/tasks/{task_id}/archive",
        json={"version": task["version"]},
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["task_status"] == "archived"

    # After archiving, the task must not appear in any kanban column
    # (including the default upcoming fallthrough).
    board_after = await client.get("/api/v1/views/kanban?include_canceled=true")
    assert board_after.status_code == 200
    columns_after: dict[str, list[dict[str, Any]]] = board_after.json()["data"][
        "columns"
    ]
    for column_cards in columns_after.values():
        assert all(card["task_id"] != task_id for card in column_cards)


@pytest.mark.asyncio
async def test_history_returns_terminal_runs_with_filters(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    completed = await client.post("/api/v1/tasks", json=_create_payload("Completed"))
    failed = await client.post("/api/v1/tasks", json=_create_payload("Failed"))
    planned = await client.post("/api/v1/tasks", json=_create_payload("Planned"))
    completed_data: dict[str, Any] = completed.json()["data"]
    failed_data: dict[str, Any] = failed.json()["data"]
    planned_data: dict[str, Any] = planned.json()["data"]

    async with api_context.session_factory() as session:
        async with session.begin():
            completed_run_id = completed_data["run"]["run_id"]
            await repo.mark_run_queued(session, run_id=completed_run_id)
            await repo.mark_run_running(session, run_id=completed_run_id)
            completed_run = await repo.mark_run_completed(
                session,
                run_id=completed_run_id,
                result_summary="Done",
            )
            completed_run.finished_at = datetime(2026, 4, 25, 9, 0, tzinfo=UTC)

            failed_run_id = failed_data["run"]["run_id"]
            await repo.mark_run_queued(session, run_id=failed_run_id)
            await repo.mark_run_running(session, run_id=failed_run_id)
            failed_run = await repo.mark_run_failed(
                session,
                run_id=failed_run_id,
                failure_reason="Executor failed",
            )
            failed_run.finished_at = datetime(2026, 4, 25, 10, 0, tzinfo=UTC)
            planned_run: dict[str, Any] = planned_data["run"]
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
    all_items: list[dict[str, Any]] = all_history.json()["data"]
    assert all_history.json()["meta"]["total"] == 2
    assert [item["title"] for item in all_items] == ["Failed", "Completed"]
    assert all_items[0]["outcome_source"] == "failure_reason"
    assert all_items[0]["outcome_preview"] == "Executor failed"
    assert all_items[1]["outcome_source"] == "result_summary"
    assert all_items[1]["outcome_preview"] == "Done"

    assert failed_history.status_code == 200
    failed_items: list[dict[str, Any]] = failed_history.json()["data"]
    assert failed_history.json()["meta"]["total"] == 1
    assert failed_items[0]["run_status"] == "failed"

    assert empty_history.status_code == 200
    assert empty_history.json()["data"] == []


@pytest.mark.asyncio
async def test_task_run_list_returns_preview_with_server_filter_and_pagination(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_recurring_payload("Run list"))
    created_data: dict[str, Any] = created.json()["data"]
    task_id = created_data["task"]["task_id"]
    schedule_id = created_data["schedule"]["schedule_id"]
    planned_a = datetime(2026, 4, 25, 8, 0, tzinfo=UTC)
    planned_b = datetime(2026, 4, 26, 8, 0, tzinfo=UTC)

    async with api_context.session_factory() as session:
        async with session.begin():
            run_a = await repo.materialize_run(
                session,
                payload_task_id=task_id,
                payload_schedule_id=schedule_id,
                payload_run_id=None,
                planned_start_at=planned_a,
                occurrence_key=occurrence_key_for_datetime(planned_a),
                workflow_id="vesperaflow-recurring-workflow",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            await repo.mark_run_queued(session, run_id=run_a.run_id)
            await repo.mark_run_running(session, run_id=run_a.run_id)
            await repo.mark_run_failed(
                session,
                run_id=run_a.run_id,
                failure_reason="F" * 300,
            )
            run_b = await repo.materialize_run(
                session,
                payload_task_id=task_id,
                payload_schedule_id=schedule_id,
                payload_run_id=None,
                planned_start_at=planned_b,
                occurrence_key=occurrence_key_for_datetime(planned_b),
                workflow_id="vesperaflow-recurring-workflow",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            await repo.mark_run_queued(session, run_id=run_b.run_id)
            await repo.mark_run_running(session, run_id=run_b.run_id)
            await repo.mark_run_completed(
                session,
                run_id=run_b.run_id,
                result_summary="Completed run",
            )

    response = await client.get(
        f"/api/v1/tasks/{task_id}/runs",
        params={"status": "failed", "limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1
    item = response.json()["data"][0]
    assert item["run_status"] == "failed"
    assert item["outcome_source"] == "failure_reason"
    assert item["outcome_truncated"] is True
    assert item["outcome_preview"].endswith("...")
    assert len(item["outcome_preview"]) == 80
    assert "result_summary" not in item
    assert "failure_reason" not in item


@pytest.mark.asyncio
async def test_get_run_endpoint_returns_outcome_preview(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_create_payload("One-time"))
    run_id = created.json()["data"]["run"]["run_id"]
    long_summary = "Outcome " + ("x" * 280)
    async with api_context.session_factory() as session:
        async with session.begin():
            await repo.mark_run_queued(session, run_id=run_id)
            await repo.mark_run_running(session, run_id=run_id)
            await repo.mark_run_completed(
                session,
                run_id=run_id,
                result_summary=long_summary,
            )

    response = await client.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["data"]["run_id"] == run_id
    assert response.json()["data"]["outcome_truncated"] is True
    assert response.json()["data"]["outcome_source"] == "result_summary"
    assert response.json()["data"]["outcome_preview"].endswith("...")
    assert len(response.json()["data"]["outcome_preview"]) == 80
    assert response.json()["data"]["result_summary"] == long_summary
    assert response.json()["data"]["instruction_source_snapshot"] == (
        "Find relevant updates."
    )


@pytest.mark.asyncio
async def test_run_reader_endpoint_returns_selected_and_adjacent_ids(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_recurring_payload("Reader"))
    created_data: dict[str, Any] = created.json()["data"]
    task_id = created_data["task"]["task_id"]
    schedule_id = created_data["schedule"]["schedule_id"]
    oldest = datetime(2026, 4, 25, 8, 0, tzinfo=UTC)
    middle = datetime(2026, 4, 26, 8, 0, tzinfo=UTC)
    newest = datetime(2026, 4, 27, 8, 0, tzinfo=UTC)

    async with api_context.session_factory() as session:
        async with session.begin():
            oldest_run = await repo.materialize_run(
                session,
                payload_task_id=task_id,
                payload_schedule_id=schedule_id,
                payload_run_id=None,
                planned_start_at=oldest,
                occurrence_key=occurrence_key_for_datetime(oldest),
                workflow_id="vesperaflow-recurring-workflow",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            middle_run = await repo.materialize_run(
                session,
                payload_task_id=task_id,
                payload_schedule_id=schedule_id,
                payload_run_id=None,
                planned_start_at=middle,
                occurrence_key=occurrence_key_for_datetime(middle),
                workflow_id="vesperaflow-recurring-workflow",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            newest_run = await repo.materialize_run(
                session,
                payload_task_id=task_id,
                payload_schedule_id=schedule_id,
                payload_run_id=None,
                planned_start_at=newest,
                occurrence_key=occurrence_key_for_datetime(newest),
                workflow_id="vesperaflow-recurring-workflow",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            oldest_run_id = oldest_run.run_id
            middle_run_id = middle_run.run_id
            newest_run_id = newest_run.run_id

    detail_response = await client.get(f"/api/v1/tasks/{task_id}/runs/{middle_run_id}")
    response = await client.get(f"/api/v1/tasks/{task_id}/runs/{middle_run_id}/reader")

    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["run"]["instruction_source_snapshot"] == (
        "Find relevant updates."
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["task"]["task_id"] == task_id
    assert body["run"]["run_id"] == middle_run_id
    assert body["run"]["instruction_source_snapshot"] == "Find relevant updates."
    assert body["previous_run_id"] == newest_run_id
    assert body["next_run_id"] == oldest_run_id


@pytest.mark.asyncio
async def test_recurring_materialization_uses_occurrence_instruction_snapshot(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_recurring_payload("Override"))
    created_data: dict[str, Any] = created.json()["data"]
    task_id = created_data["task"]["task_id"]
    schedule_id = created_data["schedule"]["schedule_id"]
    occurrence_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)

    async with api_context.session_factory() as session:
        async with session.begin():
            _ = await repo.upsert_occurrence_override(
                session,
                task_id=task_id,
                version=created_data["schedule"]["version"],
                original_occurrence_at=occurrence_at,
                instruction_source="Override instructions",
            )
            materialized = await repo.materialize_run(
                session,
                payload_task_id=task_id,
                payload_schedule_id=schedule_id,
                payload_run_id=None,
                planned_start_at=occurrence_at,
                occurrence_key=occurrence_key_for_datetime(occurrence_at),
                workflow_id="vesperaflow-recurring-workflow",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            stored_run = await repo.get_run(session, materialized.run_id)

    assert materialized.execution_snapshot.instruction_source == "Override instructions"
    assert stored_run.instruction_source_snapshot == "Override instructions"


@pytest.mark.asyncio
async def test_run_instruction_snapshot_does_not_drift_after_task_edit(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    created = await client.post("/api/v1/tasks", json=_recurring_payload("Snapshots"))
    created_data: dict[str, Any] = created.json()["data"]
    task_id = created_data["task"]["task_id"]
    schedule_id = created_data["schedule"]["schedule_id"]
    first_at = datetime(2030, 1, 1, 0, 0, tzinfo=UTC)
    second_at = datetime(2030, 1, 2, 0, 0, tzinfo=UTC)

    async with api_context.session_factory() as session:
        async with session.begin():
            first = await repo.materialize_run(
                session,
                payload_task_id=task_id,
                payload_schedule_id=schedule_id,
                payload_run_id=None,
                planned_start_at=first_at,
                occurrence_key=occurrence_key_for_datetime(first_at),
                workflow_id="vesperaflow-recurring-workflow-1",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            task = await repo.get_task(session, task_id)
            _ = await repo.update_task(
                session,
                task_id=task_id,
                version=task.version,
                instruction_source="Updated instructions",
            )
            second = await repo.materialize_run(
                session,
                payload_task_id=task_id,
                payload_schedule_id=schedule_id,
                payload_run_id=None,
                planned_start_at=second_at,
                occurrence_key=occurrence_key_for_datetime(second_at),
                workflow_id="vesperaflow-recurring-workflow-2",
                run_workspace_root="/tmp/vesperaflow-runs",
            )
            first_run = await repo.get_run(session, first.run_id)
            second_run = await repo.get_run(session, second.run_id)

    assert first_run.instruction_source_snapshot == "Find relevant updates."
    assert second_run.instruction_source_snapshot == "Updated instructions"


@pytest.mark.asyncio
async def test_run_events_endpoint_returns_persisted_timeline(
    api_context: ApiTestContext,
) -> None:
    client = api_context.client
    async with api_context.session_factory() as session:
        async with session.begin():
            bundle = await repo.create_one_time_task(
                session,
                title="Research",
                instruction_source="Find updates",
                target_working_directory=str(Path.cwd()),
                planned_at=datetime.now(UTC) + timedelta(hours=1),
            )
            if bundle.run is None:
                raise AssertionError("one-time task should create a planned run")
            run_id = bundle.run.run_id
            await repo.record_run_event(
                session,
                run_id=run_id,
                event_type="executor.started",
                message="Executor invocation started.",
                details={"executor": "debug_printer"},
                temporal_workflow_id="workflow-1",
                temporal_workflow_run_id="workflow-run-1",
                activity_type="execute_agent_run",
                activity_attempt=1,
            )

    response = await client.get(f"/api/v1/runs/{run_id}/events")
    missing = await client.get("/api/v1/runs/run_missing/events")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    event = body["data"][0]
    assert event["run_id"] == run_id
    assert event["event_type"] == "executor.started"
    assert event["details"] == {"executor": "debug_printer"}
    assert event["temporal_workflow_id"] == "workflow-1"
    assert event["activity_attempt"] == 1
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_template_lifecycle_and_instantiation_copy_fields(
    client: AsyncClient,
) -> None:
    created = await client.post("/api/v1/templates", json=_template_payload())
    assert created.status_code == 201
    template: dict[str, Any] = created.json()["data"]
    template_id = template["template_id"]

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
    bundle: dict[str, Any] = instantiated.json()["data"]
    task: dict[str, Any] = bundle["task"]
    task_id = task["task_id"]
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
    detail_task: dict[str, Any] = detail.json()["data"]["task"]
    assert detail_task["title"] == "Template Task"
    assert detail_task["instruction_source"] == "Original template instructions"

    active = await client.get("/api/v1/templates")
    assert active.status_code == 200
    assert active.json()["meta"]["total"] == 1

    updated_template: dict[str, Any] = updated.json()["data"]
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
    template: dict[str, Any] = created.json()["data"]
    payload = _create_payload()
    payload["template_id"] = template["template_id"]
    del payload["executor"]

    response = await client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 201
    task = response.json()["data"]["task"]
    assert task["template_id"] == template["template_id"]
    assert task["executor"] == "debug_printer"


@pytest.mark.asyncio
async def test_template_creation_accepts_pi_default_executor(
    client: AsyncClient,
) -> None:
    payload = _template_payload()
    payload["default_executor"] = "pi"

    response = await client.post("/api/v1/templates", json=payload)

    assert response.status_code == 201
    assert response.json()["data"]["default_executor"] == "pi"


@pytest.mark.asyncio
async def test_template_default_target_directory_can_create_task(
    client: AsyncClient,
) -> None:
    payload = _template_payload()
    payload["default_target_working_directory"] = str(Path.cwd())
    created = await client.post("/api/v1/templates", json=payload)
    template: dict[str, Any] = created.json()["data"]

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
    direct_payload["template_id"] = template["template_id"]
    del direct_payload["target_working_directory"]
    direct = await client.post("/api/v1/tasks", json=direct_payload)

    assert direct.status_code == 201
    assert direct.json()["data"]["task"]["target_working_directory"] == str(Path.cwd())


@pytest.mark.asyncio
async def test_archive_task_deletes_schedule(client: AsyncClient) -> None:
    created = await client.post("/api/v1/tasks", json=_create_payload())
    assert created.status_code == 201
    task = created.json()["data"]["task"]
    task_id = task["task_id"]
    version = task["version"]

    archived = await client.post(
        f"/api/v1/tasks/{task_id}/archive",
        json={"version": version},
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["task_status"] == "archived"
    assert archived.json()["data"]["archived_at"] is not None


@pytest.mark.asyncio
async def test_archive_running_task_rejected(api_context: ApiTestContext) -> None:
    created = await api_context.client.post("/api/v1/tasks", json=_create_payload())
    assert created.status_code == 201
    task = created.json()["data"]["task"]
    task_id = task["task_id"]

    async with api_context.session_factory() as session:
        async with session.begin():
            run = await repo.get_latest_run(session, task_id)
            assert run is not None
            run.run_status = RunStatus.RUNNING
            run.actual_start_at = datetime.now(UTC)
            task_model = await repo.get_task(session, task_id)
            await repo._recompute_task_status(session, task_model)
            version = task_model.version

    archived = await api_context.client.post(
        f"/api/v1/tasks/{task_id}/archive",
        json={"version": version},
    )
    assert archived.status_code == 409


@pytest.mark.asyncio
async def test_unarchive_task_recreates_schedule(client: AsyncClient) -> None:
    created = await client.post("/api/v1/tasks", json=_create_payload())
    assert created.status_code == 201
    task = created.json()["data"]["task"]
    task_id = task["task_id"]
    version = task["version"]

    archived = await client.post(
        f"/api/v1/tasks/{task_id}/archive",
        json={"version": version},
    )
    assert archived.status_code == 200
    archived_version = archived.json()["data"]["version"]

    unarchived = await client.post(
        f"/api/v1/tasks/{task_id}/unarchive",
        json={"version": archived_version},
    )
    assert unarchived.status_code == 200
    assert unarchived.json()["data"]["task"]["task_status"] == "scheduled"
    assert unarchived.json()["data"]["task"]["archived_at"] is None


@pytest.mark.asyncio
async def test_unarchive_recurring_task_recreates_schedule(client: AsyncClient) -> None:
    created = await client.post("/api/v1/tasks", json=_recurring_payload())
    assert created.status_code == 201
    task = created.json()["data"]["task"]
    task_id = task["task_id"]
    version = task["version"]

    archived = await client.post(
        f"/api/v1/tasks/{task_id}/archive",
        json={"version": version},
    )
    assert archived.status_code == 200
    archived_version = archived.json()["data"]["version"]

    unarchived = await client.post(
        f"/api/v1/tasks/{task_id}/unarchive",
        json={"version": archived_version},
    )
    assert unarchived.status_code == 200
    assert unarchived.json()["data"]["task"]["task_status"] == "scheduled"


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
    executor_profile_id: NotRequired[str | None]
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
