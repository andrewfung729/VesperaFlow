<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  getRecurringTodo,
  pauseRecurringTask,
  resumeRecurringTask,
  runTaskNow,
  type RecurringTodoItem,
} from '@/api'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { recurrenceSummary as summarizeRecurrence } from '@/lib/recurrence'

const router = useRouter()

const items = ref<RecurringTodoItem[]>([])
const total = ref(0)
const isLoadingTodo = ref(false)
const actionTaskId = ref<string | null>(null)
const errorMessage = ref<string | null>(null)

const scheduledItems = computed(() =>
  items.value.filter((item) => item.schedule_status === 'active'),
)
const pausedItems = computed(() => items.value.filter((item) => item.schedule_status === 'paused'))

onMounted(() => {
  void refreshTodo()
})

async function refreshTodo() {
  isLoadingTodo.value = true
  errorMessage.value = null
  try {
    const response = await getRecurringTodo({ limit: 100 })
    items.value = response.data
    total.value = response.meta.total
  } catch (error) {
    items.value = []
    total.value = 0
    errorMessage.value = readableError(error)
  } finally {
    isLoadingTodo.value = false
  }
}

async function openTask(item: RecurringTodoItem) {
  await router.push({ name: 'task-detail', params: { taskId: item.task_id } })
}

async function createRecurringTask() {
  await router.push({ name: 'compose', query: { mode: 'recurring' } })
}

async function editRecurrence(item: RecurringTodoItem) {
  await router.push({
    name: 'task-detail',
    params: { taskId: item.task_id },
    query: { edit: 'recurrence' },
  })
}

async function pauseItem(item: RecurringTodoItem) {
  actionTaskId.value = item.task_id
  errorMessage.value = null
  try {
    await pauseRecurringTask(item.task_id, item.schedule_version)
    await refreshTodo()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    actionTaskId.value = null
  }
}

async function resumeItem(item: RecurringTodoItem) {
  actionTaskId.value = item.task_id
  errorMessage.value = null
  try {
    await resumeRecurringTask(item.task_id, item.schedule_version)
    await refreshTodo()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    actionTaskId.value = null
  }
}

async function runNowItem(item: RecurringTodoItem) {
  actionTaskId.value = item.task_id
  errorMessage.value = null
  try {
    const confirmed = window.confirm(`Run "${item.title}" immediately?`)
    if (!confirmed) return
    await runTaskNow(item.task_id)
    await refreshTodo()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    actionTaskId.value = null
  }
}

function recurrenceSummary(item: RecurringTodoItem): string {
  return summarizeRecurrence(item.recurrence_rule, item.recurrence_timezone)
}

