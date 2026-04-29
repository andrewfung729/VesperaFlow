import type { ExecutorName } from '@/api'

export const executorOptions: Array<{ label: string; value: ExecutorName }> = [
  { label: 'Debug Printer', value: 'debug_printer' },
  { label: 'Claude Code', value: 'claude_code' },
  { label: 'Codex', value: 'codex' },
  { label: 'Kimi Code', value: 'kimi_code' },
]

export function executorLabel(executor: ExecutorName): string {
  return executorOptions.find((option) => option.value === executor)?.label ?? executor
}
