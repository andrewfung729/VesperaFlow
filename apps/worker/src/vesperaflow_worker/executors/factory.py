"""Executor adapter factory."""

from collections.abc import Mapping

from .base import ExecutorAdapter, ExecutorUnavailableError
from .claude_code import ClaudeCodeExecutor
from .debug import DebugPrinterExecutor
from .router import ExecutorRouter


def build_executor(
    adapter_name: str,
    *,
    claude_max_turns: int = 20,
    claude_env: Mapping[str, str] | None = None,
) -> ExecutorAdapter:
    claude_code = ClaudeCodeExecutor(
        max_turns=claude_max_turns,
        env=dict(claude_env) if claude_env is not None else None,
    )
    if adapter_name in {"auto", "router"}:
        return ExecutorRouter(
            claude_code=claude_code,
            debug_printer=DebugPrinterExecutor(),
        )
    if adapter_name == "debug_printer":
        return DebugPrinterExecutor()
    if adapter_name == "claude_code":
        return claude_code
    raise ExecutorUnavailableError(f"unknown executor adapter: {adapter_name}")
