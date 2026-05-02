"""API runtime settings."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(  # pyright: ignore[reportIncompatibleVariableOverride]
        env_prefix="VESPERAFLOW_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = Field(default="")
    temporal_address: str = "localhost:17233"
    temporal_namespace: str = "default"
    task_queue: str = "vesperaflow-default"
    run_workspace_root: str = "/tmp/vesperaflow-runs"
    cors_origins: list[str] = ["http://localhost:15173"]
    host: str = "0.0.0.0"
    port: int = 18000

    @field_validator("database_url", mode="after")
    @classmethod
    def _database_url_required(cls, v: str) -> str:
        if not v:
            raise ValueError("VESPERAFLOW_DATABASE_URL must be set")
        return v


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
