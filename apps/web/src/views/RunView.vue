<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getRunDetail, getRunEvents, type RunDetail, type RunEvent } from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import MarkdownReader from '@/components/MarkdownReader.vue'
import PageStatePanel from '@/components/PageStatePanel.vue'
import RunStatusBadge from '@/components/RunStatusBadge.vue'
import RunTimeline from '@/components/RunTimeline.vue'
import UiButton from '@/components/UiButton.vue'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { occurrenceLabel, runDuration, runOutcome } from '@/lib/runDisplay'

const props = defineProps<{
  taskId: string
  runId: string
}>()

const router = useRouter()

const runDetail = ref<RunDetail | null>(null)
const runEvents = ref<RunEvent[]>([])
const isLoading = ref(false)
const isLoadingEvents = ref(false)
const errorMessage = ref<string | null>(null)
const copyStatus = ref<'idle' | 'copied' | 'failed'>('idle')

const selectedRun = computed(() => runDetail.value?.run ?? null)
const isRecurringTask = computed(() => runDetail.value?.task.execution_mode === 'recurring')

watch(
  () => [props.taskId, props.runId],
  () => {
    copyStatus.value = 'idle'
    void loadRun()
  },
  { immediate: true },
)

async function loadRun() {
  if (!props.taskId) return
  isLoading.value = true
  errorMessage.value = null
  try {
    runDetail.value = await getRunDetail(props.taskId, props.runId)
    void loadRunEvents(props.runId)
  } catch (error) {
    runDetail.value = null
    runEvents.value = []
    errorMessage.value = readableError(error)
  } finally {
    isLoading.value = false
  }
}

async function loadRunEvents(runId: string) {
  isLoadingEvents.value = true
  try {
    runEvents.value = (await getRunEvents(runId)).data
  } catch {
    runEvents.value = []
  } finally {
    isLoadingEvents.value = false
  }
}

async function openReader() {
  await router.push({
    name: 'run-reader',
    params: { taskId: props.taskId, runId: props.runId },
  })
}

async function openTaskDetail() {
  await router.push({ name: 'task-detail', params: { taskId: props.taskId } })
}

async function openHistory() {
  await router.push({ name: 'history' })
}

async function openArchive() {
  await router.push({ name: 'recurring-run-archive', params: { taskId: props.taskId } })
}

async function openAdjacentRun(runId: string | null | undefined) {
  if (!runId) return
  await router.push({
    name: 'run-detail',
    params: { taskId: props.taskId, runId },
  })
}

async function copyResult() {
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
    <ErrorAlert :message="errorMessage" />

    <section class="max-w-6xl">
      <article v-if="runDetail && selectedRun" class="grid gap-6">
        <header
          class="rounded-md border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
        >
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p
                class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase dark:text-teal-400"
              >
                Run
              </p>
              <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
                {{ runDetail.task.title }}
              </h2>
              <p class="m-0 mt-1 text-sm font-semibold text-slate-600 dark:text-slate-400">
                {{ occurrenceLabel(selectedRun) }}
              </p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <RunStatusBadge :status="selectedRun.run_status" />
              <UiButton size="sm" @click="openReader"> Open Reader </UiButton>
              <UiButton size="sm" @click="copyResult">
                {{
                  copyStatus === 'copied'
                    ? 'Copied'
                    : copyStatus === 'failed'
                      ? 'Copy Failed'
                      : 'Copy Result'
                }}
              </UiButton>
            </div>
          </div>

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
              <dd class="m-0 text-slate-800 dark:text-slate-200">
                {{ runDuration(selectedRun) }}
              </dd>
            </div>
            <div>
              <dt class="font-bold text-slate-500 dark:text-slate-400">Workflow</dt>
              <dd class="m-0 text-slate-800 wrap-anywhere dark:text-slate-200">
                {{ selectedRun.external_execution_ref ?? 'none' }}
              </dd>
            </div>
          </dl>
        </header>

        <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div class="grid gap-6">
            <section
              class="rounded-md border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
            >
              <h3 class="m-0 mb-3 text-lg font-bold text-slate-950 dark:text-slate-50">
                User Instruction
              </h3>
              <MarkdownReader
                :content="selectedRun.instruction_source_snapshot"
                :expandable="false"
                class="run-content wrap-anywhere"
              />
            </section>

            <section
              class="rounded-md border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
            >
              <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
                <h3 class="m-0 text-lg font-bold text-slate-950 dark:text-slate-50">Result</h3>
                <UiButton size="sm" @click="copyResult">
                  {{
                    copyStatus === 'copied'
                      ? 'Copied'
                      : copyStatus === 'failed'
                        ? 'Copy Failed'
                        : 'Copy Result'
                  }}
                </UiButton>
              </div>
              <MarkdownReader
                :content="runOutcome(selectedRun)"
                :expandable="false"
                class="run-content wrap-anywhere"
              />
            </section>

            <RunTimeline
              class="rounded-md border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
              :events="runEvents"
              :is-loading="isLoadingEvents"
            />
          </div>

          <aside class="grid content-start gap-4">
            <section
              class="rounded-md border border-slate-200 bg-white p-4 text-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <h3 class="m-0 mb-3 text-base font-bold text-slate-950 dark:text-slate-50">
                Context
              </h3>
              <dl class="m-0 grid gap-2">
                <div>
                  <dt class="font-bold text-slate-500 dark:text-slate-400">Executor</dt>
                  <dd class="m-0 text-slate-700 dark:text-slate-300">
                    {{ runDetail.task.executor }}
                  </dd>
                </div>
                <div>
                  <dt class="font-bold text-slate-500 dark:text-slate-400">Profile</dt>
                  <dd class="m-0 text-slate-700 dark:text-slate-300">
                    {{ runDetail.task.executor_profile_id ?? 'default' }}
                  </dd>
                </div>
                <div>
                  <dt class="font-bold text-slate-500 dark:text-slate-400">Target Directory</dt>
                  <dd class="m-0 wrap-anywhere text-slate-700 dark:text-slate-300">
                    {{ runDetail.task.target_working_directory ?? 'none' }}
                  </dd>
                </div>
                <div>
                  <dt class="font-bold text-slate-500 dark:text-slate-400">Run ID</dt>
                  <dd class="m-0 wrap-anywhere text-slate-700 dark:text-slate-300">
                    {{ selectedRun.run_id }}
                  </dd>
                </div>
              </dl>
            </section>

            <section class="grid gap-2">
              <UiButton @click="openTaskDetail"> Task Detail </UiButton>
              <UiButton v-if="isRecurringTask" @click="openArchive"> Run Archive </UiButton>
              <UiButton @click="openHistory"> History </UiButton>
            </section>

            <section class="grid gap-2">
              <UiButton
                :disabled="!runDetail.previous_run_id"
                @click="openAdjacentRun(runDetail.previous_run_id)"
              >
                Previous Run
              </UiButton>
              <UiButton
                :disabled="!runDetail.next_run_id"
                @click="openAdjacentRun(runDetail.next_run_id)"
              >
                Next Run
              </UiButton>
            </section>
          </aside>
        </div>
      </article>

      <PageStatePanel
        v-else
        spacious
        :title="isLoading ? 'Loading run...' : 'Run unavailable'"
        :message="isLoading ? 'Loading the selected run.' : 'This run could not be loaded.'"
      />
    </section>
  </div>
</template>

<style scoped>
.run-content :deep(.markdown-body) {
  line-height: 1.7;
}
</style>
