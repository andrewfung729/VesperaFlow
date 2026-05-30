from __future__ import annotations

import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
from vesperaflow_cli.main import main


@contextmanager
def _mock_transport(
    response: httpx.Response | Exception,
) -> Iterator[tuple[httpx.MockTransport, list[httpx.Request]]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if isinstance(response, Exception):
            raise response
        return response

    yield httpx.MockTransport(handler), requests


def _run(
    argv: list[str],
    *,
    transport: httpx.BaseTransport,
    stdin: io.StringIO | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        argv,
        stdin=stdin or io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        env=env or {},
        transport=transport,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _success(data: object) -> httpx.Response:
    return httpx.Response(200, json={"data": data})


def _created(data: object) -> httpx.Response:
    return httpx.Response(201, json={"data": data})


def test_task_create_builds_one_time_payload() -> None:
    with _mock_transport(_created({"task": {"task_id": "task_1"}})) as (
        transport,
        requests,
    ):
        exit_code, stdout, stderr = _run(
            [
                "--api-url",
                "http://testserver/api/v1/",
                "--json",
                "task",
                "create",
                "--title",
                "Fix tests",
                "--instruction",
                "Run pytest and fix failures.",
                "--cwd",
                ".",
                "--executor-profile",
                "xpr_default_codex",
                "--at",
                "2026-05-11T09:00:00+08:00",
            ],
            transport=transport,
        )

    assert exit_code == 0
    assert stderr == ""
    assert json.loads(stdout) == {"data": {"task": {"task_id": "task_1"}}}
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/v1/tasks"
    payload = json.loads(requests[0].content)
    assert payload["title"] == "Fix tests"
    assert payload["instruction_source"] == "Run pytest and fix failures."
    assert payload["target_working_directory"] == str(Path(".").resolve())
    assert payload["execution_mode"] == "one_time"
    assert payload["executor_profile_id"] == "xpr_default_codex"
    assert payload["schedule"] == {
        "schedule_type": "single_run",
        "planned_at": "2026-05-11T09:00:00+08:00",
    }


def test_task_create_builds_recurring_payload() -> None:
    with _mock_transport(_created({"task": {"task_id": "task_recurring"}})) as (
        transport,
        requests,
    ):
        exit_code, _, _ = _run(
            [
                "--json",
                "task",
                "create",
                "--title",
                "Daily triage",
                "--instruction",
                "Summarize blockers.",
                "--cwd",
                "/tmp",
                "--executor",
                "debug_printer",
                "--rrule",
                "RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
                "--timezone",
                "Asia/Hong_Kong",
            ],
            transport=transport,
        )

    assert exit_code == 0
    payload = json.loads(requests[0].content)
    assert payload["execution_mode"] == "recurring"
    assert payload["executor"] == "debug_printer"
    assert payload["schedule"] == {
        "schedule_type": "recurring_rule",
        "recurrence_rule": "RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0",
        "recurrence_timezone": "Asia/Hong_Kong",
    }


def test_task_create_reads_instruction_file_and_stdin(tmp_path: Path) -> None:
    instruction_file = tmp_path / "prompt.md"
    instruction_file.write_text("File prompt", encoding="utf-8")

    with _mock_transport(_created({"task": {"task_id": "task_file"}})) as (
        transport,
        requests,
    ):
        file_exit, _, _ = _run(
            [
                "--json",
                "task",
                "create",
                "--title",
                "From file",
                "--instruction-file",
                str(instruction_file),
                "--template-id",
                "tpl_1",
                "--at",
                "2026-05-11T09:00:00+08:00",
            ],
            transport=transport,
        )

    assert file_exit == 0
    assert json.loads(requests[0].content)["instruction_source"] == "File prompt"

    with _mock_transport(_created({"task": {"task_id": "task_stdin"}})) as (
        transport,
        requests,
    ):
        stdin_exit, _, _ = _run(
            [
                "--json",
                "task",
                "create",
                "--title",
                "From stdin",
                "--instruction-file",
                "-",
                "--template-id",
                "tpl_1",
                "--at",
                "2026-05-11T09:00:00+08:00",
            ],
            transport=transport,
            stdin=io.StringIO("Stdin prompt"),
        )

    assert stdin_exit == 0
    assert json.loads(requests[0].content)["instruction_source"] == "Stdin prompt"


def test_api_url_argument_overrides_environment() -> None:
    with _mock_transport(_success([])) as (transport, requests):
        env_exit, _, _ = _run(
            ["--json", "profile", "list"],
            transport=transport,
            env={"VESPERAFLOW_API_URL": "http://env.example/api/v1"},
        )

    assert env_exit == 0
    assert requests[0].url.host == "env.example"

    with _mock_transport(_success([])) as (transport, requests):
        arg_exit, _, _ = _run(
            [
                "--api-url",
                "http://arg.example/api/v1",
                "--json",
                "profile",
                "list",
            ],
            transport=transport,
            env={"VESPERAFLOW_API_URL": "http://env.example/api/v1"},
        )

    assert arg_exit == 0
    assert requests[0].url.host == "arg.example"


def test_api_error_outputs_json_and_exit_code_one() -> None:
    response = httpx.Response(
        422,
        json={
            "error": {
                "code": "validation_error",
                "message": "Bad request",
                "details": {"field": "title"},
            }
        },
    )
    with _mock_transport(response) as (transport, _):
        exit_code, stdout, stderr = _run(
            ["--json", "profile", "list"],
            transport=transport,
        )

    assert exit_code == 1
    assert stderr == ""
    assert json.loads(stdout)["error"] == {
        "code": "validation_error",
        "message": "Bad request",
        "details": {"field": "title"},
    }


def test_network_error_outputs_json_and_exit_code_two() -> None:
    request = httpx.Request("GET", "http://testserver/api/v1/tasks")
    with _mock_transport(httpx.ConnectError("connection refused", request=request)) as (
        transport,
        _,
    ):
        exit_code, stdout, stderr = _run(
            ["--json", "profile", "list"],
            transport=transport,
        )

    assert exit_code == 2
    assert stderr == ""
    assert json.loads(stdout)["error"]["code"] == "network_error"


def test_task_create_rejects_invalid_schedule_arguments() -> None:
    with _mock_transport(_created({})) as (transport, requests):
        missing_timezone_exit, _, _ = _run(
            [
                "task",
                "create",
                "--title",
                "Missing timezone",
                "--instruction",
                "Do work",
                "--cwd",
                "/tmp",
                "--executor",
                "debug_printer",
                "--at",
                "2026-05-11T09:00:00",
            ],
            transport=transport,
        )
        mixed_exit, _, _ = _run(
            [
                "task",
                "create",
                "--title",
                "Mixed",
                "--instruction",
                "Do work",
                "--cwd",
                "/tmp",
                "--executor",
                "debug_printer",
                "--at",
                "2026-05-11T09:00:00+08:00",
                "--rrule",
                "RRULE:FREQ=DAILY",
                "--timezone",
                "Asia/Hong_Kong",
            ],
            transport=transport,
        )

    assert missing_timezone_exit == 2
    assert mixed_exit == 2
    assert requests == []


def test_task_create_requires_cwd_unless_template_is_provided() -> None:
    with _mock_transport(_created({"task": {"task_id": "task_1"}})) as (
        transport,
        requests,
    ):
        missing_cwd_exit, _, _ = _run(
            [
                "task",
                "create",
                "--title",
                "No cwd",
                "--instruction",
                "Do work",
                "--executor",
                "debug_printer",
                "--at",
                "2026-05-11T09:00:00+08:00",
            ],
            transport=transport,
        )
        template_exit, _, _ = _run(
            [
                "--json",
                "task",
                "create",
                "--title",
                "Template",
                "--instruction",
                "Do work",
                "--template-id",
                "tpl_1",
                "--at",
                "2026-05-11T09:00:00+08:00",
            ],
            transport=transport,
        )

    assert missing_cwd_exit == 2
    assert template_exit == 0
    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    assert "target_working_directory" not in payload
    assert payload["template_id"] == "tpl_1"


def test_executor_preflight_sends_expected_query_params() -> None:
    with _mock_transport(_success({"status": "available"})) as (
        transport,
        requests,
    ):
        exit_code, _, _ = _run(
            [
                "--json",
                "executor",
                "preflight",
                "--executor-profile",
                "xpr_default_pi",
                "--executor",
                "pi",
                "--cwd",
                ".",
            ],
            transport=transport,
        )

    assert exit_code == 0
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/executors/preflight"
    assert requests[0].url.params["executor_profile_id"] == "xpr_default_pi"
    assert requests[0].url.params["executor"] == "pi"
    assert requests[0].url.params["target_working_directory"] == str(
        Path(".").resolve()
    )


def test_profile_list_renders_pi_profile() -> None:
    with _mock_transport(
        _success(
            [
                {
                    "profile_id": "xpr_default_pi",
                    "name": "Pi",
                    "executor": "pi",
                    "is_enabled": True,
                    "is_default": True,
                    "default_model": "sonnet",
                    "reasoning_level": "high",
                }
            ]
        )
    ) as (transport, _):
        exit_code, stdout, stderr = _run(["profile", "list"], transport=transport)

    assert exit_code == 0
    assert stderr == ""
    assert "xpr_default_pi" in stdout
    assert "pi" in stdout
    assert "sonnet" in stdout
    assert "high" in stdout


def test_profile_create_sends_reasoning_level() -> None:
    with _mock_transport(
        _created(
            {
                "profile_id": "xpr_pi",
                "name": "Pi Custom",
                "executor": "pi",
                "is_enabled": True,
                "is_default": False,
                "default_model": "sonnet",
                "reasoning_level": "high",
            }
        )
    ) as (transport, requests):
        exit_code, stdout, stderr = _run(
            [
                "profile",
                "create",
                "--name",
                "Pi Custom",
                "--executor",
                "pi",
                "--default-model",
                "sonnet",
                "--reasoning-level",
                "high",
                "--env",
                "VISIBLE=1",
                "--secret-env",
                "TOKEN=secret",
            ],
            transport=transport,
        )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(requests[0].content)
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/v1/executor-profiles"
    assert payload["reasoning_level"] == "high"
    assert payload["env"] == {"VISIBLE": "1"}
    assert payload["secret_env"] == {"TOKEN": "secret"}
    assert "profile: " in stdout


def test_profile_update_sends_reasoning_level_and_secret_patch() -> None:
    with _mock_transport(
        _success(
            {
                "profile_id": "xpr_pi",
                "name": "Pi Custom",
                "executor": "pi",
                "is_enabled": True,
                "is_default": False,
                "default_model": "sonnet",
                "reasoning_level": None,
            }
        )
    ) as (transport, requests):
        exit_code, _, stderr = _run(
            [
                "--json",
                "profile",
                "update",
                "xpr_pi",
                "--version",
                "3",
                "--clear-reasoning-level",
                "--unset-secret-env",
                "TOKEN",
            ],
            transport=transport,
        )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(requests[0].content)
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == "/api/v1/executor-profiles/xpr_pi"
    assert payload == {
        "version": 3,
        "reasoning_level": None,
        "secret_env": {"TOKEN": None},
    }


def test_profile_validation_error_is_clear_in_text_output() -> None:
    response = httpx.Response(
        422,
        json={
            "error": {
                "code": "validation_error",
                "message": "executor profile validation failed: timed out",
                "details": {},
            }
        },
    )
    with _mock_transport(response) as (transport, _):
        exit_code, stdout, stderr = _run(
            [
                "profile",
                "create",
                "--name",
                "Bad",
                "--executor",
                "codex",
                "--reasoning-level",
                "xhigh",
            ],
            transport=transport,
        )

    assert exit_code == 1
    assert stdout == ""
    assert "executor profile validation failed: timed out" in stderr


def test_read_commands_call_expected_routes() -> None:
    commands = [
        (["--json", "task", "list"], "/api/v1/tasks"),
        (["--json", "task", "detail", "task_1"], "/api/v1/tasks/task_1/detail"),
        (["--json", "task", "run-now", "task_1"], "/api/v1/tasks/task_1/run-now"),
        (["--json", "task", "runs", "task_1"], "/api/v1/tasks/task_1/runs"),
        (
            [
                "--json",
                "task",
                "reschedule",
                "task_1",
                "--at",
                "2026-06-01T10:00:00+08:00",
            ],
            "/api/v1/tasks/task_1/schedule",
        ),
        (["--json", "run", "get", "run_1"], "/api/v1/runs/run_1"),
        (["--json", "run", "events", "run_1"], "/api/v1/runs/run_1/events"),
    ]

    for argv, path in commands:
        with _mock_transport(_success([])) as (transport, requests):
            exit_code, _, _ = _run(argv, transport=transport)
        assert exit_code == 0
        assert requests[0].url.path == path


def test_task_reschedule_happy_path() -> None:
    bundle = {
        "task": {"task_id": "task_123", "title": "Test"},
        "schedule": {"schedule_id": "sch_1", "planned_at": "2026-06-01T10:00:00+08:00"},
    }
    with _mock_transport(_success(bundle)) as (transport, requests):
        exit_code, stdout, stderr = _run(
            ["task", "reschedule", "task_123", "--at", "2026-06-01T10:00:00+08:00"],
            transport=transport,
        )
    assert exit_code == 0
    assert stderr == ""
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == "/api/v1/tasks/task_123/schedule"
    sent = json.loads(requests[0].content or b"{}")
    assert sent.get("planned_at") == "2026-06-01T10:00:00+08:00"
    assert "task: " in stdout
    assert "schedule: " in stdout


def test_task_reschedule_usage_and_api_errors() -> None:
    # missing --at
    with _mock_transport(_success({})) as (transport, _):
        exit_code, _, stderr = _run(
            ["task", "reschedule", "task_123"], transport=transport
        )
    assert exit_code != 0
    assert "--at" in stderr or "required" in stderr

    # api 422 error
    err_resp = httpx.Response(
        422,
        json={"error": {"code": "invalid_state_transition", "message": "not one-time"}},
    )
    with _mock_transport(err_resp) as (transport, _):
        exit_code, stdout, stderr = _run(
            [
                "--json",
                "task",
                "reschedule",
                "task_123",
                "--at",
                "2026-06-01T10:00:00+08:00",
            ],
            transport=transport,
        )
    assert exit_code == 1
    assert stderr == ""
    parsed = json.loads(stdout)
    assert parsed["error"]["code"] == "invalid_state_transition"

    # 409 conflict
    conflict = httpx.Response(
        409, json={"error": {"code": "conflict", "message": "version mismatch"}}
    )
    with _mock_transport(conflict) as (transport, _):
        exit_code, _, _ = _run(
            ["task", "reschedule", "task_123", "--at", "2026-06-01T10:00:00+08:00"],
            transport=transport,
        )
    assert exit_code == 1
