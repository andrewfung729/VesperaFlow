<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import {
  cancelTask,
  getTaskDetail,
  pauseRecurringTask,
  rescheduleTask,
  resumeRecurringTask,
  runTaskNow,
  updateRecurringSchedule,
  updateTask,
  type TaskDetail,
} from '@/api'
import MarkdownReader from '@/components/MarkdownReader.vue'
import { formatDateTime, isFutureLocal, toDateTimeLocal, toIsoWithOffset } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import {
  browserRecurrenceTimezone,
  buildRecurrenceRule,
  parseRecurrenceRule,
  recurrencePreview,
  recurrenceSummary,
  weekdayOptions,
  type RecurrenceCadence,
  type WeekdayCode,
} from '@/lib/recurrence'

const props = defineProps<{
  taskId: string
}>()

const route = useRoute()
const selectedDetail = ref<TaskDetail | null>(null)
const isLoadingDetail = ref(false)
const errorMessage = ref<string | null>(null)
const rescheduleAt = ref('')
const isEditingRecurrence = ref(false)
const recurrenceCadence = ref<RecurrenceCadence>('daily')
const recurrenceTime = ref('08:00')
const recurrenceWeekdays = ref<WeekdayCode[]>(['MO'])
const recurrenceTimezone = ref(browserRecurrenceTimezone())
const isScheduleActionPending = ref(false)
const isEditingTask = ref(false)
const editTitle = ref('')
const editInstructions = ref('')
const selectedRunId = computed(() => {
  const value = route.query.runId
  return typeof value === 'string' ? value : null
})
const selectedOccurrenceAt = computed(() => {
  const value = route.query.occurrenceAt
  return typeof value === 'string' ? value : null
})
const selectedRun = computed(() =>
  selectedDetail.value?.runs.find((run) => run.run_id === selectedRunId.value),
)
const isRecurringTask = computed(() => selectedDetail.value?.task.execution_mode === 'recurring')
const isTaskEditable = computed(() => {
  const status = selectedDetail.value?.task.task_status
  return (
    status !== undefined && status !== 'archived' && status !== 'running' && status !== 'completed'
  )
})
const recurrencePreviewText = computed(() =>
  recurrencePreview(
    recurrenceCadence.value,
    recurrenceTime.value,
    recurrenceWeekdays.value,
    recurrenceTimezone.value,
  ),
)

watch(
  () => props.taskId,
  () => {
    void loadTaskDetail()
  },
  { immediate: true },
)

async function loadTaskDetail() {
  if (!props.taskId) return
  isLoadingDetail.value = true
  errorMessage.value = null
  try {
    selectedDetail.value = await getTaskDetail(props.taskId)
    rescheduleAt.value = selectedDetail.value.schedule?.planned_at
      ? toDateTimeLocal(selectedDetail.value.schedule.planned_at)
      : ''
    if (selectedDetail.value.schedule?.recurrence_rule) {
      resetRecurrenceForm()
    }
    isEditingRecurrence.value = route.query.edit === 'recurrence'
  } catch (error) {
    selectedDetail.value = null
    rescheduleAt.value = ''
    errorMessage.value = readableError(error)
  } finally {
    isLoadingDetail.value = false
  }
}

async function submitReschedule() {
  if (!selectedDetail.value?.schedule) return
  if (!isFutureLocal(rescheduleAt.value)) {
    errorMessage.value = 'Choose a future execution time.'
    return
  }
  try {
    await rescheduleTask(
      props.taskId,
      selectedDetail.value.schedule.version,
      toIsoWithOffset(rescheduleAt.value),
    )
    await loadTaskDetail()
  } catch (error) {
    errorMessage.value = readableError(error)
  }
}

function startEditTask() {
  if (!selectedDetail.value) return
  editTitle.value = selectedDetail.value.task.title
  editInstructions.value = selectedDetail.value.task.instruction_source
  isEditingTask.value = true
}

function cancelEditTask() {
  isEditingTask.value = false
  editTitle.value = ''
  editInstructions.value = ''
}

async function submitTaskUpdate() {
  if (!selectedDetail.value) return
  const title = editTitle.value.trim()
  const instructionSource = editInstructions.value.trim()
  if (title.length === 0 || instructionSource.length === 0) {
    errorMessage.value = 'Title and instructions are required.'
    return
  }
  try {
    await updateTask(props.taskId, {
      version: selectedDetail.value.task.version,
      title,
      instruction_source: instructionSource,
    })
    isEditingTask.value = false
    await loadTaskDetail()
  } catch (error) {
    errorMessage.value = readableError(error)
  }
}

