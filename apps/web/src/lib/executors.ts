import type { ExecutorName, ExecutorProfile } from '@/api'

export interface ExecutorRegistryEntry {
  label: string
  supportsModelSelection: boolean
}

export const executorRegistry: Record<ExecutorName, ExecutorRegistryEntry> = {
  debug_printer: { label: 'Debug Printer', supportsModelSelection: false },
  claude_code: { label: 'Claude Code', supportsModelSelection: true },
  codex: { label: 'Codex', supportsModelSelection: true },
  opencode: { label: 'OpenCode', supportsModelSelection: true },
  pi: { label: 'Pi', supportsModelSelection: true },
}

export const executorOptions: Array<{ label: string; value: ExecutorName }> = [
  { label: executorRegistry.debug_printer.label, value: 'debug_printer' },
  { label: executorRegistry.claude_code.label, value: 'claude_code' },
  { label: executorRegistry.codex.label, value: 'codex' },
  { label: executorRegistry.opencode.label, value: 'opencode' },
  { label: executorRegistry.pi.label, value: 'pi' },
]

export function executorLabel(executor: ExecutorName): string {
  return executorRegistry[executor]?.label ?? executor
}

export function executorSupportsModelSelection(executor: ExecutorName): boolean {
  return executorRegistry[executor].supportsModelSelection
}

export function executorProfileLabel(profile: ExecutorProfile): string {
  const model = profile.default_model ? ` · ${profile.default_model}` : ''
  const reasoning = profile.reasoning_level ? ` · ${profile.reasoning_level}` : ''
  const state = profile.is_enabled ? '' : ' · disabled'
  return `${profile.name} (${executorLabel(profile.executor)}${model}${reasoning})${state}`
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
