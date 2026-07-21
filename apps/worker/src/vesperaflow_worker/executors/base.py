"""Shared executor adapter contracts."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from vesperaflow_core import (
    ExecutionSnapshot,
    ExecutorName,
    ExecutorOutcome,
    ProfileValidationResult,
    RunStatus,
    utc_now,
)

_INHERITED_ENV_KEYS = frozenset(
    {
        "HOME",
        "LANG",
        "LC_ALL",
        "LOGNAME",
        "PATH",
        "SHELL",
        "TERM",
        "TMPDIR",
        "USER",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)


class ExecutorUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutorRuntimeConfig:
    executor_profile_id: str | None = None
    executor_profile_name: str | None = None
    default_model: str | None = None
    reasoning_level: str | None = None
    env: dict[str, str] | None = None


def build_subprocess_environment(
    runtime_config: ExecutorRuntimeConfig | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if environ is None else environ
    subprocess_env = {
        key: value for key, value in source.items() if key in _INHERITED_ENV_KEYS
    }
    if runtime_config is not None and runtime_config.env is not None:
        subprocess_env.update(runtime_config.env)
    return subprocess_env


class ExecutorAdapter:
    async def execute(
        self,
        snapshot: ExecutionSnapshot,
        runtime_config: ExecutorRuntimeConfig | None = None,
    ) -> ExecutorOutcome:
        _ = snapshot, runtime_config
        raise NotImplementedError

    async def validate_profile(
        self,
        executor: ExecutorName,
        runtime_config: ExecutorRuntimeConfig,
        workspace: Path,
    ) -> ProfileValidationResult:
        artifact_dir = workspace / ".vesperaflow-validation"
        snapshot = ExecutionSnapshot(
            run_id=None,
            task_id="profile-validation",
            schedule_id=None,
            executor=executor,
            executor_profile_id=runtime_config.executor_profile_id,
            instruction_source=(
                "Validate this executor profile by replying with exactly OK. "
                "Do not inspect, create, modify, or delete files."
            ),
            planned_start_at=utc_now(),
            working_directory=str(artifact_dir),
            target_working_directory=str(workspace),
        )
        outcome = await self.execute(snapshot, runtime_config)
        if outcome.terminal_status is RunStatus.COMPLETED:
            return ProfileValidationResult(
                ok=True,
                code="profile_validation_passed",
                message="Executor profile validation passed.",
            )
        return ProfileValidationResult(
            ok=False,
            code=outcome.terminal_code or "profile_validation_failed",
            message=outcome.failure_reason or "Executor profile validation failed.",
        )
