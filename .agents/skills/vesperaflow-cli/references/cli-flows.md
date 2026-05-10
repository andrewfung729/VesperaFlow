# VesperaFlow CLI Flows

Use these flows after the task intent and required fields are clear. Prefer
`vespera --json`; in the repo workspace, `uv run vespera --json ...` is an
acceptable fallback when the global tool is not installed.

## Command Surface

- `vespera --json profile list`
- `vespera --json executor preflight --executor-profile <profile_id> --cwd <path>`
- `vespera --json task create --title <title> --instruction <text> --cwd <path> --executor-profile <profile_id> --at <timestamp>`
- `vespera --json task create --title <title> --instruction-file <path-or-> --cwd <path> --executor-profile <profile_id> --rrule <rrule> --timezone <zone>`
- `vespera --json task list [--status <status>] [--execution-mode <mode>]`
- `vespera --json task detail <task_id>`
- `vespera --json task run-now <task_id>`
- `vespera --json task runs <task_id> [--status <status>]`
- `vespera --json run get <run_id>`
- `vespera --json run events <run_id>`

Do not use cancel, archive, delete, profile mutation, template mutation, or
schedule update commands through CLI unless the CLI has added them.

## Select Executor Profile

1. List profiles:

```bash
vespera --json profile list
```

2. Choose an enabled profile matching the requested executor. Prefer the
   `profile_id` over legacy `--executor`.

3. Preflight when creating an executable task:

```bash
vespera --json executor preflight \
  --executor-profile xpr_default_codex \
  --cwd /Users/you/project
```

Preflight checks profile usability and workspace access. It does not prove live
executor authentication; live auth/configuration failures appear during Worker
execution.

## Create One-Time Task

Use this when the user wants one future execution.

```bash
vespera --json task create \
  --title "Fix flaky auth tests" \
  --instruction-file ./prompt.md \
  --cwd /Users/you/project \
  --executor-profile xpr_default_codex \
  --at "2026-05-11T09:00:00+08:00"
```

Rules:

- `--at` must include a timezone offset.
- Do not combine `--at` with `--rrule` or `--timezone`.
- Use `--instruction-file -` only when piping instruction text through stdin.

## Create Recurring Task

Use this when the user wants repeated execution.

```bash
vespera --json task create \
  --title "Daily repo triage" \
  --instruction "Summarize open failures and propose the next fix." \
  --cwd /Users/you/project \
  --executor-profile xpr_default_codex \
  --rrule "RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0" \
  --timezone "Asia/Hong_Kong"
```

Rules:

- Provide both `--rrule` and `--timezone`.
- Use an IANA timezone.
- Do not include `--at`.
- Keep RRULE simple unless the user asks for a complex cadence.

## Create From Template

Use this when the user gives a known `template_id`.

```bash
vespera --json task create \
  --title "Weekly competitor scan" \
  --instruction "Use the template defaults, but focus on pricing changes." \
  --template-id tpl_123 \
  --at "2026-05-11T09:00:00+08:00"
```

Rules:

- A template may supply target directory and executor profile defaults.
- If the user does not provide a `template_id`, do not invent one.
- The current CLI does not list, create, edit, archive, or instantiate templates
  through a dedicated template command.

## Run Existing Task Now

Use this only for an existing task.

```bash
vespera --json task run-now task_123
```

Then inspect the returned run or list runs:

```bash
vespera --json task runs task_123
```

## Inspect Task And Runs

Use list for broad state:

```bash
vespera --json task list --status scheduled
vespera --json task list --execution-mode recurring
```

Use detail for one task:

```bash
vespera --json task detail task_123
```

Use run commands for execution state and events:

```bash
vespera --json task runs task_123
vespera --json run get run_123
vespera --json run events run_123
```

## Troubleshoot

1. If command parsing fails, fix local CLI arguments first.
2. If the API returns an error, report `error.code` and `error.message`.
3. If execution failed, inspect events:

```bash
vespera --json run events run_123
```

4. If the failure looks like workspace/profile availability, rerun preflight.
5. If the CLI cannot connect and the user did not specify a custom API, mention
   that the default local API may not be running; do not ask them to confirm the
   API URL first.
