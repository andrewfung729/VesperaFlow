<script setup lang="ts">
import { computed } from 'vue'

import SelectField from '@/components/SelectField.vue'
import TextInput from '@/components/TextInput.vue'
import {
  recurrencePreview,
  type RecurrenceCadence,
  type WeekdayCode,
  weekdayOptions,
} from '@/lib/recurrence'

const cadence = defineModel<RecurrenceCadence>('cadence', { required: true })
const time = defineModel<string>('time', { required: true })
const weekdays = defineModel<WeekdayCode[]>('weekdays', { required: true })

const props = withDefaults(
  defineProps<{
    timezone: string
  }>(),
  {
    timezone: 'UTC',
  },
)

const cadenceOptions: Array<{ label: string; value: RecurrenceCadence }> = [
  { label: 'Daily', value: 'daily' },
  { label: 'Weekly', value: 'weekly' },
]

const previewText = computed(() =>
  recurrencePreview(cadence.value, time.value, weekdays.value, props.timezone),
)

function toggleWeekday(day: WeekdayCode) {
  if (weekdays.value.includes(day)) {
    weekdays.value = weekdays.value.filter((value) => value !== day)
    return
  }
  weekdays.value = [...weekdays.value, day].sort(
    (left, right) =>
      weekdayOptions.findIndex((option) => option.value === left) -
      weekdayOptions.findIndex((option) => option.value === right),
  )
}
</script>

<template>
  <div
    class="grid gap-4 rounded-md border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
  >
    <SelectField v-model="cadence" label="Cadence" :options="cadenceOptions" />
    <fieldset v-if="cadence === 'weekly'" class="m-0 grid gap-2 border-0 p-0">
      <legend class="mb-1 font-semibold text-slate-700 dark:text-slate-300">Weekdays</legend>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="day in weekdayOptions"
          :key="day.value"
          class="min-h-9 rounded-md border px-3 text-sm font-semibold transition"
          :class="
            weekdays.includes(day.value)
              ? 'border-teal-700 bg-teal-50 text-teal-800 dark:border-teal-500 dark:bg-teal-950/30 dark:text-teal-300'
              : 'border-slate-300 bg-white text-slate-700 hover:border-teal-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-teal-500'
          "
          type="button"
          @click="toggleWeekday(day.value)"
        >
          {{ day.label }}
        </button>
      </div>
    </fieldset>
    <TextInput v-model="time" label="Run Time" type="time" />
    <p class="m-0 text-sm text-slate-500 dark:text-slate-400">{{ previewText }}</p>
  </div>
</template>
