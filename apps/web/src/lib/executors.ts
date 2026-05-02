import type { ExecutorName, ExecutorProfile } from '@/api'

export const executorOptions: Array<{ label: string; value: ExecutorName }> = [
  { label: 'Debug Printer', value: 'debug_printer' },
  { label: 'Claude Code', value: 'claude_code' },
  { label: 'Codex', value: 'codex' },
  { label: 'Kimi Code', value: 'kimi_code' },
]

export function executorLabel(executor: ExecutorName): string {
  return executorOptions.find((option) => option.value === executor)?.label ?? executor
}

export function executorProfileLabel(profile: ExecutorProfile): string {
  const model = profile.default_model ? ` · ${profile.default_model}` : ''
  const state = profile.is_enabled ? '' : ' · disabled'
  return `${profile.name} (${executorLabel(profile.executor)}${model})${state}`
}

export function executorProfileOptions(
  profiles: ExecutorProfile[],
): Array<{ label: string; value: string }> {
  return profiles
    .filter((profile) => profile.archived_at === null && profile.is_enabled)
    .map((profile) => ({
      label: executorProfileLabel(profile),
      value: profile.profile_id,
    }))
}

export function defaultExecutorProfileId(profiles: ExecutorProfile[]): string {
  return (
    profiles.find((profile) => profile.executor === 'debug_printer' && profile.is_default)
      ?.profile_id ??
    profiles.find((profile) => profile.is_default)?.profile_id ??
    profiles[0]?.profile_id ??
    ''
  )
}
