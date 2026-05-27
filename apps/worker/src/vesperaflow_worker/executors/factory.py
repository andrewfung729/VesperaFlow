"""Executor adapter factory."""

from .base import ExecutorAdapter
from .claude_code import ClaudeCodeExecutor
from .codex_cli import CodexExecutor
from .debug import DebugPrinterExecutor
from .opencode_cli import OpenCodeExecutor
from .pi import PiExecutor
from .router import ExecutorRouter


def build_executor() -> ExecutorAdapter:
    return ExecutorRouter(
        claude_code=ClaudeCodeExecutor(),
        codex=CodexExecutor(),
        debug_printer=DebugPrinterExecutor(),
        opencode=OpenCodeExecutor(),
        pi=PiExecutor(),
    )
