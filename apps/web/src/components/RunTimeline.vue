<script setup lang="ts">
import type { RunEvent } from '@/api'
import { formatDateTime } from '@/lib/dateTime'

defineProps<{
  events: RunEvent[]
  isLoading?: boolean
}>()

function severityClass(severity: string) {
  if (severity === 'error') return 'border-red-200 bg-red-50 text-red-800'
  if (severity === 'warning') return 'border-amber-200 bg-amber-50 text-amber-800'
  return 'border-slate-200 bg-slate-50 text-slate-700'
}

function eventMeta(event: RunEvent): string {
  const parts = [
    event.activity_type,
    event.activity_attempt ? `attempt ${event.activity_attempt}` : null,
    typeof event.details.terminal_code === 'string' ? event.details.terminal_code : null,
  ].filter(Boolean)
  return parts.join(' · ')
}
</script>

<template>
  <section>
    <div class="mb-3 flex items-center justify-between gap-3">
      <h3 class="m-0 text-lg font-bold text-slate-950 dark:text-slate-50">Timeline</h3>
      <span class="text-xs font-semibold text-slate-500 dark:text-slate-400">
        {{ isLoading ? 'Loading' : `${events.length} events` }}
      </span>
    </div>
    <ol v-if="events.length > 0" class="m-0 grid list-none gap-2 p-0">
      <li
        v-for="event in events"
        :key="event.run_event_id"
        class="rounded-md border p-3"
        :class="severityClass(event.severity)"
      >
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p class="m-0 text-sm font-bold">{{ event.message }}</p>
            <p class="m-0 mt-0.5 text-xs opacity-80">{{ event.event_type }}</p>
          </div>
          <time class="text-xs font-semibold opacity-80" :datetime="event.created_at">
            {{ formatDateTime(event.created_at) }}
          </time>
        </div>
        <p v-if="eventMeta(event)" class="m-0 mt-2 text-xs font-semibold opacity-80">
          {{ eventMeta(event) }}
        </p>
      </li>
    </ol>
    <div
      v-else
      class="rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400"
    >
      {{ isLoading ? 'Loading run timeline.' : 'No timeline events recorded yet.' }}
    </div>
  </section>
</template>
