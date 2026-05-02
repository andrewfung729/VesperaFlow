"""Shared executor adapter contracts."""

from dataclasses import dataclass

from vesperaflow_core import ExecutionSnapshot, ExecutorOutcome


class ExecutorUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutorRuntimeConfig:
    executor_profile_id: str | None = None
    executor_profile_name: str | None = None
    default_model: str | None = None
    env: dict[str, str] | None = None


class ExecutorAdapter:
    async def execute(
        self,
        snapshot: ExecutionSnapshot,
        runtime_config: ExecutorRuntimeConfig | None = None,
    ) -> ExecutorOutcome:
        _ = snapshot, runtime_config
        raise NotImplementedError
