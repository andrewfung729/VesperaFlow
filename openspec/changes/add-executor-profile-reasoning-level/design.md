## Context

Executor profiles currently store executor kind, enable/default flags, `default_model`, plain env, and secret env. The API resolves a task's profile at creation time, but the Worker loads profile defaults inside the `execute_agent_run` Activity immediately before invoking an adapter. Workflow payloads carry only the resolved executor name and optional profile id, so profile defaults do not enter Temporal history.

Reasoning controls are not stable enough for a product enum. Pi exposes `--thinking`, Claude Code exposes `effort` through `ClaudeAgentOptions`, Codex accepts `model_reasoning_effort` configuration, and OpenCode exposes `--variant`; the accepted values vary by executor, provider, model, and release. VesperaFlow should not freeze those values in shared domain contracts. Instead, it should store the user's intended executor-specific value and prove the effective model/reasoning configuration works before saving it for scheduled use.

## Goals / Non-Goals

**Goals:**

- Add a nullable profile-level `reasoning_level` string that preserves existing behavior when omitted.
- Normalize blank `reasoning_level` input to `null` and keep `null` as “use executor default”.
- Avoid predefining product-level reasoning values.
- Validate explicit profile model/reasoning settings with a live, fail-closed executor probe before persisting a user-created or user-updated active profile.
- Keep validation and execution inside Worker Activity/adapter boundaries, not Workflow code.
- Keep secrets out of Temporal payloads, run events, structured logs, API responses, and default logs during both validation and execution.
- Expose the setting consistently through storage, API contracts, Worker runtime config, CLI/Web profile surfaces, tests, and docs.
- Keep reasoning configuration out of `ExecutionSnapshot`, task rows, template rows, and long-lived Workflow payloads.
- Emit stable run event metadata keys for executor model and reasoning values, using `null` when unset.

**Non-Goals:**

- Add per-task, per-template, or per-run reasoning overrides.
- Maintain a global enum of allowed reasoning values.
- Discover every provider/model's supported reasoning values ahead of time.
- Rewrite existing `default_model` values that already embed executor-specific reasoning suffixes.
- Validate every future run at execution time before invoking the selected executor; save-time validation protects profile configuration, while provider drift can still fail at runtime.
- Add a second scheduler or change task/profile resolution semantics.

## Decisions

### Decision: Store a nullable free-form string, not a shared enum

Add nullable `reasoning_level: str | None` fields to executor profile create/update/response shapes and the store model. Treat an omitted field or blank string as `null`. Store non-empty values as trimmed executor-specific text with a conservative length limit.

Rationale: supported reasoning values vary by executor and model and can change without a VesperaFlow release. A product enum would either reject valid future values or silently carry stale values.

Alternative considered: define `ExecutorReasoningLevel` as a union enum such as `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`. This was rejected because those values are not valid for every executor and should not become a product-level compatibility promise.

### Decision: Validate explicit model/reasoning with a live save-time probe

User-initiated profile create/update MUST run a validation probe before committing changes when the effective enabled profile has `default_model` or `reasoning_level` set and a runtime-affecting field changes (`default_model`, `reasoning_level`, `env`, or `secret_env`). The probe validates the effective executor/model/reasoning/env configuration. If the probe fails or times out, the create/update request fails and the active profile is not created or mutated.

Default profile seeding and profiles whose `default_model` and `reasoning_level` are both `null` do not perform live provider validation. Those profiles preserve the current “executor default” behavior.

Rationale: users asked for profile configuration to be proven before it can be scheduled. This avoids saving a profile whose explicit model/reasoning preference will be ignored or rejected later.

Alternative considered: validate only against static executor-specific value lists. This was rejected because reasoning values should not be predefined by VesperaFlow.

### Decision: Use transient handoff records for validation secrets

Create a short-lived transient validation handoff record containing the effective env and secret env values needed for the probe. The API starts a short Temporal validation workflow/activity with only the handoff id and non-secret metadata in the payload. The Activity loads the handoff, invokes the executor adapter probe, and deletes or expires the handoff after completion. The final executor profile is persisted only after a successful probe.

Rationale: the validation probe needs the same credentials as execution, but Temporal payloads and histories must not contain secret values. The transient handoff preserves the Activity boundary while preventing secrets from being serialized into Workflow history.

