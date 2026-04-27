<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  cancelOccurrence,
  getCalendar,
  updateOccurrence,
  type CalendarItem,
} from '@/api'
import { formatDateTime, toDateTimeLocal, toIsoWithOffset } from '@/lib/dateTime'
import { readableError } from '@/lib/errors'

const router = useRouter()

const fromLocal = ref(toDateTimeLocal(new Date().toISOString()))
const toLocal = ref(toDateTimeLocal(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()))
const includeCompleted = ref(false)
const items = ref<CalendarItem[]>([])
const total = ref(0)
const isLoading = ref(false)
const actionItemId = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const editingItem = ref<CalendarItem | null>(null)
const editScope = ref<'this_occurrence_only' | 'this_and_future'>('this_occurrence_only')
const occurrencePlannedAt = ref('')
const occurrenceInstruction = ref('')

const overlapCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const item of items.value) {
    counts.set(item.occurrence_at, (counts.get(item.occurrence_at) ?? 0) + 1)
  }
  return counts
})

onMounted(() => {
  void refreshCalendar()
})

async function refreshCalendar() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const response = await getCalendar({
      from: toIsoWithOffset(fromLocal.value),
      to: toIsoWithOffset(toLocal.value),
      include_completed: includeCompleted.value,
      limit: 500,
    })
    items.value = response.data
    total.value = response.meta.total
  } catch (error) {
    items.value = []
    total.value = 0
    errorMessage.value = readableError(error)
  } finally {
    isLoading.value = false
  }
}

async function openTask(item: CalendarItem) {
  const query =
    item.execution_mode === 'recurring'
      ? { occurrenceAt: item.original_occurrence_at ?? item.occurrence_at }
      : undefined
  await router.push({ name: 'task-detail', params: { taskId: item.task_id }, query })
}

function startEdit(item: CalendarItem) {
  editingItem.value = item
  editScope.value = 'this_occurrence_only'
  occurrencePlannedAt.value = toDateTimeLocal(item.occurrence_at)
  occurrenceInstruction.value = ''
}

async function submitOccurrenceEdit() {
  if (!editingItem.value) return
  const item = editingItem.value
  actionItemId.value = item.calendar_item_id
  errorMessage.value = null
  try {
    await updateOccurrence(item.task_id, {
      version: item.schedule_version,
      original_occurrence_at: item.original_occurrence_at ?? item.occurrence_at,
      scope: editScope.value,
      planned_at:
        editScope.value === 'this_occurrence_only'
          ? toIsoWithOffset(occurrencePlannedAt.value)
          : null,
      instruction_source: occurrenceInstruction.value.trim() || null,
    })
    editingItem.value = null
    await refreshCalendar()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    actionItemId.value = null
  }
}

async function skipOccurrence(item: CalendarItem) {
  const confirmed = window.confirm(`Skip "${item.title}" at ${formatDateTime(item.occurrence_at)}?`)
  if (!confirmed) return
  actionItemId.value = item.calendar_item_id
  errorMessage.value = null
  try {
    await cancelOccurrence(
      item.task_id,
      item.schedule_version,
      item.original_occurrence_at ?? item.occurrence_at,
    )
    await refreshCalendar()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    actionItemId.value = null
  }
}

