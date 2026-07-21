import asyncio
import json
import os
import signal
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast, override

import pytest
from vesperaflow_core import ExecutionSnapshot, ExecutorName, RunStatus
from vesperaflow_worker.executors import (
    ExecutorUnavailableError,
)
from vesperaflow_worker.executors import (
    claude_code as claude_code_module,
)
from vesperaflow_worker.executors import (
    codex_cli as codex_cli_module,
)
from vesperaflow_worker.executors import (
    opencode_cli as opencode_cli_module,
)
from vesperaflow_worker.executors import (
    pi as pi_module,
)
from vesperaflow_worker.executors.base import (
    ExecutorRuntimeConfig,
    build_subprocess_environment,
)
from vesperaflow_worker.executors.claude_code import (
    DEFAULT_CLAUDE_ENV,
    ClaudeCodeExecutor,
)
from vesperaflow_worker.executors.codex_cli import CodexExecutor
from vesperaflow_worker.executors.debug import DebugPrinterExecutor
from vesperaflow_worker.executors.factory import build_executor
from vesperaflow_worker.executors.opencode_cli import OpenCodeExecutor
from vesperaflow_worker.executors.pi import PiExecutor
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

    loaded: dict[str, bool] = json.loads(
        check.stdout.strip().splitlines()[-1],
    )

    assert loaded == {"root_loaded": False, "workflow_loaded": False}


def test_subprocess_environment_does_not_inherit_worker_secrets() -> None:
    env = build_subprocess_environment(
        ExecutorRuntimeConfig(env={"OPENAI_API_KEY": "profile-key"}),
        environ={
            "HOME": "/Users/test",
            "PATH": "/usr/bin",
            "VESPERAFLOW_DATABASE_URL": "postgresql://secret",
            "UNRELATED_SECRET": "hidden",
            "OPENAI_API_KEY": "ambient-key",
        },
    )

    assert env == {
        "HOME": "/Users/test",
        "PATH": "/usr/bin",
        "OPENAI_API_KEY": "profile-key",
    }


def _fake_codex_binary(_cmd: str) -> str:
    return "/usr/bin/codex"


def _fake_pi_binary(_cmd: str) -> str:
    return "/usr/bin/pi"


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


def test_worker_package_and_workflows_do_not_import_opencode_cli_module() -> None:
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
                "mod = 'vesperaflow_worker.executors.opencode_cli'; "
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


def test_worker_package_and_workflows_do_not_import_pi_module() -> None:
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
                "mod = 'vesperaflow_worker.executors.pi'; "
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
async def test_debug_printer_executor_logs_metadata_without_instruction(
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
    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "debug_printer_execution"
    )
    assert getattr(record, "run_id", None) == "run_123"
    assert getattr(record, "task_id", None) == "task_123"
    assert debug_snapshot.instruction_source not in caplog.text


