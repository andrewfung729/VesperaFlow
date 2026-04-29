import type { ExecutionMode } from '@/api'

export const executionModeOptions: Array<{ label: string; value: ExecutionMode }> = [
  { label: 'One-time', value: 'one_time' },
  { label: 'Recurring', value: 'recurring' },
]

export function executionModeLabel(mode: ExecutionMode): string {
  return executionModeOptions.find((option) => option.value === mode)?.label ?? mode
}

export function executionModeBadgeClass(mode: ExecutionMode): string {
  if (mode === 'recurring') {
    return 'border-indigo-200 bg-indigo-50 text-indigo-800 dark:border-indigo-800 dark:bg-indigo-950/30 dark:text-indigo-300'
  }
  return 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300'
}

export function executionModeCalendarClass(mode: ExecutionMode): string {
  if (mode === 'recurring') {
    return 'border-indigo-200 bg-indigo-50 text-indigo-950 dark:border-indigo-800 dark:bg-indigo-950/30 dark:text-indigo-200'
  }
  return 'border-teal-200 bg-teal-50 text-teal-950 dark:border-teal-800 dark:bg-teal-950/30 dark:text-teal-200'
}
