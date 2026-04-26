<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  createTask,
  listTemplates,
  type ExecutionMode,
  type ExecutorName,
  type TaskTemplate,
} from '@/api'
import { defaultDateTimeLocal, isFutureLocal, toIsoWithOffset } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import {
  browserRecurrenceTimezone,
  buildRecurrenceRule,
  recurrencePreview,
  type RecurrenceCadence,
  type WeekdayCode,
  weekdayOptions,
} from '@/lib/recurrence'

const router = useRouter()
const route = useRoute()
const executorOptions: Array<{ label: string; value: ExecutorName }> = [
  { label: 'Debug Printer', value: 'debug_printer' },
  { label: 'Claude Code', value: 'claude_code' },
]

const title = ref('')
const instructions = ref('')
const targetWorkingDirectory = ref('')
const executor = ref<ExecutorName>('debug_printer')
const executionMode = ref<ExecutionMode>('one_time')
const plannedAt = ref(defaultDateTimeLocal())
const defaultPlannedAt = ref(plannedAt.value)
const recurrenceCadence = ref<RecurrenceCadence>('daily')
const recurrenceTime = ref('08:00')
const recurrenceWeekdays = ref<WeekdayCode[]>(['MO'])
const templates = ref<TaskTemplate[]>([])
const selectedTemplateId = ref('')
const isSaving = ref(false)
const errorMessage = ref<string | null>(null)

const timezoneLabel = browserRecurrenceTimezone()
const selectedTemplate = computed(() => {
  return (
    templates.value.find((template) => template.template_id === selectedTemplateId.value) ?? null
  )
})
const recurrenceIsValid = computed(
  () =>
    recurrenceTime.value.length > 0 &&
    (recurrenceCadence.value === 'daily' || recurrenceWeekdays.value.length > 0),
)
const recurrencePreviewText = computed(() =>
  recurrencePreview(
    recurrenceCadence.value,
    recurrenceTime.value,
    recurrenceWeekdays.value,
    timezoneLabel,
  ),
)
const canSave = computed(
  () =>
    title.value.trim().length > 0 &&
    instructions.value.trim().length > 0 &&
    targetWorkingDirectory.value.trim().startsWith('/') &&
    (executionMode.value === 'one_time'
      ? isFutureLocal(plannedAt.value)
      : recurrenceIsValid.value),
)

onMounted(loadTemplates)

watch(
  () => route.query.templateId,
  (templateId) => {
    if (typeof templateId === 'string') {
      selectedTemplateId.value = templateId
      applySelectedTemplate()
    }
  },
)

watch(
  () => route.query.mode,
  (mode) => {
    if (mode === 'recurring') {
      executionMode.value = 'recurring'
    } else if (mode === 'one_time') {
      executionMode.value = 'one_time'
    }
  },
  { immediate: true },
)

async function loadTemplates() {
  try {
    const response = await listTemplates({ limit: 100 })
    templates.value = response.data
    const templateId = route.query.templateId
    if (typeof templateId === 'string') {
      selectedTemplateId.value = templateId
      applySelectedTemplate()
    }
  } catch (error) {
    errorMessage.value = readableError(error)
  }
}

function changeExecutionMode(nextMode: ExecutionMode) {
  if (nextMode === executionMode.value) return
  if (hasScheduleInput() && !window.confirm('Change schedule mode and clear timing fields?')) {
    return
  }
  executionMode.value = nextMode
  resetScheduleForMode(nextMode)
}

function applySelectedTemplate() {
  if (!selectedTemplate.value) return
  title.value = selectedTemplate.value.default_task_title || selectedTemplate.value.name
  instructions.value = selectedTemplate.value.instruction_source
  targetWorkingDirectory.value =
    selectedTemplate.value.default_target_working_directory || targetWorkingDirectory.value
  executor.value = selectedTemplate.value.default_executor || executor.value
}

function toggleWeekday(day: WeekdayCode) {
  if (recurrenceWeekdays.value.includes(day)) {
    recurrenceWeekdays.value = recurrenceWeekdays.value.filter((value) => value !== day)
    return
  }
  recurrenceWeekdays.value = [...recurrenceWeekdays.value, day].sort(
    (left, right) =>
      weekdayOptions.findIndex((option) => option.value === left) -
      weekdayOptions.findIndex((option) => option.value === right),
  )
}

async function submitTask() {
  if (!canSave.value) {
    errorMessage.value =
      executionMode.value === 'one_time'
        ? 'Add a title, instructions, an absolute target directory, and a future execution time.'
        : 'Add a title, instructions, an absolute target directory, and a valid recurrence.'
    return
  }
  isSaving.value = true
  errorMessage.value = null
  try {
    const schedulePayload =
      executionMode.value === 'recurring'
        ? {
            execution_mode: 'recurring' as const,
            recurrence_rule: buildRecurrenceRule(
              recurrenceCadence.value,
              recurrenceTime.value,
              recurrenceWeekdays.value,
            ),
            recurrence_timezone: timezoneLabel,
          }
        : {
            execution_mode: 'one_time' as const,
            planned_at: toIsoWithOffset(plannedAt.value),
          }
    const created = await createTask({
      title: title.value.trim(),
      instruction_source: instructions.value.trim(),
      target_working_directory: targetWorkingDirectory.value.trim(),
      executor: executor.value,
      template_id: selectedTemplateId.value || null,
      ...schedulePayload,
    })
    title.value = ''
    instructions.value = ''
    targetWorkingDirectory.value = ''
    resetScheduleForMode(executionMode.value)
    selectedTemplateId.value = ''
    await router.push({ name: 'task-detail', params: { taskId: created.task.task_id } })
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isSaving.value = false
  }
}

