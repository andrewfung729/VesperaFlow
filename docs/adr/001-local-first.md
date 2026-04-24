---
title: "ADR 001: Local-First (Scoped) Deployment Model"
status: accepted
date: "2026-04-24"
aligned_architecture: "docs/architecture.md"
---

# ADR 001: Local-First (Scoped) Deployment Model

## Status

Accepted for MVP.

## Context

VesperaFlow is designed for an individual user planning and executing AI work over time. Several deployment stances were considered:

- fully cloud-hosted multi-tenant service
- pure local-first (offline-first with peer sync)
- single-user, locally-deployed, online-dependent

The product must ship an MVP that one user can run on one machine with minimal setup, while preserving a clean upgrade path to richer topologies later. MVP execution is delegated to Claude Code through the Claude Agent SDK (see `docs/adr/002-execution-engine-choice.md`), which performs its own network I/O against an upstream LLM provider. That makes a pure offline-first stance self-contradictory.

## Decision

Adopt a scoped local-first interpretation:

- product data and run history live locally in a user-owned PostgreSQL instance
- local development and startup must work with `docker compose` against local services only
- VesperaFlow itself never calls an LLM provider directly; however, the executor SDK it invokes does, and requires network connectivity at run time
- Temporal server coordination also requires local network connectivity to the Temporal dev stack
- offline-first sync and peer-to-peer replication are out of scope

## Consequences

Positive:

- simplest possible MVP deployment story for a single user
- data ownership is trivially clear
- forward-compatible with hosted or multi-user variants because the backend owns all product truth

Negative:

- marketing and onboarding must not claim pure offline behavior
- any feature that implies offline execution (for example offline queuing of executor invocations) requires explicit future design
- operators still need to understand PostgreSQL and Temporal basics; it is not zero-ops
- multi-user collaboration, hosted mode, and the minimum `docker compose` footprint are not part of this ADR; they belong in deployment and setup documentation when those documents are created
