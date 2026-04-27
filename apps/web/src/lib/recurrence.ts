export type RecurrenceCadence = 'daily' | 'weekly'
export type WeekdayCode = 'MO' | 'TU' | 'WE' | 'TH' | 'FR' | 'SA' | 'SU'

export const weekdayOptions: Array<{ label: string; value: WeekdayCode }> = [
  { label: 'Mon', value: 'MO' },
  { label: 'Tue', value: 'TU' },
  { label: 'Wed', value: 'WE' },
  { label: 'Thu', value: 'TH' },
  { label: 'Fri', value: 'FR' },
  { label: 'Sat', value: 'SA' },
  { label: 'Sun', value: 'SU' },
]

const weekdayLabels = Object.fromEntries(
  weekdayOptions.map((option) => [option.value, option.label]),
) as Record<WeekdayCode, string>

export interface ParsedRecurrence {
  cadence: RecurrenceCadence
  time: string
  weekdays: WeekdayCode[]
}

export function browserRecurrenceTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}

export function buildRecurrenceRule(
  cadence: RecurrenceCadence,
  time: string,
  weekdays: WeekdayCode[],
): string {
  const [hour, minute] = parseTime(time)
  if (cadence === 'daily') {
    return `RRULE:FREQ=DAILY;BYHOUR=${hour};BYMINUTE=${minute}`
  }
  if (weekdays.length === 0) {
    throw new Error('Choose at least one weekday.')
  }
  return `RRULE:FREQ=WEEKLY;BYDAY=${weekdays.join(',')};BYHOUR=${hour};BYMINUTE=${minute}`
}

export function parseRecurrenceRule(rule: string | null | undefined): ParsedRecurrence {
  const parts = parseRuleParts(rule)
  const cadence: RecurrenceCadence = parts.FREQ === 'WEEKLY' ? 'weekly' : 'daily'
  const hour = parts.BYHOUR?.split(',')[0] ?? '8'
  const minute = parts.BYMINUTE?.split(',')[0] ?? '0'
  const weekdays = parts.BYDAY?.split(',').filter(Boolean) as WeekdayCode[] | undefined
  return {
    cadence,
    time: `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`,
    weekdays: cadence === 'weekly' && weekdays?.length ? weekdays : ['MO'],
  }
}

export function recurrenceSummary(
  rule: string | null | undefined,
  timezone: string | null | undefined,
): string {
  const parsed = parseRecurrenceRule(rule)
  const zone = timezone || 'UTC'
  if (parsed.cadence === 'daily') {
    return `Daily at ${parsed.time} (${zone})`
  }
  const days = parsed.weekdays.map((day) => weekdayLabels[day] ?? day).join(', ')
  return `Weekly on ${days} at ${parsed.time} (${zone})`
}

export function recurrencePreview(
  cadence: RecurrenceCadence,
  time: string,
  weekdays: WeekdayCode[],
  timezone: string,
): string {
  if (cadence === 'daily') {
    return `Runs daily at ${time} (${timezone})`
  }
  const days = weekdays.map((day) => weekdayLabels[day] ?? day).join(', ')
  return days ? `Runs weekly on ${days} at ${time} (${timezone})` : 'Choose at least one weekday.'
}

function parseRuleParts(rule: string | null | undefined): Record<string, string> {
  if (!rule) return { FREQ: 'DAILY', BYHOUR: '8', BYMINUTE: '0' }
  return Object.fromEntries(
    rule
      .replace(/^RRULE:/, '')
      .split(';')
      .map((part) => {
        const [key, value] = part.split('=')
        return [key, value]
      })
      .filter(([key, value]) => key && value),
  )
}

function parseTime(time: string): [string, string] {
  const [rawHour, rawMinute] = time.split(':')
  const hour = Number(rawHour)
  const minute = Number(rawMinute)
  if (
    !Number.isInteger(hour) ||
    !Number.isInteger(minute) ||
    hour < 0 ||
    hour > 23 ||
    minute < 0 ||
    minute > 59
  ) {
    throw new Error('Choose a valid time.')
  }
  return [String(hour), String(minute)]
}
