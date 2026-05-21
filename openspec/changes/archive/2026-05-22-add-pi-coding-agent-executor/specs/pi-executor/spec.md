## ADDED Requirements

### Requirement: Pi executor kind is available through executor profiles
The system SHALL support `pi` as a first-class executor kind wherever executor profiles, task executor snapshots, template executor defaults, API schemas, CLI output, or Web executor selectors expose supported executor names.

#### Scenario: Default Pi profile is created
- **WHEN** default executor profiles are ensured for an installation
- **THEN** an enabled default profile for `pi` exists and can be selected for new tasks and templates

#### Scenario: Task stores Pi execution snapshot
- **WHEN** a user creates a task with an enabled `pi` executor profile
- **THEN** the task stores `executor = "pi"` and the matching `executor_profile_id` for future runs

### Requirement: Pi preflight follows existing executor preflight semantics
The system SHALL include `pi` in executor preflight and MUST validate profile usability and target workspace accessibility without performing live Pi authentication, provider, or model checks.

#### Scenario: Pi preflight passes for accessible workspace
- **WHEN** preflight is requested for an enabled `pi` profile and an existing absolute target working directory
- **THEN** the response reports `available` with code `executor_preflight_passed` and executor `pi`

#### Scenario: Pi preflight rejects unusable profile
- **WHEN** preflight is requested for a disabled, archived, or missing `pi` profile
- **THEN** the response reports `unavailable` with code `executor_profile_unavailable`

#### Scenario: Pi preflight rejects invalid workspace
- **WHEN** preflight is requested for `pi` with a missing, relative, or non-directory target working directory
- **THEN** the response reports `unavailable` with code `executor_workspace_unavailable`

### Requirement: Worker executes Pi only through the Activity adapter
The system SHALL route `pi` runs from `execute_agent_run` to a Worker Activity-only adapter that invokes the official `pi` executable in the task target working directory. Workflow code MUST NOT import Pi SDKs, spawn Pi, access the filesystem for Pi artifacts, or load executor profiles directly.

#### Scenario: Pi run is routed by execution snapshot
- **WHEN** `execute_agent_run` receives an execution snapshot whose executor is `pi`
- **THEN** the Worker invokes the Pi adapter and does not route the run to another executor

#### Scenario: Workflow remains deterministic
- **WHEN** a Pi-backed task run is replayed by Temporal
- **THEN** Workflow replay depends only on the existing payload and Activity results, not on Pi imports, subprocesses, filesystem reads, profile loading, or network calls inside Workflow code

### Requirement: Pi adapter uses profile model and environment at runtime
The Pi adapter SHALL resolve executor profile configuration inside the Activity and pass the profile `default_model` and environment values to the Pi subprocess without storing credentials in Temporal payloads, run events, default logs, or API responses.

#### Scenario: Profile model is passed to Pi
- **WHEN** a `pi` executor profile has `default_model` set
- **THEN** the Pi subprocess is invoked with that value as the Pi model selection

#### Scenario: Profile secrets stay out of durable payloads
- **WHEN** a `pi` executor profile contains secret environment values
- **THEN** those values are available only to the Activity subprocess environment and are not serialized into Workflow history, run events, structured logs, or API response bodies

### Requirement: Pi output is normalized into run outcomes and artifacts
The Pi adapter SHALL preserve bulky Pi stdout/stderr/session data as run artifacts and return a normalized `ExecutorOutcome` containing a terminal status, short summary or failure reason, terminal code, and artifact reference.

#### Scenario: Successful Pi execution completes the run
- **WHEN** the Pi subprocess exits successfully and produces final assistant text
- **THEN** the executor outcome has terminal status `completed`, terminal code `pi_completed`, a short result summary, and an artifact reference under the run artifact directory

#### Scenario: Missing Pi binary fails the run
- **WHEN** a `pi` run starts on a Worker where the `pi` executable is not available
- **THEN** the executor outcome has terminal status `failed`, terminal code `executor_not_available`, and an actionable failure reason

#### Scenario: Pi authentication or configuration failure is classified
- **WHEN** Pi exits or reports an error indicating missing authentication, provider setup, model setup, or configuration failure
- **THEN** the executor outcome has terminal status `failed` and a terminal code of `executor_not_authenticated` or `executor_misconfigured` as appropriate

#### Scenario: Pi execution is canceled
- **WHEN** the Temporal Activity running Pi is canceled
- **THEN** the adapter interrupts the Pi subprocess, stops the process if it does not exit promptly, and returns terminal status `canceled` with terminal code `canceled`

### Requirement: Pi executor is documented and tested consistently
The system SHALL update public contracts, architecture notes, executor-profile guidance, generated facts, and automated tests so supported executor behavior consistently includes `pi`.

#### Scenario: Supported executor documentation includes Pi
- **WHEN** a developer reads the API, architecture, Temporal, executor profile, and MVP/quality documentation after the change
- **THEN** `pi` appears with its selection, preflight, runtime, artifact, model, env, auth, and failure behavior aligned across those documents

#### Scenario: Test coverage protects Pi executor behavior
- **WHEN** the project test suite runs after implementation
- **THEN** core enum validation, store default profile creation, API preflight, Worker routing/adapter behavior, and UI/CLI executor labels are covered for `pi`
