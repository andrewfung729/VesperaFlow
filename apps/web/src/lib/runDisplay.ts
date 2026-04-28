import type { Run, RunStatus } from '@/api'
import { formatDateTime } from '@/lib/dateTime'

export function runOutcome(run: Run | null | undefined): string {
  return run?.result_summary ?? run?.failure_reason ?? 'No summary recorded.'
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
