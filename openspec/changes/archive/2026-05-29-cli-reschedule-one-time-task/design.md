## Context

The VesperaFlow CLI (`vespera`) in `apps/cli/` provides agent-friendly wrappers over the `/api/v1` HTTP surface. One-time tasks are created with `--at` and can be inspected via `task list --status scheduled --execution-mode one_time` and `task detail`. The backend already exposes `PATCH /tasks/{task_id}/schedule` (see `docs/api-spec.md` §8.2 and `apps/api/src/vesperaflow_api/routes/tasks.py`) that accepts a `ScheduleUpdateRequest` containing a new future `planned_at` for one-time schedules. No CLI command currently wraps this endpoint.

## Goals / Non-Goals

**Goals:**
- Allow `vespera task reschedule <task_id> --at <future-iso-timestamp>` to change the planned execution time of a pending one-time task.
- Reuse all existing validation, optimistic concurrency (`If-Match` / version), and Temporal schedule update logic.
- Keep the change strictly one-time only (no RRULE or recurring support).
- Follow existing CLI patterns (Pydantic arg models, `_request`, formatters, dispatch table).

**Non-Goals:**
- Support rescheduling recurring tasks or editing RRULE/timezone.
- Add new API endpoints, domain enums, or schedule types.
- Change behavior for `task_status` derivation or schedule state machine.
- Provide interactive prompts or multi-field schedule updates.

## Decisions

**Decision: Command lives under `task reschedule` (not a top-level `schedule` resource)**
- Rationale: Matches the existing `task run-now`, `task runs`, `task detail` mental model. Users already think in task terms when they have a pending one-time item. Keeps parser tree shallow.
- Alternative considered: `vespera schedule update` — rejected because it would require new resource routing and dilute the task-centric CLI.

**Decision: Only `--at` flag (no `--rrule` or full schedule object)**
- Rationale: One-time tasks use `single_run` + `planned_at`. This mirrors the create path (`_task_create_schedule`) and the API contract for one-time schedule updates.
- Alternative: Accept a JSON schedule patch — rejected for CLI ergonomics; agents prefer simple flags.

**Decision: Let API return 409/422 on invalid state or version; surface as CLI error**
- Rationale: Reuses the robust error handling already in `_request` and `_normalized_error_body`. Avoids duplicating state-machine logic in the CLI.
- Alternative: Pre-flight GET detail to check `execution_mode` and `task_status` — rejected as extra round-trip for a rare error path.

**Decision: Use existing `ScheduleResponse` / schedule formatter for success output**
- Rationale: The PATCH returns the updated schedule; reuse `_format_object` or extend `_format_task_bundle` style for consistency.

## Risks / Trade-offs

- [Optimistic concurrency conflict] → CLI will surface the 409 with clear "version mismatch" message; user re-runs `task detail` to obtain fresh version (standard pattern).
- [Non-one-time or non-scheduled task] → API rejects with `invalid_state_transition`; CLI error message is sufficient.
- [Timestamp in past or malformed] → API validation catches it; no local pre-check needed beyond ISO parse (already present in create path).
- Scope limited to one-time keeps implementation small and avoids expanding the change into recurring schedule complexity.