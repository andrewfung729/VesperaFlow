---
name: vesperaflow-cli
description: >
  Use when Agent needs to operate VesperaFlow through the `vespera` CLI:
  create one-time or recurring scheduled AI tasks, ask clarifying questions
  before task generation, choose executor profiles, run executor preflight,
  update task instructions, run existing tasks now, reschedule one-time tasks,
  inspect tasks/runs/events,
  or diagnose CLI/API errors. This skill is for agent-friendly task authoring through the local
  VesperaFlow HTTP API and should be used whenever a user asks an agent to
  schedule, queue, generate, run, or review VesperaFlow tasks from the command
  line.
---

# VesperaFlow CLI

## Operating Rule

Use `vespera --json` by default. The CLI talks to the local `/api/v1` API only;
it does not write PostgreSQL, call Temporal directly, inspect executor secrets,
or bypass VesperaFlow lifecycle rules.

Do not ask the user to confirm `VESPERAFLOW_API_URL` for ordinary local use.
The CLI has a default API URL. Only use `--api-url` or discuss
`VESPERAFLOW_API_URL` when the user explicitly names a non-default API endpoint
or a command fails because it is reaching the wrong server.

## Requirement Clarification

If the user's task request is vague, ask concise questions until the task is
clear enough to execute. Do not create a scheduled task from guesses.

Before `task create`, know:

- task title or a clear title you can derive
- full executor-facing instruction
- target working directory, unless a template supplies it
- executor profile or executor, unless a template supplies it
- schedule: either one-time `--at` with timezone offset, or recurring
  `--rrule` plus `--timezone`

If any required field is missing or ambiguous, ask for that field directly.
Confirm destructive or broad instructions before scheduling them, especially
tasks that may edit many files, run migrations, delete data, spend paid
executor time, or touch production systems.

## Workflow

1. Classify the user's intent: create or update a task, create from template,
   run now, reschedule, inspect status/output, preflight, or troubleshoot.
2. Read `references/task-authoring.md` when converting natural language into a
   task title, instruction, schedule, or clarification questions.
3. Read `references/cli-flows.md` for command sequences and examples.
4. Prefer executor profiles over legacy executor names. Run preflight before
   creating executable tasks when the target directory or profile has not just
   been verified.
5. Execute the smallest CLI command sequence that satisfies the intent.
6. Report created `task_id`, `schedule_id`, and `run_id` values when present.
   For failures, report the CLI/API error code and the next useful command.

## Guardrails

- Do not invent unsupported CLI commands. Current supported surfaces are
  `task create`, `task list`, `task detail`, `task run-now`, `task runs`,
  `task update`, `task reschedule`, `run get`, `run events`,
  `executor preflight`, and `profile list`.
- Do not expose or request executor secret values. Profile responses expose
  secret keys only.
- Do not add cron, polling, sleep loops, or any scheduler outside Temporal.
- Do not claim a task executed unless `run get`, `task runs`, or `run events`
  confirms the run state.
- Use ISO 8601 timestamps with explicit timezone offsets for `--at`, such as
  `2026-05-11T09:00:00+08:00`.
- Use IANA timezones for recurring schedules, such as `Asia/Hong_Kong`.
