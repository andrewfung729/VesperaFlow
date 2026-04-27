"""Claude Code executor adapter."""

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, override

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ClaudeSDKError,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
)
from vesperaflow_core import (
    ExecutionSnapshot,
    ExecutorOutcome,
    RunStatus,
)

from .base import ExecutorAdapter

logger = logging.getLogger(__name__)

PermissionMode = Literal[
    "default",
    "acceptEdits",
    "bypassPermissions",
    "plan",
]
SettingSource = Literal["user", "project", "local"]

CLAUDE_SETTING_SOURCES: tuple[SettingSource, ...] = ("user", "project", "local")
DEFAULT_SUMMARY_MAX_CHARS = 4000


@dataclass(slots=True)
class ClaudeCodeExecutor(ExecutorAdapter):
    max_turns: int = 20
    permission_mode: PermissionMode = "bypassPermissions"
    setting_sources: tuple[SettingSource, ...] = CLAUDE_SETTING_SOURCES
    summary_max_chars: int = DEFAULT_SUMMARY_MAX_CHARS
    env: dict[str, str] | None = None

    @override
    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        workspace = _existing_directory(snapshot.target_working_directory)
        if workspace is None:
            return _failed_outcome(
                terminal_code="executor_workspace_unavailable",
                failure_reason="target_working_directory must be an existing directory",
            )
        artifact_dir = Path(snapshot.working_directory)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        messages: list[object] = []
        assistant_text: list[str] = []
        result_message: object | None = None
        client: ClaudeSDKClient | None = None

        try:
            sdk = self._build_client(workspace)
            client = sdk
            async with sdk:
                await sdk.query(snapshot.instruction_source)
                async for message in sdk.receive_response():
                    messages.append(message)
                    assistant_text.extend(_extract_text_blocks(message))
                    if type(message).__name__ == "ResultMessage":
                        result_message = message
        except asyncio.CancelledError:
            if client is not None:
                with suppress(Exception, AttributeError):
                    await client.interrupt()
            return ExecutorOutcome(
                terminal_status=RunStatus.CANCELED,
                failure_reason="executor_canceled",
                terminal_code="canceled",
            )
        except Exception as exc:
            return _map_sdk_exception(exc)

        artifact_ref = _write_claude_artifacts(
            artifact_dir=artifact_dir,
            messages=messages,
            assistant_text="".join(assistant_text),
            result_message=result_message,
        )
        if result_message is not None and bool(
            getattr(result_message, "is_error", False)
        ):
            failure_reason = (
                getattr(result_message, "result", None)
                or getattr(result_message, "subtype", None)
                or "Claude Code execution failed"
            )
            terminal_code = (
                getattr(result_message, "stop_reason", None)
                or getattr(result_message, "subtype", None)
                or "executor_failed"
            )
            return ExecutorOutcome(
                terminal_status=RunStatus.FAILED,
                failure_reason=str(failure_reason),
                result_artifact_ref=artifact_ref,
                terminal_code=str(terminal_code),
            )

        summary = _result_summary(result_message, "".join(assistant_text))
        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary=_truncate(summary, self.summary_max_chars),
            result_artifact_ref=artifact_ref,
            terminal_code="claude_code_completed",
        )

    def _build_client(self, workspace: Path) -> ClaudeSDKClient:
        if self.env:
            options = ClaudeAgentOptions(
                cwd=str(workspace),
                permission_mode=self.permission_mode,
                setting_sources=list(self.setting_sources),
                max_turns=self.max_turns,
                env=dict(self.env),
            )
        else:
            options = ClaudeAgentOptions(
                cwd=str(workspace),
                permission_mode=self.permission_mode,
                setting_sources=list(self.setting_sources),
                max_turns=self.max_turns,
            )
        return ClaudeSDKClient(options=options)


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


def _map_sdk_exception(exc: Exception) -> ExecutorOutcome:
    if isinstance(exc, CLINotFoundError):
        return _failed_outcome(
            terminal_code="executor_not_available",
            failure_reason="Claude Code CLI is not available",
            exception=exc,
        )
    if isinstance(exc, ProcessError) and _looks_like_auth_failure(exc):
        return _failed_outcome(
            terminal_code="executor_not_authenticated",
            failure_reason="Claude Code is not authenticated",
            exception=exc,
        )
    if isinstance(
        exc,
        (
            CLIConnectionError,
            CLIJSONDecodeError,
            ProcessError,
            ClaudeSDKError,
        ),
    ):
        return _failed_outcome(
            terminal_code="executor_misconfigured",
            failure_reason=f"Claude Agent SDK execution failed: {exc}",
            exception=exc,
        )
    return _failed_outcome(
        terminal_code="executor_error",
        failure_reason=f"Claude Code executor failed: {exc}",
        exception=exc,
    )


def _looks_like_auth_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("auth", "login", "credential"))


def _extract_text_blocks(message: object) -> list[str]:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    content_list = cast(list[object], content)
    text_blocks: list[str] = []
    for block in content_list:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            text_blocks.append(text)
    return text_blocks


def _result_summary(result_message: object | None, fallback: str) -> str:
    if result_message is not None:
        result = getattr(result_message, "result", None)
        if isinstance(result, str) and result.strip():
            return result
    if fallback.strip():
        return fallback
    return "Claude Code completed without a text summary."


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return f"{value[: max_chars - 3]}..."


def _write_claude_artifacts(
    *,
    artifact_dir: Path,
    messages: list[object],
    assistant_text: str,
    result_message: object | None,
) -> str:
    text_path = artifact_dir / "claude-output.txt"
    result_path = artifact_dir / "claude-result.json"
    _ = text_path.write_text(assistant_text, encoding="utf-8")
    _ = result_path.write_text(
        json.dumps(
            {
                "messages": [_message_artifact(message) for message in messages],
                "result": _message_artifact(result_message)
                if result_message is not None
                else None,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return str(text_path)


def _message_artifact(message: object) -> dict[str, object]:
    return {
        "type": type(message).__name__,
        "subtype": getattr(message, "subtype", None),
        "is_error": getattr(message, "is_error", None),
        "session_id": getattr(message, "session_id", None),
        "num_turns": getattr(message, "num_turns", None),
        "total_cost_usd": getattr(message, "total_cost_usd", None),
        "stop_reason": getattr(message, "stop_reason", None),
        "result": getattr(message, "result", None),
        "text": "".join(_extract_text_blocks(message)),
    }
