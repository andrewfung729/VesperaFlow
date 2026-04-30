"""Worker runtime settings."""

from functools import lru_cache
from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CLAUDE_ENV = {
    "DISABLE_TELEMETRY": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_FEEDBACK_COMMAND": "1",
    "DISABLE_AUTOUPDATER": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ENABLE_LSP_TOOL": "1",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "CLAUDE_CODE_NO_FLICKER": "1",
}


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
    executor_adapter: str = "auto"
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
        repr=False,
    )
    anthropic_base_url: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_BASE_URL",
    )
    anthropic_model: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_MODEL",
    )
    codex_model: str | None = None

    @field_validator("database_url", mode="after")
    @classmethod
    def _database_url_required(cls, v: str) -> str:
        if not v:
            raise ValueError("VESPERAFLOW_DATABASE_URL must be set")
        return v

    def claude_executor_env(self) -> dict[str, str]:
        env: dict[str, str] = dict(DEFAULT_CLAUDE_ENV)
        if self.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = self.anthropic_api_key
        if self.anthropic_base_url:
            env["ANTHROPIC_BASE_URL"] = self.anthropic_base_url
        if self.anthropic_model:
            env["ANTHROPIC_MODEL"] = self.anthropic_model
        return env


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
