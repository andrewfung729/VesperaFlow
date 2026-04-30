<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  cancelTask,
  getRun,
  getTaskDetail,
  rescheduleTask,
  updateRecurringSchedule,
  updateTask,
  type ExecutorName,
  type Run,
  type TaskDetail,
} from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import MarkdownReader from '@/components/MarkdownReader.vue'
import RecurrenceEditor from '@/components/RecurrenceEditor.vue'
import RunStatusBadge from '@/components/RunStatusBadge.vue'
import SelectField from '@/components/SelectField.vue'
import TextArea from '@/components/TextArea.vue'
import TextInput from '@/components/TextInput.vue'
import UiButton from '@/components/UiButton.vue'
import { useRecurringTaskActions } from '@/composables/useRecurringTaskActions'
import { formatDateTime, isFutureLocal, toDateTimeLocal, toIsoWithOffset } from '@/lib/dateTime'
import { executionModeLabel } from '@/lib/executionModeDisplay'
import { executorOptions } from '@/lib/executors'
import { readableError } from '@/lib/errors'
import {
  browserRecurrenceTimezone,
  buildRecurrenceRule,
  parseRecurrenceRule,
  recurrenceSummary,
  type RecurrenceCadence,
  type WeekdayCode,
} from '@/lib/recurrence'
import { runOutcome, runOutcomeSummary } from '@/lib/runDisplay'

const props = defineProps<{
  taskId: string
}>()

const route = useRoute()
const router = useRouter()
const selectedDetail = ref<TaskDetail | null>(null)
const selectedRun = ref<Run | null>(null)
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
const editExecutor = ref<ExecutorName>('debug_printer')
const editTargetWorkingDirectory = ref('')
const selectedRunId = computed(() => {
  const value = route.query.runId
  return typeof value === 'string' ? value : null
})
const selectedOccurrenceAt = computed(() => {
  const value = route.query.occurrenceAt
  return typeof value === 'string' ? value : null
})
const isRecurringTask = computed(() => selectedDetail.value?.task.execution_mode === 'recurring')
const isTaskEditable = computed(() => {
  const status = selectedDetail.value?.task.task_status
  return (
    status !== undefined && status !== 'archived' && status !== 'running' && status !== 'completed'
  )
})
const {
  isActionPending: isRecurringActionPending,
  pauseTask,
  resumeTask,
  runNowTask,
} = useRecurringTaskActions(loadTaskDetail, (message) => {
  errorMessage.value = message
})

watch(
  () => [props.taskId, selectedRunId.value],
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
    if (selectedDetail.value.task.execution_mode === 'one_time') {
      const runId = selectedRunId.value ?? selectedDetail.value.latest_run?.run_id
      selectedRun.value = runId ? await getRun(runId) : selectedDetail.value.latest_run
    } else {
      selectedRun.value = null
    }
    rescheduleAt.value = selectedDetail.value.schedule?.planned_at
      ? toDateTimeLocal(selectedDetail.value.schedule.planned_at)
      : ''
    if (selectedDetail.value.schedule?.recurrence_rule) {
      resetRecurrenceForm()
    }
    isEditingRecurrence.value = route.query.edit === 'recurrence'
  } catch (error) {
    selectedDetail.value = null
    selectedRun.value = null
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
  editExecutor.value = selectedDetail.value.task.executor
  editTargetWorkingDirectory.value = selectedDetail.value.task.target_working_directory ?? ''
  isEditingTask.value = true
}

function cancelEditTask() {
  isEditingTask.value = false
  editTitle.value = ''
  editInstructions.value = ''
  editExecutor.value = 'debug_printer'
  editTargetWorkingDirectory.value = ''
}

