"""Executor profile routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_core import ExecutorName, ProfileValidationInput
from vesperaflow_core.client_contracts import (
    ExecutorProfileCreateRequest,
    ExecutorProfileUpdateRequest,
    VersionedCommand,
)
from vesperaflow_store import repositories as repo
from vesperaflow_store.errors import ConflictError, InvalidStateTransitionError
from vesperaflow_store.models import ExecutorProfile

from ..dependencies import get_scheduler, get_session
from ..schemas.executor_profiles import ExecutorProfileResponse
from ..schemas.tasks import DataEnvelope, ListEnvelope
from ..temporal_scheduler import TemporalScheduler
from ._shared import observed_version

router = APIRouter()


@router.post("/executor-profiles", status_code=201)
async def create_executor_profile(
    payload: ExecutorProfileCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
) -> DataEnvelope:
    validation_input: ProfileValidationInput | None = None
    if _create_requires_validation(payload):
        async with session.begin():
            validation_input = await _create_validation_handoff(
                session,
                executor=payload.executor,
                default_model=payload.default_model,
                reasoning_level=payload.reasoning_level,
                env=payload.env,
                secret_env=payload.secret_env,
            )
        await _run_save_time_validation(session, scheduler, validation_input)

    async with session.begin():
        profile = await repo.create_executor_profile(
            session,
            name=payload.name,
            executor=payload.executor,
            is_enabled=payload.is_enabled,
            is_default=payload.is_default,
            default_model=payload.default_model,
            reasoning_level=payload.reasoning_level,
            env=payload.env,
            secret_env=payload.secret_env,
        )
    return DataEnvelope(data=ExecutorProfileResponse.from_model(profile).model_dump())


@router.get("/executor-profiles")
async def list_executor_profiles(
    session: Annotated[AsyncSession, Depends(get_session)],
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListEnvelope:
    page = await repo.list_executor_profiles(
        session,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return ListEnvelope(
        data=[
            ExecutorProfileResponse.from_model(profile).model_dump()
            for profile in page.items
        ],
        meta={"total": page.total},
    )


@router.get("/executor-profiles/{profile_id}")
async def get_executor_profile(
    profile_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    profile = await repo.get_executor_profile(session, profile_id)
    return DataEnvelope(data=ExecutorProfileResponse.from_model(profile).model_dump())


@router.patch("/executor-profiles/{profile_id}")
async def update_executor_profile(
    profile_id: str,
    payload: ExecutorProfileUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    scheduler: Annotated[TemporalScheduler, Depends(get_scheduler)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    payload_fields = payload.model_fields_set
    validation_input: ProfileValidationInput | None = None
    async with session.begin():
        profile_for_validation = await repo.get_executor_profile(session, profile_id)
        _require_profile_update_allowed(profile_for_validation, version)
        if _update_requires_validation(profile_for_validation, payload, payload_fields):
            validation_input = await _create_validation_handoff(
                session,
                executor=profile_for_validation.executor,
                default_model=_effective_default_model(
                    profile_for_validation,
                    payload,
                    payload_fields,
                ),
                reasoning_level=_effective_reasoning_level(
                    profile_for_validation,
                    payload,
                    payload_fields,
                ),
                env=_effective_env(profile_for_validation, payload, payload_fields),
                secret_env=_effective_secret_env(
                    profile_for_validation,
                    payload,
                    payload_fields,
                ),
            )
    await _run_save_time_validation(session, scheduler, validation_input)

    async with session.begin():
        profile = await repo.update_executor_profile(
            session,
            profile_id=profile_id,
            version=version,
            name=payload.name,
            is_enabled=payload.is_enabled,
            is_default=payload.is_default,
            default_model=payload.default_model,
            set_default_model="default_model" in payload_fields,
            reasoning_level=payload.reasoning_level,
            set_reasoning_level="reasoning_level" in payload_fields,
            env=payload.env,
            set_env="env" in payload_fields,
            secret_env=payload.secret_env,
        )
    return DataEnvelope(data=ExecutorProfileResponse.from_model(profile).model_dump())


def _create_requires_validation(payload: ExecutorProfileCreateRequest) -> bool:
    return payload.is_enabled and _has_explicit_runtime_default(
        payload.default_model,
        payload.reasoning_level,
    )


async def _create_validation_handoff(
    session: AsyncSession,
    *,
    executor: ExecutorName,
    default_model: str | None,
    reasoning_level: str | None,
    env: dict[str, str],
    secret_env: dict[str, str],
) -> ProfileValidationInput:
    handoff = await repo.create_profile_validation_handoff(
        session,
        executor=executor,
        default_model=default_model,
        reasoning_level=reasoning_level,
        env=env,
        secret_env=secret_env,
    )
    return ProfileValidationInput(
        handoff_id=handoff.handoff_id,
        executor=handoff.executor,
        default_model=handoff.default_model,
        reasoning_level=handoff.reasoning_level,
    )


async def _run_save_time_validation(
    session: AsyncSession,
    scheduler: TemporalScheduler,
    validation_input: ProfileValidationInput | None,
) -> None:
    if validation_input is None:
        return
    try:
        result = await scheduler.validate_executor_profile(validation_input)
    except Exception as exc:
        raise ValueError(f"executor profile validation failed: {exc}") from exc
    finally:
        async with session.begin():
            await repo.delete_profile_validation_handoff(
                session,
                validation_input.handoff_id,
            )
    if not result.ok:
        raise ValueError(f"executor profile validation failed: {result.message}")


def _require_profile_update_allowed(profile: ExecutorProfile, version: int) -> None:
    if profile.version != version:
        raise ConflictError("resource version conflict")
    if profile.archived_at is not None:
        raise InvalidStateTransitionError("archived executor profiles cannot be edited")


def _update_requires_validation(
    profile: ExecutorProfile,
    payload: ExecutorProfileUpdateRequest,
    payload_fields: set[str],
) -> bool:
    effective_enabled = (
        payload.is_enabled if "is_enabled" in payload_fields else profile.is_enabled
    )
    if not effective_enabled:
        return False
    if not _has_explicit_runtime_default(
        _effective_default_model(profile, payload, payload_fields),
        _effective_reasoning_level(profile, payload, payload_fields),
    ):
        return False
    runtime_fields_changed = bool(
        {"default_model", "reasoning_level", "env", "secret_env"} & payload_fields
    )
    profile_is_being_enabled = (
        "is_enabled" in payload_fields
        and payload.is_enabled is True
        and not profile.is_enabled
    )
    return runtime_fields_changed or profile_is_being_enabled


def _has_explicit_runtime_default(
    default_model: str | None,
    reasoning_level: str | None,
) -> bool:
    return bool(default_model or reasoning_level)


def _effective_default_model(
    profile: ExecutorProfile,
    payload: ExecutorProfileUpdateRequest,
    payload_fields: set[str],
) -> str | None:
    if "default_model" in payload_fields:
        return payload.default_model
    return profile.default_model


def _effective_reasoning_level(
    profile: ExecutorProfile,
    payload: ExecutorProfileUpdateRequest,
    payload_fields: set[str],
) -> str | None:
    if "reasoning_level" in payload_fields:
        return payload.reasoning_level
    return profile.reasoning_level


def _effective_env(
    profile: ExecutorProfile,
    payload: ExecutorProfileUpdateRequest,
    payload_fields: set[str],
) -> dict[str, str]:
    if "env" in payload_fields:
        return dict(payload.env or {})
    return dict(profile.env or {})


def _effective_secret_env(
    profile: ExecutorProfile,
    payload: ExecutorProfileUpdateRequest,
    payload_fields: set[str],
) -> dict[str, str]:
    current = dict(profile.secret_env or {})
    if "secret_env" not in payload_fields or payload.secret_env is None:
        return current
    for key, value in payload.secret_env.items():
        if value is None:
            _ = current.pop(key, None)
        else:
            current[key] = value
    return current


@router.post("/executor-profiles/{profile_id}/archive")
async def archive_executor_profile(
    profile_id: str,
    payload: VersionedCommand,
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    async with session.begin():
        profile = await repo.archive_executor_profile(
            session,
            profile_id=profile_id,
            version=version,
        )
    return DataEnvelope(data=ExecutorProfileResponse.from_model(profile).model_dump())
