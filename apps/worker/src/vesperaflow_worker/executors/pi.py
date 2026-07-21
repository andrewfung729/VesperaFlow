"""Pi CLI executor adapter."""

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

from .base import (
    ExecutorAdapter,
    ExecutorRuntimeConfig,
    build_subprocess_environment,
)

logger = logging.getLogger(__name__)

_DEFAULT_SUBPROCESS_TIMEOUT = 900.0
_SIGINT_GRACE = 5.0
_SUBPROCESS_STREAM_LIMIT = 1024 * 1024
_STREAM_READ_CHUNK_SIZE = 64 * 1024
_MAX_CAPTURED_LINE_BYTES = 4 * 1024 * 1024
_DEFAULT_RAW_EVENTS_MAX_BYTES = 16 * 1024 * 1024
_RAW_EVENTS_CAPTURE_ENV = "VESPERAFLOW_PI_CAPTURE_RAW_EVENTS"
_RAW_EVENTS_MAX_BYTES_ENV = "VESPERAFLOW_PI_RAW_EVENTS_MAX_BYTES"
_SUCCESS_STOP_REASONS = frozenset({"stop", "end_turn", "complete", "completed"})
_TERMINAL_MESSAGE_EVENT_TYPES = frozenset({"message_end", "turn_end", "agent_end"})
_STREAMING_EVENT_TYPES = frozenset({"message_update", "tool_execution_update"})
_TRUE_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


@dataclass(slots=True)
class PiExecutor(ExecutorAdapter):
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

        binary = shutil.which("pi")
        if binary is None:
            return _failed_outcome(
                terminal_code="executor_not_available",
                failure_reason="Pi CLI is not available on PATH",
            )

        artifact_dir = Path(snapshot.working_directory)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        session_dir = artifact_dir / "pi-sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        events_path = artifact_dir / "pi-events.jsonl"
        raw_events_path = artifact_dir / "pi-raw-events.jsonl"
        stderr_path = artifact_dir / "pi-stderr.txt"
        result_path = artifact_dir / "pi-result.txt"
        capture_raw_events = _capture_raw_events_enabled(runtime_config)
        raw_events_max_bytes = _raw_events_max_bytes(runtime_config)

        proc: asyncio.subprocess.Process | None = None
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            proc = await asyncio.create_subprocess_exec(
                *self._command_args(
                    binary=binary,
                    session_dir=session_dir,
                    runtime_config=runtime_config,
                ),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
                env=build_subprocess_environment(runtime_config),
                limit=_SUBPROCESS_STREAM_LIMIT,
                start_new_session=True,
            )

            try:
                await asyncio.wait_for(
                    _run_subprocess(
                        proc,
                        instruction=snapshot.instruction_source,
                        stdout_lines=stdout_lines,
                        stderr_lines=stderr_lines,
                    ),
                    timeout=_DEFAULT_SUBPROCESS_TIMEOUT,
                )
            except TimeoutError:
                _kill_proc(proc)
                artifact_ref = _write_pi_artifacts(
                    events_path=events_path,
                    raw_events_path=raw_events_path,
                    stderr_path=stderr_path,
                    result_path=result_path,
                    stdout_lines=stdout_lines,
                    stderr_lines=stderr_lines,
                    capture_raw_events=capture_raw_events,
                    raw_events_max_bytes=raw_events_max_bytes,
                )
                return _failed_outcome(
                    terminal_code="executor_error",
                    failure_reason="Pi CLI process did not exit within timeout",
                    result_artifact_ref=artifact_ref,
                )

            artifact_ref = _write_pi_artifacts(
                events_path=events_path,
                raw_events_path=raw_events_path,
                stderr_path=stderr_path,
                result_path=result_path,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                capture_raw_events=capture_raw_events,
                raw_events_max_bytes=raw_events_max_bytes,
            )
            assistant_failure = _assistant_failure(stdout_lines)
            if assistant_failure is not None:
                return _classify_diagnostic_text(
                    assistant_failure,
                    default_terminal_code="executor_error",
                    default_failure_reason=assistant_failure,
                    result_artifact_ref=artifact_ref,
                )

            returncode = proc.returncode
            if returncode is not None and returncode != 0:
                return _classify_exit_code(
                    returncode,
                    "\n".join([*stderr_lines, *stdout_lines]),
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
            _ = _write_pi_artifacts(
                events_path=events_path,
                raw_events_path=raw_events_path,
                stderr_path=stderr_path,
                result_path=result_path,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                capture_raw_events=capture_raw_events,
                raw_events_max_bytes=raw_events_max_bytes,
            )
            return ExecutorOutcome(
                terminal_status=RunStatus.CANCELED,
                failure_reason="executor_canceled",
                terminal_code="canceled",
            )
        except Exception as exc:
            logger.debug("pi_executor_error: %s", exc, exc_info=True)
            artifact_ref = _write_pi_artifacts(
                events_path=events_path,
                raw_events_path=raw_events_path,
                stderr_path=stderr_path,
                result_path=result_path,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                capture_raw_events=capture_raw_events,
                raw_events_max_bytes=raw_events_max_bytes,
            )
            return _failed_outcome(
                terminal_code="executor_error",
                failure_reason=f"Pi CLI executor failed: {exc}",
                result_artifact_ref=artifact_ref,
                exception=exc,
            )
        finally:
            if proc is not None and proc.returncode is None:
                _kill_proc(proc)

        summary = result_path.read_text(encoding="utf-8").strip()
        if not summary:
            summary = "Pi completed without a text summary."

        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary=summary,
            result_artifact_ref=str(result_path),
            terminal_code="pi_completed",
        )

    def _command_args(
        self,
        *,
        binary: str,
        session_dir: Path,
        runtime_config: ExecutorRuntimeConfig | None,
    ) -> tuple[str, ...]:
        args = [
            binary,
            "--mode",
            "json",
            "--session-dir",
            str(session_dir),
        ]
        model = runtime_config.default_model if runtime_config else None
        if model:
            args.extend(["--model", model])
        reasoning_level = runtime_config.reasoning_level if runtime_config else None
        if reasoning_level:
            args.extend(["--thinking", reasoning_level])
        return tuple(args)


