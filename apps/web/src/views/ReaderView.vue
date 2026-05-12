<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getRunDetail, type RunDetail } from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import MarkdownArticle from '@/components/MarkdownArticle.vue'
import PageStatePanel from '@/components/PageStatePanel.vue'
import RunStatusBadge from '@/components/RunStatusBadge.vue'
import UiButton from '@/components/UiButton.vue'
import { useReaderPreference, type ReaderFontSize } from '@/composables/useReaderPreference'
import { useReaderShortcuts } from '@/composables/useReaderShortcuts'
import { useScrollDirection } from '@/composables/useScrollDirection'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { occurrenceLabel, runDuration, runOutcome } from '@/lib/runDisplay'

const props = defineProps<{
  taskId: string
  runId: string
}>()

const router = useRouter()

const readerDetail = ref<RunDetail | null>(null)
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const copyStatus = ref<'idle' | 'copied' | 'failed'>('idle')
const showMetadataDetails = ref(false)

const { fontSize } = useReaderPreference()
const { direction, isAtTop } = useScrollDirection()

const selectedRun = computed(() => readerDetail.value?.run ?? null)
const previousRunId = computed(() => readerDetail.value?.previous_run_id ?? null)
const nextRunId = computed(() => readerDetail.value?.next_run_id ?? null)

const toolbarHidden = computed(() => direction.value === 'down' && !isAtTop.value)

watch(
  () => [props.taskId, props.runId],
  () => {
    copyStatus.value = 'idle'
    showMetadataDetails.value = false
    void loadReader()
  },
  { immediate: true },
)

async function loadReader() {
  if (!props.taskId) return
  isLoading.value = true
  errorMessage.value = null
  try {
    readerDetail.value = await getRunDetail(props.taskId, props.runId)
  } catch (error) {
    readerDetail.value = null
    errorMessage.value = readableError(error)
  } finally {
    isLoading.value = false
  }
}

async function openRunDetail() {
  await router.push({ name: 'run-detail', params: { taskId: props.taskId, runId: props.runId } })
}

async function openRun(runId: string | null | undefined) {
  if (!runId) return
  await router.push({
    name: 'run-reader',
    params: { taskId: props.taskId, runId },
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

useReaderShortcuts({
  onPrev: () => openRun(previousRunId.value),
  onNext: () => openRun(nextRunId.value),
  onFontInc: () => cycleFontSize('up'),
  onFontDec: () => cycleFontSize('down'),
  onBack: () => openRunDetail(),
  onCopy: () => copyOutcome(),
})
</script>

<template>
  <div>
    <ErrorAlert :message="errorMessage" />

    <section>
      <div
        data-testid="reader-toolbar"
        class="sticky top-0 z-10 -mx-5 border-b border-slate-200/60 bg-slate-50/80 px-5 py-3 backdrop-blur transition-transform duration-200 md:-mx-8 md:px-8 dark:border-slate-700/60 dark:bg-slate-900/80"
        :data-hidden="toolbarHidden"
      >
        <div class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap gap-2">
            <UiButton size="sm" title="Back to Run (Esc)" @click="openRunDetail">
              Back to Run
            </UiButton>
            <UiButton
              size="sm"
              title="Previous Run (←)"
              :disabled="!previousRunId"
              @click="openRun(previousRunId)"
            >
              Previous Run
            </UiButton>
            <UiButton
              size="sm"
              title="Next Run (→)"
              :disabled="!nextRunId"
              @click="openRun(nextRunId)"
            >
              Next Run
            </UiButton>
          </div>
          <div class="flex items-center gap-2">
            <RunStatusBadge v-if="selectedRun" :status="selectedRun.run_status" />
            <div
              class="inline-flex items-center rounded-md border border-slate-300 bg-white shadow-xs dark:border-slate-600 dark:bg-slate-800"
            >
              <button
                class="min-h-9 cursor-pointer px-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55 dark:text-slate-200 dark:hover:bg-slate-700"
                type="button"
                title="Decrease font size (-)"
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
                title="Increase font size (+)"
                aria-label="Increase font size"
                :disabled="fontSize === 'xl'"
                @click="cycleFontSize('up')"
              >
                A+
              </button>
            </div>
            <UiButton
              size="sm"
              title="Copy Outcome (c)"
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

      <article v-if="readerDetail && selectedRun" class="mx-auto max-w-5xl">
        <header class="border-b border-slate-200 pb-6 pt-8 dark:border-slate-700">
          <h1 class="m-0 text-3xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
            {{ readerDetail.task.title }}
          </h1>
          <p class="m-0 mt-2 text-base font-semibold text-slate-700 dark:text-slate-300">
            {{ occurrenceLabel(selectedRun) }}
          </p>

          <div
            class="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600 dark:text-slate-400"
          >
            <span data-testid="metadata-summary">
              {{ formatDateTime(selectedRun.actual_start_at ?? selectedRun.planned_start_at) }} ·
              {{ runDuration(selectedRun) }} ·
              <RunStatusBadge :status="selectedRun.run_status" />
            </span>
            <button
              type="button"
              data-testid="metadata-details-toggle"
              class="cursor-pointer border-0 bg-transparent p-0 text-sm font-semibold text-teal-700 transition hover:text-teal-900 dark:text-teal-400 dark:hover:text-teal-300"
              @click="showMetadataDetails = !showMetadataDetails"
            >
              {{ showMetadataDetails ? 'Hide Details' : 'Details' }}
            </button>
          </div>

          <dl
            v-if="showMetadataDetails"
            data-testid="metadata-details"
            class="m-0 mt-4 grid gap-3 border-t border-slate-200 pt-4 text-sm sm:grid-cols-2 lg:grid-cols-5 dark:border-slate-700"
          >
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

        <div class="pb-12 pt-8" :class="`reader-font-${fontSize}`" data-testid="reader-body">
          <section>
            <h2 class="m-0 mb-4 text-base font-bold text-slate-950 dark:text-slate-50">
              User Instruction
            </h2>
            <MarkdownArticle :content="selectedRun.instruction_source_snapshot" />
          </section>
          <section class="border-t border-slate-200 pt-8 dark:border-slate-700">
            <h2 class="m-0 mb-4 text-base font-bold text-slate-950 dark:text-slate-50">Result</h2>
            <MarkdownArticle :content="runOutcome(selectedRun)" />
          </section>
        </div>

        <footer
          class="flex flex-wrap justify-between gap-3 border-t border-slate-200 pt-6 dark:border-slate-700"
        >
          <UiButton :disabled="!previousRunId" @click="openRun(previousRunId)">
            Previous Run
          </UiButton>
          <UiButton :disabled="!nextRunId" @click="openRun(nextRunId)"> Next Run </UiButton>
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
[data-hidden='true'] {
  transform: translateY(-100%);
}

.reader-font-sm {
  font-size: 1rem;
  --reader-line-height: 1.7;
}
.reader-font-md {
  font-size: 1.125rem;
  --reader-line-height: 1.75;
}
.reader-font-lg {
  font-size: 1.25rem;
  --reader-line-height: 1.85;
}
.reader-font-xl {
  font-size: 1.375rem;
  --reader-line-height: 1.9;
}
</style>
