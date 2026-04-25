import asyncio
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from vesperaflow_core import ExecutionSnapshot, ExecutorName, RunStatus
from vesperaflow_worker.executors import (
    ExecutorUnavailableError,
)
from vesperaflow_worker.executors import (
    claude_code as claude_code_module,
)
from vesperaflow_worker.executors.claude_code import ClaudeCodeExecutor
from vesperaflow_worker.executors.debug import DebugPrinterExecutor
from vesperaflow_worker.executors.factory import build_executor
from vesperaflow_worker.executors.router import ExecutorRouter


def test_worker_package_and_workflows_do_not_import_claude_sdk() -> None:
    env = os.environ.copy()
    pythonpath = os.pathsep.join(
        [
            str(Path.cwd() / "packages/core/src"),
            str(Path.cwd() / "apps/worker/src"),
            env.get("PYTHONPATH", ""),
        ]
    )
    env["PYTHONPATH"] = pythonpath
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib, json, sys; "
                "import vesperaflow_worker; "
                "root_loaded = 'claude_agent_sdk' in sys.modules; "
                "importlib.import_module('vesperaflow_worker.workflows'); "
                "print(json.dumps({"
                "'root_loaded': root_loaded, "
                "'workflow_loaded': 'claude_agent_sdk' in sys.modules"
                "}))"
            ),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    loaded = json.loads(check.stdout.strip().splitlines()[-1])

    assert loaded == {"root_loaded": False, "workflow_loaded": False}


