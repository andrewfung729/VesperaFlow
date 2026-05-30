"""Codex CLI executor adapter."""

import asyncio
import json
import logging
import os
import shutil
import signal
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import cast, override

from vesperaflow_core import ExecutionSnapshot, ExecutorOutcome, RunStatus

from .base import ExecutorAdapter, ExecutorRuntimeConfig

logger = logging.getLogger(__name__)

_DEFAULT_SUBPROCESS_TIMEOUT = 900.0
_SIGINT_GRACE = 5.0
_SUBPROCESS_STREAM_LIMIT = 1024 * 1024
_STREAM_READ_CHUNK_SIZE = 64 * 1024
_MAX_CAPTURED_LINE_BYTES = 4 * 1024 * 1024


@dataclass(slots=True)
class CodexExecutor(ExecutorAdapter):
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

        binary = shutil.which("codex")
        if binary is None:
            return _failed_outcome(
                terminal_code="executor_not_available",
                failure_reason="Codex CLI is not available on PATH",
            )

        artifact_dir = Path(snapshot.working_directory)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        last_message_path = artifact_dir / "codex-last-message.txt"
        events_path = artifact_dir / "codex-events.jsonl"
        stderr_path = artifact_dir / "codex-stderr.txt"
        last_message_path.unlink(missing_ok=True)

        proc: asyncio.subprocess.Process | None = None
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            proc = await asyncio.create_subprocess_exec(
                *self._command_args(
                    binary=binary,
                    last_message_path=last_message_path,
                    workspace=workspace,
                    runtime_config=runtime_config,
                ),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_subprocess_env(runtime_config),
                limit=_SUBPROCESS_STREAM_LIMIT,
                start_new_session=True,
            )

            stdin_task = asyncio.create_task(
                _write_stdin(proc, snapshot.instruction_source)
            )
            stdout_task = asyncio.create_task(_read_stdout(proc, stdout_lines))
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
                    _ = _write_codex_artifacts(
                        events_path=events_path,
                        stderr_path=stderr_path,
                        last_message_path=last_message_path,
                        stdout_lines=stdout_lines,
                        stderr_lines=stderr_lines,
                    )
                    return _failed_outcome(
                        terminal_code="executor_error",
                        failure_reason="Codex CLI process did not exit within timeout",
                    )

            artifact_ref = _write_codex_artifacts(
                events_path=events_path,
                stderr_path=stderr_path,
                last_message_path=last_message_path,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
            )
            failed_event = _first_failed_turn(stdout_lines)
            if failed_event is not None:
                return _failed_outcome(
                    terminal_code="executor_error",
                    failure_reason=_failure_reason_from_event(failed_event),
                    result_artifact_ref=artifact_ref,
                )

            returncode = proc.returncode
            if returncode is not None and returncode != 0:
                return _classify_exit_code(
                    returncode,
                    "\n".join(stderr_lines),
                    artifact_ref=artifact_ref,
                )

        except asyncio.CancelledError:
            if proc is not None:
                _cancel_proc(proc)
                with suppress(TimeoutError):
                    _ = await asyncio.wait_for(proc.wait(), timeout=_SIGINT_GRACE)
                if proc.returncode is None:
                    _kill_proc(proc)
                    with suppress(TimeoutError):
                        _ = await asyncio.wait_for(proc.wait(), timeout=2.0)
            _ = _write_codex_artifacts(
                events_path=events_path,
                stderr_path=stderr_path,
                last_message_path=last_message_path,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
            )
            return ExecutorOutcome(
                terminal_status=RunStatus.CANCELED,
                failure_reason="executor_canceled",
                terminal_code="canceled",
            )
        except Exception as exc:
            logger.debug("codex_executor_error: %s", exc, exc_info=True)
            _ = _write_codex_artifacts(
                events_path=events_path,
                stderr_path=stderr_path,
                last_message_path=last_message_path,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
            )
            return _failed_outcome(
                terminal_code="executor_error",
                failure_reason=f"Codex CLI executor failed: {exc}",
                exception=exc,
            )
        finally:
            if proc is not None and proc.returncode is None:
                _kill_proc(proc)

        summary = last_message_path.read_text(encoding="utf-8").strip()
        if not summary:
            summary = "Codex completed without a final message."

        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary=summary,
            result_artifact_ref=str(last_message_path),
            terminal_code="codex_completed",
        )

    def _command_args(
        self,
        *,
        binary: str,
        last_message_path: Path,
        workspace: Path,
        runtime_config: ExecutorRuntimeConfig | None,
    ) -> tuple[str, ...]:
        args = [
            binary,
            "exec",
            "--json",
            "--output-last-message",
            str(last_message_path),
            "--skip-git-repo-check",
            "-C",
            str(workspace),
        ]
        model = runtime_config.default_model if runtime_config else None
        if model:
            args.extend(["--model", model])
        reasoning_level = runtime_config.reasoning_level if runtime_config else None
        if reasoning_level:
            args.extend(["-c", f'model_reasoning_effort="{reasoning_level}"'])
        args.extend(["--dangerously-bypass-approvals-and-sandbox", "-"])
        return tuple(args)


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
    stdout_lines: list[str],
) -> None:
    if proc.stdout is None:
        return
    await _read_stream_lines(proc.stdout, stdout_lines, stream_name="stdout")


async def _read_stderr(
    proc: asyncio.subprocess.Process,
    stderr_lines: list[str],
) -> None:
    if proc.stderr is None:
        return
    await _read_stream_lines(proc.stderr, stderr_lines, stream_name="stderr")