def _capture_raw_events_enabled(
    runtime_config: ExecutorRuntimeConfig | None,
) -> bool:
    value = _runtime_env_value(runtime_config, _RAW_EVENTS_CAPTURE_ENV)
    if value is None:
        return False
    return value.strip().lower() in _TRUE_ENV_VALUES


def _raw_events_max_bytes(runtime_config: ExecutorRuntimeConfig | None) -> int:
    value = _runtime_env_value(runtime_config, _RAW_EVENTS_MAX_BYTES_ENV)
    if value is None or not value.strip():
        return _DEFAULT_RAW_EVENTS_MAX_BYTES
    with suppress(ValueError):
        return max(0, int(value))
    return _DEFAULT_RAW_EVENTS_MAX_BYTES


def _runtime_env_value(
    runtime_config: ExecutorRuntimeConfig | None,
    key: str,
) -> str | None:
    if runtime_config is not None and runtime_config.env is not None:
        configured = runtime_config.env.get(key)
        if configured is not None:
            return configured
    return os.environ.get(key)


async def _run_subprocess(
    proc: asyncio.subprocess.Process,
    *,
    instruction: str,
    stdout_lines: list[str],
    stderr_lines: list[str],
) -> None:
    tasks = [
        asyncio.create_task(_write_stdin(proc, instruction)),
        asyncio.create_task(_read_stdout(proc, stdout_lines)),
        asyncio.create_task(_read_stderr(proc, stderr_lines)),
        asyncio.create_task(_wait_for_process(proc)),
    ]
    try:
        _ = await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                _ = task.cancel()
        _ = await asyncio.gather(*tasks, return_exceptions=True)


async def _wait_for_process(proc: asyncio.subprocess.Process) -> None:
    _ = await proc.wait()


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


def _write_pi_artifacts(
    *,
    events_path: Path,
    raw_events_path: Path,
    stderr_path: Path,
    result_path: Path,
    stdout_lines: list[str],
    stderr_lines: list[str],
    capture_raw_events: bool,
    raw_events_max_bytes: int,
) -> str:
    _ = events_path.write_text(
        "".join(f"{line}\n" for line in _audit_event_lines(stdout_lines)),
        encoding="utf-8",
    )
    if capture_raw_events:
        _ = raw_events_path.write_text(
            "".join(
                f"{line}\n"
                for line in _bounded_raw_event_lines(
                    stdout_lines,
                    max_bytes=raw_events_max_bytes,
                )
            ),
            encoding="utf-8",
        )
    _ = stderr_path.write_text(
        "".join(f"{line}\n" for line in stderr_lines),
        encoding="utf-8",
    )
    _ = result_path.write_text(_final_assistant_text(stdout_lines), encoding="utf-8")
    return str(result_path)


def _audit_event_lines(stdout_lines: list[str]) -> list[str]:
    audit_lines: list[str] = []
    for line in stdout_lines:
        event = _json_object(line)
        if event is not None and event.get("type") in _STREAMING_EVENT_TYPES:
            continue
        audit_lines.append(line)
    return audit_lines


def _bounded_raw_event_lines(
    stdout_lines: list[str],
    *,
    max_bytes: int,
) -> list[str]:
    raw_lines: list[str] = []
    captured_bytes = 0
    for index, line in enumerate(stdout_lines):
        line_bytes = len(f"{line}\n".encode())
        if captured_bytes + line_bytes > max_bytes:
            raw_lines.append(
                json.dumps(
                    {
                        "type": "executor.raw_events_truncated",
                        "max_bytes": max_bytes,
                        "discarded_lines": len(stdout_lines) - index,
                    },
                    separators=(",", ":"),
                )
            )
            break
        raw_lines.append(line)
        captured_bytes += line_bytes
    return raw_lines


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
    diagnostic_text: str,
    *,
    artifact_ref: str,
) -> ExecutorOutcome:
    return _classify_diagnostic_text(
        diagnostic_text,
        default_terminal_code="executor_error",
        default_failure_reason=f"Pi CLI exited with code {returncode}",
        result_artifact_ref=artifact_ref,
    )


