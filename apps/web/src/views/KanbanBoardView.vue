<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getKanban, type KanbanBoard } from '@/api'
import { formatDateTime } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'

const columns = ['upcoming', 'running', 'completed', 'failed', 'canceled'] as const
const router = useRouter()

const board = ref<KanbanBoard>({ columns: emptyColumns() })
const isLoadingBoard = ref(false)
const errorMessage = ref<string | null>(null)

onMounted(() => {
  void refreshBoard()
})

async function refreshBoard() {
  isLoadingBoard.value = true
  errorMessage.value = null
  try {
    board.value = await getKanban()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isLoadingBoard.value = false
  }
}

async function openTask(taskId: string) {
  await router.push({ name: 'task-detail', params: { taskId } })
}

function emptyColumns(): KanbanBoard['columns'] {
  return Object.fromEntries(columns.map((column) => [column, []]))
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
      <div class="mb-6 flex items-center justify-between gap-4">
        <div>
          <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">Board</p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">One-Time Tasks</h2>
        </div>
        <button
          class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
          :disabled="isLoadingBoard"
          @click="refreshBoard"
        >
          Refresh
        </button>
      </div>
      <div class="grid grid-cols-[repeat(5,minmax(180px,1fr))] gap-3.5 overflow-x-auto">
        <section
          v-for="column in columns"
          :key="column"
          class="min-h-96 rounded-md border border-slate-200 bg-slate-200/70 p-3"
        >
          <h3 class="m-0 mb-3 text-sm font-bold text-slate-700 capitalize">{{ column }}</h3>
          <button
            v-for="card in board.columns[column] ?? []"
            :key="card.card_id"
            class="mb-2.5 grid min-h-24 w-full cursor-pointer rounded-md border border-slate-200 bg-white p-3 text-left text-slate-950 shadow-xs transition hover:border-teal-300 hover:shadow-sm"
            @click="openTask(card.task_id)"
          >
            <strong class="[overflow-wrap:anywhere]">{{ card.title }}</strong>
            <span class="text-sm text-slate-500 [overflow-wrap:anywhere]">
              {{ formatDateTime(card.next_run_at) }}
            </span>
            <small class="text-slate-500 [overflow-wrap:anywhere]">
              {{ card.latest_run_status ?? 'planned' }}
            </small>
          </button>
          <p v-if="(board.columns[column] ?? []).length === 0" class="text-sm text-slate-500">
            No tasks
          </p>
        </section>
      </div>
    </section>
  </div>
</template>
