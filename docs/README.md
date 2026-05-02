# VesperaFlow Documentation

This directory is the durable context layer for humans and coding agents. Use
this index to find the smallest document that answers the current question.

## Product And UX

- `requirements.md`: product problem, personas, scope, acceptance criteria.
- `functional-spec.md`: detailed product behavior and flows.
- `ux-spec.md`: UI information architecture, interaction rules, labels.
- `glossary.md`: shared vocabulary across product, API, Temporal, and UI.
- `MVP_PROGRESS.md`: MVP implementation status and known gaps.

## Architecture

- `architecture.md`: system boundaries, components, data flow, decisions.
- `domain-model.md`: task, schedule, run, status, and read-model semantics.
- `temporal-architecture.md`: Workflow, Activity, Schedule, task queue, retry,
  idempotency, and replay policy.
- `api-spec.md`: application-facing API contract.
- `executor-profiles.md`: executor/profile selection, no-fallback rules,
  preflight, runtime resolution, and artifact policy.
- `local-full-stack-runbook.md`: local Postgres, Temporal, API, Worker, web,
  and opt-in live executor smoke paths.
- `adr/`: accepted architecture decisions and rationale.

## ADR Index

- `adr/001-local-first.md`: local-first scope and operational boundaries.
- `adr/002-execution-engine-choice.md`: Temporal as the sole scheduler and
  executor integration modes (SDK and CLI transport).
- `adr/003-task-schedule-run-separation.md`: separation of Task, Schedule, Run,
  and OccurrenceOverride concepts.
- `adr/004-security-posture.md`: local secret handling and security posture.
- `adr/005-derived-view-states.md`: UI view states derived from backend
  semantics instead of independent labels.
- `adr/006-kimi-code-executor.md`: Kimi Code text CLI transport decision and
  trade-offs.

## Agent Operating Context

- `QUALITY.md`: current codebase health, known gaps, and recently fixed areas.
- `plans/active/`: current implementation plans. Read these before resuming
  unfinished work.
- `plans/completed/`: retained plans for historical context after work lands.
- `generated/`: generated facts that should be refreshed from the running or
  built system.

## Change Map

| When changing | Also check |
|---|---|
| API payloads, endpoints, or errors | `api-spec.md`, `apps/api/README.md`, API tests |
| Executor/profile selection, preflight, runtime env, or artifacts | `executor-profiles.md`, `api-spec.md`, `apps/worker/README.md`, executor tests |
| Task, schedule, run, or status semantics | `domain-model.md`, `glossary.md`, core/store tests |
| Temporal Workflow, Activity, Schedule, or task queue behavior | `temporal-architecture.md`, `adr/002-execution-engine-choice.md`, Worker tests |
| UI labels, views, or interaction states | `apps/web/README.md`, `ux-spec.md`, `functional-spec.md`, web tests |
| Architecture boundaries or durable decisions | `architecture.md`, a new or updated ADR, `QUALITY.md` |
| Known debt, coverage, or enforcement posture | `QUALITY.md`, `scripts/check_agent_repo.py`, CI |
| MVP feature status or delivery order | `MVP_PROGRESS.md`, relevant active plan, tests |

## Writing Rules

- Keep root `AGENTS.md` short and point here for detail.
- Prefer adding an ADR for durable architectural decisions.
- Prefer active plans for in-progress work instead of burying state in chats.
- Keep `MVP_PROGRESS.md` honest when implementation diverges from the product
  specs.
- Add regeneration commands to generated documents when they are introduced.
