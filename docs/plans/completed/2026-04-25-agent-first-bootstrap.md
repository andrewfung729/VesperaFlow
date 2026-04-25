# Plan: Agent-First Bootstrap

## Goal

Make VesperaFlow easier for coding agents to navigate, verify, and extend by
adding a short root entry point, progressive documentation navigation, quality
tracking, package ownership docs, CI, and repo health checks.

## Final State

- Root `AGENTS.md` now acts as the short agent map and stays under 150 lines.
- Root `README.md` provides human project orientation and local setup commands.
- `docs/README.md` indexes product, UX, architecture, ADR, plan, generated, and
  quality documents.
- `docs/QUALITY.md` records domain scores, known gaps, golden rules, update
  triggers, and recent improvements.
- Package READMEs describe ownership, local commands, and boundaries for API,
  Worker, Core, and Store.
- `docs/plans/active/`, `docs/plans/completed/`, and `docs/plans/TEMPLATE.md`
  make multi-session work resumable.
- `docs/generated/README.md` reserves a home for generated system facts.
- `scripts/check_agent_repo.py` and CI enforce the first agent-first invariants.

## Decisions

- Keep `AGENTS.md` as a map rather than a policy manual; deeper context belongs
  in focused docs.
- Preserve the existing architecture and product docs instead of moving them
  into a new folder hierarchy.
- Treat Temporal as the primary golden rule: it is the only scheduler for
  one-time and recurring work.
- Rename tracked `infra/.env` to `infra/.env.example`; local `infra/.env` is
  developer-specific.
- Use CI and a repo health script for structural checks before adding heavier
  custom lint infrastructure.

## Verification

- `python scripts/check_agent_repo.py`
- `uv run ruff check .`
- `uv run pytest`
- `bun run type-check`
- `bun run lint:check`
- `bun run test:unit:run`
- `bun run test:e2e:smoke`

## Follow-Up

- Generate `docs/generated/db-schema.md`, `api-routes.md`,
  `temporal-surface.md`, and `dependency-graph.md`.
- Add Temporal replay tests before non-trivial Workflow evolution.
- Expand web E2E beyond smoke coverage.
- Add a cleanup loop that opens targeted PRs when scheduled scans find drift.
