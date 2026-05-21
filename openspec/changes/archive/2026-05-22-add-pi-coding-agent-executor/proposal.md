## Why

VesperaFlow already supports multiple local coding-agent runtimes behind the Worker executor adapter boundary, and Pi is a local terminal coding harness with supported non-interactive, JSON, RPC, and SDK modes. Adding Pi as an executor lets users schedule work for the same `pi` workflow they use interactively without changing VesperaFlow's Temporal or product state model.

## What Changes

- Add `pi` as a first-class executor kind available through executor profiles, task/template creation, API preflight, Worker routing, and Web/CLI labels.
- Add a Worker adapter that invokes the official `pi` CLI in headless mode from `execute_agent_run`, captures JSON/session artifacts, and normalizes terminal outcomes into existing run statuses and failure reasons.
- Pass executor profile `default_model` and environment overrides into the Pi invocation without serializing credentials or bulky output into Temporal history.
- Update documentation, tests, and generated facts so supported executor lists and run-event behavior include Pi.
- No breaking API changes; existing executor names and profiles remain valid.

## Capabilities

### New Capabilities
- `pi-executor`: Selecting, preflighting, and executing scheduled tasks through Pi as a profile-driven Worker executor.

### Modified Capabilities

None.

## Impact

- `packages/core`: add the new executor enum value and shared validation/test coverage.
- `packages/store`: seed/default executor profile support for Pi and repository tests.
- `apps/api`: include Pi in executor validation and preflight behavior.
- `apps/worker`: add the Pi CLI adapter, route it from the executor router/factory, and cover success, failure, artifacts, model/env passthrough, and cancellation.
- `apps/web` and `apps/cli`: expose Pi executor/profile labels and selector options where executor kinds are presented.
- `docs`: update architecture, Temporal/executor profile docs, API spec, MVP/quality notes, and add an ADR for the Pi CLI integration decision.
