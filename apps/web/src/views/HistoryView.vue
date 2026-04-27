<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getHistory, type ExecutionMode, type HistoryItem } from '@/api'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'

const router = useRouter()

const items = ref<HistoryItem[]>([])
const total = ref(0)
const isLoadingHistory = ref(false)
const errorMessage = ref<string | null>(null)
const statusFilter = ref<HistoryItem['run_status'] | ''>('')
const modeFilter = ref<ExecutionMode | ''>('')

onMounted(() => {
  void refreshHistory()
})

async function refreshHistory() {
  isLoadingHistory.value = true
  errorMessage.value = null
  try {
    const response = await getHistory({
      status: statusFilter.value,
      execution_mode: modeFilter.value,
      limit: 50,
    })
    items.value = response.data
    total.value = response.meta.total
  } catch (error) {
    items.value = []
    total.value = 0
    errorMessage.value = readableError(error)
  } finally {
    isLoadingHistory.value = false
  }
}

async function openHistoryItem(item: HistoryItem) {
  await router.push({
    name: 'task-detail',
    params: { taskId: item.task_id },
    query: { runId: item.run_id },
  })
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
          <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">History</p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">Run History</h2>
          <p class="m-0 text-sm text-slate-500">{{ total }} terminal runs</p>
        </div>
        <div class="flex flex-wrap items-end gap-3">
          <label class="grid gap-1 text-sm font-semibold text-slate-700">
            <span>Status</span>
            <select
              v-model="statusFilter"
              class="min-h-10 rounded-md border border-slate-300 bg-white px-3 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              @change="refreshHistory"
            >
              <option value="">All</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-semibold text-slate-700">
            <span>Mode</span>
            <select
              v-model="modeFilter"
              class="min-h-10 rounded-md border border-slate-300 bg-white px-3 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              @change="refreshHistory"
            >
              <option value="">All</option>
              <option value="one_time">One-Time</option>
              <option value="recurring">Recurring</option>
            </select>
          </label>
          <button
            class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="isLoadingHistory"
            @click="refreshHistory"
          >
            Refresh
          </button>
        </div>
      </div>

      <div
        v-if="isLoadingHistory"
        class="rounded-md border border-slate-200 bg-white p-7 text-slate-600"
      >
        Loading history...
      </div>
      <div v-else-if="items.length === 0" class="rounded-md border border-slate-200 bg-white p-7">
        <h3 class="m-0 text-lg font-bold text-slate-950">No completed or failed runs</h3>
        <p class="mb-0 text-slate-600">Terminal task runs will appear here.</p>
      </div>
      <div v-else class="overflow-x-auto rounded-md border border-slate-200 bg-white">
        <table class="w-full min-w-[760px] border-collapse text-left">
          <thead class="bg-slate-50 text-xs font-bold tracking-wide text-slate-500 uppercase">
            <tr>
              <th class="px-4 py-3">Task</th>
              <th class="px-4 py-3">Status</th>
              <th class="px-4 py-3">Mode</th>
              <th class="px-4 py-3">Finished</th>
              <th class="px-4 py-3">Outcome</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.history_item_id" class="border-t border-slate-200">
              <td class="px-4 py-3">
                <button
                  class="cursor-pointer border-0 bg-transparent p-0 text-left font-bold text-teal-700 [overflow-wrap:anywhere] hover:text-teal-900"
                  @click="openHistoryItem(item)"
                >
                  {{ item.title }}
                </button>
              </td>
              <td class="px-4 py-3 font-semibold text-slate-700">
                {{ item.run_status }}
              </td>
              <td class="px-4 py-3 text-slate-600">
                {{ item.execution_mode }}
              </td>
              <td class="px-4 py-3 text-slate-600">
                {{ formatDateTime(item.finished_at) }}
              </td>
              <td class="px-4 py-3 max-w-xs text-slate-600">
                <div class="line-clamp-2 wrap-anywhere">
                  {{ item.result_summary ?? item.failure_reason ?? 'No summary' }}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