async function submitTaskUpdate() {
  if (!selectedDetail.value) return
  const title = editTitle.value.trim()
  const instructionSource = editInstructions.value.trim()
  if (title.length === 0 || instructionSource.length === 0) {
    errorMessage.value = 'Title and instructions are required.'
    return
  }
  const targetWorkingDirectory = editTargetWorkingDirectory.value.trim()
  if (isRecurringTask.value && targetWorkingDirectory.length === 0) {
    errorMessage.value = 'Target directory is required.'
    return
  }
  try {
    if (isRecurringTask.value && selectedDetail.value.schedule) {
      await updateRecurringSchedule(
        props.taskId,
        selectedDetail.value.schedule.version,
        selectedDetail.value.schedule.recurrence_rule ?? '',
        selectedDetail.value.schedule.recurrence_timezone ?? browserRecurrenceTimezone(),
        {
          title,
          instruction_source: instructionSource,
          target_working_directory: targetWorkingDirectory,
          executor: editExecutor.value,
        },
      )
    } else {
      await updateTask(props.taskId, {
        version: selectedDetail.value.task.version,
        title,
        instruction_source: instructionSource,
      })
    }
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
  await pauseTask(props.taskId, selectedDetail.value.schedule.version)
}

async function submitResume() {
  if (!selectedDetail.value?.schedule) return
  await resumeTask(props.taskId, selectedDetail.value.schedule.version)
}

async function submitRunNow() {
  if (!selectedDetail.value?.task) return
  await runNowTask(props.taskId, selectedDetail.value.task.title)
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

function resetRecurrenceForm() {
  const parsed = parseRecurrenceRule(selectedDetail.value?.schedule?.recurrence_rule)
  recurrenceCadence.value = parsed.cadence
  recurrenceTime.value = parsed.time
  recurrenceWeekdays.value = parsed.weekdays
  recurrenceTimezone.value =
    selectedDetail.value?.schedule?.recurrence_timezone || browserRecurrenceTimezone()
}

async function openRunArchive() {
  await router.push({ name: 'recurring-run-archive', params: { taskId: props.taskId } })
}
</script>

<template>
  <div>
    <ErrorAlert :message="errorMessage" />

    <section class="max-w-7xl">
      <div
        v-if="selectedDetail"
        class="grid gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]"
      >
        <div>
          <p
            class="mb-2 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase"
          >
            Task Detail
          </p>
          <template v-if="isEditingTask">
            <TextInput v-model="editTitle" label="Title" />
            <TextArea v-model="editInstructions" class="mt-4" label="Instructions" rows="9" />
            <template v-if="isRecurringTask">
              <div class="mt-4 grid gap-4 sm:grid-cols-2">
                <SelectField v-model="editExecutor" label="Executor" :options="executorOptions" />
                <TextInput
                  v-model="editTargetWorkingDirectory"
                  label="Target Directory"
                  placeholder="/Users/you/project"
                />
              </div>
            </template>
            <div class="mt-4 flex flex-wrap gap-3">
              <UiButton
                variant="primary"
                :disabled="
                  !editTitle.trim() ||
                  !editInstructions.trim() ||
                  (isRecurringTask && !editTargetWorkingDirectory.trim())
                "
                @click="submitTaskUpdate"
              >
                Save Changes
              </UiButton>
              <UiButton @click="cancelEditTask"> Cancel </UiButton>
            </div>
          </template>
          <template v-else>
            <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
              {{ selectedDetail.task.title }}
            </h2>
            <p class="m-0 text-sm text-slate-500 dark:text-slate-400">
              {{ executionModeLabel(selectedDetail.task.execution_mode) }} ·
              {{ selectedDetail.task.task_status }} ·
              {{ selectedDetail.latest_run?.run_status ?? 'planned' }}
            </p>
            <p class="m-0 text-sm text-slate-500 dark:text-slate-400">
              Executor: {{ selectedDetail.task.executor }}
            </p>
            <p class="m-0 text-sm text-slate-500 dark:text-slate-400">
              Target: {{ selectedDetail.task.target_working_directory ?? 'none' }}
            </p>
            <pre
              class="mt-6 mb-0 whitespace-pre-wrap rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 text-sm text-slate-900 dark:text-slate-100 wrap-anywhere"
              >{{ selectedDetail.task.instruction_source }}</pre
            >
            <UiButton v-if="isTaskEditable" class="mt-4 w-fit" @click="startEditTask">
              Edit Task
            </UiButton>
          </template>
          <section
            v-if="isRecurringTask"
            class="mt-6 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5"
          >
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h3 class="m-0 text-lg font-bold text-slate-950 dark:text-slate-50">Run Archive</h3>
                <p class="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Read each recurring outcome in a focused single-column reader.
                </p>
              </div>
              <UiButton variant="primary" @click="openRunArchive"> Open Run Archive </UiButton>
            </div>
          </section>
          <section v-else class="mt-6">
            <h3 class="m-0 mb-3 text-lg font-bold text-slate-950 dark:text-slate-50">
              Recent Runs
            </h3>
            <article
              v-if="selectedRun"
              class="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5"
            >
              <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
                <h4 class="m-0 text-base font-bold text-slate-950 dark:text-slate-50">
                  {{ selectedRun.run_id }}
                </h4>
                <RunStatusBadge :status="selectedRun.run_status" />
              </div>
              <dl class="m-0 mb-4 grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt class="font-bold text-slate-500 dark:text-slate-400">Planned</dt>
                  <dd class="m-0 text-slate-700 dark:text-slate-300">
                    {{ formatDateTime(selectedRun.planned_start_at) }}
                  </dd>
                </div>
                <div>
                  <dt class="font-bold text-slate-500 dark:text-slate-400">Started</dt>
                  <dd class="m-0 text-slate-700 dark:text-slate-300">
                    {{ formatDateTime(selectedRun.actual_start_at) }}
                  </dd>
                </div>
                <div>
                  <dt class="font-bold text-slate-500 dark:text-slate-400">Finished</dt>
                  <dd class="m-0 text-slate-700 dark:text-slate-300">
                    {{ formatDateTime(selectedRun.finished_at) }}
                  </dd>
                </div>
              </dl>
              <div class="max-w-3xl border-t border-slate-200 dark:border-slate-700 pt-4">
                <MarkdownReader
                  :content="runOutcome(selectedRun)"
                  :expandable="false"
                  class="wrap-anywhere"
                />
              </div>
            </article>
            <div
              v-else
              class="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5"
            >
              <h4 class="m-0 text-base font-bold text-slate-950 dark:text-slate-50">
                No runs recorded
              </h4>
              <p class="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">
                This task has no run output yet.
              </p>
            </div>
          </section>
        </div>
        <aside
          class="grid content-start gap-4 border-t border-slate-200 dark:border-slate-700 pt-5 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-6"
        >
          <dl class="m-0 grid gap-1.5">
            <dt class="text-sm font-bold text-slate-500 dark:text-slate-400">Planned</dt>
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
            <template v-if="isRecurringTask">
              <dt class="text-sm font-bold text-slate-500 dark:text-slate-400">Timezone</dt>
              <dd class="m-0 mb-2.5 wrap-break-word">
                {{ selectedDetail.schedule?.recurrence_timezone ?? 'none' }}
              </dd>
              <dt class="text-sm font-bold text-slate-500 dark:text-slate-400">Next Run</dt>
              <dd class="m-0 mb-2.5 wrap-break-word">
                {{ formatDateTime(selectedDetail.schedule?.next_run_at ?? null) }}
              </dd>
            </template>
            <dt class="text-sm font-bold text-slate-500 dark:text-slate-400">Schedule</dt>
            <dd class="m-0 mb-2.5 wrap-break-word">
              {{ selectedDetail.schedule?.schedule_status ?? 'none' }}
            </dd>
            <dt class="text-sm font-bold text-slate-500 dark:text-slate-400">Latest Result</dt>
            <dd
              class="m-0 mb-2.5 wrap-break-word rounded-md border p-3 text-sm line-clamp-4"
              :class="
                selectedDetail.latest_run?.run_status === 'failed'
                  ? 'border-red-200 bg-red-50 text-red-800'
                  : 'border-slate-200 bg-white text-slate-600'
              "
            >
              <RunStatusBadge
                v-if="selectedDetail.latest_run"
                class="mb-1"
                :status="selectedDetail.latest_run.run_status"
              />
              <span class="block">
                {{ runOutcomeSummary(selectedDetail.latest_run, 'Pending') }}
              </span>
            </dd>
            <template v-if="selectedRun && !isRecurringTask">
              <dt class="text-sm font-bold text-slate-500 dark:text-slate-400">Selected Run</dt>
              <dd
                class="m-0 mb-2.5 wrap-break-word text-sm text-slate-600 dark:text-slate-400 line-clamp-3"
              >
                {{ selectedRun.run_status }} · {{ runOutcomeSummary(selectedRun, 'No summary') }}
              </dd>
            </template>
            <template v-if="selectedOccurrenceAt">
              <dt class="text-sm font-bold text-slate-500 dark:text-slate-400">
                Selected Occurrence
              </dt>
              <dd class="m-0 mb-2.5 wrap-break-word">
                {{ formatDateTime(selectedOccurrenceAt) }}
              </dd>
            </template>
          </dl>
          <UiButton
            v-if="
              selectedDetail.schedule?.schedule_status === 'active' &&
              (isRecurringTask ||
                (selectedDetail.task.task_status === 'scheduled' &&
                  selectedDetail.latest_run?.run_status === 'planned'))
            "
            variant="primary"
            :disabled="isRecurringActionPending"
            @click="submitRunNow"
          >
            Run Now
          </UiButton>
          <template v-if="!isRecurringTask">
            <TextInput v-model="rescheduleAt" label="Reschedule" type="datetime-local" />
            <UiButton :disabled="!selectedDetail.schedule" @click="submitReschedule">
              Reschedule
            </UiButton>
          </template>
          <template v-else>
            <UiButton
              :disabled="
                !selectedDetail.schedule || isScheduleActionPending || isRecurringActionPending
              "
              @click="isEditingRecurrence = !isEditingRecurrence"
            >
              {{ isEditingRecurrence ? 'Close Recurrence Editor' : 'Edit Recurrence' }}
            </UiButton>
            <form
              v-if="isEditingRecurrence"
              class="grid gap-4"
              @submit.prevent="submitRecurrenceUpdate"
            >
              <RecurrenceEditor
                v-model:cadence="recurrenceCadence"
                v-model:time="recurrenceTime"
                v-model:weekdays="recurrenceWeekdays"
                :timezone="recurrenceTimezone"
              />
              <UiButton variant="primary" :disabled="isScheduleActionPending" type="submit">
                {{ isScheduleActionPending ? 'Saving...' : 'Save Recurrence' }}
              </UiButton>
            </form>
            <UiButton
              v-if="selectedDetail.schedule?.schedule_status === 'active'"
              :disabled="isRecurringActionPending"
              @click="submitPause"
            >
              Pause
            </UiButton>
            <UiButton
              v-if="selectedDetail.schedule?.schedule_status === 'paused'"
              :disabled="isRecurringActionPending"
              @click="submitResume"
            >
              Resume
            </UiButton>
          </template>
          <UiButton variant="danger" :disabled="!selectedDetail.schedule" @click="submitCancel">
            {{ isRecurringTask ? 'Cancel Series' : 'Cancel Task' }}
          </UiButton>
        </aside>
      </div>
      <div
        v-else
        class="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-7"
      >
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
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