@pytest.mark.asyncio
async def test_debug_printer_executor_logs_snapshot(
    snapshot: ExecutionSnapshot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    debug_snapshot = snapshot.model_copy(
        update={"executor": ExecutorName.DEBUG_PRINTER}
    )
    caplog.set_level("INFO")

    outcome = await DebugPrinterExecutor().execute(debug_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "debug_printer_completed"
    assert outcome.result_summary == (
        "Debug printer completed run run_123 for task task_123."
    )
    assert debug_snapshot.model_dump_json() in caplog.text


@pytest.mark.asyncio
async def test_executor_router_dispatches_debug_printer(
    snapshot: ExecutionSnapshot,
) -> None:
    debug_snapshot = snapshot.model_copy(
        update={"executor": ExecutorName.DEBUG_PRINTER}
    )
    executor = build_executor("auto")

    outcome = await executor.execute(debug_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "debug_printer_completed"


def test_executor_factory_builds_claude_code_without_function_body_import() -> None:
    executor = build_executor("claude_code")
    source = inspect.getsource(build_executor)

    assert isinstance(executor, ClaudeCodeExecutor)
    assert "from .claude_code import" not in source


@pytest.mark.asyncio
async def test_executor_router_rejects_unknown_executor(
    snapshot: ExecutionSnapshot,
) -> None:
    router = ExecutorRouter(
        claude_code=DebugPrinterExecutor(),
        debug_printer=DebugPrinterExecutor(),
    )
    invalid_snapshot = snapshot.model_copy(update={"executor": "unknown"})

    with pytest.raises(ExecutorUnavailableError, match="unknown executor"):
        _ = await router.execute(invalid_snapshot)


@pytest.mark.asyncio
async def test_claude_code_executor_runs_sdk_and_writes_artifact(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = _fake_sdk(
        [
            AssistantMessage([TextBlock("Working...")]),
            ResultMessage(result="Done from Claude"),
        ],
        monkeypatch=monkeypatch,
    )
    executor = ClaudeCodeExecutor(max_turns=3, max_budget_usd=0.25)
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    sdk_snapshot = snapshot.model_copy(
        update={
            "working_directory": str(run_dir),
            "target_working_directory": str(target_dir),
        }
    )

    outcome = await executor.execute(sdk_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "claude_code_completed"
    assert outcome.result_summary == "Done from Claude"
    assert outcome.result_artifact_ref is not None
    assert Path(outcome.result_artifact_ref).read_text() == "Working..."
    assert sdk.options.kwargs["cwd"] == str(target_dir)
    assert sdk.options.kwargs["permission_mode"] == "bypassPermissions"
    assert sdk.options.kwargs["setting_sources"] == ["user", "project", "local"]
    assert sdk.options.kwargs["max_turns"] == 3
    assert sdk.options.kwargs["max_budget_usd"] == 0.25
    assert sdk.clients[0].prompt == "Do work"


@pytest.mark.asyncio
async def test_claude_code_executor_rejects_invalid_workspace(
    snapshot: ExecutionSnapshot,
) -> None:
    outcome = await ClaudeCodeExecutor().execute(
        snapshot.model_copy(
            update={"target_working_directory": "/tmp/does-not-exist-vespera"}
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_workspace_unavailable"


@pytest.mark.asyncio
async def test_claude_code_executor_maps_auth_process_error(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ProcessError(Exception):
        pass

    monkeypatch.setattr(claude_code_module, "ProcessError", ProcessError)
    _fake_sdk(
        [],
        monkeypatch=monkeypatch,
        enter_error=ProcessError("login required"),
    )
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = ClaudeCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(update={"target_working_directory": str(target_dir)})
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_authenticated"


@pytest.mark.asyncio
async def test_claude_code_executor_interrupts_on_cancellation(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = _fake_sdk([], monkeypatch=monkeypatch, cancel_on_receive=True)
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = ClaudeCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(update={"target_working_directory": str(target_dir)})
    )

    assert outcome.terminal_status is RunStatus.CANCELED
    assert outcome.terminal_code == "canceled"
    assert sdk.clients[0].interrupted is True


@pytest.fixture
def snapshot() -> ExecutionSnapshot:
    from datetime import UTC, datetime

    return ExecutionSnapshot(
        run_id="run_123",
        task_id="task_123",
        schedule_id="sch_123",
        executor=ExecutorName.CLAUDE_CODE,
        instruction_source="Do work",
        planned_start_at=datetime.now(UTC),
        working_directory="/tmp/vesperaflow-runs/run_123",
        target_working_directory="/tmp",
    )


class TextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class AssistantMessage:
    def __init__(self, content: list[TextBlock]) -> None:
        self.content = content


class ResultMessage:
    def __init__(
        self,
        *,
        result: str | None = None,
        is_error: bool = False,
        subtype: str = "success",
    ) -> None:
        self.result = result
        self.is_error = is_error
        self.subtype = subtype
        self.session_id = "session_123"
        self.num_turns = 1
        self.total_cost_usd = 0.01
        self.stop_reason = None


class FakeClaudeAgentOptions:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class FakeClaudeSDKClient:
    def __init__(
        self,
        *,
        options: FakeClaudeAgentOptions,
        messages: list[object],
        clients: list["FakeClaudeSDKClient"],
        enter_error: Exception | None,
        cancel_on_receive: bool,
    ) -> None:
        self.options = options
        self._messages = messages
        self._enter_error = enter_error
        self._cancel_on_receive = cancel_on_receive
        self.prompt: str | None = None
        self.interrupted = False
        clients.append(self)

    async def __aenter__(self) -> "FakeClaudeSDKClient":
        if self._enter_error is not None:
            raise self._enter_error
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def query(self, prompt: str) -> None:
        self.prompt = prompt

    async def receive_response(self):
        if self._cancel_on_receive:
            raise asyncio.CancelledError
        for message in self._messages:
            yield message

    async def interrupt(self) -> None:
        self.interrupted = True


def _fake_sdk(
    messages: list[object],
    *,
    monkeypatch: pytest.MonkeyPatch,
    enter_error: Exception | None = None,
    cancel_on_receive: bool = False,
) -> SimpleNamespace:
    clients: list[FakeClaudeSDKClient] = []

    def client_factory(options: FakeClaudeAgentOptions) -> FakeClaudeSDKClient:
        return FakeClaudeSDKClient(
            options=options,
            messages=messages,
            clients=clients,
            enter_error=enter_error,
            cancel_on_receive=cancel_on_receive,
        )

    sdk = SimpleNamespace(clients=clients, options=None)

    class CapturingOptions(FakeClaudeAgentOptions):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            sdk.options = self

    monkeypatch.setattr(claude_code_module, "ClaudeAgentOptions", CapturingOptions)
    monkeypatch.setattr(claude_code_module, "ClaudeSDKClient", client_factory)
    return sdk
