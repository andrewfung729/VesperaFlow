"""Kimi Code executor adapter (text CLI transport)."""

import asyncio
import json
import logging
import os
import shutil
import signal
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import override

from vesperaflow_core import ExecutionSnapshot, ExecutorOutcome, RunStatus

from .base import ExecutorAdapter, ExecutorRuntimeConfig

logger = logging.getLogger(__name__)

_DEFAULT_SUBPROCESS_TIMEOUT = 900.0
_SIGINT_GRACE = 5.0


@dataclass(slots=True)
class KimiCodeExecutor(ExecutorAdapter):
    @override
    async def execute(
        self,
        snapshot: ExecutionSnapshot,
        runtime_config: ExecutorRuntimeConfig | None = None,
    ) -> ExecutorOutcome:
        workspace = _existing_directory(snapshot.target_working_directory)
        if workspace is None:
            return _failed_outcome(
                terminal_code="executor_workspace_unavailable",
                failure_reason="target_working_directory must be an existing directory",
            )

        binary = shutil.which("kimi")
        if binary is None:
            return _failed_outcome(
                terminal_code="executor_not_available",
                failure_reason="Kimi Code CLI is not available on PATH",
            )

        artifact_dir = Path(snapshot.working_directory)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        proc: asyncio.subprocess.Process | None = None
        assistant_text: list[str] = []
        stderr_lines: list[str] = []

        try:
            proc = await asyncio.create_subprocess_exec(
                binary,
                "--print",
                "--final-message-only",
                "--work-dir",
                str(workspace),
                "--yolo",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_subprocess_env(runtime_config),
                start_new_session=True,
            )

            stdin_task = asyncio.create_task(
                _write_stdin(proc, snapshot.instruction_source)
            )
            stdout_task = asyncio.create_task(
                _read_stdout(proc, assistant_text)
            )
            stderr_task = asyncio.create_task(_read_stderr(proc, stderr_lines))

            await stdin_task
            await stdout_task
            await stderr_task

            if proc.returncode is None:
                try:
                    _ = await asyncio.wait_for(
                        proc.wait(), timeout=_DEFAULT_SUBPROCESS_TIMEOUT
                    )
                except TimeoutError:
                    _kill_proc(proc)
                    return _failed_outcome(
                        terminal_code="executor_error",
                        failure_reason="Kimi Code process did not exit within timeout",
                    )

            returncode = proc.returncode
            if returncode is not None and returncode != 0:
                stderr_text = "\n".join(stderr_lines)
                return _classify_exit_code(returncode, stderr_text)

        except asyncio.CancelledError:
            if proc is not None:
                _cancel_proc(proc)
                with suppress(TimeoutError):
                    _ = await asyncio.wait_for(proc.wait(), timeout=_SIGINT_GRACE + 2.0)
                if proc.returncode is None:
                    _kill_proc(proc)
            return ExecutorOutcome(
                terminal_status=RunStatus.CANCELED,
                failure_reason="executor_canceled",
                terminal_code="canceled",
            )
        except Exception as exc:
            logger.debug("kimi_code_executor_error: %s", exc, exc_info=True)
            return _failed_outcome(
                terminal_code="executor_error",
                failure_reason=f"Kimi Code executor failed: {exc}",
                exception=exc,
            )
        finally:
            if proc is not None and proc.returncode is None:
                _kill_proc(proc)

        summary = "".join(assistant_text).strip()
        if not summary:
            summary = "Kimi Code completed without output."

        artifact_ref = _write_kimi_artifacts(
            artifact_dir=artifact_dir,
            assistant_text=summary,
            stderr_lines=stderr_lines,
        )

        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary=summary,
            result_artifact_ref=artifact_ref,
            terminal_code="kimi_code_completed",
        )


def _subprocess_env(
    runtime_config: ExecutorRuntimeConfig | None,
) -> dict[str, str] | None:
    if runtime_config is None or not runtime_config.env:
        return None
    env = dict(os.environ)
    env.update(runtime_config.env)
    return env


async def _write_stdin(proc: asyncio.subprocess.Process, instruction: str) -> None:
    if proc.stdin is None:
        return
    proc.stdin.write(instruction.encode("utf-8") + b"\n")
    await proc.stdin.drain()
    proc.stdin.close()


async def _read_stdout(
    proc: asyncio.subprocess.Process,
    assistant_text: list[str],
) -> None:
    if proc.stdout is None:
        return
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        assistant_text.append(line.decode("utf-8"))


async def _read_stderr(
    proc: asyncio.subprocess.Process,
    stderr_lines: list[str],
) -> None:
    if proc.stderr is None:
        return
    while True:
        line = await proc.stderr.readline()
        if not line:
            break
        stderr_lines.append(line.decode("utf-8", errors="replace").rstrip("\n"))


def _write_kimi_artifacts(
    *,
    artifact_dir: Path,
    assistant_text: str,
    stderr_lines: list[str],
) -> str:
    text_path = artifact_dir / "kimi-output.txt"
    result_path = artifact_dir / "kimi-result.json"
    _ = text_path.write_text(assistant_text, encoding="utf-8")
    _ = result_path.write_text(
        json.dumps(
            {
                "stdout": assistant_text,
                "stderr": stderr_lines,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    return str(text_path)


def _existing_directory(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.exists() or not path.is_dir():
        return None
    return path.resolve()


def _failed_outcome(
    *,
    terminal_code: str,
    failure_reason: str,
    exception: Exception | None = None,
) -> ExecutorOutcome:
    if exception is not None:
        logger.debug("%s: %s", terminal_code, exception)
    return ExecutorOutcome(
        terminal_status=RunStatus.FAILED,
        failure_reason=failure_reason,
        terminal_code=terminal_code,
    )


def _classify_exit_code(returncode: int, stderr_text: str) -> ExecutorOutcome:
    lowered = stderr_text.lower()
    auth_tokens = ("auth", "login", "credential", "api key")
    if any(token in lowered for token in auth_tokens):
        return _failed_outcome(
            terminal_code="executor_not_authenticated",
            failure_reason="Kimi Code is not authenticated",
        )
    missing_tokens = ("not found", "no such file", "command not found")
    if any(token in lowered for token in missing_tokens):
        return _failed_outcome(
            terminal_code="executor_not_available",
            failure_reason="Kimi Code CLI is not available",
        )
    return _failed_outcome(
        terminal_code="executor_error",
        failure_reason=f"Kimi Code exited with code {returncode}",
    )


def _cancel_proc(proc: asyncio.subprocess.Process) -> None:
    with suppress(ProcessLookupError, OSError):
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)


def _kill_proc(proc: asyncio.subprocess.Process) -> None:
    with suppress(ProcessLookupError, OSError):
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGKILL)