def _classify_diagnostic_text(
    diagnostic_text: str,
    *,
    default_terminal_code: str,
    default_failure_reason: str,
    result_artifact_ref: str,
) -> ExecutorOutcome:
    lowered = diagnostic_text.lower()
    auth_tokens = (
        "auth",
        "login",
        "credential",
        "api key",
        "unauthorized",
        "not authenticated",
    )
    if any(token in lowered for token in auth_tokens):
        return _failed_outcome(
            terminal_code="executor_not_authenticated",
            failure_reason="Pi CLI is not authenticated",
            result_artifact_ref=result_artifact_ref,
        )
    missing_tokens = ("not found", "no such file", "command not found")
    if any(token in lowered for token in missing_tokens):
        return _failed_outcome(
            terminal_code="executor_not_available",
            failure_reason="Pi CLI is not available",
            result_artifact_ref=result_artifact_ref,
        )
    config_tokens = (
        "config",
        "model",
        "provider",
        "settings",
        "permission",
        "no models available",
    )
    if any(token in lowered for token in config_tokens):
        return _failed_outcome(
            terminal_code="executor_misconfigured",
            failure_reason="Pi CLI is misconfigured",
            result_artifact_ref=result_artifact_ref,
        )
    return _failed_outcome(
        terminal_code=default_terminal_code,
        failure_reason=default_failure_reason,
        result_artifact_ref=result_artifact_ref,
    )


def _assistant_failure(stdout_lines: list[str]) -> str | None:
    terminal_failure: str | None = None
    for line in stdout_lines:
        event = _json_object(line)
        if event is None:
            continue
        terminal_failure = _terminal_failure_from_event(event, terminal_failure)
    return terminal_failure


def _terminal_failure_from_event(
    event: dict[str, object],
    current_failure: str | None,
) -> str | None:
    failure = current_failure
    event_type = event.get("type")
    is_terminal_message_event = event_type in _TERMINAL_MESSAGE_EVENT_TYPES
    if event_type == "error":
        failure = _event_error_message(event, default="Pi assistant reported an error")
    if event_type == "compaction_end" and event.get("aborted") is True:
        failure = _event_error_message(event, default="Pi compaction aborted")
    message = event.get("message")
    if is_terminal_message_event and isinstance(message, dict):
        failure = _message_failure_state(cast(dict[str, object], message), failure)
    messages = event.get("messages")
    if is_terminal_message_event and isinstance(messages, list):
        for item in cast(list[object], messages):
            if isinstance(item, dict):
                failure = _message_failure_state(cast(dict[str, object], item), failure)
    return failure


def _message_failure_state(
    message: dict[str, object],
    current_failure: str | None,
) -> str | None:
    role = message.get("role")
    if role is not None and role != "assistant":
        return current_failure
    stop_reason = message.get("stopReason") or message.get("stop_reason")
    if stop_reason in _SUCCESS_STOP_REASONS:
        return None
    if stop_reason not in {"error", "aborted"}:
        return current_failure
    error_message = message.get("errorMessage") or message.get("error_message")
    if isinstance(error_message, str) and error_message.strip():
        return error_message.strip()
    return f"Pi assistant stopped with {stop_reason}"


def _event_error_message(event: dict[str, object], *, default: str) -> str:
    for key in ("errorMessage", "error_message", "message", "reason"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    error = event.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, dict):
        error_data = cast(dict[str, object], error)
        for key in ("message", "error", "reason", "type"):
            value = error_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return default


def _final_assistant_text(stdout_lines: list[str]) -> str:
    delta_text: list[str] = []
    final_text = ""
    for line in stdout_lines:
        event = _json_object(line)
        if event is None:
            continue
        delta = _text_delta_from_event(event)
        if delta:
            delta_text.append(delta)
        message = event.get("message")
        if isinstance(message, dict):
            text = _text_from_message(cast(dict[str, object], message))
            if text:
                final_text = text
        messages = event.get("messages")
        if isinstance(messages, list):
            for item in cast(list[object], messages):
                if not isinstance(item, dict):
                    continue
                text = _text_from_message(cast(dict[str, object], item))
                if text:
                    final_text = text
    if final_text:
        return final_text
    return "".join(delta_text).strip()


def _text_delta_from_event(event: dict[str, object]) -> str:
    assistant_event = event.get("assistantMessageEvent") or event.get(
        "assistant_message_event"
    )
    if not isinstance(assistant_event, dict):
        return ""
    assistant_event_data = cast(dict[str, object], assistant_event)
    for key in ("delta", "text"):
        value = assistant_event_data.get(key)
        if isinstance(value, str):
            return value
    return ""


def _text_from_message(message: dict[str, object]) -> str:
    role = message.get("role")
    if role is not None and role != "assistant":
        return ""
    for key in ("text", "message"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in cast(list[object], content):
        text = _text_from_content_part(item)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _text_from_content_part(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    part = cast(dict[str, object], value)
    for key in ("text", "content", "delta"):
        text = part.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
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
