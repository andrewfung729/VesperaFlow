# Test Layout

Run all Python tests from the repository root:

```bash
uv run pytest
```

Run a single package test suite:

```bash
uv run pytest packages/core/tests
uv run pytest packages/store/tests
uv run pytest apps/api/tests
uv run pytest apps/worker/tests
```

Run integration tests separately:

```bash
uv run pytest tests/integration
```

The full local Temporal/Postgres one-time smoke test is opt-in. Start the local
infrastructure from `docs/local-full-stack-runbook.md`, then run:

```bash
VESPERAFLOW_FULL_STACK_SMOKE_DATABASE_URL=postgresql+asyncpg://vespera:password@localhost:15432/vespera \
  uv run pytest tests/integration/test_full_stack_one_time_smoke.py
```

Live Claude Code verification is also opt-in because it uses local developer
credentials and workspace access. Follow the live smoke path in
`docs/local-full-stack-runbook.md` and create a live Claude-backed task through
the normal API/Worker execution path.

Run web checks from `apps/web`:

```bash
bun run type-check
bun run lint
bun run format
bun run test:unit:run
bun run test:e2e:smoke
```

Web fix commands also run from `apps/web`:

```bash
bun run lint
bun run format
```

Test ownership:

- `packages/core/tests`: dependency-free domain rules, enums, Temporal ID helpers, and pure contracts.
- `packages/store/tests`: database models, repositories, migrations, and transaction behavior.
- `apps/api/tests`: API route and service behavior, with Temporal mocked or faked.
- `apps/worker/tests`: workflow, activity, and executor adapter behavior with a fake executor.
- `apps/web/src/__tests__`: API helpers, shared UI behavior, and view logic
  that can run with mocked browser/API state.
- `apps/web/e2e`: Playwright smoke coverage for critical navigation and
  mocked API contracts.
- `tests/integration`: cross-package scenarios that may require Postgres,
  Temporal, or service orchestration.