function overlapLabel(item: CalendarItem): string {
  const count = overlapCounts.value.get(item.occurrence_at) ?? 0
  return count > 1 ? `${count} overlapping` : 'No overlap'
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
          <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 uppercase">Calendar</p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950">Agenda</h2>
          <p class="m-0 text-sm text-slate-500">{{ total }} planned items</p>
        </div>
        <form class="flex flex-wrap items-end gap-3" @submit.prevent="refreshCalendar">
          <label class="grid gap-1 text-sm font-semibold text-slate-700">
            <span>From</span>
            <input
              v-model="fromLocal"
              class="min-h-10 rounded-md border border-slate-300 bg-white px-3 text-slate-950 shadow-xs outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              type="datetime-local"
            />
          </label>
          <label class="grid gap-1 text-sm font-semibold text-slate-700">
            <span>To</span>
            <input
              v-model="toLocal"
              class="min-h-10 rounded-md border border-slate-300 bg-white px-3 text-slate-950 shadow-xs outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              type="datetime-local"
            />
          </label>
          <label class="flex min-h-10 items-center gap-2 text-sm font-semibold text-slate-700">
            <input v-model="includeCompleted" type="checkbox" />
            <span>Completed</span>
          </label>
          <button
            class="min-h-10 cursor-pointer rounded-md border border-slate-300 bg-white px-4 font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="isLoading"
            type="submit"
          >
            Refresh
          </button>
        </form>
      </div>

      <form
        v-if="editingItem"
        class="mb-6 grid gap-4 rounded-md border border-slate-200 bg-white p-4"
        @submit.prevent="submitOccurrenceEdit"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 class="m-0 text-lg font-bold text-slate-950">Edit Recurring Task</h3>
            <p class="m-0 text-sm text-slate-500">
              {{ editingItem.title }} · {{ formatDateTime(editingItem.occurrence_at) }}
            </p>
          </div>
          <button
            class="min-h-9 rounded-md border border-slate-300 bg-white px-3 font-semibold text-slate-700 transition hover:bg-slate-50"
            type="button"
            @click="editingItem = null"
          >
            Cancel
          </button>
        </div>
        <fieldset class="m-0 grid gap-2 border-0 p-0">
          <legend class="font-semibold text-slate-700">Scope</legend>
          <div class="flex flex-wrap gap-2">
            <button
              class="min-h-9 rounded-md border px-3 text-sm font-semibold transition"
              :class="
                editScope === 'this_occurrence_only'
                  ? 'border-teal-700 bg-teal-50 text-teal-800'
                  : 'border-slate-300 bg-white text-slate-700 hover:border-teal-700'
              "
              type="button"
              @click="editScope = 'this_occurrence_only'"
            >
              Only This Occurrence
            </button>
            <button
              class="min-h-9 rounded-md border px-3 text-sm font-semibold transition"
              :class="
                editScope === 'this_and_future'
                  ? 'border-teal-700 bg-teal-50 text-teal-800'
                  : 'border-slate-300 bg-white text-slate-700 hover:border-teal-700'
              "
              type="button"
              @click="editScope = 'this_and_future'"
            >
              This And Future
            </button>
          </div>
        </fieldset>
        <label
          v-if="editScope === 'this_occurrence_only'"
          class="grid gap-2 font-semibold text-slate-700"
        >
          <span>Occurrence Time</span>
          <input
            v-model="occurrencePlannedAt"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            type="datetime-local"
          />
        </label>
        <label class="grid gap-2 font-semibold text-slate-700">
          <span>Instructions</span>
          <textarea
            v-model="occurrenceInstruction"
            class="min-h-24 w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
          />
        </label>
        <button
          class="min-h-10 cursor-pointer rounded-md border border-transparent bg-teal-700 px-4 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
          :disabled="actionItemId === editingItem.calendar_item_id"
          type="submit"
        >
          Save
        </button>
      </form>

      <div v-if="isLoading" class="rounded-md border border-slate-200 bg-white p-7 text-slate-600">
        Loading calendar items...
      </div>
      <div v-else-if="items.length === 0" class="rounded-md border border-slate-200 bg-white p-7">
        <h3 class="m-0 text-lg font-bold text-slate-950">No planned work in this window</h3>
      </div>
      <div v-else class="overflow-x-auto rounded-md border border-slate-200 bg-white">
        <table class="w-full min-w-[860px] border-collapse text-left text-sm">
          <thead class="bg-slate-50 text-xs font-bold tracking-wide text-slate-500 uppercase">
            <tr>
              <th class="px-4 py-3">Time</th>
              <th class="px-4 py-3">Task</th>
              <th class="px-4 py-3">Mode</th>
              <th class="px-4 py-3">Overlap</th>
              <th class="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.calendar_item_id" class="border-t border-slate-200">
              <td class="px-4 py-3 text-slate-700">{{ formatDateTime(item.occurrence_at) }}</td>
              <td class="px-4 py-3">
                <button
                  class="cursor-pointer border-0 bg-transparent p-0 text-left font-bold text-teal-700 [overflow-wrap:anywhere] hover:text-teal-900"
                  @click="openTask(item)"
                >
                  {{ item.title }}
                </button>
                <span
                  v-if="item.is_occurrence_override"
                  class="ml-2 inline-flex rounded-md bg-amber-50 px-2 py-1 text-xs font-bold text-amber-800"
                >
                  Override
                </span>
              </td>
              <td class="px-4 py-3 text-slate-600">{{ item.execution_mode }}</td>
              <td class="px-4 py-3 text-slate-600">{{ overlapLabel(item) }}</td>
              <td class="px-4 py-3">
                <div class="flex justify-end gap-2">
                  <button
                    class="min-h-9 rounded-md border border-slate-300 bg-white px-3 font-semibold text-slate-700 transition hover:border-teal-700 hover:text-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                    type="button"
                    @click="openTask(item)"
                  >
                    Detail
                  </button>
                  <button
                    v-if="item.execution_mode === 'recurring'"
                    class="min-h-9 rounded-md border border-slate-300 bg-white px-3 font-semibold text-slate-700 transition hover:border-teal-700 hover:text-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
                    :disabled="actionItemId === item.calendar_item_id"
                    type="button"
                    @click="startEdit(item)"
                  >
                    Edit
                  </button>
                  <button
                    v-if="item.execution_mode === 'recurring'"
                    class="min-h-9 rounded-md border border-red-300 bg-red-50 px-3 font-semibold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-55"
                    :disabled="actionItemId === item.calendar_item_id"
                    type="button"
                    @click="skipOccurrence(item)"
                  >
                    Skip
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
