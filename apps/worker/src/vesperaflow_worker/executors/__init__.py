"""Executor adapter boundary."""

import logging
from dataclasses import dataclass

from vesperaflow_core import ExecutionSnapshot, ExecutorName, ExecutorOutcome, RunStatus

logger = logging.getLogger(__name__)


class ExecutorUnavailableError(RuntimeError):
    pass


class ExecutorAdapter:
    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        raise NotImplementedError


@dataclass(slots=True)
class FakeExecutor(ExecutorAdapter):
    result_summary: str = "Fake executor completed the planned task."
    fail: bool = False

    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        if self.fail:
            return ExecutorOutcome(
                terminal_status=RunStatus.FAILED,
                failure_reason="fake_executor_failure",
                terminal_code="fake_failed",
            )
        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary=self.result_summary,
            terminal_code="fake_completed",
        )


class DebugPrinterExecutor(ExecutorAdapter):
    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        logger.info("debug_printer_snapshot %s", snapshot.model_dump_json())
        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary=(
                f"Debug printer completed run {snapshot.run_id} "
                f"for task {snapshot.task_id}."
            ),
            terminal_code="debug_printer_completed",
        )


class ClaudeCodeExecutor(ExecutorAdapter):
    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        try:
            await self._import_sdk()
        except ModuleNotFoundError as exc:
            raise ExecutorUnavailableError(
                "Claude Agent SDK is not installed in the worker environment"
            ) from exc
        raise ExecutorUnavailableError(
            "Claude Code SDK execution is a configured adapter boundary; "
            "full SDK invocation is deferred to the hardening phase"
        )

    async def _import_sdk(self) -> object:
        import claude_agent_sdk  # type: ignore[import-not-found]

        return claude_agent_sdk


@dataclass(slots=True)
class ExecutorRouter(ExecutorAdapter):
    claude_code: ExecutorAdapter
    debug_printer: ExecutorAdapter

    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        if snapshot.executor is ExecutorName.CLAUDE_CODE:
            return await self.claude_code.execute(snapshot)
        if snapshot.executor is ExecutorName.DEBUG_PRINTER:
            return await self.debug_printer.execute(snapshot)
        raise ExecutorUnavailableError(f"unknown executor: {snapshot.executor}")


def build_executor(adapter_name: str) -> ExecutorAdapter:
    if adapter_name in {"auto", "router"}:
        return ExecutorRouter(
            claude_code=ClaudeCodeExecutor(),
            debug_printer=DebugPrinterExecutor(),
        )
    if adapter_name == "fake":
        return FakeExecutor()
    if adapter_name == "fake_fail":
        return FakeExecutor(fail=True)
    if adapter_name == "debug_printer":
        return DebugPrinterExecutor()
    if adapter_name == "claude_code":
        return ClaudeCodeExecutor()
    raise ExecutorUnavailableError(f"unknown executor adapter: {adapter_name}")