Alternative considered: call executor CLIs directly from the API before saving. This was rejected because executor invocation belongs in Worker Activities through executor adapters.

### Decision: Probe in a safe temporary workspace

Validation probes MUST run in a VesperaFlow-owned temporary workspace, not a user task workspace. Adapters should use the smallest executor-supported non-mutating probe, for example a short “respond OK” prompt with tools disabled or read-only when the executor supports that mode. Probe artifacts should be minimal, temporary, and excluded from user run history.

Rationale: profile validation is about configuration compatibility, not user work. It must not mutate project files or create product runs.

### Decision: Keep reasoning resolution Activity-only for scheduled runs

Do not add `reasoning_level` to `ExecutionSnapshot`, task rows, template rows, or scheduled Workflow payloads. The Worker Activity should load the current profile and build `ExecutorRuntimeConfig(default_model, reasoning_level, env)` immediately before adapter execution, matching existing `default_model` semantics.

Rationale: Workflows remain deterministic and payloads stay small. Profile edits before a future scheduled run intentionally affect that future run, just like profile model/env edits do today.

### Decision: Map raw reasoning text in adapters

`ExecutorRuntimeConfig` carries the normalized string value. Each adapter maps the value to its invocation mechanism when set:

- `pi`: append `--thinking <reasoning_level>`.
- `claude_code`: pass `effort=<reasoning_level>` to `ClaudeAgentOptions`.
- `codex`: pass `-c model_reasoning_effort="<reasoning_level>"`.
- `opencode`: append `--variant <reasoning_level>`.
- `debug_printer`: accept the value as metadata-only no-op behavior so propagation can be tested without calling an external model provider.

Adapters MUST omit the executor-specific reasoning option when `reasoning_level` is `null`. A saved non-null value MUST NOT be silently ignored by real executor adapters; runtime failures should be classified as executor misconfiguration if provider behavior changes after save-time validation.

Rationale: executor-specific command shapes belong in adapters; API/store contracts should not expose CLI flags or maintain static value lists.

### Decision: Use stable nullable metadata keys in run events

Executor run event details MUST include `executor_model` and `executor_reasoning_level` keys for every executor started/terminal event. Values are strings when configured and `null` when unset. Event details MUST NOT include env, secret env, full instructions, or executor output.

Rationale: fixed keys simplify CLI/Web rendering and debugging while keeping sensitive data out of event streams.

## Risks / Trade-offs

- [Save latency and cost] Live validation may call a provider and incur latency/cost. → Run only for explicit runtime defaults, use a short prompt, set a timeout, and fail closed with a clear validation error.
- [Offline or unauthenticated environments] Users cannot save explicit model/reasoning profiles while the executor cannot be validated. → Null/default profiles remain available, and the error explains the missing auth/configuration.
- [Transient secret cleanup] Validation handoff records must not linger indefinitely. → Delete after completion and add expiry cleanup for abandoned records.
- [Provider drift after save] A model/provider may later reject a previously valid reasoning value. → Classify runtime failures as executor misconfiguration and surface the failing profile metadata without secrets.
- [Probe side effects] Coding-agent CLIs can run tools. → Use temporary workspaces and tool-disabled/read-only probe modes where supported.
- [Existing model suffix conflicts] Some Pi `default_model` values may already include a `:<thinking>` suffix. → Do not rewrite existing model strings; document that explicit `reasoning_level` is preferred for new profiles.

## Migration Plan

1. Add nullable `reasoning_level` to `executor_profiles` with no backfill.
2. Add transient validation handoff storage with expiry/cleanup support.
3. Update contracts, schemas, repositories, and API routes so existing profiles serialize `reasoning_level: null` and user saves run fail-closed validation when explicit defaults are configured.
4. Add validation workflow/activity and adapter probe methods.
5. Update Worker runtime config and adapters; because scheduled-run reasoning remains Activity-only, no Temporal replay migration is required for existing task-run Workflows.
6. Update CLI/Web displays/forms and docs.
7. Rollback is safe before users depend on the setting by removing adapter usage and the nullable column; profiles with null behavior are unchanged.

## Open Questions

None blocking. During implementation, verify each executor's safest low-cost probe command and timeout behavior against the installed package/CLI versions before finalizing adapter tests.