function latestOutcome(item: RecurringTodoItem): string {
  if (!item.latest_run_outcome) return 'No runs yet'
  return item.result_summary ?? item.failure_reason ?? item.latest_run_outcome
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
      <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">Recurring Todo</p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">Recurring Tasks</h2>
          <p class="m-0 text-sm text-slate-500">{{ total }} ongoing tasks</p>
        </div>
        <button
          class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
          :disabled="isLoadingTodo"
          @click="refreshTodo"
        >
          Refresh
        </button>
      </div>

      <div
        v-if="isLoadingTodo"
        class="rounded-md border border-slate-200 bg-white p-7 text-slate-600"
      >
        Loading recurring tasks...
      </div>
      <div v-else-if="items.length === 0" class="rounded-md border border-slate-200 bg-white p-7">
        <h3 class="m-0 text-lg font-bold text-slate-950">No recurring tasks yet</h3>
        <button
          class="mt-4 min-h-10 cursor-pointer rounded-md border border-transparent bg-teal-700 px-4 font-semibold text-white transition hover:bg-teal-800"
          type="button"
          @click="createRecurringTask"
        >
          Create Recurring Task
        </button>
      </div>
      <div v-else class="grid gap-7">
        <section v-if="scheduledItems.length > 0">
          <h3 class="m-0 mb-3 text-lg font-bold text-slate-950">Scheduled</h3>
          <div class="overflow-x-auto rounded-md border border-slate-200 bg-white">
            <table class="w-full min-w-[820px] border-collapse text-left text-sm">
              <thead class="bg-slate-50 text-xs font-bold tracking-wide text-slate-500 uppercase">
                <tr>
                  <th class="px-4 py-3">Task</th>
                  <th class="px-4 py-3">Recurrence</th>
                  <th class="px-4 py-3">Next Run</th>
                  <th class="px-4 py-3">Latest Outcome</th>
                  <th class="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in scheduledItems"
                  :key="item.item_id"
                  class="border-t border-slate-200"
                >
                  <td class="px-4 py-3">
                    <button
                      class="cursor-pointer border-0 bg-transparent p-0 text-left font-bold text-teal-700 [overflow-wrap:anywhere] hover:text-teal-900"
                      @click="openTask(item)"
                    >
                      {{ item.title }}
                    </button>
                  </td>
                  <td class="px-4 py-3 text-slate-600">{{ recurrenceSummary(item) }}</td>
                  <td class="px-4 py-3 text-slate-600">{{ formatDateTime(item.next_run_at) }}</td>
                  <td class="px-4 py-3 text-slate-600">
                    <span
                      v-if="item.latest_run_outcome === 'failed'"
                      class="inline-flex rounded-md bg-red-50 px-2 py-1 font-semibold text-red-700"
                    >
                      Failed
                    </span>
                    <span class="[overflow-wrap:anywhere]">{{ latestOutcome(item) }}</span>
                  </td>
                  <td class="px-4 py-3">
                    <div class="flex justify-end gap-2">
                      <button
                        class="min-h-9 rounded-md border border-slate-300 bg-white px-3 font-semibold text-slate-700 transition hover:border-teal-700 hover:text-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                        type="button"
                        :disabled="actionTaskId === item.task_id"
                        @click="runNowItem(item)"
                      >
                        Run Now
                      </button>
                      <button
                        class="min-h-9 rounded-md border border-slate-300 bg-white px-3 font-semibold text-slate-700 transition hover:border-teal-700 hover:text-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                        type="button"
                        :disabled="actionTaskId === item.task_id"
                        @click="editRecurrence(item)"
                      >
                        Edit
                      </button>
                      <button
                        class="min-h-9 rounded-md border border-slate-300 bg-white px-3 font-semibold text-slate-700 transition hover:border-teal-700 hover:text-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                        type="button"
                        :disabled="actionTaskId === item.task_id"
                        @click="pauseItem(item)"
                      >
                        Pause
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="pausedItems.length > 0">
          <h3 class="m-0 mb-3 text-lg font-bold text-slate-950">Paused</h3>
          <div class="overflow-x-auto rounded-md border border-slate-200 bg-white">
            <table class="w-full min-w-[760px] border-collapse text-left text-sm">
              <thead class="bg-slate-50 text-xs font-bold tracking-wide text-slate-500 uppercase">
                <tr>
                  <th class="px-4 py-3">Task</th>
                  <th class="px-4 py-3">Recurrence</th>
                  <th class="px-4 py-3">Latest Outcome</th>
                  <th class="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in pausedItems"
                  :key="item.item_id"
                  class="border-t border-slate-200"
                >
                  <td class="px-4 py-3">
                    <button
                      class="cursor-pointer border-0 bg-transparent p-0 text-left font-bold text-teal-700 [overflow-wrap:anywhere] hover:text-teal-900"
                      @click="openTask(item)"
                    >
                      {{ item.title }}
                    </button>
                  </td>
                  <td class="px-4 py-3 text-slate-600">{{ recurrenceSummary(item) }}</td>
                  <td class="px-4 py-3 text-slate-600 [overflow-wrap:anywhere]">
                    {{ latestOutcome(item) }}
                  </td>
                  <td class="px-4 py-3">
                    <div class="flex justify-end gap-2">
                      <button
                        class="min-h-9 rounded-md border border-slate-300 bg-white px-3 font-semibold text-slate-700 transition hover:border-teal-700 hover:text-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                        type="button"
                        :disabled="actionTaskId === item.task_id"
                        @click="editRecurrence(item)"
                      >
                        Edit
                      </button>
                      <button
                        class="min-h-9 rounded-md border border-slate-300 bg-white px-3 font-semibold text-slate-700 transition hover:border-teal-700 hover:text-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                        type="button"
                        :disabled="actionTaskId === item.task_id"
                        @click="resumeItem(item)"
                      >
                        Resume
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </section>
  </div>
</template>
