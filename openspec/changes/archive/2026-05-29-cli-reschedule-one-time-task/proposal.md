## Why

CLI users and agents cannot adjust the execution time of a pending one-time task after creation. They must either cancel/recreate the task or fall back to raw `curl` against the API. This friction blocks the common workflow of refining schedules for AI work without losing task history or executor context.

## What Changes

- Add new CLI command `vespera task reschedule <task_id> --at <iso8601>` that updates the `planned_at` of a one-time task (only).
- The command validates the task is `one_time` + `scheduled` state, accepts a future timestamp, and calls the existing `PATCH /tasks/{id}/schedule` endpoint.
- No support for recurring schedules or other schedule fields in this change (one-time only per request).
- **BREAKING**: none.

## Capabilities

### New Capabilities
- `cli-one-time-reschedule`: Command-line rescheduling of pending one-time tasks via the existing schedule update API.

### Modified Capabilities
- (none — this is additive CLI surface only; no requirement changes to existing specs)

## Impact
- `apps/cli/src/vesperaflow_cli/main.py` (new arg model, handler, parser entry, formatter)
- `apps/cli/tests/` (new unit tests for the command)
- `docs/api-spec.md` (minor usage note if needed)
- No changes to core domain, API routes, or Temporal logic (reuses existing PATCH endpoint and validation)