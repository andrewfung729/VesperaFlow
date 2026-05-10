# VesperaFlow Core

Shared domain package for code that must be imported safely across API, Worker,
Store, tests, and Temporal payload boundaries.

## Ownership

- `enums.py`: shared domain enums for execution, task, schedule, and run state.
- `contracts.py`: Pydantic payload contracts crossing Workflow and Activity
  boundaries.
- `client_contracts.py`: dependency-light API request DTOs shared by HTTP
  clients and the API layer.
- `status.py`: deterministic status projection helpers.
- `temporal_ids.py`: Temporal Schedule and Workflow ID helpers.
- `time.py`: timezone and serialization helpers.
- `validation.py`: domain consistency checks.

## Constraints

- Keep this package dependency-light.
- Do not add database, FastAPI, network, filesystem, or executor SDK imports.
- Anything imported by Workflow code must remain deterministic and
  Temporal-sandbox friendly.
- Preserve compatibility of Temporal payload fields; add explicit migration or
  versioning notes before breaking contract shape.
- Share client-facing request DTOs here when they need common validation; keep
  API response models in the API layer unless they are pure and mapper-free.

## Tests

Run from the repository root:

```bash
uv run pytest packages/core/tests
```