async function submitRecurrenceUpdate() {
  if (!selectedDetail.value?.schedule) return
  if (recurrenceCadence.value === 'weekly' && recurrenceWeekdays.value.length === 0) {
    errorMessage.value = 'Choose at least one weekday.'
    return
  }
  isScheduleActionPending.value = true
  errorMessage.value = null
  try {
    await updateRecurringSchedule(
      props.taskId,
      selectedDetail.value.schedule.version,
      buildRecurrenceRule(recurrenceCadence.value, recurrenceTime.value, recurrenceWeekdays.value),
      recurrenceTimezone.value,
    )
    await loadTaskDetail()
    isEditingRecurrence.value = false
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isScheduleActionPending.value = false
  }
}

async function submitPause() {
  if (!selectedDetail.value?.schedule) return
  isScheduleActionPending.value = true
  errorMessage.value = null
  try {
    await pauseRecurringTask(props.taskId, selectedDetail.value.schedule.version)
    await loadTaskDetail()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isScheduleActionPending.value = false
  }
}

async function submitResume() {
  if (!selectedDetail.value?.schedule) return
  isScheduleActionPending.value = true
  errorMessage.value = null
  try {
    await resumeRecurringTask(props.taskId, selectedDetail.value.schedule.version)
    await loadTaskDetail()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isScheduleActionPending.value = false
  }
}

async function submitRunNow() {
  if (!selectedDetail.value?.task) return
  const confirmed = window.confirm(`Run "${selectedDetail.value.task.title}" immediately?`)
  if (!confirmed) return
  try {
    await runTaskNow(props.taskId)
    await loadTaskDetail()
  } catch (error) {
    errorMessage.value = readableError(error)
  }
}

