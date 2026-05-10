"""API schemas for task templates."""

from datetime import datetime

from pydantic import BaseModel
from vesperaflow_core import ExecutionMode, ExecutorName
from vesperaflow_core.client_contracts import TemplateScheduleConfig
from vesperaflow_store.models import Template


class TemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str | None
    instruction_source: str
    default_task_title: str | None
    default_target_working_directory: str | None
    default_execution_mode: ExecutionMode
    default_schedule_config: TemplateScheduleConfig
    default_executor: ExecutorName | None
    default_executor_profile_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @classmethod
    def from_model(cls, template: Template) -> "TemplateResponse":
        return cls(
            template_id=template.template_id,
            name=template.name,
            description=template.description,
            instruction_source=template.instruction_source,
            default_task_title=template.default_task_title,
            default_target_working_directory=template.default_target_working_directory,
            default_execution_mode=template.default_execution_mode,
            default_schedule_config=TemplateScheduleConfig(
                schedule_type=template.default_schedule_type,
                planned_at=template.default_planned_at,
                recurrence_rule=template.default_recurrence_rule,
                recurrence_timezone=template.default_recurrence_timezone,
            ),
            default_executor=template.default_executor,
            default_executor_profile_id=template.default_executor_profile_id,
            version=template.version,
            created_at=template.created_at,
            updated_at=template.updated_at,
            archived_at=template.archived_at,
        )
