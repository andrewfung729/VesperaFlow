# Generated System Facts

This directory stores generated, agent-readable snapshots. Regenerate the
current snapshots from the repository root with:

```bash
uv run python scripts/generate_agent_facts.py
```

Each generated file includes:

- the command used to regenerate it
- the source system or files it was generated from
- the generation date
- any known limitations

Current snapshots:

- `db-schema.md`: tables, columns, indexes, constraints, and relationships from
  the current database metadata.
- `api-routes.md`: FastAPI route map with methods, paths, request models, and
  response models.
- `temporal-surface.md`: task queues, Workflow types, Activity names, Schedule
  naming conventions, and payload models.
- `dependency-graph.md`: package-level dependency graph for `apps` and
  `packages`.