function hasScheduleInput(): boolean {
  if (executionMode.value === 'one_time') {
    return plannedAt.value !== defaultPlannedAt.value
  }
  return (
    recurrenceTime.value !== '08:00' ||
    recurrenceCadence.value !== 'daily' ||
    recurrenceWeekdays.value.join(',') !== 'MO'
  )
}

function resetScheduleForMode(mode: ExecutionMode) {
  if (mode === 'one_time') {
    plannedAt.value = defaultDateTimeLocal()
    defaultPlannedAt.value = plannedAt.value
    return
  }
  recurrenceCadence.value = 'daily'
  recurrenceTime.value = '08:00'
  recurrenceWeekdays.value = ['MO']
}
</script>

<template>
  <div>
    <div
      v-if="errorMessage"
      class="mb-5 max-w-5xl rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800"
    >
      {{ errorMessage }}
    </div>

    <section class="max-w-3xl">
      <div class="mb-6">
        <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">Composer</p>
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">
          {{ executionMode === 'recurring' ? 'Create Recurring Task' : 'Create One-Time Task' }}
        </h2>
      </div>
      <form class="grid gap-5" @submit.prevent="submitTask">
        <label v-if="templates.length > 0" class="grid gap-2 font-semibold text-slate-700">
          <span>Template</span>
          <select
            v-model="selectedTemplateId"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            @change="applySelectedTemplate"
          >
            <option value="">Blank task</option>
            <option
              v-for="template in templates"
              :key="template.template_id"
              :value="template.template_id"
            >
              {{ template.name }}
            </option>
          </select>
        </label>
        <div class="grid gap-2 font-semibold text-slate-700">
          <span>Mode</span>
          <div class="grid grid-cols-2 gap-2 rounded-md border border-slate-200 bg-slate-50 p-1">
            <button
              class="min-h-10 rounded-md border px-3 font-semibold transition"
              :class="
                executionMode === 'one_time'
                  ? 'border-teal-700 bg-white text-teal-800 shadow-xs'
                  : 'border-transparent text-slate-600 hover:bg-white'
              "
              type="button"
              @click="changeExecutionMode('one_time')"
            >
              One-Time
            </button>
            <button
              class="min-h-10 rounded-md border px-3 font-semibold transition"
              :class="
                executionMode === 'recurring'
                  ? 'border-teal-700 bg-white text-teal-800 shadow-xs'
                  : 'border-transparent text-slate-600 hover:bg-white'
              "
              type="button"
              @click="changeExecutionMode('recurring')"
            >
              Recurring
            </button>
          </div>
        </div>
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Title</span>
          <input
            v-model="title"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            type="text"
            placeholder="Nightly Deep Research"
          />
        </label>
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Instructions</span>
          <textarea
            v-model="instructions"
            class="w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            rows="9"
            placeholder="Describe the AI work to run later..."
          />
        </label>
        <label v-if="executionMode === 'one_time'" class="grid gap-2 font-semibold text-slate-700">
          <span>Execution Time</span>
          <input
            v-model="plannedAt"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            type="datetime-local"
          />
        </label>
        <div v-else class="grid gap-4 rounded-md border border-slate-200 bg-white p-4">
          <label class="grid gap-2 font-semibold text-slate-700">
            <span>Cadence</span>
            <select
              v-model="recurrenceCadence"
              class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
          </label>
          <fieldset v-if="recurrenceCadence === 'weekly'" class="m-0 grid gap-2 border-0 p-0">
            <legend class="mb-1 font-semibold text-slate-700">Weekdays</legend>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="day in weekdayOptions"
                :key="day.value"
                class="min-h-9 rounded-md border px-3 text-sm font-semibold transition"
                :class="
                  recurrenceWeekdays.includes(day.value)
                    ? 'border-teal-700 bg-teal-50 text-teal-800'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-teal-700'
                "
                type="button"
                @click="toggleWeekday(day.value)"
              >
                {{ day.label }}
              </button>
            </div>
          </fieldset>
          <label class="grid gap-2 font-semibold text-slate-700">
            <span>Run Time</span>
            <input
              v-model="recurrenceTime"
              class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              type="time"
            />
          </label>
          <p class="m-0 text-sm text-slate-500">{{ recurrencePreviewText }}</p>
        </div>
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Target Directory</span>
          <input
            v-model="targetWorkingDirectory"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            type="text"
            placeholder="/Users/you/project"
          />
        </label>
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Executor</span>
          <select
            v-model="executor"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
          >
            <option v-for="option in executorOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <p class="m-0 text-sm text-slate-500">Timezone: {{ timezoneLabel }}</p>
        <button
          class="min-h-10 w-fit cursor-pointer rounded-md border border-transparent bg-teal-700 px-5 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
          type="submit"
          :disabled="!canSave || isSaving"
        >
          {{ isSaving ? 'Saving...' : 'Save Task' }}
        </button>
      </form>
    </section>
  </div>
</template>
