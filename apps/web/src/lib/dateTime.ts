export function defaultDateTimeLocal(): string {
  const date = new Date(Date.now() + 60 * 60 * 1000)
  date.setMinutes(Math.ceil(date.getMinutes() / 5) * 5, 0, 0)
  return toDateTimeLocal(date.toISOString())
}

export function toDateTimeLocal(value: string): string {
  const date = new Date(value)
  const offsetMs = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

export function toIsoWithOffset(value: string): string {
  const date = new Date(value)
  const offsetMinutes = -date.getTimezoneOffset()
  const sign = offsetMinutes >= 0 ? '+' : '-'
  const absolute = Math.abs(offsetMinutes)
  const hours = String(Math.floor(absolute / 60)).padStart(2, '0')
  const minutes = String(absolute % 60).padStart(2, '0')
  return `${value}:00${sign}${hours}:${minutes}`
}

export function isFutureLocal(value: string): boolean {
  return value.length > 0 && new Date(value).getTime() > Date.now()
}

export function formatDateTime(value: string | null): string {
  if (!value) return 'No time set'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
