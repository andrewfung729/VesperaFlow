## ADDED Requirements

### Requirement: CLI reschedules one-time task execution time
The `vespera` CLI SHALL expose a `task reschedule` subcommand that updates the `planned_at` of a pending one-time task by calling the existing schedule update API.

#### Scenario: Successful reschedule of pending one-time task
- **WHEN** user runs `vespera task reschedule task_123 --at "2026-06-01T10:00:00+08:00"`
- **THEN** the CLI sends `PATCH /tasks/task_123/schedule` with the new timestamp and version, then prints the updated schedule object

#### Scenario: Reject non-one-time task
- **WHEN** user attempts to reschedule a recurring task
- **THEN** the API returns `invalid_state_transition` and CLI surfaces a clear error

#### Scenario: Reject past or malformed timestamp
- **WHEN** user supplies a timestamp in the past or without timezone offset
- **THEN** the API validation fails and CLI reports the error without creating a local request

#### Scenario: Handle optimistic concurrency conflict
- **WHEN** the task version has changed since last observation
- **THEN** CLI reports HTTP 409 conflict and advises re-running `task detail` to obtain fresh version

#### Scenario: Require task_id and --at
- **WHEN** user omits required arguments
- **THEN** argparse raises usage error before any HTTP call

### Requirement: Output format consistency
On success the CLI SHALL render the returned schedule using the same object formatter style as `task detail` and `task create`.

#### Scenario: JSON and human-readable modes
- **WHEN** `--json` is supplied
- **THEN** the full JSON envelope is emitted
- **WHEN** `--json` is absent
- **THEN** a human-readable "schedule: ..." line is printed

### Requirement: One-time scope only
The reschedule command SHALL NOT accept `--rrule` or `--timezone`; those flags remain exclusive to `task create` for recurring tasks.

#### Scenario: Extra flags rejected at parse time
- **WHEN** user supplies `--rrule` with `task reschedule`
- **THEN** argparse reports unknown argument (or mutually-exclusive error if implemented)