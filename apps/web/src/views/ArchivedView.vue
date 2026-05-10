<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listTasks, type Task } from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import PageStatePanel from '@/components/PageStatePanel.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import UiButton from '@/components/UiButton.vue'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'
import { executionModeLabel } from '@/lib/executionModeDisplay'

const router = useRouter()

const tasks = ref<Task[]>([])
const total = ref(0)
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const currentPage = ref(1)
const pageSize = 20

onMounted(() => {
  void refresh()
})

async function refresh() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const response = await listTasks({
      include_archived: true,
      status: 'archived',
      limit: pageSize,
      offset: (currentPage.value - 1) * pageSize,
    })
    tasks.value = response.data
    total.value = response.meta.total
  } catch (error) {
    tasks.value = []
    total.value = 0
    errorMessage.value = readableError(error)
  } finally {
    isLoading.value = false
  }
}

async function openTask(taskId: string) {
  await router.push({ name: 'task-detail', params: { taskId } })
}
</script>

<template>
  <div>
    <ErrorAlert :message="errorMessage" />

    <section class="max-w-7xl">
      <div class="mb-6 flex items-center justify-between gap-4">
        <div>
          <p
            class="mb-2 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase"
          >
            Archive
          </p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
            Archived Tasks
          </h2>
        </div>
        <UiButton :disabled="isLoading" @click="refresh"> Refresh </UiButton>
      </div>

      <PageStatePanel
        v-if="isLoading && tasks.length === 0"
        spacious
        title="Loading archived tasks..."
      />
      <PageStatePanel
        v-else-if="!isLoading && tasks.length === 0"
        spacious
        title="No archived tasks yet."
      />

      <div v-if="tasks.length > 0" class="grid gap-3">
        <div
          v-for="task in tasks"
          :key="task.task_id"
          class="cursor-pointer rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 transition hover:border-teal-300 dark:hover:border-teal-700"
          @click="openTask(task.task_id)"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="m-0 text-base font-bold text-slate-950 dark:text-slate-50">
                {{ task.title }}
              </h3>
              <p class="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">
                {{ executionModeLabel(task.execution_mode) }} · Archived at
                {{ formatDateTime(task.archived_at) }}
              </p>
            </div>
            <span
              class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium"
              :class="
                task.task_status === 'archived'
                  ? 'border-slate-200 bg-slate-100 text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
                  : 'border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400'
              "
            >
              {{ task.task_status }}
            </span>
          </div>
        </div>
      </div>

      <PaginationControls
        v-if="total > pageSize"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        @update:current-page="refresh"
      />
    </section>
  </div>
</template>
