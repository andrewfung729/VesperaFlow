from datetime import datetime

import pytest
from pydantic import ValidationError
from vesperaflow_core import ExecutionMode, ExecutorName, ScheduleType
from vesperaflow_core.client_contracts import (
    ExecutorProfileCreateRequest,
    ScheduleCreate,
    TaskCreateRequest,
)


def test_task_create_request_serializes_api_payload() -> None:
    request = TaskCreateRequest(
        title="Fix flaky tests",
        instruction_source="Run pytest and fix failures.",
        target_working_directory="/tmp",
        execution_mode=ExecutionMode.ONE_TIME,
        executor=ExecutorName.DEBUG_PRINTER,
        schedule=ScheduleCreate(
            schedule_type=ScheduleType.SINGLE_RUN,
            planned_at=datetime.fromisoformat("2026-05-11T09:00:00+08:00"),
        ),
    )

    assert request.model_dump(mode="json", exclude_none=True) == {
        "title": "Fix flaky tests",
        "instruction_source": "Run pytest and fix failures.",
        "target_working_directory": "/tmp",
        "execution_mode": "one_time",
        "executor": "debug_printer",
        "schedule": {
            "schedule_type": "single_run",
            "planned_at": "2026-05-11T09:00:00+08:00",
        },
    }


def test_executor_profile_request_validates_env_keys() -> None:
    with pytest.raises(ValidationError):
        ExecutorProfileCreateRequest(
            name="Bad env",
            executor=ExecutorName.CODEX,
            env={"bad-key": "value"},
        )
