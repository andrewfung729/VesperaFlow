"""Executor profile routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_store import repositories as repo

from ..dependencies import get_session
from ..schemas.executor_profiles import (
    ExecutorProfileCreateRequest,
    ExecutorProfileResponse,
    ExecutorProfileUpdateRequest,
)
from ..schemas.tasks import DataEnvelope, ListEnvelope, VersionedCommand
from ._shared import observed_version

router = APIRouter()


@router.post("/executor-profiles", status_code=201)
async def create_executor_profile(
    payload: ExecutorProfileCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    async with session.begin():
        profile = await repo.create_executor_profile(
            session,
            name=payload.name,
            executor=payload.executor,
            is_enabled=payload.is_enabled,
            is_default=payload.is_default,
            default_model=payload.default_model,
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
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DataEnvelope:
    version = observed_version(payload.version, if_match)
    payload_fields = payload.model_fields_set
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
            env=payload.env,
            set_env="env" in payload_fields,
            secret_env=payload.secret_env,
        )
    return DataEnvelope(data=ExecutorProfileResponse.from_model(profile).model_dump())


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
