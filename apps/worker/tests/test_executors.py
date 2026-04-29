import asyncio
import inspect
import json
import os
import signal
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
from vesperaflow_core import ExecutionSnapshot, ExecutorName, RunStatus
from vesperaflow_worker.executors import (
    ExecutorUnavailableError,
)
from vesperaflow_worker.executors import (
    claude_code as claude_code_module,
)
from vesperaflow_worker.executors.claude_code import ClaudeCodeExecutor
from vesperaflow_worker.executors.codex_cli import CodexExecutor
from vesperaflow_worker.executors.debug import DebugPrinterExecutor
from vesperaflow_worker.executors.factory import build_executor
from vesperaflow_worker.executors.kimi_code import KimiCodeExecutor
from vesperaflow_worker.executors.router import ExecutorRouter
from vesperaflow_worker.settings import DEFAULT_CLAUDE_ENV, WorkerSettings


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

    loaded: dict[str, bool] = json.loads(
        check.stdout.strip().splitlines()[-1],
    )

    assert loaded == {"root_loaded": False, "workflow_loaded": False}


def test_worker_package_and_workflows_do_not_import_kimi_code_module() -> None:
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
                "mod = 'vesperaflow_worker.executors.kimi_code'; "
                "root_loaded = mod in sys.modules; "
                "importlib.import_module('vesperaflow_worker.workflows'); "
                "print(json.dumps({"
                "'root_loaded': root_loaded, "
                "'workflow_loaded': mod in sys.modules"
                "}))"
            ),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    loaded: dict[str, bool] = json.loads(
        check.stdout.strip().splitlines()[-1],
    )

    assert loaded == {"root_loaded": False, "workflow_loaded": False}


def test_worker_package_and_workflows_do_not_import_codex_cli_module() -> None:
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
                "mod = 'vesperaflow_worker.executors.codex_cli'; "
                "root_loaded = mod in sys.modules; "
                "importlib.import_module('vesperaflow_worker.workflows'); "
                "print(json.dumps({"
                "'root_loaded': root_loaded, "
                "'workflow_loaded': mod in sys.modules"
                "}))"
            ),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    loaded: dict[str, bool] = json.loads(
        check.stdout.strip().splitlines()[-1],
    )

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


