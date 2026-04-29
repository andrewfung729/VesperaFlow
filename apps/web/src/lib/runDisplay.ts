import type { Run, RunStatus } from '@/api'
import { formatDateTime } from '@/lib/dateTime'

export const runStatusOptions: Array<{ label: string; value: RunStatus }> = [
  { label: 'Planned', value: 'planned' },
  { label: 'Queued', value: 'queued' },
  { label: 'Running', value: 'running' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Canceled', value: 'canceled' },
]

export interface RunOutcomeSource {
  result_summary?: string | null
  failure_reason?: string | null
  run_status?: RunStatus | null
  latest_run_outcome?: RunStatus | null
}

export function runOutcome(
  run: RunOutcomeSource | null | undefined,
  fallback: string = 'No summary recorded.',
): string {
  return run?.result_summary ?? run?.failure_reason ?? fallback
}

export function runOutcomeSummary(
  run: RunOutcomeSource | null | undefined,
  fallback: string = 'No summary',
): string {
  return runOutcome(run, runStatusLabel(runStatusValue(run)) ?? fallback)
}

export function occurrenceLabel(run: Run): string {
  if (!run.occurrence_key) return formatDateTime(run.planned_start_at)
  const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(run.occurrence_key)
  if (!match) return run.occurrence_key
  const [, year, month, day, hour, minute, second] = match
  return formatDateTime(`${year}-${month}-${day}T${hour}:${minute}:${second}Z`)
}

export function statusBadgeClass(status: RunStatus): string {
  switch (status) {
    case 'completed':
      return 'border-emerald-200 bg-emerald-50 text-emerald-800'
    case 'failed':
      return 'border-red-200 bg-red-50 text-red-800'
    case 'running':
      return 'border-blue-200 bg-blue-50 text-blue-800'
    case 'queued':
      return 'border-amber-200 bg-amber-50 text-amber-800'
    case 'canceled':
      return 'border-slate-300 bg-slate-100 text-slate-700'
    case 'planned':
      return 'border-indigo-200 bg-indigo-50 text-indigo-800'
  }
}

export function runStatusLabel(status: RunStatus | null | undefined): string | null {
  if (!status) return null
  return runStatusOptions.find((option) => option.value === status)?.label ?? status
}

function runStatusValue(run: RunOutcomeSource | null | undefined): RunStatus | null | undefined {
  return run?.run_status ?? run?.latest_run_outcome
}

export function runDuration(run: Run): string {
  if (!run.actual_start_at || !run.finished_at) return 'Not finished'
  const durationMs = new Date(run.finished_at).getTime() - new Date(run.actual_start_at).getTime()
  if (!Number.isFinite(durationMs) || durationMs < 0) return 'Not available'
  const minutes = Math.floor(durationMs / 60_000)
  const seconds = Math.floor((durationMs % 60_000) / 1000)
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60)
    const remainingMinutes = minutes % 60
    return `${hours}h ${remainingMinutes}m`
  }
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}
