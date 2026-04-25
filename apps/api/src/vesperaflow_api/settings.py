"""API runtime settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from vesperaflow_core import ExecutorName


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
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
    run_workspace_root: str = "/tmp/vesperaflow-runs"
    default_executor: ExecutorName = ExecutorName.CLAUDE_CODE
    cors_origins: list[str] = ["http://localhost:5173"]
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
