# VesperaFlow Web

Vue 3 UI for planning tasks, reviewing runs, managing templates, checking
executor readiness, and navigating calendar/history views.

## Ownership

- App shell and route registration live in `src/App.vue`, `src/main.ts`, and
  `src/router/`.
- API transport and DTO types live in `src/api.ts`.
- Reusable UI primitives live in `src/components/`.
- View-specific orchestration lives in `src/views/`.
- Shared view logic belongs in `src/composables/` or `src/lib/` before being
  copied across views.
- Unit tests live beside the app under `src/__tests__/`.
- Playwright smoke coverage lives in `e2e/`.

## Local Commands

Run these from `apps/web`:

```bash
bun run dev
bun run type-check
bun run lint:check
bun run lint
bun run format:check
bun run format
bun run test:unit:run
bun run test:e2e:smoke
```

`bun run lint` and `bun run format` rewrite files. Use the `*:check` variants
when validating without edits.

## UI Patterns

- Keep API payload semantics in `src/api.ts`; views should call typed helpers
  instead of assembling URLs or envelopes inline.
- Use shared form and state components before adding local variants:
  `FormField`, `TextInput`, `TextArea`, `SelectField`, `UiButton`,
  `ErrorAlert`, `PageStatePanel`, `RunStatusBadge`, `ExecutionModeBadge`,
  `RecurrenceEditor`, `RunTimeline`, and `MarkdownReader`.
- Use `src/lib/executors.ts` for executor and executor-profile labels,
  filtering, and default profile selection.
- Keep backend-derived state names intact. Do not introduce UI-only task, run,
  or schedule status labels that conflict with `docs/domain-model.md`.
- Keep route-level data loading explicit inside the owning view unless the logic
  is shared by more than one view.

## Executor UX Rules

- New task and template flows are profile-primary. The selected
  `executor_profile_id` determines the executor kind.
- A legacy `executor` can still be sent when a profile is not selected, but the
  backend resolves it to that executor's default profile.
- Composer preflight should call `/executors/preflight` with
  `executor_profile_id` and `target_working_directory` when a profile is
  selected.
- Preflight does not prove live authentication for Claude Code, Codex, or Kimi
  Code. It checks profile usability, target workspace access, and CLI presence
  where applicable.

## Test Ownership

- Add unit tests for API helper changes in `src/__tests__/api.spec.ts`.
- Add unit tests for view logic when loading, empty, error, or mutation states
  change.
- Keep Playwright smoke tests focused on critical navigation and mocked API
  contracts. They are not a replacement for unit coverage of branching logic.
- Do not require live executor credentials, local Temporal, or Postgres for web
  tests.
