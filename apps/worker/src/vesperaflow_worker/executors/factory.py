"""Executor adapter factory."""

from .base import ExecutorAdapter, ExecutorUnavailableError
from .claude_code import ClaudeCodeExecutor
from .debug import DebugPrinterExecutor
from .router import ExecutorRouter


def build_executor(
    adapter_name: str,
    *,
    claude_max_turns: int = 20,
    claude_max_budget_usd: float | None = None,
) -> ExecutorAdapter:
    claude_code = ClaudeCodeExecutor(
        max_turns=claude_max_turns,
        max_budget_usd=claude_max_budget_usd,
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