async function submitCancel() {
  if (!selectedDetail.value?.schedule) return
  const action = isRecurringTask.value ? 'Cancel series' : 'Cancel'
  const confirmed = window.confirm(`${action} "${selectedDetail.value.task.title}"?`)
  if (!confirmed) return
  try {
    await cancelTask(props.taskId, selectedDetail.value.schedule.version)
    await loadTaskDetail()
  } catch (error) {
    errorMessage.value = readableError(error)
  }
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

function resetRecurrenceForm() {
  const parsed = parseRecurrenceRule(selectedDetail.value?.schedule?.recurrence_rule)
  recurrenceCadence.value = parsed.cadence
  recurrenceTime.value = parsed.time
  recurrenceWeekdays.value = parsed.weekdays
  recurrenceTimezone.value =
    selectedDetail.value?.schedule?.recurrence_timezone || browserRecurrenceTimezone()
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

    <section class="max-w-7xl">
      <div
        v-if="selectedDetail"
        class="grid gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]"
      >
        <div>
          <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">Task Detail</p>
          <template v-if="isEditingTask">
            <label class="grid gap-2 font-semibold text-slate-700">
              <span>Title</span>
              <input
                v-model="editTitle"
                class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
                type="text"
              />
            </label>
            <label class="mt-4 grid gap-2 font-semibold text-slate-700">
              <span>Instructions</span>
              <textarea
                v-model="editInstructions"
                class="w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
                rows="9"
              />
            </label>
            <div class="mt-4 flex flex-wrap gap-3">
              <button
                class="min-h-10 cursor-pointer rounded-md border border-transparent bg-teal-700 px-4 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                :disabled="!editTitle.trim() || !editInstructions.trim()"
                @click="submitTaskUpdate"
              >
                Save Changes
              </button>
              <button
                class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50"
                @click="cancelEditTask"
              >
                Cancel
              </button>
            </div>
          </template>
          <template v-else>
            <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">
              {{ selectedDetail.task.title }}
            </h2>
            <p class="m-0 text-sm text-slate-500">
              {{ selectedDetail.task.execution_mode }} · {{ selectedDetail.task.task_status }} ·
              {{ selectedDetail.latest_run?.run_status ?? 'planned' }}
            </p>
            <p class="m-0 text-sm text-slate-500">Executor: {{ selectedDetail.task.executor }}</p>
            <p class="m-0 text-sm text-slate-500">
              Target: {{ selectedDetail.task.target_working_directory ?? 'none' }}
            </p>
            <pre
              class="mt-6 mb-0 whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-900 wrap-anywhere"
              >{{ selectedDetail.task.instruction_source }}</pre
            >
            <button
              v-if="isTaskEditable"
              class="mt-4 min-h-10 w-fit cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50"
              @click="startEditTask"
            >
              Edit Task
            </button>
          </template>
          <section class="mt-6">
            <h3 class="m-0 mb-3 text-lg font-bold text-slate-950">Recent Runs</h3>
            <div v-if="selectedDetail.runs.length > 0" class="grid gap-2">
              <article
                v-for="run in selectedDetail.runs"
                :key="run.run_id"
                class="rounded-md border p-3"
                :class="
                  selectedRunId === run.run_id
                    ? 'border-teal-400 bg-teal-50'
                    : 'border-slate-200 bg-white'
                "
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <strong class="text-slate-800">{{ run.run_status }}</strong>
                  <span class="text-sm text-slate-500">
                    {{
                      formatDateTime(run.finished_at ?? run.actual_start_at ?? run.planned_start_at)
                    }}
                  </span>
                </div>
                <MarkdownReader
                  :content="run.result_summary ?? run.failure_reason"
                  class="wrap-anywhere"
                />
              </article>
            </div>
            <p v-else class="text-sm text-slate-500">No runs recorded.</p>
          </section>
        </div>
        <aside
          class="grid content-start gap-4 border-t border-slate-200 pt-5 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-6"
        >
          <dl class="m-0 grid gap-1.5">
            <dt class="text-sm font-bold text-slate-500">Planned</dt>
            <dd class="m-0 mb-2.5 wrap-break-word">
              {{
                isRecurringTask
                  ? recurrenceSummary(
                      selectedDetail.schedule?.recurrence_rule,
                      selectedDetail.schedule?.recurrence_timezone,
                    )
                  : formatDateTime(selectedDetail.schedule?.planned_at ?? null)
              }}
            </dd>
            <dt class="text-sm font-bold text-slate-500">Schedule</dt>
            <dd class="m-0 mb-2.5 wrap-break-word">
              {{ selectedDetail.schedule?.schedule_status ?? 'none' }}
            </dd>
            <dt class="text-sm font-bold text-slate-500">Latest Result</dt>
            <dd class="m-0 mb-2.5 wrap-break-word text-sm text-slate-600 line-clamp-3">
              {{
                selectedDetail.latest_run?.result_summary ??
                selectedDetail.latest_run?.failure_reason ??
                'Pending'
              }}
            </dd>
            <template v-if="selectedRun">
              <dt class="text-sm font-bold text-slate-500">Selected Run</dt>
              <dd class="m-0 mb-2.5 wrap-break-word text-sm text-slate-600 line-clamp-3">
                {{ selectedRun.run_status }} ·
                {{ selectedRun.result_summary ?? selectedRun.failure_reason ?? 'No summary' }}
              </dd>
            </template>
            <template v-if="selectedOccurrenceAt">
              <dt class="text-sm font-bold text-slate-500">Selected Occurrence</dt>
              <dd class="m-0 mb-2.5 wrap-break-word">
                {{ formatDateTime(selectedOccurrenceAt) }}
              </dd>
            </template>
          </dl>
          <button
            v-if="
              selectedDetail.schedule?.schedule_status === 'active' &&
              (isRecurringTask ||
                (selectedDetail.task.task_status === 'scheduled' &&
                  selectedDetail.latest_run?.run_status === 'planned'))
            "
            class="min-h-10 cursor-pointer rounded-md border border-transparent bg-teal-700 px-4 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
            @click="submitRunNow"
          >
            Run Now
          </button>
          <template v-if="!isRecurringTask">
            <label class="grid gap-2 font-semibold text-slate-700">
              <span>Reschedule</span>
              <input
                v-model="rescheduleAt"
                class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
                type="datetime-local"
              />
            </label>
            <button
              class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="!selectedDetail.schedule"
              @click="submitReschedule"
            >
              Reschedule
            </button>
          </template>
          <template v-else>
            <button
              class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="!selectedDetail.schedule || isScheduleActionPending"
              @click="isEditingRecurrence = !isEditingRecurrence"
            >
              {{ isEditingRecurrence ? 'Close Recurrence Editor' : 'Edit Recurrence' }}
            </button>
            <form
              v-if="isEditingRecurrence"
              class="grid gap-4 rounded-md border border-slate-200 bg-white p-4"
              @submit.prevent="submitRecurrenceUpdate"
            >
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
              <button
                class="min-h-10 cursor-pointer rounded-md border border-transparent bg-teal-700 px-4 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                :disabled="isScheduleActionPending"
                type="submit"
              >
                {{ isScheduleActionPending ? 'Saving...' : 'Save Recurrence' }}
              </button>
            </form>
            <button
              v-if="selectedDetail.schedule?.schedule_status === 'active'"
              class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="isScheduleActionPending"
              @click="submitPause"
            >
              Pause
            </button>
            <button
              v-if="selectedDetail.schedule?.schedule_status === 'paused'"
              class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="isScheduleActionPending"
              @click="submitResume"
            >
              Resume
            </button>
          </template>
          <button
            class="min-h-10 cursor-pointer rounded-md border border-red-300 bg-red-50 px-4 font-semibold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="!selectedDetail.schedule"
            @click="submitCancel"
          >
            {{ isRecurringTask ? 'Cancel Series' : 'Cancel Task' }}
          </button>
        </aside>
      </div>
      <div v-else class="rounded-md border border-slate-200 bg-white p-7">
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">
          {{ isLoadingDetail ? 'Loading task...' : 'Task unavailable' }}
        </h2>
        <p>
          {{
            isLoadingDetail ? 'Loading the selected task detail.' : 'Open a task from the board.'
          }}
        </p>
      </div>
    </section>
  </div>
</template>
