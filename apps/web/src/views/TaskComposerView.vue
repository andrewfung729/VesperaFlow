<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  createTask,
  listExecutorProfiles,
  listTemplates,
  preflightExecutor,
  type ExecutionMode,
  type ExecutorName,
  type ExecutorProfile,
  type ExecutorPreflightResult,
  type TaskTemplate,
} from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import RecurrenceEditor from '@/components/RecurrenceEditor.vue'
import SelectField from '@/components/SelectField.vue'
import TextArea from '@/components/TextArea.vue'
import TextInput from '@/components/TextInput.vue'
import UiButton from '@/components/UiButton.vue'
import { defaultDateTimeLocal, isFutureLocal, toIsoWithOffset } from '@/lib/dateTime'
import { executionModeLabel, executionModeOptions } from '@/lib/executionModeDisplay'
import { defaultExecutorProfileId, executorLabel, executorProfileOptions } from '@/lib/executors'
import { readableError } from '@/lib/errors'
import {
  browserRecurrenceTimezone,
  buildRecurrenceRule,
  type RecurrenceCadence,
  type WeekdayCode,
} from '@/lib/recurrence'

const router = useRouter()
const route = useRoute()

const title = ref('')
const instructions = ref('')
const targetWorkingDirectory = ref('')
const executorProfileId = ref('')
const executionMode = ref<ExecutionMode>('one_time')
const plannedAt = ref(defaultDateTimeLocal())
const defaultPlannedAt = ref(plannedAt.value)
const recurrenceCadence = ref<RecurrenceCadence>('daily')
const recurrenceTime = ref('08:00')
const recurrenceWeekdays = ref<WeekdayCode[]>(['MO'])
const templates = ref<TaskTemplate[]>([])
const executorProfiles = ref<ExecutorProfile[]>([])
const selectedTemplateId = ref('')
const isSaving = ref(false)
const isCheckingExecutor = ref(false)
const errorMessage = ref<string | null>(null)
const executorPreflight = ref<ExecutorPreflightResult | null>(null)

const timezoneLabel = browserRecurrenceTimezone()
const selectedTemplate = computed(() => {
  return (
    templates.value.find((template) => template.template_id === selectedTemplateId.value) ?? null
  )
})
const selectedExecutorProfile = computed(
  () =>
    executorProfiles.value.find((profile) => profile.profile_id === executorProfileId.value) ??
    null,
)
const selectedExecutor = computed<ExecutorName | null>(
  () => selectedExecutorProfile.value?.executor ?? null,
)
const executorProfileSelectOptions = computed(() => executorProfileOptions(executorProfiles.value))
const templateOptions = computed(() =>
  templates.value.map((template) => ({ label: template.name, value: template.template_id })),
)
const recurrenceIsValid = computed(
  () =>
    recurrenceTime.value.length > 0 &&
    (recurrenceCadence.value === 'daily' || recurrenceWeekdays.value.length > 0),
)
const canSave = computed(
  () =>
    title.value.trim().length > 0 &&
    instructions.value.trim().length > 0 &&
    targetWorkingDirectory.value.trim().startsWith('/') &&
    selectedExecutor.value !== null &&
    (executionMode.value === 'one_time' ? isFutureLocal(plannedAt.value) : recurrenceIsValid.value),
)
const executorStatusText = computed(() => {
  if (!selectedExecutor.value) return 'Select an executor profile.'
  if (selectedExecutor.value === 'debug_printer') return 'Debug printer is available.'
  if (!executorPreflight.value)
    return `${executorLabel(selectedExecutor.value)} has not been checked for this target.`
  return executorPreflight.value.message
})
const executorStatusClass = computed(() => {
  if (!executorPreflight.value) return 'border-slate-200 bg-white text-slate-600'
  if (executorPreflight.value.status === 'unavailable') {
    return 'border-red-200 bg-red-50 text-red-800'
  }
  if (executorPreflight.value.status === 'warning') {
    return 'border-amber-200 bg-amber-50 text-amber-800'
  }
  return 'border-emerald-200 bg-emerald-50 text-emerald-800'
})

onMounted(loadInitialData)

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