@pytest.mark.asyncio
async def test_executor_router_dispatches_debug_printer(
    snapshot: ExecutionSnapshot,
) -> None:
    debug_snapshot = snapshot.model_copy(
        update={"executor": ExecutorName.DEBUG_PRINTER}
    )
    executor = build_executor()

    outcome = await executor.execute(debug_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "debug_printer_completed"


def test_executor_factory_builds_router_with_all_adapters() -> None:
    executor = build_executor()

    assert isinstance(executor, ExecutorRouter)
    assert isinstance(executor.claude_code, ClaudeCodeExecutor)
    assert isinstance(executor.codex, CodexExecutor)
    assert isinstance(executor.debug_printer, DebugPrinterExecutor)
    assert isinstance(executor.opencode, OpenCodeExecutor)
    assert isinstance(executor.pi, PiExecutor)


def test_executor_factory_uses_claude_runtime_defaults() -> None:
    executor = build_executor()

    assert isinstance(executor, ExecutorRouter)
    assert isinstance(executor.claude_code, ClaudeCodeExecutor)
    assert executor.claude_code.env == DEFAULT_CLAUDE_ENV


@pytest.mark.asyncio
async def test_executor_router_rejects_unknown_executor(
    snapshot: ExecutionSnapshot,
) -> None:
    router = ExecutorRouter(
        claude_code=DebugPrinterExecutor(),
        codex=DebugPrinterExecutor(),
        debug_printer=DebugPrinterExecutor(),
        opencode=DebugPrinterExecutor(),
        pi=DebugPrinterExecutor(),
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


@pytest.mark.asyncio
async def test_executor_router_dispatches_codex(
    snapshot: ExecutionSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    codex_snapshot = snapshot.model_copy(update={"executor": ExecutorName.CODEX})
    executor = build_executor()

    outcome = await executor.execute(codex_snapshot)

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


@pytest.mark.asyncio
async def test_executor_router_dispatches_opencode(
    snapshot: ExecutionSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    opencode_snapshot = snapshot.model_copy(update={"executor": ExecutorName.OPENCODE})
    executor = build_executor()

    outcome = await executor.execute(opencode_snapshot)

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


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
    monkeypatch.setattr("shutil.which", _fake_codex_binary)
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
        '{"msg":"turn.started"}\n{"msg":"agent_message","message":"Done from Codex"}\n'
    )
    assert (run_dir / "codex-stderr.txt").read_text() == ""
    args = cast(tuple[str, ...], proc.calls[0]["args"])
    kwargs = cast(dict[str, object], proc.calls[0]["kwargs"])
    assert args[0].endswith("codex")
    assert args[1:] == (
        "exec",
        "--json",
        "--output-last-message",
        str(run_dir / "codex-last-message.txt"),
        "--skip-git-repo-check",
        "-C",
        str(target_dir.resolve()),
        "--dangerously-bypass-approvals-and-sandbox",
        "-",
    )
    assert "--model" not in args
    assert "model_reasoning_effort" not in " ".join(args)
    assert kwargs["limit"] == 1024 * 1024
    assert proc.stdin_data is not None
    assert proc.stdin_data.decode("utf-8") == "Do work\n"


@pytest.mark.asyncio
async def test_claude_code_executor_passes_runtime_reasoning_effort(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = _fake_sdk([ResultMessage(result="OK")], monkeypatch=monkeypatch)
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = ClaudeCodeExecutor(env=None)
    runtime_config = ExecutorRuntimeConfig(
        default_model="claude-sonnet-4-5",
        reasoning_level="high",
        env={"ANTHROPIC_API_KEY": "sk-test"},
    )

    outcome = await executor.execute(
        snapshot.model_copy(update={"target_working_directory": str(target_dir)}),
        runtime_config,
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    options = sdk.options
    assert options is not None
    assert options.kwargs["effort"] == "high"
    assert options.kwargs["env"] == {
        "ANTHROPIC_API_KEY": "sk-test",
        "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    }


@pytest.mark.asyncio
async def test_codex_executor_passes_runtime_profile_model(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    proc = _fake_subprocess(
        stdout_lines=[b'{"msg":"agent_message","message":"Done from Codex"}\n'],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", _fake_codex_binary)
    executor = CodexExecutor()
    runtime_config = ExecutorRuntimeConfig(
        default_model="gpt-5.2",
        reasoning_level="high",
    )

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.CODEX,
                "working_directory": str(run_dir),
                "target_working_directory": str(target_dir),
            }
        ),
        runtime_config,
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    args = cast(tuple[str, ...], proc.calls[0]["args"])
    assert args[1:] == (
        "exec",
        "--json",
        "--output-last-message",
        str(run_dir / "codex-last-message.txt"),
        "--skip-git-repo-check",
        "-C",
        str(target_dir.resolve()),
        "--model",
        "gpt-5.2",
        "-c",
        'model_reasoning_effort="high"',
        "--dangerously-bypass-approvals-and-sandbox",
        "-",
    )


@pytest.mark.asyncio
async def test_codex_executor_captures_long_jsonl_line(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    long_message = "x" * 70_000
    proc = _fake_subprocess(
        stdout_lines=[
            json.dumps({"msg": "agent_message", "message": long_message}).encode()
            + b"\n",
        ],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", _fake_codex_binary)

    outcome = await CodexExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.CODEX,
                "working_directory": str(run_dir),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.result_summary == long_message
    assert json.loads((run_dir / "codex-events.jsonl").read_text()) == {
        "msg": "agent_message",
        "message": long_message,
    }


@pytest.mark.asyncio
async def test_codex_executor_truncates_oversized_jsonl_line_and_continues(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    monkeypatch.setattr(codex_cli_module, "_MAX_CAPTURED_LINE_BYTES", 64)
    proc = _fake_subprocess(
        stdout_lines=[
            b'{"type":"large","payload":"' + (b"x" * 80) + b'"}\n',
            b'{"msg":"agent_message","message":"Recovered"}\n',
        ],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", _fake_codex_binary)

    outcome = await CodexExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.CODEX,
                "working_directory": str(run_dir),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.result_summary == "Recovered"
    artifact_lines = (run_dir / "codex-events.jsonl").read_text().splitlines()
    assert json.loads(artifact_lines[0]) == {
        "type": "executor.stream_line_truncated",
        "stream": "stdout",
        "captured_bytes": 64,
        "truncated_bytes": 45,
    }
    assert json.loads(artifact_lines[1]) == {
        "msg": "agent_message",
        "message": "Recovered",
    }


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
    monkeypatch.setattr("shutil.which", _fake_codex_binary)
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
    monkeypatch.setattr("shutil.which", _fake_codex_binary)
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
    monkeypatch.setattr("shutil.which", _fake_codex_binary)
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


@pytest.mark.asyncio
async def test_codex_executor_timeout_bounds_stream_reads(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[b'{"msg":"agent_message","message":"partial"}\n'],
        stderr_lines=[b"still running\n"],
        returncode=None,
        hang_streams=True,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", _fake_codex_binary)
    monkeypatch.setattr(codex_cli_module, "_DEFAULT_SUBPROCESS_TIMEOUT", 0.01)
    monkeypatch.setattr(codex_cli_module, "_kill_proc", lambda _proc: None)
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    outcome = await asyncio.wait_for(
        CodexExecutor().execute(
            snapshot.model_copy(
                update={
                    "executor": ExecutorName.CODEX,
                    "working_directory": str(tmp_path / "run"),
                    "target_working_directory": str(target_dir),
                }
            )
        ),
        timeout=0.2,
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.failure_reason == "Codex CLI process did not exit within timeout"


@pytest.mark.asyncio
async def test_executor_router_dispatches_pi(
    snapshot: ExecutionSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    pi_snapshot = snapshot.model_copy(update={"executor": ExecutorName.PI})
    executor = build_executor()

    outcome = await executor.execute(pi_snapshot)

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


@pytest.mark.asyncio
async def test_opencode_executor_runs_subprocess_and_writes_artifacts(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    proc = _fake_subprocess(
        stdout_lines=[
            b'{"type":"step_start","part":{"id":"step-1"}}\n',
            b'{"type":"text","part":{"text":"Done from OpenCode"}}\n',
        ],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/opencode")
    executor = OpenCodeExecutor()
    opencode_snapshot = snapshot.model_copy(
        update={
            "executor": ExecutorName.OPENCODE,
            "working_directory": str(run_dir),
            "target_working_directory": str(target_dir),
        }
    )

    outcome = await executor.execute(opencode_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "opencode_completed"
    assert outcome.result_summary == "Done from OpenCode"
    assert outcome.result_artifact_ref == str(run_dir / "opencode-result.txt")
    assert (run_dir / "opencode-result.txt").read_text() == "Done from OpenCode"
    assert (run_dir / "opencode-events.jsonl").read_text() == (
        '{"type":"step_start","part":{"id":"step-1"}}\n'
        '{"type":"text","part":{"text":"Done from OpenCode"}}\n'
    )
    assert (run_dir / "opencode-stderr.txt").read_text() == ""
    args = cast(tuple[str, ...], proc.calls[0]["args"])
    assert args[0].endswith("opencode")
    assert args[1:] == (
        "run",
        "--format",
        "json",
        "--dir",
        str(target_dir.resolve()),
        "--dangerously-skip-permissions",
        "--title",
        "run_123",
    )
    assert "--model" not in args
    assert "--variant" not in args
    assert proc.stdin_data is not None
    assert proc.stdin_data.decode("utf-8") == "Do work\n"


@pytest.mark.asyncio
async def test_opencode_executor_passes_runtime_profile_model(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    proc = _fake_subprocess(
        stdout_lines=[b'{"type":"text","part":{"text":"Done from OpenCode"}}\n'],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/opencode")
    executor = OpenCodeExecutor()
    runtime_config = ExecutorRuntimeConfig(
        default_model="anthropic/claude-sonnet-4-5",
        reasoning_level="high",
    )

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.OPENCODE,
                "working_directory": str(run_dir),
                "target_working_directory": str(target_dir),
            }
        ),
        runtime_config,
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    args = cast(tuple[str, ...], proc.calls[0]["args"])
    assert args[1:] == (
        "run",
        "--format",
        "json",
        "--dir",
        str(target_dir.resolve()),
        "--dangerously-skip-permissions",
        "--title",
        "run_123",
        "--model",
        "anthropic/claude-sonnet-4-5",
        "--variant",
        "high",
    )


@pytest.mark.asyncio
async def test_opencode_executor_rejects_invalid_workspace(
    snapshot: ExecutionSnapshot,
) -> None:
    outcome = await OpenCodeExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.OPENCODE,
                "target_working_directory": "/tmp/does-not-exist-vespera",
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_workspace_unavailable"


@pytest.mark.asyncio
async def test_opencode_executor_rejects_missing_binary(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = OpenCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.OPENCODE,
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


@pytest.mark.asyncio
async def test_opencode_executor_maps_nonzero_auth_exit_to_failure(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[],
        stderr_lines=[b"opencode: login required\n"],
        returncode=1,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/opencode")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = OpenCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.OPENCODE,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_authenticated"
    assert (tmp_path / "run" / "opencode-stderr.txt").read_text() == (
        "opencode: login required\n"
    )


@pytest.mark.asyncio
async def test_opencode_executor_maps_error_event_to_failure(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[
            b'{"type":"step_start","part":{"id":"step-1"}}\n',
            b'{"type":"error","error":{"message":"provider unavailable"}}\n',
        ],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/opencode")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = OpenCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.OPENCODE,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_error"
    assert outcome.failure_reason == "provider unavailable"


@pytest.mark.asyncio
async def test_opencode_executor_cancels_on_cancelled_error(
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
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/opencode")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    executor = OpenCodeExecutor()

    outcome = await executor.execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.OPENCODE,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.CANCELED
    assert outcome.terminal_code == "canceled"


@pytest.mark.asyncio
async def test_opencode_executor_timeout_bounds_stream_reads(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[b'{"type":"text","part":{"text":"partial"}}\n'],
        stderr_lines=[b"still running\n"],
        returncode=None,
        hang_streams=True,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/opencode")
    monkeypatch.setattr(opencode_cli_module, "_DEFAULT_SUBPROCESS_TIMEOUT", 0.01)
    monkeypatch.setattr(opencode_cli_module, "_kill_proc", lambda _proc: None)
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    outcome = await asyncio.wait_for(
        OpenCodeExecutor().execute(
            snapshot.model_copy(
                update={
                    "executor": ExecutorName.OPENCODE,
                    "working_directory": str(tmp_path / "run"),
                    "target_working_directory": str(target_dir),
                }
            )
        ),
        timeout=0.2,
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.failure_reason == "OpenCode CLI process did not exit within timeout"


@pytest.mark.asyncio
async def test_pi_executor_runs_subprocess_and_writes_artifacts(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    stdout_events: list[object] = [
        {"type": "session", "version": 3},
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "Done "},
        },
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "from Pi"},
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Done from Pi"}],
                "stopReason": "stop",
            },
        },
    ]
    proc = _fake_subprocess(
        stdout_lines=[_json_line_bytes(event) for event in stdout_events],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", _fake_pi_binary)
    executor = PiExecutor()
    pi_snapshot = snapshot.model_copy(
        update={
            "executor": ExecutorName.PI,
            "working_directory": str(run_dir),
            "target_working_directory": str(target_dir),
        }
    )

    outcome = await executor.execute(pi_snapshot)

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "pi_completed"
    assert outcome.result_summary == "Done from Pi"
    assert outcome.result_artifact_ref == str(run_dir / "pi-result.txt")
    assert (run_dir / "pi-result.txt").read_text() == "Done from Pi"
    assert (run_dir / "pi-events.jsonl").read_text() == (
        _json_lines_excluding_event_types(stdout_events, {"message_update"})
    )
    assert not (run_dir / "pi-raw-events.jsonl").exists()
    assert (run_dir / "pi-stderr.txt").read_text() == ""
    assert (run_dir / "pi-sessions").is_dir()
    args = cast(tuple[str, ...], proc.calls[0]["args"])
    kwargs = cast(dict[str, object], proc.calls[0]["kwargs"])
    assert args[0].endswith("pi")
    assert args[1:] == (
        "--mode",
        "json",
        "--session-dir",
        str(run_dir / "pi-sessions"),
    )
    assert "--model" not in args
    assert "--thinking" not in args
    assert kwargs["cwd"] == str(target_dir.resolve())
    assert kwargs["limit"] == 1024 * 1024
    assert proc.stdin_data is not None
    assert proc.stdin_data.decode("utf-8") == "Do work\n"


@pytest.mark.asyncio
async def test_pi_executor_passes_runtime_model_and_env_without_artifact_leaks(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    proc = _fake_subprocess(
        stdout_lines=[
            _json_line_bytes(
                {
                    "type": "agent_end",
                    "messages": [
                        {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "Done"}],
                            "stopReason": "stop",
                        }
                    ],
                }
            )
        ],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/pi")
    runtime_config = ExecutorRuntimeConfig(
        default_model="sonnet:high",
        reasoning_level="high",
        env={"VISIBLE_FLAG": "1", "SECRET_TOKEN": "secret-token"},
    )
    caplog.set_level("DEBUG")

    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "working_directory": str(run_dir),
                "target_working_directory": str(target_dir),
            }
        ),
        runtime_config,
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    args = cast(tuple[str, ...], proc.calls[0]["args"])
    kwargs = cast(dict[str, object], proc.calls[0]["kwargs"])
    env = cast(dict[str, str], kwargs["env"])
    assert args[1:] == (
        "--mode",
        "json",
        "--session-dir",
        str(run_dir / "pi-sessions"),
        "--model",
        "sonnet:high",
        "--thinking",
        "high",
    )
    assert env["VISIBLE_FLAG"] == "1"
    assert env["SECRET_TOKEN"] == "secret-token"
    artifact_text = "\n".join(
        [
            (run_dir / "pi-events.jsonl").read_text(),
            (run_dir / "pi-stderr.txt").read_text(),
            (run_dir / "pi-result.txt").read_text(),
            caplog.text,
        ]
    )
    assert "secret-token" not in artifact_text


@pytest.mark.asyncio
async def test_pi_executor_rejects_invalid_workspace(
    snapshot: ExecutionSnapshot,
) -> None:
    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "target_working_directory": "/tmp/does-not-exist-vespera",
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_workspace_unavailable"


@pytest.mark.asyncio
async def test_pi_executor_rejects_missing_binary(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_available"


@pytest.mark.asyncio
async def test_pi_executor_maps_nonzero_auth_exit_to_failure(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[],
        stderr_lines=[b"pi: login required\n"],
        returncode=1,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/pi")
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_not_authenticated"
    assert (tmp_path / "run" / "pi-stderr.txt").read_text() == "pi: login required\n"


@pytest.mark.asyncio
async def test_pi_executor_maps_assistant_model_error_to_misconfigured(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[
            _json_line_bytes(
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "content": [],
                        "stopReason": "error",
                        "errorMessage": "model unavailable",
                    },
                }
            )
        ],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/pi")
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_misconfigured"


@pytest.mark.asyncio
async def test_pi_executor_uses_final_assistant_status_after_recovered_error(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    stdout_events: list[object] = [
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [],
                "stopReason": "error",
                "errorMessage": "WebSocket error",
            },
        },
        {
            "type": "turn_end",
            "message": {
                "role": "assistant",
                "content": [],
                "stopReason": "error",
                "errorMessage": "WebSocket error",
            },
        },
        {"type": "agent_end"},
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Recovered from Pi"}],
                "stopReason": "stop",
            },
        },
        {
            "type": "turn_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Recovered from Pi"}],
                "stopReason": "stop",
            },
        },
        {"type": "agent_end"},
    ]
    proc = _fake_subprocess(
        stdout_lines=[_json_line_bytes(event) for event in stdout_events],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", _fake_pi_binary)

    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "working_directory": str(run_dir),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert outcome.terminal_code == "pi_completed"
    assert outcome.result_summary == "Recovered from Pi"
    assert outcome.result_artifact_ref == str(run_dir / "pi-result.txt")
    assert (run_dir / "pi-result.txt").read_text() == "Recovered from Pi"


@pytest.mark.asyncio
async def test_pi_executor_can_opt_into_capped_raw_event_artifact(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    stdout_events: list[object] = [
        {"type": "session", "version": 3},
        {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "text_delta",
                "delta": "streamed text",
            },
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Done"}],
                "stopReason": "stop",
            },
        },
    ]
    proc = _fake_subprocess(
        stdout_lines=[_json_line_bytes(event) for event in stdout_events],
        returncode=0,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", _fake_pi_binary)

    first_raw_line = _json_line(stdout_events[0]).rstrip("\n")
    max_raw_bytes = len(f"{first_raw_line}\n".encode())
    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "working_directory": str(run_dir),
                "target_working_directory": str(target_dir),
            }
        ),
        ExecutorRuntimeConfig(
            env={
                "VESPERAFLOW_PI_CAPTURE_RAW_EVENTS": "1",
                "VESPERAFLOW_PI_RAW_EVENTS_MAX_BYTES": str(max_raw_bytes),
            }
        ),
    )

    assert outcome.terminal_status is RunStatus.COMPLETED
    assert (run_dir / "pi-events.jsonl").read_text() == (
        _json_lines_excluding_event_types(stdout_events, {"message_update"})
    )
    raw_event_lines = (run_dir / "pi-raw-events.jsonl").read_text().splitlines()
    assert raw_event_lines[0] == first_raw_line
    assert json.loads(raw_event_lines[1]) == {
        "type": "executor.raw_events_truncated",
        "max_bytes": max_raw_bytes,
        "discarded_lines": 2,
    }


@pytest.mark.asyncio
async def test_pi_executor_times_out_and_writes_artifacts(
    snapshot: ExecutionSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _fake_subprocess(
        stdout_lines=[
            b'{"type":"message_update","assistantMessageEvent":{"delta":"partial"}}\n'
        ],
        stderr_lines=[b"still running\n"],
        returncode=None,
        wait_never=True,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", proc.factory)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/pi")
    monkeypatch.setattr(pi_module, "_DEFAULT_SUBPROCESS_TIMEOUT", 0.01)
    monkeypatch.setattr(pi_module, "_kill_proc", lambda _proc: None)
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.FAILED
    assert outcome.terminal_code == "executor_error"
    assert outcome.result_artifact_ref == str(tmp_path / "run" / "pi-result.txt")
    assert (tmp_path / "run" / "pi-result.txt").read_text() == "partial"
    assert (tmp_path / "run" / "pi-stderr.txt").read_text() == "still running\n"


@pytest.mark.asyncio
async def test_pi_executor_cancels_on_cancelled_error(
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
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/pi")
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    outcome = await PiExecutor().execute(
        snapshot.model_copy(
            update={
                "executor": ExecutorName.PI,
                "working_directory": str(tmp_path / "run"),
                "target_working_directory": str(target_dir),
            }
        )
    )

    assert outcome.terminal_status is RunStatus.CANCELED
    assert outcome.terminal_code == "canceled"
    assert (tmp_path / "run" / "pi-events.jsonl").exists()


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


def _json_line(value: object) -> str:
    return json.dumps(value, separators=(",", ":")) + "\n"


def _json_lines_excluding_event_types(
    values: list[object],
    excluded_types: set[str],
) -> str:
    lines: list[str] = []
    for value in values:
        if isinstance(value, dict) and value.get("type") in excluded_types:
            continue
        lines.append(_json_line(value))
    return "".join(lines)


def _json_line_bytes(value: object) -> bytes:
    return _json_line(value).encode("utf-8")


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
        self._data: bytes = b"".join(lines)
        self._offset: int = 0

    async def readline(self) -> bytes:
        if self._offset >= len(self._data):
            return b""
        newline_index = self._data.find(b"\n", self._offset)
        end = len(self._data) if newline_index == -1 else newline_index + 1
        line = self._data[self._offset : end]
        self._offset = end
        return line

    async def read(self, n: int = -1) -> bytes:
        if self._offset >= len(self._data):
            return b""
        end = len(self._data) if n < 0 else min(len(self._data), self._offset + n)
        chunk = self._data[self._offset : end]
        self._offset = end
        return chunk


class FakeCancellingStreamReader(FakeStreamReader):
    @override
    async def readline(self) -> bytes:
        raise asyncio.CancelledError

    @override
    async def read(self, n: int = -1) -> bytes:
        raise asyncio.CancelledError


class FakeHangingStreamReader(FakeStreamReader):
    @override
    async def readline(self) -> bytes:
        line = await super().readline()
        if line:
            return line
        return await asyncio.Future()

    @override
    async def read(self, n: int = -1) -> bytes:
        chunk = await super().read(n)
        if chunk:
            return chunk
        return await asyncio.Future()

class FakeSubprocess:
    def __init__(
        self,
        *,
        stdout_lines: list[bytes],
        stderr_lines: list[bytes] | None = None,
        returncode: int | None = 0,
        cancel_on_stdout: bool = False,
        wait_never: bool = False,
        hang_streams: bool = False,
    ) -> None:
        self.stdout_lines = stdout_lines
        self.stderr_lines = stderr_lines or []
        self._returncode = returncode
        self.cancel_on_stdout = cancel_on_stdout
        self.wait_never = wait_never
        self.hang_streams = hang_streams
        self.calls: list[dict[str, object]] = []
        self.stdin: FakeStreamWriter | None = None
        self.stdout: FakeStreamReader | None = None
        self.stderr: FakeStreamReader | None = None
        self.pid = 12345

    @property
    def returncode(self) -> int | None:
        return self._returncode

    async def wait(self) -> int:
        if self.wait_never:
            _ = await asyncio.Event().wait()
        return self._returncode if self._returncode is not None else 0

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
        elif self.hang_streams:
            self.stdout = FakeHangingStreamReader(self.stdout_lines)
        else:
            self.stdout = FakeStreamReader(self.stdout_lines)
        self.stderr = (
            FakeHangingStreamReader(self.stderr_lines)
            if self.hang_streams
            else FakeStreamReader(self.stderr_lines)
        )
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
    returncode: int | None = 0,
    cancel_on_stdout: bool = False,
    wait_never: bool = False,
    hang_streams: bool = False,
) -> FakeSubprocess:
    return FakeSubprocess(
        stdout_lines=stdout_lines,
        stderr_lines=stderr_lines,
        returncode=returncode,
        cancel_on_stdout=cancel_on_stdout,
        wait_never=wait_never,
        hang_streams=hang_streams,
    )