def test_executor_factory_passes_claude_env() -> None:
    executor = build_executor(
        "claude_code",
        claude_env={
            "ANTHROPIC_API_KEY": "sk-test",
            "ANTHROPIC_BASE_URL": "https://proxy.example.com/v1",
            "ANTHROPIC_MODEL": "claude-sonnet-4-5",
        },
    )

    assert isinstance(executor, ClaudeCodeExecutor)
    assert executor.env == {
        "ANTHROPIC_API_KEY": "sk-test",
        "ANTHROPIC_BASE_URL": "https://proxy.example.com/v1",
        "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    }


def test_worker_settings_builds_claude_executor_env() -> None:
    settings = WorkerSettings.model_validate(
        {
            "database_url": "postgresql+asyncpg://test@localhost/test",
            "ANTHROPIC_API_KEY": "sk-test",
            "ANTHROPIC_BASE_URL": "https://proxy.example.com/v1",
            "ANTHROPIC_MODEL": "claude-sonnet-4-5",
        }
    )

    env = settings.claude_executor_env()

    assert env == {
        **DEFAULT_CLAUDE_ENV,
        "ANTHROPIC_API_KEY": "sk-test",
        "ANTHROPIC_BASE_URL": "https://proxy.example.com/v1",
        "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    }


def test_worker_settings_reads_claude_passthrough_from_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = (tmp_path / ".env").write_text(
        "\n".join(
            [
                "VESPERAFLOW_DATABASE_URL=postgresql+asyncpg://test@localhost/test",
                "ANTHROPIC_API_KEY=sk-dotenv",
                "ANTHROPIC_BASE_URL=https://dotenv-proxy.example.com/v1",
                "ANTHROPIC_MODEL=claude-sonnet-4-5",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VESPERAFLOW_DATABASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    settings = WorkerSettings()

    env = settings.claude_executor_env()

    assert env == {
        **DEFAULT_CLAUDE_ENV,
        "ANTHROPIC_API_KEY": "sk-dotenv",
        "ANTHROPIC_BASE_URL": "https://dotenv-proxy.example.com/v1",
        "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    }


def test_worker_settings_process_env_overrides_dotenv_passthrough(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = (tmp_path / ".env").write_text(
        "\n".join(
            [
                "VESPERAFLOW_DATABASE_URL=postgresql+asyncpg://test@localhost/test",
                "ANTHROPIC_BASE_URL=https://dotenv.example.com/v1",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://process.example.com/v1")
    settings = WorkerSettings()

    env = settings.claude_executor_env()

    assert env["ANTHROPIC_BASE_URL"] == "https://process.example.com/v1"


@pytest.mark.asyncio
async def test_executor_router_rejects_unknown_executor(
    snapshot: ExecutionSnapshot,
) -> None:
    router = ExecutorRouter(
        claude_code=DebugPrinterExecutor(),
        codex=DebugPrinterExecutor(),
        debug_printer=DebugPrinterExecutor(),
        kimi_code=DebugPrinterExecutor(),
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
    executor = ClaudeCodeExecutor(
        env={
            "ANTHROPIC_API_KEY": "sk-test",
            "ANTHROPIC_BASE_URL": "https://proxy.example.com/v1",
            "ANTHROPIC_MODEL": "claude-sonnet-4-5",
        },
    )
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
    options = sdk.options
    assert options is not None
    assert options.kwargs["cwd"] == str(target_dir)
    assert options.kwargs["permission_mode"] == "bypassPermissions"
    assert options.kwargs["setting_sources"] == ["user", "project", "local"]
    assert options.kwargs["env"] == {
        "ANTHROPIC_API_KEY": "sk-test",
        "ANTHROPIC_BASE_URL": "https://proxy.example.com/v1",
        "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    }
    assert sdk.clients[0].prompt == "Do work"


@pytest.mark.asyncio
async def test_claude_code_executor_does_not_truncate_long_result(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_result = "A" * 8000
    _ = _fake_sdk(
        [ResultMessage(result=long_result)],
        monkeypatch=monkeypatch,
    )
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = ClaudeCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.result_summary == long_result


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
    _ = _fake_sdk(
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


def test_executor_factory_builds_kimi_code_without_function_body_import() -> None:
    executor = build_executor("kimi_code")
    source = inspect.getsource(build_executor)

    assert isinstance(executor, KimiCodeExecutor)
    assert "from .kimi_code import" not in source


def test_executor_factory_builds_codex_without_function_body_import() -> None:
    executor = build_executor("codex")
    source = inspect.getsource(build_executor)

    assert isinstance(executor, CodexExecutor)
    assert "from .codex_cli import" not in source


@pytest.mark.asyncio
async def test_executor_router_dispatches_kimi_code(
    snapshot: ExecutionSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    kimi_snapshot = snapshot.model_copy(update={"executor": ExecutorName.KIMI_CODE})
    executor = build_executor("auto")

    outcome = await executor.execute(kimi_snapshot)

    # KimiCodeExecutor fails because 'kimi' binary is not on PATH,
    # but routing must reach it.
    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


@pytest.mark.asyncio
async def test_executor_router_dispatches_codex(
    snapshot: ExecutionSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    codex_snapshot = snapshot.model_copy(update={"executor": ExecutorName.CODEX})
    executor = build_executor("auto")

    outcome = await executor.execute(codex_snapshot)

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


@pytest.mark.asyncio
async def test_kimi_code_executor_runs_subprocess_and_writes_artifact(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    proc = _fake_subprocess(
        stdout_lines=[b"Done from Kimi\n"],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)

    def fake_which(_cmd: str) -> str:
        return "/usr/bin/kimi"

    monkeypatch.setattr("shutil.which", fake_which)
    executor = KimiCodeExecutor()
    kimi_snapshot = snapshot.model_copy(
        update={
            "executor": ExecutorName.KIMI_CODE,
            "working_directory": str(run_dir),
            "target_working_directory": str(target_dir),
        }
    )

    outcome = await executor.execute(kimi_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "kimi_code_completed"
    assert outcome.result_summary == "Done from Kimi"
    assert outcome.result_artifact_ref is not None
    assert Path(outcome.result_artifact_ref).read_text() == "Done from Kimi"
    result = cast(
        dict[str, object],
        json.loads((run_dir / "kimi-result.json").read_text()),
    )
    assert result == {"stdout": "Done from Kimi", "stderr": []}
    args = cast(tuple[str, ...], proc.calls[0]["args"])
    assert args[0].endswith("kimi")
    assert args[1:] == (
        "--print",
        "--final-message-only",
        "--work-dir",
        str(target_dir.resolve()),
        "--yolo",
    )
    assert proc.stdin_data is not None
    assert proc.stdin_data.decode("utf-8") == "Do work\n"


@pytest.mark.asyncio
async def test_kimi_code_executor_rejects_invalid_workspace(
    snapshot: ExecutionSnapshot,
) -> None:
    outcome = await KimiCodeExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.KIMI_CODE,
                "target_working_directory": "/tmp/does-not-exist-vespera",
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_workspace_unavailable"


@pytest.mark.asyncio
async def test_kimi_code_executor_rejects_missing_binary(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = KimiCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.KIMI_CODE,
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


@pytest.mark.asyncio
async def test_kimi_code_executor_maps_nonzero_exit_to_failure(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[],
        stderr_lines=[b"kimi: error: api key invalid\n"],
        returncode=1,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/kimi")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = KimiCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.KIMI_CODE,
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_authenticated"


@pytest.mark.asyncio
async def test_kimi_code_executor_cancels_on_cancelled_error(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[],
        cancel_on_stdout=True,
        returncode=-signal.SIGINT,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/kimi")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = KimiCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.KIMI_CODE,
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.CANCELED
    assert outcome.terminal_code == "canceled"


@pytest.mark.asyncio
async def test_codex_executor_runs_subprocess_and_writes_artifacts(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    proc = _fake_subprocess(
        stdout_lines=[
            b'{"msg":"turn.started"}\n',
            b'{"msg":"agent_message","message":"Done from Codex"}\n',
        ],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/codex")
    executor = CodexExecutor()
    codex_snapshot = snapshot.model_copy(
        update={
            "executor": ExecutorName.CODEX,
            "working_directory": str(run_dir),
            "target_working_directory": str(target_dir),
        }
    )

    outcome = await executor.execute(codex_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "codex_completed"
    assert outcome.result_summary == "Done from Codex"
    assert outcome.result_artifact_ref == str(run_dir / "codex-last-message.txt")
    assert (run_dir / "codex-last-message.txt").read_text() == "Done from Codex"
    assert (run_dir / "codex-events.jsonl").read_text() == (
        '{"msg":"turn.started"}\n'
        '{"msg":"agent_message","message":"Done from Codex"}\n'
    )
    assert (run_dir / "codex-stderr.txt").read_text() == ""
    args = cast(tuple[str, ...], proc.calls[0]["args"])
    assert args[0].endswith("codex")
    assert args[1:] == (
        "exec",
        "--json",
        "--output-last-message",
        str(run_dir / "codex-last-message.txt"),
        "--skip-git-repo-check",
        "-C",
        str(target_dir.resolve()),
        "--sandbox",
        "workspace-write",
        "-",
    )
    assert proc.stdin_data is not None
    assert proc.stdin_data.decode("utf-8") == "Do work\n"


@pytest.mark.asyncio
async def test_codex_executor_rejects_invalid_workspace(
    snapshot: ExecutionSnapshot,
) -> None:
    outcome = await CodexExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.CODEX,
                "target_working_directory": "/tmp/does-not-exist-vespera",
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_workspace_unavailable"


@pytest.mark.asyncio
async def test_codex_executor_rejects_missing_binary(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = CodexExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.CODEX,
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


@pytest.mark.asyncio
async def test_codex_executor_maps_nonzero_auth_exit_to_failure(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[],
        stderr_lines=[b"codex: login required\n"],
        returncode=1,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/codex")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = CodexExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.CODEX,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_authenticated"
    assert (tmp_path / "run" / "codex-stderr.txt").read_text() == (
        "codex: login required\n"
    )


@pytest.mark.asyncio
async def test_codex_executor_maps_turn_failed_jsonl_to_failure(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[
            b'{"msg":"turn.started"}\n',
            b'{"msg":"turn.failed","error":{"message":"model unavailable"}}\n',
        ],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/codex")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = CodexExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.CODEX,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_error"
    assert outcome.failure_reason == "model unavailable"


@pytest.mark.asyncio
async def test_codex_executor_cancels_on_cancelled_error(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[],
        cancel_on_stdout=True,
        returncode=-signal.SIGINT,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/codex")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = CodexExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.CODEX,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.CANCELED
    assert outcome.terminal_code == "canceled"


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
        self.text: str = text


class AssistantMessage:
    def __init__(self, content: list[TextBlock]) -> None:
        self.content: list[TextBlock] = content


class ResultMessage:
    def __init__(
        self,
        *,
        result: str | None = None,
        is_error: bool = False,
        subtype: str = "success",
    ) -> None:
        self.result: str | None = result
        self.is_error: bool = is_error
        self.subtype: str = subtype
        self.session_id: str = "session_123"
        self.num_turns: int = 1
        self.total_cost_usd: float = 0.01
        self.stop_reason: str | None = None


class FakeClaudeAgentOptions:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs: dict[str, object] = kwargs


class FakeSDKHarness:
    def __init__(self) -> None:
        self.clients: list[FakeClaudeSDKClient] = []
        self.options: FakeClaudeAgentOptions | None = None


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
        self.options: FakeClaudeAgentOptions = options
        self._messages: list[object] = messages
        self._enter_error: Exception | None = enter_error
        self._cancel_on_receive: bool = cancel_on_receive
        self.prompt: str | None = None
        self.interrupted: bool = False
        clients.append(self)

    async def __aenter__(self) -> "FakeClaudeSDKClient":
        if self._enter_error is not None:
            raise self._enter_error
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def query(self, prompt: str) -> None:
        self.prompt = prompt

    async def receive_response(self) -> AsyncIterator[object]:
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
) -> FakeSDKHarness:
    sdk = FakeSDKHarness()

    def client_factory(options: FakeClaudeAgentOptions) -> FakeClaudeSDKClient:
        return FakeClaudeSDKClient(
            options=options,
            messages=messages,
            clients=sdk.clients,
            enter_error=enter_error,
            cancel_on_receive=cancel_on_receive,
        )

    class CapturingOptions(FakeClaudeAgentOptions):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            sdk.options = self

    monkeypatch.setattr(
        claude_code_module,
        "ClaudeAgentOptions",
        CapturingOptions,
    )
    monkeypatch.setattr(
        claude_code_module,
        "ClaudeSDKClient",
        client_factory,
    )
    return sdk


class FakeStreamWriter:
    def __init__(self) -> None:
        self._data: list[bytes] = []

    def write(self, data: bytes) -> None:
        self._data.append(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    @property
    def data(self) -> bytes:
        return b"".join(self._data)


class FakeStreamReader:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = iter(lines)

    async def readline(self) -> bytes:
        try:
            return next(self._lines)
        except StopIteration:
            return b""


class FakeCancellingStreamReader(FakeStreamReader):
    async def readline(self) -> bytes:
        raise asyncio.CancelledError


class FakeSubprocess:
    def __init__(
        self,
        *,
        stdout_lines: list[bytes],
        stderr_lines: list[bytes] | None = None,
        returncode: int = 0,
        cancel_on_stdout: bool = False,
    ) -> None:
        self.stdout_lines = stdout_lines
        self.stderr_lines = stderr_lines or []
        self._returncode = returncode
        self.cancel_on_stdout = cancel_on_stdout
        self.calls: list[dict[str, object]] = []
        self.stdin: FakeStreamWriter | None = None
        self.stdout: FakeStreamReader | None = None
        self.stderr: FakeStreamReader | None = None
        self.pid = 12345

    @property
    def returncode(self) -> int | None:
        return self._returncode

    async def wait(self) -> int:
        return self._returncode

    @property
    def stdin_data(self) -> bytes | None:
        return self.stdin.data if self.stdin is not None else None

    async def _factory(
        self,
        *args: str,
        **kwargs: object,
    ) -> "FakeSubprocess":
        self.calls.append({"args": args, "kwargs": kwargs})
        self.stdin = FakeStreamWriter()
        if self.cancel_on_stdout:
            self.stdout = FakeCancellingStreamReader(self.stdout_lines)
        else:
            self.stdout = FakeStreamReader(self.stdout_lines)
        self.stderr = FakeStreamReader(self.stderr_lines)
        returncode = kwargs.get("returncode")
        if isinstance(returncode, int):
            self._returncode = returncode
        return self

    @property
    def factory(self) -> "FakeSubprocessFactory":
        return FakeSubprocessFactory(self)


class FakeSubprocessFactory:
    def __init__(self, proc: FakeSubprocess) -> None:
        self._proc = proc

    async def __call__(self, *args: str, **kwargs: object) -> FakeSubprocess:
        return await self._proc._factory(*args, **kwargs)


def _fake_subprocess(
    *,
    stdout_lines: list[bytes],
    stderr_lines: list[bytes] | None = None,
    returncode: int = 0,
    cancel_on_stdout: bool = False,
) -> FakeSubprocess:
    return FakeSubprocess(
        stdout_lines=stdout_lines,
        stderr_lines=stderr_lines,
        returncode=returncode,
        cancel_on_stdout=cancel_on_stdout,
    )
