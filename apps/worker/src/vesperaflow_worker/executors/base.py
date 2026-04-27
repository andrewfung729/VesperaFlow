"""Shared executor adapter contracts."""

from vesperaflow_core import ExecutionSnapshot, ExecutorOutcome


class ExecutorUnavailableError(RuntimeError):
    pass


class ExecutorAdapter:
    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError
