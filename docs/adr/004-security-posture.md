---
title: "ADR 004: MVP Security Posture and Secrets Handling"
status: accepted
date: "2026-04-24"
aligned_architecture: "docs/architecture.md"
aligned_temporal_architecture: "docs/temporal-architecture.md"
---

# ADR 004: MVP Security Posture and Secrets Handling

## Status

Accepted for MVP. Explicitly scoped; to be revisited before any multi-user or hosted deployment.

## Context

MVP targets a single local user. Full authentication, authorization, and encryption-at-rest work is unnecessary at this phase but must not be blocked by MVP choices.

Per `docs/adr/002-execution-engine-choice.md`, VesperaFlow delegates MVP AI execution to Claude Code through the Claude Agent SDK. The executor handles its own authentication against the upstream LLM provider. This removes one class of credential-handling risk from VesperaFlow entirely, but introduces a different concern: VesperaFlow must never interfere with, extract, or log those credentials even though its Worker process can see them in the environment and the credentials are directly accessible to the same Python process that VesperaFlow runs.

Key pressures:

- VesperaFlow must not store, transmit, or log executor credentials, even though the executor SDK may rely on environment variables or config files in the user's home directory and runs inside VesperaFlow's own Python process
- task `instruction_source` and executor output may contain sensitive information and must not leak through logs at default log levels
- future multi-user support must be possible without rewriting the domain model
- PostgreSQL may contain sensitive user prompts; encryption at rest is a deployment concern, not an MVP feature

## Decision

MVP security posture:

- authentication and authorization are intentionally out of scope; the API assumes a single local user
- the domain model reserves a clean extension point for a future `user_id` association on every user-owned aggregate
- VesperaFlow does not manage LLM provider credentials; the supported executor SDK authenticates itself against its upstream provider through its own mechanism, for example an expected environment variable or runtime config file
- VesperaFlow must not read, copy, transmit, or log executor credential material, even when SDK-based integration places it directly in reach of the same Python process
- executor credentials are never serialized into Workflow inputs, Activity inputs, Activity return values, or Workflow history, because VesperaFlow does not pass them in the first place
- structured logs must not include full task instructions or full executor output at default log levels; summary-level fields are sufficient
- PostgreSQL is assumed to run on trusted local storage; at-rest encryption is a deployment decision, not an MVP feature
- credential rotation for an executor is a user-side operation on the SDK; VesperaFlow requires no code changes and no Worker restart beyond what the executor itself requires
- adapter preflight must surface `executor_sdk_not_importable`, `executor_not_authenticated`, `executor_misconfigured`, and `executor_workspace_unavailable` as distinct actionable states rather than generic run failures

## Consequences

Positive:

- MVP avoids building auth infrastructure that would be redesigned later
- VesperaFlow never holds LLM provider credentials, removing a whole class of leak risk
- credential rotation is entirely a user/executor SDK concern, not a VesperaFlow code concern
- the extension point for `user_id` keeps multi-user upgrades viable

Negative:

- VesperaFlow cannot inspect provider authentication directly; authentication failures surface as SDK exceptions or failed SDK preflight checks
- MVP cannot be exposed publicly as-is; it is only safe on a trusted local machine
- any cross-machine deployment requires an explicit security follow-up before go-live
- the lack of authz means API clients are fully trusted; operators must understand this
