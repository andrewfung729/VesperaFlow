<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getHistory, type ExecutionMode, type HistoryItem } from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import ExecutionModeBadge from '@/components/ExecutionModeBadge.vue'
import PageStatePanel from '@/components/PageStatePanel.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import RunStatusBadge from '@/components/RunStatusBadge.vue'
import SelectField from '@/components/SelectField.vue'
import UiButton from '@/components/UiButton.vue'
import { formatDateTime } from '@/lib/dateTime'
import { executionModeOptions } from '@/lib/executionModeDisplay'
import { readableError } from '@/lib/errors'
import { runOutcomeSummary } from '@/lib/runDisplay'

const router = useRouter()

const items = ref<HistoryItem[]>([])
const total = ref(0)
const isLoadingHistory = ref(false)
const errorMessage = ref<string | null>(null)
const statusFilter = ref<HistoryItem['run_status'] | ''>('')
const modeFilter = ref<ExecutionMode | ''>('')
const currentPage = ref(1)
const pageSize = 20
const terminalStatusOptions: Array<{ label: string; value: HistoryItem['run_status'] }> = [
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
]

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
      limit: pageSize,
      offset: (currentPage.value - 1) * pageSize,
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

function resetPageAndRefresh() {
  currentPage.value = 1
  void refreshHistory()
}

async function openHistoryItem(item: HistoryItem) {
  await router.push({
    name: 'run-detail',
    params: { taskId: item.task_id, runId: item.run_id },
  })
}
</script>

<template>
  <div>
    <ErrorAlert :message="errorMessage" />

    <section class="max-w-7xl">
      <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p
            class="mb-2 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase"
          >
            History
          </p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
            Run History
          </h2>
          <p class="m-0 text-sm text-slate-500 dark:text-slate-400">{{ total }} terminal runs</p>
        </div>
        <div class="flex flex-wrap items-end gap-3">
          <SelectField
            v-model="statusFilter"
            compact
            label="Status"
            :options="terminalStatusOptions"
            empty-label="All"
            @change="resetPageAndRefresh"
          />
          <SelectField
            v-model="modeFilter"
            compact
            label="Mode"
            :options="executionModeOptions"
            empty-label="All"
            @change="resetPageAndRefresh"
          />
          <UiButton :disabled="isLoadingHistory" @click="refreshHistory"> Refresh </UiButton>
        </div>
      </div>

      <PageStatePanel v-if="isLoadingHistory" spacious title="Loading history..." />
      <PageStatePanel
        v-else-if="items.length === 0"
        spacious
        title="No completed or failed runs"
        message="Terminal task runs will appear here."
      />
      <div
        v-else
        class="overflow-x-auto rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
      >
        <table class="w-full min-w-[760px] border-collapse text-left">
          <thead
            class="bg-slate-50 dark:bg-slate-800/50 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400 uppercase"
          >
            <tr>
              <th class="px-4 py-3">Task</th>
              <th class="px-4 py-3">Status</th>
              <th class="px-4 py-3">Mode</th>
              <th class="px-4 py-3">Finished</th>
              <th class="px-4 py-3">Result Preview</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in items"
              :key="item.history_item_id"
              class="border-t border-slate-200 dark:border-slate-700"
            >
              <td class="px-4 py-3">
                <button
                  class="cursor-pointer border-0 bg-transparent p-0 text-left font-bold text-teal-700 dark:text-teal-400 wrap-anywhere hover:text-teal-900 dark:hover:text-teal-300"
                  @click="openHistoryItem(item)"
                >
                  {{ item.title }}
                </button>
              </td>
              <td class="px-4 py-3">
                <RunStatusBadge :status="item.run_status" />
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                <ExecutionModeBadge :mode="item.execution_mode" />
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ formatDateTime(item.finished_at) }}
              </td>
              <td class="px-4 py-3 max-w-xs text-slate-600 dark:text-slate-400">
                <div class="line-clamp-2 wrap-anywhere">
                  {{ runOutcomeSummary(item, 'No summary') }}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationControls
        v-if="!isLoadingHistory && items.length > 0"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        @update:current-page="refreshHistory"
      />
    </section>
  </div>
</template>
