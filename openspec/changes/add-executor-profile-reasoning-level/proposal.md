## Why

Executor profiles already centralize model and environment defaults, but they cannot express the reasoning/thinking intensity a user wants for scheduled agent work. A fixed product enum is too brittle because reasoning values are executor-, model-, and provider-specific and can change independently of VesperaFlow releases.

Adding a nullable, profile-level `reasoning_level` as executor-specific text lets users tune cost/latency/quality consistently while requiring a live save-time probe to prove the selected executor/model/reasoning combination works before the profile is persisted for future scheduled runs.

## What Changes

- Add an optional nullable `reasoning_level` string to executor profiles, alongside `default_model` and environment defaults. Blank input normalizes to `null`; `null` means the executor uses its own default reasoning behavior.
- Do not predefine product-level reasoning values. CLI/Web use free-text input with explanatory hints, and compatibility is decided by live executor validation.
- Before creating or updating an enabled profile with an explicit `default_model` or `reasoning_level`, run a fail-closed validation probe for the effective executor/model/reasoning/env configuration.
- Pass secrets to the validation probe through a short-lived transient handoff record. Temporal validation payloads carry only a handoff id, never secret values.
- Persist `reasoning_level` in PostgreSQL only after save-time validation succeeds; existing profiles and default profile seeding remain compatible with `reasoning_level = null`.
- Resolve `reasoning_level` inside Worker Activities and pass it to executor adapters when set.
- Surface `reasoning_level` through executor profile create/update/list/get API contracts and client-facing responses without exposing secret env values.
- Always include `executor_model` and `executor_reasoning_level` keys in executor run event details, using `null` when unset and excluding env/secret env values.
- Surface the setting in CLI/Web profile management displays and forms where executor profile model defaults are configured.

## Capabilities

### New Capabilities
- `executor-profile-reasoning-level`: Covers profile-level reasoning defaults, live save-time validation, API/storage contracts, runtime propagation, adapter mappings, UI/CLI exposure, run event metadata, and backward compatibility.

### Modified Capabilities

None. Existing executor-specific capabilities continue to describe base executor behavior; this change centralizes reasoning-level behavior across executors.

## Impact

- API/contracts: executor profile create/update/request/response schemas, validation error behavior, and API documentation.
- Store: `ExecutorProfile` model, Alembic migration, repository create/update/default-profile logic, transient validation handoff storage, and repository tests.
- Temporal/Worker: short validation workflow/activity, `ExecutorRuntimeConfig`, runtime profile resolution, executor adapter probe hooks, executor adapter argument/env mapping, run event metadata, and adapter tests.
- Web/CLI: executor profile forms, free-text reasoning input, failed-save validation messages, labels, payload types, and displays.
- Docs/specs: executor profile guidance, API spec, domain model, and reasoning validation behavior.
