"""Import boundary tests for shared HTTP request contracts."""

from inspect import signature

import vesperaflow_core.client_contracts as client_contracts
from vesperaflow_api.routes import executor_profiles, tasks, templates
from vesperaflow_api.schemas import executor_profiles as executor_profile_schemas
from vesperaflow_api.schemas import tasks as task_schemas
from vesperaflow_api.schemas import templates as template_schemas


def test_api_routes_import_request_contracts_from_core() -> None:
    assert (
        signature(tasks.create_task).parameters["payload"].annotation
        is client_contracts.TaskCreateRequest
    )
    assert (
        signature(tasks.update_task).parameters["payload"].annotation
        is client_contracts.TaskUpdateRequest
    )
    assert (
        signature(tasks.update_schedule).parameters["payload"].annotation
        is client_contracts.ScheduleUpdateRequest
    )
    assert (
        signature(tasks.pause_schedule).parameters["payload"].annotation
        is client_contracts.VersionedCommand
    )
    assert (
        signature(tasks.update_occurrence).parameters["payload"].annotation
        is client_contracts.OccurrenceUpdateRequest
    )
    assert (
        signature(tasks.cancel_occurrence).parameters["payload"].annotation
        is client_contracts.OccurrenceCancelRequest
    )
    assert (
        signature(templates.create_template).parameters["payload"].annotation
        is client_contracts.TemplateCreateRequest
    )
    assert (
        signature(templates.update_template).parameters["payload"].annotation
        is client_contracts.TemplateUpdateRequest
    )
    assert (
        signature(templates.archive_template).parameters["payload"].annotation
        is client_contracts.VersionedCommand
    )
    assert (
        signature(templates.instantiate_template).parameters["payload"].annotation
        is client_contracts.TemplateInstantiateRequest
    )
    assert (
        signature(executor_profiles.create_executor_profile)
        .parameters["payload"]
        .annotation
        is client_contracts.ExecutorProfileCreateRequest
    )
    assert (
        signature(executor_profiles.update_executor_profile)
        .parameters["payload"]
        .annotation
        is client_contracts.ExecutorProfileUpdateRequest
    )
    assert (
        signature(executor_profiles.archive_executor_profile)
        .parameters["payload"]
        .annotation
        is client_contracts.VersionedCommand
    )


def test_api_schema_modules_do_not_reexport_request_contracts() -> None:
    task_request_names = {
        "OccurrenceCancelRequest",
        "OccurrenceUpdateRequest",
        "ScheduleCreate",
        "ScheduleUpdateRequest",
        "TaskCreateRequest",
        "TaskUpdateRequest",
        "VersionedCommand",
    }
    template_request_names = {
        "TemplateCreateRequest",
        "TemplateInstantiateRequest",
        "TemplateUpdateRequest",
    }
    executor_profile_request_names = {
        "ExecutorProfileCreateRequest",
        "ExecutorProfileUpdateRequest",
    }

    assert task_request_names.isdisjoint(task_schemas.__dict__)
    assert template_request_names.isdisjoint(template_schemas.__dict__)
    assert executor_profile_request_names.isdisjoint(
        executor_profile_schemas.__dict__
    )
