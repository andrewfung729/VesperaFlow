"""Generate agent-readable system fact snapshots from the current code."""

from __future__ import annotations

import inspect
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args, get_origin

from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy import Index, UniqueConstraint
from vesperaflow_api.app import create_app
from vesperaflow_api.settings import ApiSettings
from vesperaflow_core import ExecutionSnapshot, TaskRunInput, temporal_schedule_id
from vesperaflow_store import Base
from vesperaflow_worker.activities import TaskRunActivities
from vesperaflow_worker.settings import WorkerSettings
from vesperaflow_worker.workflows import TaskRunWorkflow

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "generated"
COMMAND = "uv run python scripts/generate_agent_facts.py"


def main() -> int:
    GENERATED.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).date().isoformat()
    _write("db-schema.md", _db_schema(generated_at))
    _write("api-routes.md", _api_routes(generated_at))
    _write("temporal-surface.md", _temporal_surface(generated_at))
    _write("dependency-graph.md", _dependency_graph(generated_at))
    return 0


def _write(name: str, content: str) -> None:
    (GENERATED / name).write_text(content, encoding="utf-8")


def _header(title: str, generated_at: str, sources: list[str]) -> list[str]:
    return [
        f"# {title}",
        "",
        f"- Generated: {generated_at}",
        f"- Regenerate: `{COMMAND}`",
        f"- Sources: {', '.join(f'`{source}`' for source in sources)}",
        "- Limitations: generated from importable application metadata, "
        "not a live deployment.",
        "",
    ]


