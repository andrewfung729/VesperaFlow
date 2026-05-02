"""Executor availability routes."""

import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import (
    ExecutorName,
    ExecutorPreflightResult,
    ExecutorPreflightStatus,
)
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import NotFoundError

from ..dependencies import get_session
from ..schemas.tasks import DataEnvelope

router = APIRouter()


@router.get("/executors/preflight")
async def preflight_executor(
    session: Annotated[AsyncSession, Depends(get_session)],
    executor: ExecutorName = ExecutorName.CLAUDE_CODE,
    executor_profile_id: Annotated[str | None, Query(min_length=1)] = None,
    target_working_directory: Annotated[str | None, Query(min_length=1)] = None,
) -> DataEnvelope:
    if executor_profile_id is not None:
        try:
            profile = await repo.get_executor_profile(session, executor_profile_id)
        except NotFoundError:
            return DataEnvelope(
                data=_result(
                    executor=executor,
                    status=ExecutorPreflightStatus.UNAVAILABLE,
                    code="executor_profile_unavailable",
                    message="Executor profile was not found",
                ).model_dump()
            )
        if profile.archived_at is not None or not profile.is_enabled:
            return DataEnvelope(
                data=_result(
                    executor=profile.executor,
                    status=ExecutorPreflightStatus.UNAVAILABLE,
                    code="executor_profile_unavailable",
                    message="Executor profile is disabled or archived",
                ).model_dump()
            )
        executor = profile.executor
    if executor is ExecutorName.DEBUG_PRINTER:
        return DataEnvelope(
            data=ExecutorPreflightResult(
                executor=ExecutorName.DEBUG_PRINTER,
                status=ExecutorPreflightStatus.AVAILABLE,
                code="executor_preflight_passed",
                message="Debug printer executor is available",
            ).model_dump()
        )
    if executor is ExecutorName.KIMI_CODE:
        return DataEnvelope(
            data=_kimi_code_preflight(target_working_directory).model_dump()
        )
    if executor is ExecutorName.CODEX:
        return DataEnvelope(
            data=_codex_preflight(target_working_directory).model_dump()
        )
    return DataEnvelope(
        data=_claude_code_preflight(target_working_directory).model_dump()
    )


def _claude_code_preflight(
    target_working_directory: str | None,
) -> ExecutorPreflightResult:
    workspace = _existing_directory(target_working_directory)
    if workspace is None:
        return _result(
            executor=ExecutorName.CLAUDE_CODE,
            status=ExecutorPreflightStatus.UNAVAILABLE,
            code="executor_workspace_unavailable",
            message="target_working_directory must be an existing absolute directory",
        )
    return _result(
        executor=ExecutorName.CLAUDE_CODE,
        status=ExecutorPreflightStatus.AVAILABLE,
        code="executor_preflight_passed",
        message="Claude Code target workspace is available",
        details={"live": False},
    )


def _kimi_code_preflight(
    target_working_directory: str | None,
) -> ExecutorPreflightResult:
    workspace = _existing_directory(target_working_directory)
    if workspace is None:
        return _result(
            executor=ExecutorName.KIMI_CODE,
            status=ExecutorPreflightStatus.UNAVAILABLE,
            code="executor_workspace_unavailable",
            message="target_working_directory must be an existing absolute directory",
        )
    if shutil.which("kimi") is None:
        return _result(
            executor=ExecutorName.KIMI_CODE,
            status=ExecutorPreflightStatus.UNAVAILABLE,
            code="executor_not_available",
            message="Kimi Code CLI is not available on PATH",
        )
    return _result(
        executor=ExecutorName.KIMI_CODE,
        status=ExecutorPreflightStatus.AVAILABLE,
        code="executor_preflight_passed",
        message="Kimi Code target workspace is available",
        details={"live": False},
    )


def _codex_preflight(
    target_working_directory: str | None,
) -> ExecutorPreflightResult:
    workspace = _existing_directory(target_working_directory)
    if workspace is None:
        return _result(
            executor=ExecutorName.CODEX,
            status=ExecutorPreflightStatus.UNAVAILABLE,
            code="executor_workspace_unavailable",
            message="target_working_directory must be an existing absolute directory",
        )
    if shutil.which("codex") is None:
        return _result(
            executor=ExecutorName.CODEX,
            status=ExecutorPreflightStatus.UNAVAILABLE,
            code="executor_not_available",
            message="Codex CLI is not available on PATH",
        )
    return _result(
        executor=ExecutorName.CODEX,
        status=ExecutorPreflightStatus.AVAILABLE,
        code="executor_preflight_passed",
        message="Codex target workspace is available",
        details={"live": False},
    )


def _existing_directory(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.exists() or not path.is_dir():
        return None
    return path.resolve()


def _result(
    *,
    executor: ExecutorName,
    status: ExecutorPreflightStatus,
    code: str,
    message: str,
    details: dict[str, str | bool | None] | None = None,
) -> ExecutorPreflightResult:
    return ExecutorPreflightResult(
        executor=executor,
        status=status,
        code=code,
        message=message,
        details=details or {},
    )
