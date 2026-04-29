"""Executor adapter factory."""

from collections.abc import Mapping

from .base import ExecutorAdapter, ExecutorUnavailableError
from .claude_code import ClaudeCodeExecutor
from .codex_cli import CodexExecutor
from .debug import DebugPrinterExecutor
from .kimi_code import KimiCodeExecutor
from .router import ExecutorRouter


def build_executor(
    adapter_name: str,
    *,
    claude_env: Mapping[str, str] | None = None,
) -> ExecutorAdapter:
    claude_code = ClaudeCodeExecutor(
        env=dict(claude_env) if claude_env is not None else None,
    )
    codex = CodexExecutor()
    kimi_code = KimiCodeExecutor()
    if adapter_name in {"auto", "router"}:
        return ExecutorRouter(
            claude_code=claude_code,
            codex=codex,
            debug_printer=DebugPrinterExecutor(),
            kimi_code=kimi_code,
        )
    if adapter_name == "debug_printer":
        return DebugPrinterExecutor()
    if adapter_name == "claude_code":
        return claude_code
    if adapter_name == "codex":
        return codex
    if adapter_name == "kimi_code":
        return kimi_code
    raise ExecutorUnavailableError(f"unknown executor adapter: {adapter_name}")
