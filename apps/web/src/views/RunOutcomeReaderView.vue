<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getTaskDetail, getTaskRuns, type Run, type TaskDetail } from '@/api'
import MarkdownReader from '@/components/MarkdownReader.vue'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { occurrenceLabel, runDuration, runOutcome, statusBadgeClass } from '@/lib/runDisplay'

const props = defineProps<{
  taskId: string
  runId: string
}>()

const router = useRouter()

const selectedDetail = ref<TaskDetail | null>(null)
const runs = ref<Run[]>([])
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const copyStatus = ref<'idle' | 'copied' | 'failed'>('idle')

const selectedRun = computed(() => runs.value.find((run) => run.run_id === props.runId) ?? null)
const selectedRunIndex = computed(() =>
  runs.value.findIndex((run) => run.run_id === selectedRun.value?.run_id),
)
const previousRun = computed(() => {
  const index = selectedRunIndex.value
  return index > 0 ? runs.value[index - 1] : null
})
const nextRun = computed(() => {
  const index = selectedRunIndex.value
  return index >= 0 && index < runs.value.length - 1 ? runs.value[index + 1] : null
})

watch(
  () => [props.taskId, props.runId],
  () => {
    copyStatus.value = 'idle'
    void loadReader()
  },
  { immediate: true },
)

async function loadReader() {
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

async function openArchive() {
  await router.push({ name: 'recurring-run-archive', params: { taskId: props.taskId } })
}

async function openRun(run: Run | null | undefined) {
  if (!run) return
  await router.push({
    name: 'recurring-run-reader',
    params: { taskId: props.taskId, runId: run.run_id },
  })
}

async function copyOutcome() {
  if (!selectedRun.value) return
  try {
    await navigator.clipboard.writeText(runOutcome(selectedRun.value))
    copyStatus.value = 'copied'
  } catch {
    copyStatus.value = 'failed'
  }
}
</script>

<template>
  <div>
    <div
      v-if="errorMessage"
      class="mb-5 max-w-5xl rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800"
      role="alert"
    >
      {{ errorMessage }}
    </div>

    <section class="max-w-none">
      <div
        class="sticky top-0 z-10 -mx-6 mb-6 border-b border-slate-200 bg-slate-50/95 px-6 py-3 backdrop-blur"
      >
        <div class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap gap-2">
            <button
              class="min-h-9 cursor-pointer rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50"
              type="button"
              @click="openArchive"
            >
              Back to Archive
            </button>
            <button
              class="min-h-9 cursor-pointer rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
              type="button"
              :disabled="!previousRun"
              @click="openRun(previousRun)"
            >
              Previous Run
            </button>
            <button
              class="min-h-9 cursor-pointer rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
              type="button"
              :disabled="!nextRun"
              @click="openRun(nextRun)"
            >
              Next Run
            </button>
          </div>
          <div class="flex items-center gap-2">
            <span
              v-if="selectedRun"
              class="inline-flex rounded-md border px-2 py-1 text-xs font-bold uppercase"
              :class="statusBadgeClass(selectedRun.run_status)"
            >
              {{ selectedRun.run_status }}
            </span>
            <button
              class="min-h-9 cursor-pointer rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
              type="button"
              :disabled="!selectedRun"
              @click="copyOutcome"
            >
              {{
                copyStatus === 'copied'
                  ? 'Copied'
                  : copyStatus === 'failed'
                    ? 'Copy Failed'
                    : 'Copy Outcome'
              }}
            </button>
          </div>
        </div>
      </div>

      <article v-if="selectedDetail && selectedRun" class="mx-auto max-w-5xl">
        <header class="mb-8 rounded-md border border-slate-200 bg-white p-5">
          <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">Outcome Reader</p>
          <h2 class="m-0 text-3xl font-bold tracking-normal text-slate-950">
            {{ selectedDetail.task.title }}
          </h2>
          <p class="m-0 mt-2 text-base font-semibold text-slate-700">
            {{ occurrenceLabel(selectedRun) }}
          </p>
          <dl class="m-0 mt-5 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
            <div>
              <dt class="font-bold text-slate-500">Planned</dt>
              <dd class="m-0 text-slate-800">{{ formatDateTime(selectedRun.planned_start_at) }}</dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500">Started</dt>
              <dd class="m-0 text-slate-800">{{ formatDateTime(selectedRun.actual_start_at) }}</dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500">Finished</dt>
              <dd class="m-0 text-slate-800">{{ formatDateTime(selectedRun.finished_at) }}</dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500">Duration</dt>
              <dd class="m-0 text-slate-800">{{ runDuration(selectedRun) }}</dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500">Status</dt>
              <dd class="m-0">
                <span
                  class="inline-flex rounded-md border px-2 py-1 text-xs font-bold uppercase"
                  :class="statusBadgeClass(selectedRun.run_status)"
                >
                  {{ selectedRun.run_status }}
                </span>
              </dd>
            </div>
          </dl>
        </header>

        <div class="mx-auto max-w-prose rounded-md border border-slate-200 bg-white p-6 sm:p-8">
          <MarkdownReader
            :content="runOutcome(selectedRun)"
            :expandable="false"
            class="run-reader-content wrap-anywhere"
          />
        </div>

        <footer class="mx-auto mt-6 flex max-w-prose flex-wrap justify-between gap-3">
          <button
            class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
            type="button"
            :disabled="!previousRun"
            @click="openRun(previousRun)"
          >
            Previous Run
          </button>
          <button
            class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
            type="button"
            :disabled="!nextRun"
            @click="openRun(nextRun)"
          >
            Next Run
          </button>
        </footer>
      </article>

      <div v-else class="mx-auto max-w-5xl rounded-md border border-slate-200 bg-white p-7">
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">
          {{ isLoading ? 'Loading outcome...' : 'Outcome unavailable' }}
        </h2>
        <p class="m-0 mt-1 text-slate-600">
          {{
            isLoading
              ? 'Loading the selected run outcome.'
              : 'This run was not found in the recurring task archive.'
          }}
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.run-reader-content :deep(.markdown-body) {
  font-size: 1rem;
  line-height: 1.75;
}

.run-reader-content :deep(.markdown-body h1) {
  font-size: 1.75rem;
}

.run-reader-content :deep(.markdown-body h2) {
  font-size: 1.375rem;
}

.run-reader-content :deep(.markdown-body h3) {
  font-size: 1.125rem;
}

.run-reader-content :deep(.markdown-body p),
.run-reader-content :deep(.markdown-body ul),
.run-reader-content :deep(.markdown-body ol),
.run-reader-content :deep(.markdown-body pre),
.run-reader-content :deep(.markdown-body table),
.run-reader-content :deep(.markdown-body blockquote) {
  margin-top: 1em;
  margin-bottom: 1em;
}

.run-reader-content :deep(.markdown-body table) {
  display: block;
  overflow-x: auto;
  max-width: 100%;
}
</style>
