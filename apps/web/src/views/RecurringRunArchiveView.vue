<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getTaskDetail, getTaskRuns, type RunPreview, type RunStatus, type TaskDetail } from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import PageStatePanel from '@/components/PageStatePanel.vue'
import RunStatusBadge from '@/components/RunStatusBadge.vue'
import SelectField from '@/components/SelectField.vue'
import UiButton from '@/components/UiButton.vue'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { recurrenceSummary } from '@/lib/recurrence'
import { occurrenceLabel, runOutcome, runStatusOptions } from '@/lib/runDisplay'

const props = defineProps<{
  taskId: string
}>()

const router = useRouter()

const selectedDetail = ref<TaskDetail | null>(null)
const runs = ref<RunPreview[]>([])
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const statusFilter = ref<RunStatus | ''>('')
const archiveStatusOptions = runStatusOptions.filter((option) =>
  ['completed', 'failed', 'running', 'planned'].includes(option.value),
)

const latestRun = computed(() => runs.value[0] ?? selectedDetail.value?.latest_run ?? null)

watch(
  () => props.taskId,
  () => {
    statusFilter.value = ''
  },
)

watch(
  [() => props.taskId, statusFilter],
  () => {
    void loadArchive()
  },
  { immediate: true },
)

async function loadArchive() {
  if (!props.taskId) return
  isLoading.value = true
  errorMessage.value = null
  try {
    selectedDetail.value = await getTaskDetail(props.taskId)
    const runsResponse = await getTaskRuns(props.taskId, { status: statusFilter.value })
    runs.value = runsResponse.data
  } catch (error) {
    selectedDetail.value = null
    runs.value = []
    errorMessage.value = readableError(error)
  } finally {
    isLoading.value = false
  }
}

async function openTaskDetail() {
  await router.push({ name: 'task-detail', params: { taskId: props.taskId } })
}

async function openRun(run: RunPreview) {
  await router.push({
    name: 'recurring-run-reader',
    params: { taskId: props.taskId, runId: run.run_id },
  })
}
</script>

<template>
  <div>
    <ErrorAlert :message="errorMessage" />

    <section class="max-w-5xl">
      <div v-if="selectedDetail" class="grid gap-6">
        <div
          class="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5"
        >
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p
                class="mb-2 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase"
              >
                {{ selectedDetail.task.title }}
              </p>
              <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
                Run Archive
              </h2>
              <p class="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">
                {{ runs.length }} recorded occurrences
              </p>
            </div>
            <UiButton @click="openTaskDetail"> Task Detail </UiButton>
          </div>

          <dl class="m-0 mt-5 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Cadence</dt>
              <dd class="m-0 text-slate-800 dark:text-slate-200">
                {{
                  recurrenceSummary(
                    selectedDetail.schedule?.recurrence_rule,
                    selectedDetail.schedule?.recurrence_timezone,
                  )
                }}
              </dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Timezone</dt>
              <dd class="m-0 text-slate-800 dark:text-slate-200">
                {{ selectedDetail.schedule?.recurrence_timezone ?? 'none' }}
              </dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Next Run</dt>
              <dd class="m-0 text-slate-800 dark:text-slate-200">
                {{ formatDateTime(selectedDetail.schedule?.next_run_at ?? null) }}
              </dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Latest Status</dt>
              <dd class="m-0">
                <RunStatusBadge v-if="latestRun" :status="latestRun.run_status" />
                <span v-else class="text-slate-500 dark:text-slate-400">No runs yet</span>
              </dd>
            </div>
          </dl>
        </div>

        <div class="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 class="m-0 text-lg font-bold text-slate-950 dark:text-slate-50">Occurrences</h3>
            <p class="m-0 text-sm text-slate-500 dark:text-slate-400">Newest first</p>
          </div>
          <SelectField
            v-model="statusFilter"
            compact
            label="Status"
            :options="archiveStatusOptions"
            empty-label="All"
          />
        </div>

        <div v-if="runs.length > 0" class="grid gap-3">
          <article
            v-for="run in runs"
            :key="run.run_id"
            class="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 transition-colors hover:border-teal-300"
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h4 class="m-0 text-base font-bold text-slate-950 dark:text-slate-50">
                  {{ occurrenceLabel(run) }}
                </h4>
                <p class="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Planned {{ formatDateTime(run.planned_start_at) }} · Started
                  {{ formatDateTime(run.actual_start_at) }} · Finished
                  {{ formatDateTime(run.finished_at) }}
                </p>
              </div>
              <RunStatusBadge :status="run.run_status" />
            </div>
            <p
              class="mt-3 mb-0 text-sm text-slate-600 dark:text-slate-400 line-clamp-2 wrap-anywhere"
            >
              {{ runOutcome(run) }}
            </p>
            <UiButton class="mt-3" size="sm" @click="openRun(run)"> Read Outcome </UiButton>
          </article>
        </div>

        <PageStatePanel
          v-else
          title="No matching runs"
          :message="
            statusFilter
              ? 'No occurrences match the selected status.'
              : 'This recurring series has not recorded any runs yet.'
          "
        />
      </div>

      <PageStatePanel
        v-else
        spacious
        :title="isLoading ? 'Loading run archive...' : 'Run archive unavailable'"
        :message="isLoading ? 'Loading recorded occurrences.' : 'Open a recurring task first.'"
      />
    </section>
  </div>
</template>
