"""Run routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vesperaflow_store import repositories as repo

from ..dependencies import get_session
from ..schemas.tasks import DataEnvelope, ListEnvelope, RunEventResponse, RunResponse

router = APIRouter()


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataEnvelope:
    run = await repo.get_run(session, run_id)
    return DataEnvelope(data=RunResponse.from_model(run).model_dump())


@router.get("/runs/{run_id}/events")
async def list_run_events(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListEnvelope:
    events = await repo.list_run_events(
        session,
        run_id=run_id,
        limit=limit,
        offset=offset,
    )
    return ListEnvelope(
        data=[
            RunEventResponse.from_model(event).model_dump()
            for event in events.items
        ],
        meta={"total": events.total},
    )
