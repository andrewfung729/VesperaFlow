"""Worker runtime settings."""

from functools import lru_cache
from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="VESPERAFLOW_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = Field(default="")
    temporal_address: str = "localhost:17233"
    temporal_namespace: str = "default"
    task_queue: str = "vesperaflow-default"
    run_workspace_root: str = "/tmp/vesperaflow-runs"
    log_level: str = "INFO"

    @field_validator("database_url", mode="after")
    @classmethod
    def _database_url_required(cls, v: str) -> str:
        if not v:
            raise ValueError("VESPERAFLOW_DATABASE_URL must be set")
        return v


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
