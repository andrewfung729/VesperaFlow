<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { createTask, type ExecutorName } from '@/api'
import { defaultDateTimeLocal, isFutureLocal, toIsoWithOffset } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'

const router = useRouter()
const executorOptions: Array<{ label: string; value: ExecutorName }> = [
  { label: 'Debug Printer', value: 'debug_printer' },
  { label: 'Claude Code', value: 'claude_code' },
]

const title = ref('')
const instructions = ref('')
const executor = ref<ExecutorName>('debug_printer')
const plannedAt = ref(defaultDateTimeLocal())
const isSaving = ref(false)
const errorMessage = ref<string | null>(null)

const timezoneLabel = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local time'
const canSave = computed(
  () =>
    title.value.trim().length > 0 &&
    instructions.value.trim().length > 0 &&
    isFutureLocal(plannedAt.value),
)

async function submitTask() {
  if (!canSave.value) {
    errorMessage.value = 'Add a title, instructions, and a future execution time.'
    return
  }
  isSaving.value = true
  errorMessage.value = null
  try {
    const created = await createTask({
      title: title.value.trim(),
      instruction_source: instructions.value.trim(),
      executor: executor.value,
      planned_at: toIsoWithOffset(plannedAt.value),
    })
    title.value = ''
    instructions.value = ''
    plannedAt.value = defaultDateTimeLocal()
    await router.push({ name: 'task-detail', params: { taskId: created.task.task_id } })
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isSaving.value = false
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

    <section class="max-w-3xl">
      <div class="mb-6">
        <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">Composer</p>
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">
          Create One-Time Task
        </h2>
      </div>
      <form class="grid gap-5" @submit.prevent="submitTask">
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Title</span>
          <input
            v-model="title"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            type="text"
            placeholder="Nightly Deep Research"
          />
        </label>
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Instructions</span>
          <textarea
            v-model="instructions"
            class="w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            rows="9"
            placeholder="Describe the AI work to run later..."
          />
        </label>
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Execution Time</span>
          <input
            v-model="plannedAt"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            type="datetime-local"
          />
        </label>
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Executor</span>
          <select
            v-model="executor"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
          >
            <option v-for="option in executorOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <p class="m-0 text-sm text-slate-500">Timezone: {{ timezoneLabel }}</p>
        <button
          class="min-h-10 w-fit cursor-pointer rounded-md border border-transparent bg-teal-700 px-5 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
          type="submit"
          :disabled="!canSave || isSaving"
        >
          {{ isSaving ? 'Saving...' : 'Save Task' }}
        </button>
      </form>
    </section>
  </div>
</template>
