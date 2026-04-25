"""Worker runtime settings."""

from functools import lru_cache
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="VESPERAFLOW_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://vespera:password@localhost:5432/vespera"
    )
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = "vesperaflow-default"
    executor_adapter: str = "auto"
    claude_max_turns: int = 20
    claude_max_budget_usd: float | None = None


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
