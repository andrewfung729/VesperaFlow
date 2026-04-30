"""Run routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_store import repositories as repo

from ..dependencies import get_session
from ..schemas.tasks import DataEnvelope, RunResponse

router = APIRouter()


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    run = await repo.get_run(session, run_id)
    return DataEnvelope(data=RunResponse.from_model(run).model_dump())
