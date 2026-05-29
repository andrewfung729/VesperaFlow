## 1. CLI Surface

- [x] 1.1 Add `_TaskRescheduleArgs` Pydantic model (task_id + at: str) in main.py
- [x] 1.2 Extend `task` subparser with `reschedule` command + `--at` argument
- [x] 1.3 Add `("task", "reschedule")` entry to `_DISPATCH`

## 2. Handler Implementation

- [x] 2.1 Implement `_handle_task_reschedule` that validates args, builds `ScheduleUpdateRequest`, calls `_request("PATCH", f"tasks/{id}/schedule", json_body=...)`
- [x] 2.2 Reuse or extend formatter to print the returned schedule (use `_format_object` style)
- [x] 2.3 Ensure error paths (409, 422, non-one-time) surface cleanly via existing `_write_result`

## 3. Validation & Edge Cases

- [x] 3.1 Add local ISO timestamp validation for `--at` (reuse `_require_timezone` logic)
- [x] 3.2 Confirm one-time scope: reject `--rrule` / `--timezone` at argparse level if possible

## 4. Tests

- [x] 4.1 Add unit test for successful reschedule happy path (mock transport)
- [x] 4.2 Add tests for usage errors, API error responses, and JSON vs human output

## 5. Documentation & Polish

- [x] 5.1 Update `apps/cli/README.md` examples with the new command
- [x] 5.2 Run `uv run ruff check .` + type check + existing tests to verify no breakage
- [x] 5.3 (Optional) Update `docs/api-spec.md` usage notes if the CLI example section grows