# Python Test Layout

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

Test ownership:

- `packages/core/tests`: dependency-free domain rules, enums, Temporal ID helpers, and pure contracts.
- `packages/store/tests`: database models, repositories, migrations, and transaction behavior.
- `apps/api/tests`: API route and service behavior, with Temporal mocked or faked.
- `apps/worker/tests`: workflow, activity, and executor adapter behavior with a fake executor.
- `tests/integration`: cross-package scenarios that may require Postgres, Temporal, or service orchestration.