def _db_schema(generated_at: str) -> str:
    lines = _header(
        "Database Schema Snapshot",
        generated_at,
        [
            "packages/store/src/vesperaflow_store/models.py",
            "packages/store/alembic/versions/",
        ],
    )
    for table in sorted(Base.metadata.sorted_tables, key=lambda item: item.name):
        lines.extend(
            [f"## `{table.name}`", "", "| Column | Type | Nullable | Default |"]
        )
        lines.append("|---|---|---:|---|")
        for column in table.columns:
            default = ""
            if column.default is not None:
                default = str(column.default.arg)
            lines.append(
                f"| `{column.name}` | `{column.type}` | "
                f"{'yes' if column.nullable else 'no'} | `{default}` |"
            )
        if table.primary_key.columns:
            pk = ", ".join(f"`{column.name}`" for column in table.primary_key.columns)
            lines.extend(["", f"- Primary key: {pk}"])
        for constraint in sorted(
            table.constraints, key=lambda item: item.name or item.__class__.__name__
        ):
            if isinstance(constraint, UniqueConstraint):
                columns = ", ".join(f"`{column.name}`" for column in constraint.columns)
                lines.append(f"- Unique constraint `{constraint.name}`: {columns}")
        for fk in sorted(table.foreign_keys, key=lambda item: item.parent.name):
            lines.append(f"- Foreign key: `{fk.parent.name}` -> `{fk.column}`")
        indexes = sorted(table.indexes, key=lambda item: item.name or "")
        for index in indexes:
            if isinstance(index, Index):
                columns = ", ".join(f"`{column.name}`" for column in index.columns)
                lines.append(f"- Index `{index.name}`: {columns}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _api_routes(generated_at: str) -> str:
    app = create_app()
    lines = _header(
        "API Route Snapshot",
        generated_at,
        [
            "apps/api/src/vesperaflow_api/app.py",
            "apps/api/src/vesperaflow_api/routes/",
            "apps/api/src/vesperaflow_api/schemas/",
        ],
    )
    lines.extend(["| Methods | Path | Handler | Request model | Response annotation |"])
    lines.append("|---|---|---|---|---|")
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    for route in sorted(routes, key=lambda item: (item.path, sorted(item.methods))):
        methods = ", ".join(sorted(method for method in route.methods if method))
        endpoint = route.endpoint
        request_model = _request_model_name(endpoint)
        response = _type_name(inspect.signature(endpoint).return_annotation)
        lines.append(
            f"| `{methods}` | `{route.path}` | `{endpoint.__name__}` | "
            f"`{request_model}` | `{response}` |"
        )
    lines.extend(
        [
            "",
            "## Error Envelopes",
            "",
            "- Store errors map to `ErrorEnvelope` with 404, 409, or 500 status.",
            "- `ValueError` and request validation errors map to 422 "
            "`validation_error`.",
            "- `unsupported_operation` and `execution_unavailable` runtime "
            "errors map to 409.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _temporal_surface(generated_at: str) -> str:
    api_settings = ApiSettings()
    worker_settings = WorkerSettings()
    workflow = getattr(TaskRunWorkflow.run, "__temporal_workflow_definition", None)
    activities = _activity_names()
    lines = _header(
        "Temporal Surface Snapshot",
        generated_at,
        [
            "apps/api/src/vesperaflow_api/temporal_scheduler.py",
            "apps/worker/src/vesperaflow_worker/main.py",
            "apps/worker/src/vesperaflow_worker/workflows/",
            "apps/worker/src/vesperaflow_worker/activities/",
            "packages/core/src/vesperaflow_core/contracts.py",
        ],
    )
    workflow_name = getattr(workflow, "name", None) or "TaskRunWorkflow"
    lines.extend(
        [
            f"- Default API task queue: `{api_settings.task_queue}`",
            f"- Default Worker task queue: `{worker_settings.task_queue}`",
            f"- Default namespace: `{api_settings.temporal_namespace}`",
            f"- Workflow type: `{workflow_name}`",
            "- Workflow class: "
            f"`{TaskRunWorkflow.__module__}.{TaskRunWorkflow.__name__}`",
            f"- Schedule ID helper: `{temporal_schedule_id('sch_example')}`",
            "- Workflow ID helper: `vesperaflow.run.<run_id>`",
            "- Data converter: `temporalio.contrib.pydantic.pydantic_data_converter`",
            "",
            "## Activities",
            "",
        ]
    )
    for activity_name in activities:
        lines.append(f"- `{activity_name}`")
    lines.extend(
        [
            "",
            "## Payload Models",
            "",
            _model_fields("TaskRunInput", TaskRunInput),
            "",
            _model_fields("ExecutionSnapshot", ExecutionSnapshot),
            "",
            "## Schedule Behavior",
            "",
            "- One-time API creation creates a Temporal Schedule whose action "
            "starts `TaskRunWorkflow`.",
            "- The product `runs` row is created before Schedule creation and "
            "passed to the Workflow by `run_id`.",
            "- Recurring API creation creates a Temporal Schedule whose action "
            "starts `TaskRunWorkflow` without a pre-existing `run_id`.",
            "- The first persistence Activity materializes each recurring "
            "occurrence into a product `runs` row idempotently by "
            "`(schedule_id, occurrence_key)`.",
            "- Pause/resume/update/cancel commands mutate both PostgreSQL "
            "schedule truth and the matching Temporal Schedule.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _dependency_graph(generated_at: str) -> str:
    lines = _header(
        "Package Dependency Snapshot",
        generated_at,
        ["pyproject.toml", "apps/*/pyproject.toml", "packages/*/pyproject.toml"],
    )
    lines.extend(
        [
            "```mermaid",
            "flowchart LR",
            '  api["apps/api"] --> core["packages/core"]',
            '  api --> store["packages/store"]',
            "  api --> temporalio[temporalio]",
            "  store --> core",
            '  worker["apps/worker"] --> core',
            "  worker --> store",
            "  worker --> temporalio",
            "  worker --> claude[claude-agent-sdk]",
            '  web["apps/web"] --> api_contract["HTTP /api/v1"]',
            "```",
            "",
            "## Notes",
            "",
            "- `packages/core` is dependency-light and imported by Workflows.",
            "- `packages/store` owns SQLAlchemy models and repository behavior.",
            "- `apps/api` creates Temporal Schedules but does not execute agents.",
            "- `apps/worker` executes Workflows and Activities and owns "
            "executor adapters.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _request_model_name(endpoint: Any) -> str:
    for parameter in inspect.signature(endpoint).parameters.values():
        annotation = parameter.annotation
        if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            return annotation.__name__
    return ""


def _type_name(annotation: Any) -> str:
    if annotation is inspect.Signature.empty:
        return ""
    if isinstance(annotation, str):
        return annotation
    origin = get_origin(annotation)
    if origin is types.UnionType:
        return " | ".join(_type_name(arg) for arg in get_args(annotation))
    if origin is not None:
        args = ", ".join(_type_name(arg) for arg in get_args(annotation))
        return f"{_type_name(origin)}[{args}]"
    if annotation is None or annotation is types.NoneType:
        return "None"
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


def _activity_names() -> list[str]:
    activities = []
    for _, member in inspect.getmembers(TaskRunActivities, inspect.iscoroutinefunction):
        definition = getattr(member, "__temporal_activity_definition", None)
        if definition is not None:
            activities.append((inspect.getsourcelines(member)[1], definition.name))
    return [name for _, name in sorted(activities)]


def _model_fields(name: str, model: type[BaseModel]) -> str:
    lines = [f"### `{name}`", "", "| Field | Type | Required |", "|---|---|---:|"]
    for field_name, field in model.model_fields.items():
        lines.append(
            f"| `{field_name}` | `{_type_name(field.annotation)}` | "
            f"{'yes' if field.is_required() else 'no'} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
