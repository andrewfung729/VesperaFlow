<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getTaskDetail, getTaskRuns, type Run, type RunStatus, type TaskDetail } from '@/api'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { recurrenceSummary } from '@/lib/recurrence'
import { occurrenceLabel, runOutcome, statusBadgeClass } from '@/lib/runDisplay'

const props = defineProps<{
  taskId: string
}>()

const router = useRouter()

const selectedDetail = ref<TaskDetail | null>(null)
const runs = ref<Run[]>([])
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const statusFilter = ref<RunStatus | ''>('')

const filteredRuns = computed(() => {
  if (!statusFilter.value) return runs.value
  return runs.value.filter((run) => run.run_status === statusFilter.value)
})

const latestRun = computed(() => runs.value[0] ?? selectedDetail.value?.latest_run ?? null)

watch(
  () => props.taskId,
  () => {
    statusFilter.value = ''
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
    const runsResponse = await getTaskRuns(props.taskId)
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

async function openRun(run: Run) {
  await router.push({
    name: 'recurring-run-reader',
    params: { taskId: props.taskId, runId: run.run_id },
  })
}
</script>

<template>
  <div>
    <div
      v-if="errorMessage"
      class="mb-5 max-w-5xl rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm font-medium text-red-800 dark:text-red-300"
      role="alert"
    >
      {{ errorMessage }}
    </div>

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
            <button
              class="min-h-10 cursor-pointer rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-4 font-semibold text-slate-700 dark:text-slate-300 shadow-xs transition hover:bg-slate-50"
              type="button"
              @click="openTaskDetail"
            >
              Task Detail
            </button>
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
                <span
                  v-if="latestRun"
                  class="inline-flex rounded-md border px-2 py-1 text-xs font-bold uppercase"
                  :class="statusBadgeClass(latestRun.run_status)"
                >
                  {{ latestRun.run_status }}
                </span>
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
          <label class="grid gap-1 text-sm font-semibold text-slate-700 dark:text-slate-300">
            <span>Status</span>
            <select
              v-model="statusFilter"
              class="min-h-10 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 text-slate-950 dark:text-slate-50 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            >
              <option value="">All</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="running">Running</option>
              <option value="planned">Planned</option>
            </select>
          </label>
        </div>

        <div v-if="filteredRuns.length > 0" class="grid gap-3">
          <article
            v-for="run in filteredRuns"
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
              <span
                class="inline-flex rounded-md border px-2 py-1 text-xs font-bold uppercase"
                :class="statusBadgeClass(run.run_status)"
              >
                {{ run.run_status }}
              </span>
            </div>
            <p
              class="mt-3 mb-0 text-sm text-slate-600 dark:text-slate-400 line-clamp-2 wrap-anywhere"
            >
              {{ runOutcome(run) }}
            </p>
            <button
              class="mt-3 min-h-9 cursor-pointer rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 text-sm font-semibold text-slate-700 dark:text-slate-300 transition hover:border-teal-700 dark:hover:border-teal-500 hover:text-teal-800"
              type="button"
              @click="openRun(run)"
            >
              Read Outcome
            </button>
          </article>
        </div>

        <div
          v-else
          class="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6"
        >
          <h3 class="m-0 text-lg font-bold text-slate-950 dark:text-slate-50">No matching runs</h3>
          <p class="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">
            {{
              statusFilter
                ? 'No occurrences match the selected status.'
                : 'This recurring series has not recorded any runs yet.'
            }}
          </p>
        </div>
      </div>

      <div
        v-else
        class="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-7"
      >
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
          {{ isLoading ? 'Loading run archive...' : 'Run archive unavailable' }}
        </h2>
        <p class="m-0 mt-1 text-slate-600 dark:text-slate-400">
          {{ isLoading ? 'Loading recorded occurrences.' : 'Open a recurring task first.' }}
        </p>
      </div>
    </section>
  </div>
</template>
