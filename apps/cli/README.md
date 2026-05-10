# VesperaFlow CLI

`vespera` is the agent-friendly command line client for VesperaFlow.

It talks only to the local `/api/v1` HTTP API. It does not write PostgreSQL,
call Temporal, import Worker code, or inspect executor secrets.

## Install

`vesperaflow-cli` and its `vesperaflow-core` dependency are uv workspace
members and are not published to PyPI. To install `vespera` globally from the
local source tree, build both wheels and install with `uv tool` from the
repository root:

```bash
uv build --package vesperaflow-core --out-dir ./dist
uv build --package vesperaflow-cli  --out-dir ./dist
uv tool install vesperaflow-cli --find-links ./dist
```

Verify with `vespera --help`. After changing CLI or core source, rebuild both
wheels and reinstall with `--reinstall`:

```bash
uv build --package vesperaflow-core --out-dir ./dist
uv build --package vesperaflow-cli  --out-dir ./dist
uv tool install vesperaflow-cli --find-links ./dist --reinstall
```

To remove the installed tool: `uv tool uninstall vesperaflow-cli`.

## Examples

```bash
vespera --json task create \
  --title "Fix flaky auth tests" \
  --instruction-file ./prompt.md \
  --cwd /Users/you/project \
  --executor-profile xpr_default_codex \
  --at "2026-05-11T09:00:00+08:00"

vespera --json task list --status scheduled
vespera --json task run-now task_123
vespera --json run events run_123
```