async def _read_stream_lines(
    stream: asyncio.StreamReader,
    lines: list[str],
    *,
    stream_name: str,
) -> None:
    pending = bytearray()
    truncated_bytes = 0

    while True:
        chunk = await stream.read(_STREAM_READ_CHUNK_SIZE)
        if not chunk:
            break

        start = 0
        while start < len(chunk):
            newline_index = chunk.find(b"\n", start)
            end = newline_index if newline_index != -1 else len(chunk)
            segment = chunk[start:end]
            truncated_bytes = _append_line_segment(
                pending,
                segment,
                truncated_bytes=truncated_bytes,
            )

            if newline_index == -1:
                break

            _append_completed_line(
                lines,
                pending,
                stream_name=stream_name,
                truncated_bytes=truncated_bytes,
            )
            pending.clear()
            truncated_bytes = 0
            start = newline_index + 1

    if pending or truncated_bytes:
        _append_completed_line(
            lines,
            pending,
            stream_name=stream_name,
            truncated_bytes=truncated_bytes,
        )


def _append_line_segment(
    pending: bytearray,
    segment: bytes,
    *,
    truncated_bytes: int,
) -> int:
    remaining = _MAX_CAPTURED_LINE_BYTES - len(pending)
    if remaining <= 0:
        return truncated_bytes + len(segment)
    pending.extend(segment[:remaining])
    return truncated_bytes + max(0, len(segment) - remaining)


def _append_completed_line(
    lines: list[str],
    pending: bytearray,
    *,
    stream_name: str,
    truncated_bytes: int,
) -> None:
    if truncated_bytes:
        lines.append(
            _truncated_stream_line(
                stream_name=stream_name,
                captured_bytes=len(pending),
                truncated_bytes=truncated_bytes,
            )
        )
        return
    lines.append(pending.decode("utf-8", errors="replace"))


def _truncated_stream_line(
    *,
    stream_name: str,
    captured_bytes: int,
    truncated_bytes: int,
) -> str:
    if stream_name == "stdout":
        return json.dumps(
            {
                "type": "executor.stream_line_truncated",
                "stream": stream_name,
                "captured_bytes": captured_bytes,
                "truncated_bytes": truncated_bytes,
            },
            separators=(",", ":"),
        )
    return (
        f"[VesperaFlow truncated {stream_name} line after "
        f"{captured_bytes} bytes; discarded {truncated_bytes} bytes]"
    )


def _write_codex_artifacts(
    *,
    events_path: Path,
    stderr_path: Path,
    last_message_path: Path,
    stdout_lines: list[str],
    stderr_lines: list[str],
) -> str:
    _ = events_path.write_text(
        "".join(f"{line}\n" for line in stdout_lines),
        encoding="utf-8",
    )
    _ = stderr_path.write_text(
        "".join(f"{line}\n" for line in stderr_lines),
        encoding="utf-8",
    )
    if not last_message_path.exists():
        _ = last_message_path.write_text(
            _last_message_from_events(stdout_lines),
            encoding="utf-8",
        )
    return str(last_message_path)


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
    result_artifact_ref: str | None = None,
    exception: Exception | None = None,
) -> ExecutorOutcome:
    if exception is not None:
        logger.debug("%s: %s", terminal_code, exception)
    return ExecutorOutcome(
        terminal_status=RunStatus.FAILED,
        failure_reason=failure_reason,
        result_artifact_ref=result_artifact_ref,
        terminal_code=terminal_code,
    )


def _classify_exit_code(
    returncode: int,
    stderr_text: str,
    *,
    artifact_ref: str,
) -> ExecutorOutcome:
    lowered = stderr_text.lower()
    auth_tokens = ("auth", "login", "credential", "api key", "not authenticated")
    if any(token in lowered for token in auth_tokens):
        return _failed_outcome(
            terminal_code="executor_not_authenticated",
            failure_reason="Codex CLI is not authenticated",
            result_artifact_ref=artifact_ref,
        )
    missing_tokens = ("not found", "no such file", "command not found")
    if any(token in lowered for token in missing_tokens):
        return _failed_outcome(
            terminal_code="executor_not_available",
            failure_reason="Codex CLI is not available",
            result_artifact_ref=artifact_ref,
        )
    return _failed_outcome(
        terminal_code="executor_error",
        failure_reason=f"Codex CLI exited with code {returncode}",
        result_artifact_ref=artifact_ref,
    )


def _first_failed_turn(stdout_lines: list[str]) -> dict[str, object] | None:
    for line in stdout_lines:
        event = _json_object(line)
        if event is None:
            continue
        if event.get("msg") == "turn.failed" or event.get("type") == "turn.failed":
            return event
    return None


def _failure_reason_from_event(event: dict[str, object]) -> str:
    error = event.get("error")
    if isinstance(error, str) and error.strip():
        return error
    if isinstance(error, dict):
        error_data = cast(dict[str, object], error)
        message = (
            error_data.get("message")
            or error_data.get("error")
            or error_data.get("reason")
        )
        if isinstance(message, str) and message.strip():
            return message
    message = event.get("message")
    if isinstance(message, str) and message.strip():
        return message
    return "Codex CLI reported turn.failed"


def _last_message_from_events(stdout_lines: list[str]) -> str:
    for line in reversed(stdout_lines):
        event = _json_object(line)
        if event is None:
            continue
        for key in ("message", "text", "content"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _json_object(line: str) -> dict[str, object] | None:
    try:
        parsed = cast(object, json.loads(line))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return cast(dict[str, object], parsed)


def _cancel_proc(proc: asyncio.subprocess.Process) -> None:
    with suppress(ProcessLookupError, OSError):
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)


def _kill_proc(proc: asyncio.subprocess.Process) -> None:
    with suppress(ProcessLookupError, OSError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
