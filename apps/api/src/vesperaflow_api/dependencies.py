"""FastAPI dependencies."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .settings import ApiSettings
from .temporal_scheduler import TemporalScheduler

_settings: ApiSettings | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_scheduler: TemporalScheduler | None = None


def set_app_state(
    settings: ApiSettings,
    session_factory: async_sessionmaker[AsyncSession],
    scheduler: TemporalScheduler,
) -> None:
    global _settings, _session_factory, _scheduler
    _settings = settings
    _session_factory = session_factory
    _scheduler = scheduler


async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("session_factory not initialized")
    async with _session_factory() as session:
        yield session


def get_settings() -> ApiSettings:
    if _settings is None:
        raise RuntimeError("settings not initialized")
    return _settings


def get_scheduler() -> TemporalScheduler:
    if _scheduler is None:
        raise RuntimeError("scheduler not initialized")
    return _scheduler
