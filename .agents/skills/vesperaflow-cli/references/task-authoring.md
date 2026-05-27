# Task Authoring

Use this guide when turning a user's natural language request into a
VesperaFlow task.

## Required Understanding

Before creating a task, have a concrete answer for:

- what work should the executor perform?
- what directory should the executor work in?
- which executor profile should run it?
- when should it run?
- is the task one-time or recurring?
- what outcome should the user expect to review?

If the user request is underspecified, ask questions before creating the task.
Do not silently fill missing schedule, workspace, or executor choices.

## Clarifying Questions

Ask only for missing or risky fields. Keep questions short.

Examples:

- "Which working directory should the agent run in?"
- "Which executor profile should run this task?"
- "Should this run once, or repeat on a schedule?"
- "What exact date/time and timezone should I schedule it for?"
- "For recurring work, what cadence and timezone should I use?"
- "This sounds broad. Should the agent edit files, or only produce a report?"

When the request may cause broad changes, confirm the scope:

- repository-wide refactors
- migrations or data changes
- dependency upgrades
- destructive filesystem operations
- production credentials or production systems

## Title

Create a short operational title, max roughly 80 characters. It should identify
the work, not the schedule.

Good:

- `Fix flaky auth tests`
- `Daily repo triage`
- `Weekly competitor pricing scan`

Avoid:

- `Run this later`
- `AI task`
- `Tomorrow morning job`

## Instruction

Write the instruction for the executor as a direct work order. Include:

- goal
- relevant files, modules, URLs, or commands if known
- expected output or stopping condition
- constraints from the user
- whether to edit files or only report findings

Avoid including secrets, full unrelated context, or vague instructions such as
`do the thing we discussed`.

If the instruction is long, write it to a prompt file or pipe it with
`--instruction-file -` rather than forcing a long shell argument.

## Schedule Conversion

For one-time tasks, use `--at` with explicit timezone offset:

```text
2026-05-11T09:00:00+08:00
```

For recurring tasks, use RRULE plus IANA timezone:

```text
RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0
Asia/Hong_Kong
```

Common examples:

- every day at 8:00 in Hong Kong:
  `RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0`
- every Monday at 9:30:
  `RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=30`
- every weekday at 18:00:
  `RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=18;BYMINUTE=0`

If the user says "tomorrow", "tonight", "next Monday", or another relative
time, resolve it against the current date and timezone before scheduling. If the
timezone is unclear, ask.

## Executor Selection

Prefer `--executor-profile <profile_id>`. Use `profile list` to discover
profiles. Use legacy `--executor <executor_name>` only when the user explicitly
requests it or profiles are unavailable.

Supported executor names may include:

- `debug_printer`
- `claude_code`
- `codex`
- `opencode`

Do not request or print secret environment values.
