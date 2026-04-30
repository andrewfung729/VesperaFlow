<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getRecurringTodo, type RecurringTodoItem } from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import PageStatePanel from '@/components/PageStatePanel.vue'
import RunStatusBadge from '@/components/RunStatusBadge.vue'
import UiButton from '@/components/UiButton.vue'
import { useRecurringTaskActions } from '@/composables/useRecurringTaskActions'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { recurrenceSummary as summarizeRecurrence } from '@/lib/recurrence'
import { runOutcomeSummary } from '@/lib/runDisplay'

const router = useRouter()

const items = ref<RecurringTodoItem[]>([])
const total = ref(0)
const isLoadingTodo = ref(false)
const errorMessage = ref<string | null>(null)

const scheduledItems = computed(() =>
  items.value.filter((item) => item.schedule_status === 'active'),
)
const pausedItems = computed(() => items.value.filter((item) => item.schedule_status === 'paused'))

const { actionTaskId, pauseTask, resumeTask, runNowTask } = useRecurringTaskActions(
  refreshTodo,
  (message) => {
    errorMessage.value = message
  },
)

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

async function viewRuns(item: RecurringTodoItem) {
  await router.push({
    name: 'recurring-run-archive',
    params: { taskId: item.task_id },
  })
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
  await pauseTask(item.task_id, item.schedule_version)
}

async function resumeItem(item: RecurringTodoItem) {
  await resumeTask(item.task_id, item.schedule_version)
}

async function runNowItem(item: RecurringTodoItem) {
  await runNowTask(item.task_id, item.title)
}

function recurrenceSummary(item: RecurringTodoItem): string {
  return summarizeRecurrence(item.recurrence_rule, item.recurrence_timezone)
}

function latestOutcome(item: RecurringTodoItem): string {
  return runOutcomeSummary(item, 'No runs yet')
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
            Recurring Todo
          </p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
            Recurring Tasks
          </h2>
          <p class="m-0 text-sm text-slate-500 dark:text-slate-400">{{ total }} ongoing tasks</p>
        </div>
        <UiButton :disabled="isLoadingTodo" @click="refreshTodo"> Refresh </UiButton>
      </div>

      <PageStatePanel v-if="isLoadingTodo" spacious title="Loading recurring tasks..." />
      <PageStatePanel v-else-if="items.length === 0" spacious title="No recurring tasks yet">
        <UiButton class="mt-4" variant="primary" @click="createRecurringTask">
          Create Recurring Task
        </UiButton>
      </PageStatePanel>
      <div v-else class="grid gap-7">
        <section v-if="scheduledItems.length > 0">
          <h3 class="m-0 mb-3 text-lg font-bold text-slate-950 dark:text-slate-50">Scheduled</h3>
          <div
            class="overflow-x-auto rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
          >
            <table class="w-full min-w-[820px] border-collapse text-left text-sm">
              <thead
                class="bg-slate-50 dark:bg-slate-800/50 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400 uppercase"
              >
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
                  class="border-t border-slate-200 dark:border-slate-700"
                >
                  <td class="px-4 py-3">
                    <button
                      class="cursor-pointer border-0 bg-transparent p-0 text-left font-bold text-teal-700 dark:text-teal-400 wrap-anywhere hover:text-teal-900 dark:hover:text-teal-300"
                      @click="openTask(item)"
                    >
                      {{ item.title }}
                    </button>
                  </td>
                  <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                    {{ recurrenceSummary(item) }}
                  </td>
                  <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                    {{ formatDateTime(item.next_run_at) }}
                  </td>
                  <td class="px-4 py-3 max-w-xs text-slate-600 dark:text-slate-400">
                    <RunStatusBadge
                      v-if="item.latest_run_outcome"
                      class="mb-1"
                      :status="item.latest_run_outcome"
                    />
                    <div class="line-clamp-2 wrap-anywhere">
                      {{ latestOutcome(item) }}
                    </div>
                  </td>
                  <td class="px-4 py-3">
                    <div class="flex justify-end gap-2">
                      <UiButton
                        size="sm"
                        :disabled="actionTaskId === item.task_id"
                        @click="viewRuns(item)"
                      >
                        View Runs
                      </UiButton>
                      <UiButton
                        size="sm"
                        :disabled="actionTaskId === item.task_id"
                        @click="runNowItem(item)"
                      >
                        Run Now
                      </UiButton>
                      <UiButton
                        size="sm"
                        :disabled="actionTaskId === item.task_id"
                        @click="editRecurrence(item)"
                      >
                        Edit
                      </UiButton>
                      <UiButton
                        size="sm"
                        :disabled="actionTaskId === item.task_id"
                        @click="pauseItem(item)"
                      >
                        Pause
                      </UiButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="pausedItems.length > 0">
          <h3 class="m-0 mb-3 text-lg font-bold text-slate-950 dark:text-slate-50">Paused</h3>
          <div
            class="overflow-x-auto rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
          >
            <table class="w-full min-w-[760px] border-collapse text-left text-sm">
              <thead
                class="bg-slate-50 dark:bg-slate-800/50 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400 uppercase"
              >
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
                  class="border-t border-slate-200 dark:border-slate-700"
                >
                  <td class="px-4 py-3">
                    <button
                      class="cursor-pointer border-0 bg-transparent p-0 text-left font-bold text-teal-700 dark:text-teal-400 wrap-anywhere hover:text-teal-900 dark:hover:text-teal-300"
                      @click="openTask(item)"
                    >
                      {{ item.title }}
                    </button>
                  </td>
                  <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                    {{ recurrenceSummary(item) }}
                  </td>
                  <td class="px-4 py-3 max-w-xs text-slate-600 dark:text-slate-400">
                    <RunStatusBadge
                      v-if="item.latest_run_outcome"
                      class="mb-1"
                      :status="item.latest_run_outcome"
                    />
                    <div class="line-clamp-2 wrap-anywhere">
                      {{ latestOutcome(item) }}
                    </div>
                  </td>
                  <td class="px-4 py-3">
                    <div class="flex justify-end gap-2">
                      <UiButton
                        size="sm"
                        :disabled="actionTaskId === item.task_id"
                        @click="viewRuns(item)"
                      >
                        View Runs
                      </UiButton>
                      <UiButton
                        size="sm"
                        :disabled="actionTaskId === item.task_id"
                        @click="editRecurrence(item)"
                      >
                        Edit
                      </UiButton>
                      <UiButton
                        size="sm"
                        :disabled="actionTaskId === item.task_id"
                        @click="resumeItem(item)"
                      >
                        Resume
                      </UiButton>
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
