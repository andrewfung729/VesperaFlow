<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getTaskDetail, getTaskRuns, type Run, type TaskDetail } from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import MarkdownReader from '@/components/MarkdownReader.vue'
import PageStatePanel from '@/components/PageStatePanel.vue'
import RunStatusBadge from '@/components/RunStatusBadge.vue'
import UiButton from '@/components/UiButton.vue'
import { useReaderPreference, type ReaderFontSize } from '@/composables/useReaderPreference'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { occurrenceLabel, runDuration, runOutcome } from '@/lib/runDisplay'

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

const { fontSize } = useReaderPreference()

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

function cycleFontSize(direction: 'down' | 'up') {
  const sizes: ReaderFontSize[] = ['sm', 'md', 'lg', 'xl']
  const currentIndex = sizes.indexOf(fontSize.value)
  if (direction === 'down' && currentIndex > 0) {
    const next = sizes[currentIndex - 1]
    if (next) fontSize.value = next
  } else if (direction === 'up' && currentIndex < sizes.length - 1) {
    const next = sizes[currentIndex + 1]
    if (next) fontSize.value = next
  }
}
</script>

<template>
  <div>
    <ErrorAlert :message="errorMessage" />

    <section class="max-w-none">
      <div
        class="sticky top-0 z-10 -mx-5 mb-6 border-b border-slate-200 bg-slate-50/95 px-5 py-3 backdrop-blur md:-mx-8 md:px-8 dark:border-slate-700 dark:bg-slate-900/95"
      >
        <div class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap gap-2">
            <UiButton size="sm" @click="openArchive">
              Back to Archive
            </UiButton>
            <UiButton
              size="sm"
              :disabled="!previousRun"
              @click="openRun(previousRun)"
            >
              Previous Run
            </UiButton>
            <UiButton
              size="sm"
              :disabled="!nextRun"
              @click="openRun(nextRun)"
            >
              Next Run
            </UiButton>
          </div>
          <div class="flex items-center gap-2">
            <RunStatusBadge
              v-if="selectedRun"
              :status="selectedRun.run_status"
            />
            <div
              class="inline-flex items-center rounded-md border border-slate-300 bg-white shadow-xs dark:border-slate-600 dark:bg-slate-800"
            >
              <button
                class="min-h-9 cursor-pointer px-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55 dark:text-slate-200 dark:hover:bg-slate-700"
                type="button"
                aria-label="Decrease font size"
                :disabled="fontSize === 'sm'"
                @click="cycleFontSize('down')"
              >
                A-
              </button>
              <span class="px-1 text-xs font-bold text-slate-500 dark:text-slate-400">{{
                fontSize.toUpperCase()
              }}</span>
              <button
                class="min-h-9 cursor-pointer px-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55 dark:text-slate-200 dark:hover:bg-slate-700"
                type="button"
                aria-label="Increase font size"
                :disabled="fontSize === 'xl'"
                @click="cycleFontSize('up')"
              >
                A+
              </button>
            </div>
            <UiButton
              size="sm"
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
            </UiButton>
          </div>
        </div>
      </div>

      <article v-if="selectedDetail && selectedRun" class="mx-auto max-w-5xl">
        <header
          class="mb-8 rounded-md border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
        >
          <p
            class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase dark:text-teal-400"
          >
            Outcome Reader
          </p>
          <h2 class="m-0 text-3xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
            {{ selectedDetail.task.title }}
          </h2>
          <p class="m-0 mt-2 text-base font-semibold text-slate-700 dark:text-slate-300">
            {{ occurrenceLabel(selectedRun) }}
          </p>
          <dl class="m-0 mt-5 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Planned</dt>
              <dd class="m-0 text-slate-800 dark:text-slate-200">
                {{ formatDateTime(selectedRun.planned_start_at) }}
              </dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Started</dt>
              <dd class="m-0 text-slate-800 dark:text-slate-200">
                {{ formatDateTime(selectedRun.actual_start_at) }}
              </dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Finished</dt>
              <dd class="m-0 text-slate-800 dark:text-slate-200">
                {{ formatDateTime(selectedRun.finished_at) }}
              </dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Duration</dt>
              <dd class="m-0 text-slate-800 dark:text-slate-200">{{ runDuration(selectedRun) }}</dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Status</dt>
              <dd class="m-0">
                <RunStatusBadge :status="selectedRun.run_status" />
              </dd>
            </div>
          </dl>
        </header>

        <div
          class="mx-auto w-full max-w-[88ch] rounded-md border border-slate-200 bg-white p-6 sm:p-8 dark:border-slate-700 dark:bg-slate-900"
          :class="`reader-font-${fontSize}`"
          data-testid="reader-body"
        >
          <MarkdownReader
            :content="runOutcome(selectedRun)"
            :expandable="false"
            class="run-reader-content wrap-anywhere"
          />
        </div>

        <footer class="mx-auto mt-6 flex w-full max-w-[88ch] flex-wrap justify-between gap-3">
          <UiButton
            :disabled="!previousRun"
            @click="openRun(previousRun)"
          >
            Previous Run
          </UiButton>
          <UiButton
            :disabled="!nextRun"
            @click="openRun(nextRun)"
          >
            Next Run
          </UiButton>
        </footer>
      </article>

      <PageStatePanel
        v-else
        class="mx-auto max-w-5xl rounded-md border border-slate-200 bg-white p-7 dark:border-slate-700 dark:bg-slate-900"
        spacious
        :title="isLoading ? 'Loading outcome...' : 'Outcome unavailable'"
        :message="
          isLoading
            ? 'Loading the selected run outcome.'
            : 'This run was not found in the recurring task archive.'
        "
      />
    </section>
  </div>
</template>

<style scoped>
.run-reader-content :deep(.markdown-body) {
  line-height: 1.75;
}

.reader-font-sm .run-reader-content :deep(.markdown-body) {
  font-size: 1rem;
}
.reader-font-md .run-reader-content :deep(.markdown-body) {
  font-size: 1.125rem;
}
.reader-font-lg .run-reader-content :deep(.markdown-body) {
  font-size: 1.25rem;
}
.reader-font-xl .run-reader-content :deep(.markdown-body) {
  font-size: 1.375rem;
}

.reader-font-sm .run-reader-content :deep(.markdown-body h1) {
  font-size: 1.625rem;
}
.reader-font-sm .run-reader-content :deep(.markdown-body h2) {
  font-size: 1.375rem;
}
.reader-font-sm .run-reader-content :deep(.markdown-body h3) {
  font-size: 1.125rem;
}

.reader-font-md .run-reader-content :deep(.markdown-body h1) {
  font-size: 1.875rem;
}
.reader-font-md .run-reader-content :deep(.markdown-body h2) {
  font-size: 1.5rem;
}
.reader-font-md .run-reader-content :deep(.markdown-body h3) {
  font-size: 1.25rem;
}

.reader-font-lg .run-reader-content :deep(.markdown-body h1) {
  font-size: 2rem;
}
.reader-font-lg .run-reader-content :deep(.markdown-body h2) {
  font-size: 1.625rem;
}
.reader-font-lg .run-reader-content :deep(.markdown-body h3) {
  font-size: 1.375rem;
}

.reader-font-xl .run-reader-content :deep(.markdown-body h1) {
  font-size: 2.25rem;
}
.reader-font-xl .run-reader-content :deep(.markdown-body h2) {
  font-size: 1.875rem;
}
.reader-font-xl .run-reader-content :deep(.markdown-body h3) {
  font-size: 1.5rem;
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