async function loadInitialData() {
  try {
    const [templatesResponse, profilesResponse] = await Promise.all([
      listTemplates({ limit: 100 }),
      listExecutorProfiles({ limit: 100 }),
    ])
    templates.value = templatesResponse.data
    executorProfiles.value = profilesResponse.data
    if (!executorProfileId.value) {
      executorProfileId.value = defaultExecutorProfileId(executorProfiles.value)
    }
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
  executorProfileId.value =
    selectedTemplate.value.default_executor_profile_id || executorProfileId.value
  executorPreflight.value = null
}

async function submitTask() {
  if (!canSave.value) {
    errorMessage.value =
      executionMode.value === 'one_time'
        ? 'Add a title, instructions, executor profile, absolute target directory, and a future execution time.'
        : 'Add a title, instructions, executor profile, absolute target directory, and a valid recurrence.'
    return
  }
  const executor = selectedExecutor.value
  if (executor === null) {
    errorMessage.value = 'Select an executor profile.'
    return
  }
  isSaving.value = true
  errorMessage.value = null
  try {
    if (executor !== 'debug_printer') {
      const preflight = await checkExecutor()
      if (preflight?.status === 'unavailable') {
        errorMessage.value = preflight.message
        return
      }
    }
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
      executor,
      executor_profile_id: executorProfileId.value || null,
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

async function checkExecutor(): Promise<ExecutorPreflightResult | null> {
  const executor = selectedExecutor.value
  if (executor === null) {
    executorPreflight.value = null
    return null
  }
  if (executor === 'debug_printer') {
    executorPreflight.value = {
      executor: 'debug_printer',
      status: 'available',
      code: 'executor_preflight_passed',
      message: 'Debug printer is available.',
      details: {},
    }
    return executorPreflight.value
  }
  if (!targetWorkingDirectory.value.trim().startsWith('/')) {
    executorPreflight.value = {
      executor,
      status: 'unavailable',
      code: 'executor_workspace_unavailable',
      message: 'Target directory must be an existing absolute directory.',
      details: {},
    }
    return executorPreflight.value
  }
  isCheckingExecutor.value = true
  try {
    executorPreflight.value = await preflightExecutor({
      executor,
      executor_profile_id: executorProfileId.value || undefined,
      target_working_directory: targetWorkingDirectory.value.trim(),
    })
    return executorPreflight.value
  } catch (error) {
    executorPreflight.value = {
      executor,
      status: 'unavailable',
      code: 'executor_preflight_failed',
      message: readableError(error),
      details: {},
    }
    return executorPreflight.value
  } finally {
    isCheckingExecutor.value = false
  }
}

watch([executorProfileId, targetWorkingDirectory], () => {
  executorPreflight.value = null
})

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
    <ErrorAlert :message="errorMessage" />

    <section class="max-w-3xl">
      <div class="mb-6">
        <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase">
          Composer
        </p>
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
          {{ executionMode === 'recurring' ? 'Create Recurring Task' : 'Create One-Time Task' }}
        </h2>
      </div>
      <form class="grid gap-5" @submit.prevent="submitTask">
        <SelectField
          v-if="templates.length > 0"
          v-model="selectedTemplateId"
          label="Template"
          :options="templateOptions"
          empty-label="Blank task"
          @change="applySelectedTemplate"
        />
        <div class="grid gap-2 font-semibold text-slate-700 dark:text-slate-300">
          <span>Mode</span>
          <div
            class="grid grid-cols-2 gap-2 rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-1"
          >
            <button
              v-for="option in executionModeOptions"
              :key="option.value"
              class="min-h-10 rounded-md border px-3 font-semibold transition"
              :class="
                executionMode === option.value
                  ? 'border-teal-700 bg-white text-teal-800 shadow-xs'
                  : 'border-transparent text-slate-600 hover:bg-white'
              "
              type="button"
              @click="changeExecutionMode(option.value)"
            >
              {{ executionModeLabel(option.value) }}
            </button>
          </div>
        </div>
        <TextInput v-model="title" label="Title" placeholder="Nightly Deep Research" />
        <TextArea
          v-model="instructions"
          label="Instructions"
          rows="9"
          placeholder="Describe the AI work to run later..."
        />
        <TextInput
          v-if="executionMode === 'one_time'"
          v-model="plannedAt"
          label="Execution Time"
          type="datetime-local"
        />
        <RecurrenceEditor
          v-else
          v-model:cadence="recurrenceCadence"
          v-model:time="recurrenceTime"
          v-model:weekdays="recurrenceWeekdays"
          :timezone="timezoneLabel"
        />
        <TextInput
          v-model="targetWorkingDirectory"
          label="Target Directory"
          placeholder="/Users/you/project"
        />
        <SelectField
          v-model="executorProfileId"
          label="Executor Profile"
          :options="executorProfileSelectOptions"
        />
        <div class="grid gap-2">
          <div
            class="rounded-md border px-3 py-2 text-sm font-medium"
            :class="executorStatusClass"
            role="status"
          >
            {{ executorStatusText }}
          </div>
          <UiButton
            v-if="selectedExecutor && selectedExecutor !== 'debug_printer'"
            class="w-fit"
            :disabled="isCheckingExecutor || targetWorkingDirectory.trim().length === 0"
            @click="checkExecutor"
          >
            {{ isCheckingExecutor ? 'Checking...' : 'Check Executor' }}
          </UiButton>
        </div>
        <p class="m-0 text-sm text-slate-500 dark:text-slate-400">Timezone: {{ timezoneLabel }}</p>
        <UiButton
          class="w-fit px-5"
          type="submit"
          variant="primary"
          :disabled="!canSave || isSaving"
        >
          {{ isSaving ? 'Saving...' : 'Save Task' }}
        </UiButton>
      </form>
    </section>
  </div>
</template>
