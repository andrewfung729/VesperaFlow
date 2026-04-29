"""Executor routing adapter."""

from dataclasses import dataclass
from typing import override

from vesperaflow_core import ExecutionSnapshot, ExecutorName, ExecutorOutcome

from .base import ExecutorAdapter, ExecutorUnavailableError


@dataclass(slots=True)
class ExecutorRouter(ExecutorAdapter):
    claude_code: ExecutorAdapter
    codex: ExecutorAdapter
    kimi_code: ExecutorAdapter
    debug_printer: ExecutorAdapter

    @override
    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        if snapshot.executor is ExecutorName.CLAUDE_CODE:
            return await self.claude_code.execute(snapshot)
        if snapshot.executor is ExecutorName.CODEX:
            return await self.codex.execute(snapshot)
        if snapshot.executor is ExecutorName.DEBUG_PRINTER:
            return await self.debug_printer.execute(snapshot)
        if snapshot.executor is ExecutorName.KIMI_CODE:
            return await self.kimi_code.execute(snapshot)
        raise ExecutorUnavailableError(f"unknown executor: {snapshot.executor}")
