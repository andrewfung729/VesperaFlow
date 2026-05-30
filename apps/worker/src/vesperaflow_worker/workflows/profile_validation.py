"""Executor profile validation workflow definition."""

from datetime import timedelta
from typing import cast

from temporalio import workflow
from vesperaflow_core import ProfileValidationInput, ProfileValidationResult


@workflow.defn(name="ExecutorProfileValidationWorkflow")
class ExecutorProfileValidationWorkflow:
    @workflow.run
    async def run(self, payload: ProfileValidationInput) -> ProfileValidationResult:
        workflow.logger.info(
            "workflow.executor_profile_validation.started",
            extra={
                "handoff_id": payload.handoff_id,
                "executor": payload.executor.value,
                "default_model": payload.default_model,
                "reasoning_level": payload.reasoning_level,
            },
        )
        result = cast(
            ProfileValidationResult,
            await workflow.execute_activity(
                "validate_executor_profile",
                payload,
                start_to_close_timeout=timedelta(seconds=90),
            ),
        )
        if isinstance(result, dict):
            result = ProfileValidationResult.model_validate(result)
        workflow.logger.info(
            "workflow.executor_profile_validation.completed",
            extra={
                "handoff_id": payload.handoff_id,
                "executor": payload.executor.value,
                "validation_ok": result.ok,
                "validation_code": result.code,
            },
        )
        return result
