import { computed, ref } from 'vue'

import { pauseRecurringTask, resumeRecurringTask, runTaskNow } from '@/api'
import { readableError } from '@/lib/errors'

type ErrorSetter = (message: string | null) => void

export function useRecurringTaskActions(refresh: () => Promise<void>, setError: ErrorSetter) {
  const actionTaskId = ref<string | null>(null)
  const isActionPending = computed(() => actionTaskId.value !== null)

  async function pauseTask(taskId: string, scheduleVersion: number) {
    await runScheduleAction(taskId, () => pauseRecurringTask(taskId, scheduleVersion))
  }

  async function resumeTask(taskId: string, scheduleVersion: number) {
    await runScheduleAction(taskId, () => resumeRecurringTask(taskId, scheduleVersion))
  }

  async function runNowTask(taskId: string, title: string) {
    const confirmed = window.confirm(`Run "${title}" immediately?`)
    if (!confirmed) return
    await runScheduleAction(taskId, () => runTaskNow(taskId))
  }

  async function runScheduleAction(taskId: string, action: () => Promise<unknown>) {
    actionTaskId.value = taskId
    setError(null)
    try {
      await action()
      await refresh()
    } catch (error) {
      setError(readableError(error))
    } finally {
      actionTaskId.value = null
    }
  }

  return {
    actionTaskId,
    isActionPending,
    pauseTask,
    resumeTask,
    runNowTask,
  }
}
