"""API schemas for executor profiles."""

from datetime import datetime

from pydantic import BaseModel
from vesperaflow_core import ExecutorName
from vesperaflow_store.models import ExecutorProfile


class ExecutorProfileResponse(BaseModel):
    profile_id: str
    name: str
    executor: ExecutorName
    is_enabled: bool
    is_default: bool
    default_model: str | None
    env: dict[str, str]
    secret_env_keys: list[str]
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @classmethod
    def from_model(cls, profile: ExecutorProfile) -> "ExecutorProfileResponse":
        return cls(
            profile_id=profile.profile_id,
            name=profile.name,
            executor=profile.executor,
            is_enabled=profile.is_enabled,
            is_default=profile.is_default,
            default_model=profile.default_model,
            env=dict(profile.env or {}),
            secret_env_keys=sorted((profile.secret_env or {}).keys()),
            version=profile.version,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            archived_at=profile.archived_at,
        )
