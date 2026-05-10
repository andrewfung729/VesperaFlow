"""Agent-friendly CLI for the VesperaFlow HTTP API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar, NoReturn, TextIO, TypeIs, override
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, TypeAdapter
from vesperaflow_core import ExecutionMode, ScheduleType
from vesperaflow_core.client_contracts import ScheduleCreate, TaskCreateRequest

DEFAULT_API_URL = "http://127.0.0.1:18000/api/v1"
API_URL_ENV = "VESPERAFLOW_API_URL"
type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]
type QueryValue = str | int | float | bool


class CliUsageError(Exception):
    """Raised when parsed arguments fail local CLI validation."""


class RaisingArgumentParser(argparse.ArgumentParser):
    @override
    def error(self, message: str) -> NoReturn:
        raise CliUsageError(message)


@dataclass(frozen=True)
class CliContext:
    api_url: str
    timeout: float
    json_output: bool
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO
    transport: httpx.BaseTransport | None


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    body: JsonObject
    formatter: Callable[[JsonObject], str] | None = None


# --------------------------------------------------------------------------- #
# Typed argument models                                                       #
# --------------------------------------------------------------------------- #
# Per-command Pydantic models replace dynamic `getattr(args, name)` lookups
# (which are typed `Any`). `vars(args)` is validated once into the relevant
# model, after which all field accesses are statically typed and require no
# `cast` at the boundary. `extra="ignore"` lets each command-specific model
# coexist with the global routing fields in `argparse.Namespace`.


_IGNORE_EXTRA: ConfigDict = ConfigDict(extra="ignore")


class _RoutingArgs(BaseModel):
    model_config: ClassVar[ConfigDict] = _IGNORE_EXTRA
    api_url: str | None = None
    timeout: float = 10.0
    json_output: bool = False
    resource: str
    action: str


class _TaskCreateArgs(BaseModel):
    model_config: ClassVar[ConfigDict] = _IGNORE_EXTRA
    title: str
    instruction: str | None = None
    instruction_file: str | None = None
    cwd: str | None = None
    executor_profile: str | None = None
    executor: str | None = None
    template_id: str | None = None
    at: str | None = None
    rrule: str | None = None
    timezone: str | None = None


class _TaskListArgs(BaseModel):
    model_config: ClassVar[ConfigDict] = _IGNORE_EXTRA
    status: str | None = None
    execution_mode: str | None = None
    include_archived: bool = False
    limit: int = 100
    offset: int = 0


class _TaskIdArg(BaseModel):
    model_config: ClassVar[ConfigDict] = _IGNORE_EXTRA
    task_id: str


class _TaskRunsArgs(BaseModel):
    model_config: ClassVar[ConfigDict] = _IGNORE_EXTRA
    task_id: str
    status: str | None = None
    limit: int = 100
    offset: int = 0


class _RunIdArg(BaseModel):
    model_config: ClassVar[ConfigDict] = _IGNORE_EXTRA
    run_id: str


class _RunEventsArgs(BaseModel):
    model_config: ClassVar[ConfigDict] = _IGNORE_EXTRA
    run_id: str
    limit: int = 100
    offset: int = 0


class _ExecutorPreflightArgs(BaseModel):
    model_config: ClassVar[ConfigDict] = _IGNORE_EXTRA
    executor_profile: str | None = None
    executor: str | None = None
    cwd: str | None = None


# `TypeAdapter` validates an arbitrary `Any` (from `httpx.Response.json()`)
# into a fully-typed `JsonValue`. Wrapping the validation step here is what
# lets `_response_body` accept the JSON body without leaking `Any` into the
# rest of the CLI.
_JSON_VALUE_ADAPTER: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


# --------------------------------------------------------------------------- #
# Entry point and dispatch                                                    #
# --------------------------------------------------------------------------- #


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    env: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    parser = _build_parser()
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    input_stream = stdin or sys.stdin
    environ = env or os.environ

    try:
        args = parser.parse_args(argv)
        routing = _RoutingArgs.model_validate(vars(args))
        context = CliContext(
            api_url=_resolve_api_url(routing.api_url, environ),
            timeout=routing.timeout,
            json_output=routing.json_output,
            stdin=input_stream,
            stdout=out,
            stderr=err,
            transport=transport,
        )
        handler = _DISPATCH[(routing.resource, routing.action)]
        result = handler(args, context)
    except CliUsageError as exc:
        message = str(exc)
        if message:
            print(f"usage error: {message}", file=err)
        return 2

    _write_result(context, result)
    return result.exit_code


def _build_parser() -> RaisingArgumentParser:
    parser = RaisingArgumentParser(prog="vespera")
    _ = parser.add_argument(
        "--api-url",
        default=None,
        help="VesperaFlow /api/v1 base URL.",
    )
    _ = parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print machine-readable JSON.",
    )
    _ = parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds.",
    )

    resources = parser.add_subparsers(dest="resource", required=True)
    _add_task_commands(resources.add_parser("task"))
    _add_run_commands(resources.add_parser("run"))
    _add_executor_commands(resources.add_parser("executor"))
    _add_profile_commands(resources.add_parser("profile"))
    return parser


def _add_task_commands(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="action", required=True)

    create = commands.add_parser("create")
    _ = create.add_argument("--title", required=True)
    instruction = create.add_mutually_exclusive_group(required=True)
    _ = instruction.add_argument("--instruction")
    _ = instruction.add_argument("--instruction-file")
    _ = create.add_argument("--cwd")
    _ = create.add_argument("--executor-profile", dest="executor_profile")
    _ = create.add_argument("--executor")
    _ = create.add_argument("--template-id")
    _ = create.add_argument("--at")
    _ = create.add_argument("--rrule")
    _ = create.add_argument("--timezone")

    list_tasks = commands.add_parser("list")
    _ = list_tasks.add_argument("--status")
    _ = list_tasks.add_argument("--execution-mode")
    _ = list_tasks.add_argument("--include-archived", action="store_true")
    _ = list_tasks.add_argument("--limit", type=int, default=100)
    _ = list_tasks.add_argument("--offset", type=int, default=0)

    detail = commands.add_parser("detail")
    _ = detail.add_argument("task_id")

    run_now = commands.add_parser("run-now")
    _ = run_now.add_argument("task_id")

    runs = commands.add_parser("runs")
    _ = runs.add_argument("task_id")
    _ = runs.add_argument("--status")
    _ = runs.add_argument("--limit", type=int, default=100)
    _ = runs.add_argument("--offset", type=int, default=0)


def _add_run_commands(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="action", required=True)

    get = commands.add_parser("get")
    _ = get.add_argument("run_id")

    events = commands.add_parser("events")
    _ = events.add_argument("run_id")
    _ = events.add_argument("--limit", type=int, default=100)
    _ = events.add_argument("--offset", type=int, default=0)


def _add_executor_commands(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="action", required=True)

    preflight = commands.add_parser("preflight")
    _ = preflight.add_argument("--executor-profile", dest="executor_profile")
    _ = preflight.add_argument("--executor")
    _ = preflight.add_argument("--cwd")


def _add_profile_commands(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="action", required=True)
    _ = commands.add_parser("list")


def _handle_task_create(args: argparse.Namespace, context: CliContext) -> CommandResult:
    parsed = _TaskCreateArgs.model_validate(vars(args))
    if parsed.cwd is None and parsed.template_id is None:
        raise CliUsageError("--cwd is required unless --template-id is provided")
    if (
        parsed.executor_profile is None
        and parsed.executor is None
        and parsed.template_id is None
    ):
        message = (
            "--executor-profile or --executor is required unless"
            + " --template-id is provided"
        )
        raise CliUsageError(message)

    schedule = _task_create_schedule(parsed)
    task_request = _task_create_request(
        title=parsed.title,
        instruction_source=_read_instruction(
            parsed.instruction,
            parsed.instruction_file,
            context.stdin,
        ),
        target_working_directory=(
            _absolute_path(parsed.cwd) if parsed.cwd is not None else None
        ),
        template_id=parsed.template_id,
        executor_profile_id=parsed.executor_profile,
        executor=parsed.executor,
        schedule=schedule,
    )
    # `model_dump(mode="json", ...)` returns `dict[str, Any]`; `_request` accepts
    # `Mapping[str, object]`, so no cast is needed at the boundary.
    payload = task_request.model_dump(mode="json", exclude_none=True)
    return _request(
        context,
        "POST",
        "tasks",
        json_body=payload,
        formatter=_format_task_bundle,
    )


def _handle_task_list(args: argparse.Namespace, context: CliContext) -> CommandResult:
    parsed = _TaskListArgs.model_validate(vars(args))
    params = _query_without_none(
        {
            "status": parsed.status,
            "execution_mode": parsed.execution_mode,
            "include_archived": parsed.include_archived or None,
            "limit": parsed.limit,
            "offset": parsed.offset,
        }
    )
    return _request(context, "GET", "tasks", params=params, formatter=_format_task_list)


def _handle_task_detail(args: argparse.Namespace, context: CliContext) -> CommandResult:
    parsed = _TaskIdArg.model_validate(vars(args))
    return _request(
        context,
        "GET",
        f"tasks/{parsed.task_id}/detail",
        formatter=_format_task_detail,
    )


def _handle_task_run_now(
    args: argparse.Namespace,
    context: CliContext,
) -> CommandResult:
    parsed = _TaskIdArg.model_validate(vars(args))
    return _request(
        context,
        "POST",
        f"tasks/{parsed.task_id}/run-now",
        formatter=_format_run,
    )


def _handle_task_runs(args: argparse.Namespace, context: CliContext) -> CommandResult:
    parsed = _TaskRunsArgs.model_validate(vars(args))
    params = _query_without_none(
        {
            "status": parsed.status,
            "limit": parsed.limit,
            "offset": parsed.offset,
        }
    )
    return _request(
        context,
        "GET",
        f"tasks/{parsed.task_id}/runs",
        params=params,
        formatter=_format_run_list,
    )


def _handle_run_get(args: argparse.Namespace, context: CliContext) -> CommandResult:
    parsed = _RunIdArg.model_validate(vars(args))
    return _request(
        context,
        "GET",
        f"runs/{parsed.run_id}",
        formatter=_format_run,
    )


def _handle_run_events(args: argparse.Namespace, context: CliContext) -> CommandResult:
    parsed = _RunEventsArgs.model_validate(vars(args))
    params: dict[str, QueryValue] = {"limit": parsed.limit, "offset": parsed.offset}
    return _request(
        context,
        "GET",
        f"runs/{parsed.run_id}/events",
        params=params,
        formatter=_format_event_list,
    )


def _handle_executor_preflight(
    args: argparse.Namespace, context: CliContext
) -> CommandResult:
    parsed = _ExecutorPreflightArgs.model_validate(vars(args))
    params = _query_without_none(
        {
            "executor_profile_id": parsed.executor_profile,
            "executor": parsed.executor,
            "target_working_directory": (
                _absolute_path(parsed.cwd) if parsed.cwd is not None else None
            ),
        }
    )
    return _request(
        context,
        "GET",
        "executors/preflight",
        params=params,
        formatter=_format_preflight,
    )


def _handle_profile_list(_: argparse.Namespace, context: CliContext) -> CommandResult:
    return _request(
        context,
        "GET",
        "executor-profiles",
        formatter=_format_profile_list,
    )


type _Handler = Callable[[argparse.Namespace, CliContext], CommandResult]


# Static dispatch table replaces the previous `args.handler` (typed `Any`) and
# the `cast(Callable, args.handler)` it required. The keys mirror the
# (resource, action) pair captured by argparse's nested subparsers.
_DISPATCH: Mapping[tuple[str, str], _Handler] = {
    ("task", "create"): _handle_task_create,
    ("task", "list"): _handle_task_list,
    ("task", "detail"): _handle_task_detail,
    ("task", "run-now"): _handle_task_run_now,
    ("task", "runs"): _handle_task_runs,
    ("run", "get"): _handle_run_get,
    ("run", "events"): _handle_run_events,
    ("executor", "preflight"): _handle_executor_preflight,
    ("profile", "list"): _handle_profile_list,
}


def _task_create_request(
    *,
    title: str,
    instruction_source: str,
    target_working_directory: str | None,
    template_id: str | None,
    executor_profile_id: str | None,
    executor: str | None,
    schedule: ScheduleCreate,
) -> TaskCreateRequest:
    body: dict[str, object] = {
        "title": title,
        "instruction_source": instruction_source,
        "target_working_directory": target_working_directory,
        "execution_mode": (
            ExecutionMode.ONE_TIME
            if schedule.schedule_type is ScheduleType.SINGLE_RUN
            else ExecutionMode.RECURRING
        ),
        "template_id": template_id,
        "executor_profile_id": executor_profile_id,
        "executor": executor,
        "schedule": schedule,
    }
    try:
        return TaskCreateRequest.model_validate(body)
    except ValueError as exc:
        raise CliUsageError(str(exc)) from exc


def _task_create_schedule(parsed: _TaskCreateArgs) -> ScheduleCreate:
    at = parsed.at
    has_recurring = parsed.rrule is not None or parsed.timezone is not None
    if at is not None and has_recurring:
        raise CliUsageError("--at cannot be combined with --rrule or --timezone")
    if at is not None:
        _require_timezone(at)
        return ScheduleCreate.model_validate(
            {"schedule_type": ScheduleType.SINGLE_RUN, "planned_at": at}
        )
    if parsed.rrule is None or parsed.timezone is None:
        raise CliUsageError("provide either --at or both --rrule and --timezone")
    return ScheduleCreate.model_validate(
        {
            "schedule_type": ScheduleType.RECURRING_RULE,
            "recurrence_rule": parsed.rrule,
            "recurrence_timezone": parsed.timezone,
        }
    )


def _read_instruction(
    instruction: str | None,
    instruction_file: str | None,
    stdin: TextIO,
) -> str:
    if instruction is not None:
        return _require_nonempty_instruction(instruction)
    if instruction_file == "-":
        return _require_nonempty_instruction(stdin.read())
    if instruction_file is not None:
        try:
            return _require_nonempty_instruction(
                Path(instruction_file).expanduser().read_text(encoding="utf-8")
            )
        except OSError as exc:
            raise CliUsageError(f"cannot read --instruction-file: {exc}") from exc
    raise CliUsageError("--instruction or --instruction-file is required")


def _require_nonempty_instruction(value: str) -> str:
    if not value.strip():
        raise CliUsageError("instruction must not be empty")
    return value


def _require_timezone(value: str) -> None:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CliUsageError("--at must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CliUsageError("--at must include an explicit timezone offset")


def _absolute_path(value: str) -> str:
    return str(Path(value).expanduser().resolve(strict=False))


def _resolve_api_url(value: str | None, env: Mapping[str, str]) -> str:
    raw = value or env.get(API_URL_ENV) or DEFAULT_API_URL
    base_url = raw.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CliUsageError("--api-url must be an absolute HTTP(S) URL")
    if not parsed.path.endswith("/api/v1"):
        raise CliUsageError("--api-url must point to the /api/v1 base path")
    return base_url + "/"


def _request(
    context: CliContext,
    method: str,
    path: str,
    *,
    json_body: Mapping[str, object] | None = None,
    params: Mapping[str, QueryValue] | None = None,
    formatter: Callable[[JsonObject], str] | None = None,
) -> CommandResult:
    try:
        with httpx.Client(
            base_url=context.api_url,
            timeout=context.timeout,
            transport=context.transport,
        ) as client:
            response = client.request(method, path, json=json_body, params=params)
    except httpx.RequestError as exc:
        return CommandResult(
            exit_code=2,
            body=_error_body("network_error", str(exc), {}),
        )

    body = _response_body(response)
    if response.is_error:
        return CommandResult(exit_code=1, body=_normalized_error_body(body, response))
    return CommandResult(exit_code=0, body=body, formatter=formatter)


def _is_json_object(value: object) -> TypeIs[JsonObject]:
    """Trust-boundary narrowing predicate.

    Returning ``True`` is a signal to type checkers that ``value`` may be used
    as a ``JsonObject``. The runtime check is intentionally shallow because
    callers only narrow values that already came out of ``response.json()`` or
    a structurally-validated ``JsonObject``, both of which guarantee string
    keys and JSON-shaped children.
    """
    return isinstance(value, dict)


def _response_body(response: httpx.Response) -> JsonObject:
    try:
        decoded: JsonValue = _JSON_VALUE_ADAPTER.validate_python(response.json())
    except ValueError:
        return _error_body(
            "invalid_response",
            "API response was not valid JSON",
            {"status_code": response.status_code},
        )
    if _is_json_object(decoded):
        return decoded
    return _error_body(
        "invalid_response",
        "API response JSON was not an object",
        {"status_code": response.status_code},
    )


def _normalized_error_body(
    body: JsonObject,
    response: httpx.Response,
) -> JsonObject:
    error = body.get("error")
    if isinstance(error, dict):
        return body
    return _error_body(
        "api_error",
        f"API returned HTTP {response.status_code}",
        {"status_code": response.status_code},
    )


def _error_body(
    code: str,
    message: str,
    details: JsonObject,
) -> JsonObject:
    return {"error": {"code": code, "message": message, "details": details}}


def _write_result(context: CliContext, result: CommandResult) -> None:
    if context.json_output:
        print(json.dumps(result.body, ensure_ascii=False), file=context.stdout)
        return
    if result.exit_code != 0:
        error = result.body.get("error")
        error_values = error if isinstance(error, dict) else {}
        code_value = error_values.get("code")
        message_value = error_values.get("message")
        code = code_value if isinstance(code_value, str) else "error"
        message = message_value if isinstance(message_value, str) else "command failed"
        print(f"error: {code}: {message}", file=context.stderr)
        return
    if result.formatter is None:
        print(
            json.dumps(result.body, ensure_ascii=False, indent=2),
            file=context.stdout,
        )
        return
    print(result.formatter(result.body), file=context.stdout)


def _query_without_none(
    values: Mapping[str, QueryValue | None],
) -> dict[str, QueryValue]:
    return {key: value for key, value in values.items() if value is not None}


def _format_task_bundle(body: JsonObject) -> str:
    data = _data_dict(body)
    task = _json_object(data.get("task"))
    schedule = _json_object(data.get("schedule"))
    run = _json_object_or_none(data.get("run"))
    lines = [_format_object("task", task), _format_object("schedule", schedule)]
    if run is not None:
        lines.append(_format_object("run", run))
    return "\n".join(lines)


def _format_task_list(body: JsonObject) -> str:
    return _table(
        _data_list(body),
        [
            "task_id",
            "title",
            "execution_mode",
            "task_status",
            "executor",
            "executor_profile_id",
        ],
    )


def _format_task_detail(body: JsonObject) -> str:
    return _format_task_bundle(body)


def _format_run(body: JsonObject) -> str:
    return _format_object("run", _data_dict(body))


def _format_run_list(body: JsonObject) -> str:
    return _table(
        _data_list(body),
        ["run_id", "run_status", "planned_start_at", "finished_at", "occurrence_key"],
    )


def _format_event_list(body: JsonObject) -> str:
    return _table(
        _data_list(body),
        ["run_event_id", "created_at", "severity", "event_type", "message"],
    )


def _format_preflight(body: JsonObject) -> str:
    data = _data_dict(body)
    return _format_object("executor", data)


def _format_profile_list(body: JsonObject) -> str:
    return _table(
        _data_list(body),
        ["profile_id", "name", "executor", "is_enabled", "is_default", "default_model"],
    )


def _format_object(label: str, values: Mapping[str, JsonValue]) -> str:
    if not values:
        return f"{label}: -"
    rendered = ", ".join(f"{key}={_cell(value)}" for key, value in values.items())
    return f"{label}: {rendered}"


def _table(rows: Sequence[Mapping[str, JsonValue]], columns: Sequence[str]) -> str:
    if not rows:
        return "no results"
    widths = {
        column: max(len(column), *(len(_cell(row.get(column))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    divider = "  ".join("-" * widths[column] for column in columns)
    lines = [header, divider]
    for row in rows:
        lines.append(
            "  ".join(
                _cell(row.get(column)).ljust(widths[column]) for column in columns
            )
        )
    return "\n".join(lines)


def _cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _data_dict(body: JsonObject) -> JsonObject:
    data = body.get("data")
    if _is_json_object(data):
        return data
    return {}


def _data_list(body: JsonObject) -> list[JsonObject]:
    data = body.get("data")
    if not isinstance(data, list):
        return []
    return [item for item in data if _is_json_object(item)]


def _json_object(value: JsonValue) -> JsonObject:
    if _is_json_object(value):
        return value
    return {}


def _json_object_or_none(value: JsonValue) -> JsonObject | None:
    if value is None:
        return None
    return _json_object(value)


if __name__ == "__main__":
    raise SystemExit(main())
