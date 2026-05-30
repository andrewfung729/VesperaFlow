## ADDED Requirements

### Requirement: Executor profiles expose optional reasoning level
The system SHALL support an optional nullable `reasoning_level` string on executor profiles, where `null` means the selected executor uses its default reasoning behavior. The system SHALL NOT require `reasoning_level` to match a product-defined enum of reasoning values.

#### Scenario: Profile is created without reasoning level
- **WHEN** a user creates an executor profile without `reasoning_level`
- **THEN** the profile is persisted with `reasoning_level = null` and the API response includes `reasoning_level: null`

#### Scenario: Blank reasoning level is normalized
- **WHEN** a user creates or updates an executor profile with a blank `reasoning_level` string
- **THEN** the request is treated as `reasoning_level: null`

#### Scenario: Profile is created with reasoning level
- **WHEN** a user creates an executor profile with a non-empty `reasoning_level`
- **THEN** the system validates the effective executor/model/reasoning/env configuration before persisting the profile
- **AND** the API response includes the normalized `reasoning_level` after validation succeeds

#### Scenario: Profile reasoning level is updated
- **WHEN** a user updates an active executor profile with a non-empty `reasoning_level`
- **THEN** the system validates the effective executor/model/reasoning/env configuration before mutating the active profile
- **AND** the profile version increments only after validation succeeds

#### Scenario: Profile reasoning level is cleared
- **WHEN** a user updates an active executor profile with `reasoning_level: null`
- **THEN** the stored profile reasoning level is cleared and future runs use the executor default reasoning behavior

### Requirement: Explicit profile runtime defaults are validated before save
The system SHALL fail closed when saving an enabled executor profile whose effective runtime configuration explicitly sets `default_model` or `reasoning_level` and validation cannot prove that the selected executor accepts the effective model/reasoning/env configuration.

#### Scenario: Create validates explicit model and reasoning
- **WHEN** a user creates an enabled executor profile with `default_model` or `reasoning_level` set
- **THEN** the system runs a live validation probe before creating the profile
- **AND** the profile is not persisted unless the probe succeeds

#### Scenario: Update validates runtime-affecting changes
- **WHEN** a user updates `default_model`, `reasoning_level`, `env`, or `secret_env` on an enabled profile whose effective `default_model` or `reasoning_level` is set
- **THEN** the system validates the effective runtime configuration before applying the update
- **AND** the existing active profile remains unchanged if validation fails or times out

#### Scenario: Validation failure rejects save
- **WHEN** the validation probe reports unsupported model/reasoning, authentication failure, missing executor, configuration failure, or timeout
- **THEN** the create/update request fails with a validation error
- **AND** no active profile is created or mutated

#### Scenario: Null defaults do not require live provider validation
- **WHEN** a default profile is seeded or a user saves an enabled profile with both `default_model = null` and `reasoning_level = null`
- **THEN** the system does not need to call a live model provider before saving the profile

#### Scenario: Validation uses transient secret handoff
- **WHEN** a save-time validation probe needs profile secret environment values
- **THEN** the API stores them only in a short-lived transient handoff record
- **AND** Temporal validation payloads contain only the handoff id and non-secret metadata
- **AND** the handoff record is deleted or expired after validation completes

#### Scenario: Validation probe avoids user workspace mutation
- **WHEN** the system validates a profile before save
- **THEN** the probe runs in a VesperaFlow-owned temporary workspace and not in a task target working directory
- **AND** no product run is created for the validation probe

### Requirement: Reasoning level is resolved at Activity runtime
The system SHALL resolve executor profile `reasoning_level` inside the Worker Activity and provide it to executor adapters through runtime configuration without adding it to Workflow payloads.

#### Scenario: Runtime config includes profile reasoning level
- **WHEN** `execute_agent_run` loads an enabled, unarchived executor profile that has `reasoning_level` set
- **THEN** the adapter runtime config includes that reasoning level along with profile id, profile name, default model, and environment values

#### Scenario: Runtime config omits unset reasoning level
- **WHEN** `execute_agent_run` loads an enabled, unarchived executor profile with `reasoning_level = null`
- **THEN** the adapter runtime config has no reasoning level and the adapter does not pass a reasoning option to the executor

#### Scenario: Workflow payload remains deterministic
- **WHEN** a task using a reasoning-configured executor profile is replayed by Temporal
- **THEN** Workflow replay depends only on the existing execution snapshot and Activity results, not on loading profile reasoning configuration inside Workflow code

### Requirement: Executor adapters map reasoning level to executor-specific controls
The system SHALL map saved non-null profile `reasoning_level` text to the selected executor's invocation option and MUST NOT silently ignore it for real executor adapters.

#### Scenario: Pi receives thinking option
- **WHEN** a Pi executor profile has `reasoning_level` set
- **THEN** the Pi adapter invokes `pi` with `--thinking` matching that value

#### Scenario: Claude Code receives effort option
- **WHEN** a Claude Code executor profile has `reasoning_level` set
- **THEN** the Claude Code adapter starts the SDK session with the matching effort setting

#### Scenario: Codex receives reasoning effort config
- **WHEN** a Codex executor profile has `reasoning_level` set
- **THEN** the Codex adapter invokes `codex exec` with a `model_reasoning_effort` configuration override matching that value

#### Scenario: OpenCode receives variant option
- **WHEN** an OpenCode executor profile has `reasoning_level` set
- **THEN** the OpenCode adapter invokes `opencode run` with the matching provider variant option

#### Scenario: Debug Printer remains deterministic
- **WHEN** a Debug Printer executor profile has `reasoning_level` set
- **THEN** Debug Printer execution remains deterministic and does not call an external model provider
- **AND** the value remains visible through profile/runtime metadata for propagation tests

### Requirement: Reasoning level and model are safe in user-facing metadata
The system SHALL treat `default_model` and `reasoning_level` as non-secret executor metadata and MUST NOT expose environment or secret environment values when displaying or recording them.

#### Scenario: Run event records stable executor metadata keys
- **WHEN** an executor run starts or reaches a terminal outcome
- **THEN** run event details include `executor_model` and `executor_reasoning_level` keys
- **AND** each key is set to the configured string value or `null` when unset
- **AND** run event details exclude all env and secret env values

#### Scenario: API response excludes secret values
- **WHEN** an executor profile response includes `default_model` and `reasoning_level`
- **THEN** the response still exposes only `secret_env_keys` for secret environment variables and never returns secret values

### Requirement: Client surfaces edit free-form profile reasoning level
The system SHALL expose executor profile `reasoning_level` in CLI and Web profile management surfaces wherever profile model defaults are shown or edited, without constraining input to a product-defined enum.

#### Scenario: CLI lists profile reasoning level
- **WHEN** a user runs the profile list command
- **THEN** the output includes each profile's reasoning level or an empty/default marker when unset

#### Scenario: CLI saves reasoning level through validation
- **WHEN** a user creates or updates an executor profile with `reasoning_level` through the CLI
- **THEN** the CLI sends the free-form value to the API and surfaces save-time validation failure messages clearly

#### Scenario: Web profile form edits reasoning level
- **WHEN** a user creates or edits an executor profile in the Web UI
- **THEN** the form allows entering a free-form reasoning level or leaving it unset
- **AND** failed save-time validation is shown without creating or mutating the active profile
