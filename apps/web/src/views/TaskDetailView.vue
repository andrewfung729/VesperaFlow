<script setup lang="ts">
import { ref, watch } from 'vue'

import { cancelTask, getTaskDetail, rescheduleTask, type TaskDetail } from '@/api'
import { formatDateTime, isFutureLocal, toDateTimeLocal, toIsoWithOffset } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'

const props = defineProps<{
  taskId: string
}>()

const selectedDetail = ref<TaskDetail | null>(null)
const isLoadingDetail = ref(false)
const errorMessage = ref<string | null>(null)
const rescheduleAt = ref('')

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

async function submitCancel() {
  if (!selectedDetail.value?.schedule) return
  const confirmed = window.confirm(`Cancel "${selectedDetail.value.task.title}"?`)
  if (!confirmed) return
  try {
    await cancelTask(props.taskId, selectedDetail.value.schedule.version)
    await loadTaskDetail()
  } catch (error) {
    errorMessage.value = readableError(error)
  }
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
      <div v-if="selectedDetail" class="grid gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
        <div>
          <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">Task Detail</p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">
            {{ selectedDetail.task.title }}
          </h2>
          <p class="m-0 text-sm text-slate-500">
            {{ selectedDetail.task.task_status }} ·
            {{ selectedDetail.latest_run?.run_status ?? 'planned' }}
          </p>
          <p class="m-0 text-sm text-slate-500">Executor: {{ selectedDetail.task.executor }}</p>
          <p class="m-0 text-sm text-slate-500">
            Target: {{ selectedDetail.task.target_working_directory ?? 'none' }}
          </p>
          <pre
            class="mt-6 mb-0 whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-900 [overflow-wrap:anywhere]"
          >{{ selectedDetail.task.instruction_source }}</pre>
        </div>
        <aside
          class="grid content-start gap-4 border-t border-slate-200 pt-5 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-6"
        >
          <dl class="m-0 grid gap-1.5">
            <dt class="text-sm font-bold text-slate-500">Planned</dt>
            <dd class="m-0 mb-2.5 break-words">
              {{ formatDateTime(selectedDetail.schedule?.planned_at ?? null) }}
            </dd>
            <dt class="text-sm font-bold text-slate-500">Schedule</dt>
            <dd class="m-0 mb-2.5 break-words">
              {{ selectedDetail.schedule?.schedule_status ?? 'none' }}
            </dd>
            <dt class="text-sm font-bold text-slate-500">Latest Result</dt>
            <dd class="m-0 mb-2.5 break-words">
              {{
                selectedDetail.latest_run?.result_summary ??
                selectedDetail.latest_run?.failure_reason ??
                'Pending'
              }}
            </dd>
          </dl>
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
          <button
            class="min-h-10 cursor-pointer rounded-md border border-red-300 bg-red-50 px-4 font-semibold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="!selectedDetail.schedule"
            @click="submitCancel"
          >
            Cancel Task
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
