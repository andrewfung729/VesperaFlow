# Generated System Facts

Store generated, agent-readable snapshots here when they exist. Each generated
file should include:

- the command used to regenerate it
- the source system or files it was generated from
- the generation date
- any known limitations

High-value future snapshots:

- `db-schema.md`: tables, columns, indexes, constraints, and relationships from
  the current database metadata.
- `api-routes.md`: FastAPI route map with methods, paths, request models, and
  response models.
- `temporal-surface.md`: task queues, Workflow types, Activity names, Schedule
  naming conventions, and payload models.
- `dependency-graph.md`: package-level dependency graph for `apps` and
  `packages`.
