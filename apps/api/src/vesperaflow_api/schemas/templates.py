"""API schemas for task templates."""

from datetime import datetime

from pydantic import BaseModel, Field
from vesperaflow_core import ExecutionMode, ExecutorName, ScheduleType
from vesperaflow_store.models import Template


class TemplateScheduleConfig(BaseModel):
    schedule_type: ScheduleType
    planned_at: datetime | None = None
    recurrence_rule: str | None = None
    recurrence_timezone: str | None = None


class TemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str | None = None
    instruction_source: str = Field(min_length=1)
    default_task_title: str | None = Field(default=None, min_length=1, max_length=240)
    default_target_working_directory: str | None = Field(default=None, min_length=1)
    default_execution_mode: ExecutionMode
    default_schedule_config: TemplateScheduleConfig
    default_executor: ExecutorName | None = None


class TemplateUpdateRequest(BaseModel):
    version: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    instruction_source: str | None = Field(default=None, min_length=1)
    default_task_title: str | None = Field(default=None, min_length=1, max_length=240)
    default_target_working_directory: str | None = Field(default=None, min_length=1)
    default_execution_mode: ExecutionMode | None = None
    default_schedule_config: TemplateScheduleConfig | None = None
    default_executor: ExecutorName | None = None


class TemplateInstantiateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    instruction_source: str | None = Field(default=None, min_length=1)
    target_working_directory: str | None = Field(default=None, min_length=1)
    execution_mode: ExecutionMode | None = None
    executor: ExecutorName | None = None
    schedule: TemplateScheduleConfig | None = None


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
            version=template.version,
            created_at=template.created_at,
            updated_at=template.updated_at,
            archived_at=template.archived_at,
        )
