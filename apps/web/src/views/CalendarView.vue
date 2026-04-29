<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  cancelOccurrence,
  createTask,
  getCalendar,
  updateOccurrence,
  type CalendarItem,
  type ExecutorName,
} from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import PageStatePanel from '@/components/PageStatePanel.vue'
import SelectField from '@/components/SelectField.vue'
import TextArea from '@/components/TextArea.vue'
import TextInput from '@/components/TextInput.vue'
import UiButton from '@/components/UiButton.vue'
import {
  defaultDateTimeLocal,
  formatDateTime,
  isFutureLocal,
  toDateTimeLocal,
  toIsoWithOffset,
} from '@/lib/dateTime'
import { executionModeCalendarClass, executionModeLabel } from '@/lib/executionModeDisplay'
import { executorOptions } from '@/lib/executors'
import { readableError } from '@/lib/errors'

type CalendarViewMode = 'day' | 'week' | 'month'

interface CalendarDay {
  date: Date
  key: string
  label: string
  weekday: string
  dayNumber: number
  isToday: boolean
  isOutsideMonth: boolean
}

const router = useRouter()

const viewMode = ref<CalendarViewMode>('week')
const anchorDate = ref(startOfDay(new Date()))
const includeCompleted = ref(false)
const currentTime = ref(new Date())
const items = ref<CalendarItem[]>([])
const total = ref(0)
const isLoading = ref(false)
const isCreatingTask = ref(false)
const actionItemId = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const selectedItem = ref<CalendarItem | null>(null)
const editingItem = ref<CalendarItem | null>(null)
const editScope = ref<'this_occurrence_only' | 'this_and_future'>('this_occurrence_only')
const occurrencePlannedAt = ref('')
const occurrenceInstruction = ref('')
const newTaskPlannedAt = ref('')
const newTaskTitle = ref('')
const newTaskInstructions = ref('')
const newTaskTargetDirectory = ref('')
const newTaskExecutor = ref<ExecutorName>('debug_printer')
let currentTimeTimer: number | undefined

const hours = Array.from({ length: 24 }, (_, hour) => hour)
const currentDateKey = computed(() => dateKey(currentTime.value))
const currentHour = computed(() => currentTime.value.getHours())
const currentMinuteOffset = computed(() => `${(currentTime.value.getMinutes() / 60) * 100}%`)
const currentClockLabel = computed(() =>
  new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(
    currentTime.value,
  ),
)
const visibleRange = computed(() => rangeForMode(viewMode.value, anchorDate.value))
const rangeLabel = computed(() =>
  labelForRange(viewMode.value, visibleRange.value, anchorDate.value),
)
const calendarDays = computed(() =>
  daysBetween(visibleRange.value.start, visibleRange.value.end).map((date) =>
    buildCalendarDay(date, anchorDate.value),
  ),
)
const visibleToday = computed(() => calendarDays.value.some((day) => day.isToday))
const timeGridDays = computed(() => (viewMode.value === 'month' ? [] : calendarDays.value))
const monthRows = computed(() => {
  const rows: CalendarDay[][] = []
  for (let index = 0; index < calendarDays.value.length; index += 7) {
    rows.push(calendarDays.value.slice(index, index + 7))
  }
  return rows
})

const overlapCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const item of items.value) {
    counts.set(item.occurrence_at, (counts.get(item.occurrence_at) ?? 0) + 1)
  }
  return counts
})

const itemsByDay = computed(() => {
  const grouped = new Map<string, CalendarItem[]>()
  for (const item of sortedItems(items.value)) {
    const key = dateKey(new Date(item.occurrence_at))
    const dayItems = grouped.get(key) ?? []
    dayItems.push(item)
    grouped.set(key, dayItems)
  }
  return grouped
})

const itemsByHour = computed(() => {
  const grouped = new Map<string, CalendarItem[]>()
  for (const item of sortedItems(items.value)) {
    const date = new Date(item.occurrence_at)
    const key = `${dateKey(date)}-${date.getHours()}`
    const hourItems = grouped.get(key) ?? []
    hourItems.push(item)
    grouped.set(key, hourItems)
  }
  return grouped
})
const canCreateTask = computed(
  () =>
    newTaskTitle.value.trim().length > 0 &&
    newTaskInstructions.value.trim().length > 0 &&
    newTaskTargetDirectory.value.trim().startsWith('/') &&
    isFutureLocal(newTaskPlannedAt.value),
)

onMounted(() => {
  void refreshCalendar()
  currentTimeTimer = window.setInterval(() => {
    currentTime.value = new Date()
  }, 60_000)
})

onUnmounted(() => {
  if (currentTimeTimer !== undefined) {
    window.clearInterval(currentTimeTimer)
  }
})

watch([viewMode, anchorDate, includeCompleted], () => {
  void refreshCalendar()
})

async function refreshCalendar() {
  isLoading.value = true
  errorMessage.value = null
  const range = visibleRange.value
  try {
    const response = await getCalendar({
      from: toIsoWithOffset(toDateTimeLocal(range.start.toISOString())),
      to: toIsoWithOffset(toDateTimeLocal(range.end.toISOString())),
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

function openItemModal(item: CalendarItem) {
  selectedItem.value = item
}

function closeItemModal() {
  selectedItem.value = null
}

async function openSelectedTask() {
  if (!selectedItem.value) return
  const item = selectedItem.value
  selectedItem.value = null
  await openTask(item)
}

function editSelectedItem() {
  if (!selectedItem.value) return
  startEdit(selectedItem.value)
}

async function skipSelectedItem() {
  if (!selectedItem.value) return
  await skipOccurrence(selectedItem.value)
}

function startEdit(item: CalendarItem) {
  selectedItem.value = null
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
  selectedItem.value = null
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

function openAddTaskModal(date: Date) {
  selectedItem.value = null
  editingItem.value = null
  newTaskPlannedAt.value =
    date.getTime() > Date.now() ? toDateTimeLocal(date.toISOString()) : defaultDateTimeLocal()
  newTaskTitle.value = ''
  newTaskInstructions.value = ''
  newTaskTargetDirectory.value = ''
  newTaskExecutor.value = 'debug_printer'
}

function closeAddTaskModal() {
  newTaskPlannedAt.value = ''
}

async function submitNewTask() {
  if (!canCreateTask.value) {
    errorMessage.value =
      'Add a title, instructions, an absolute target directory, and a future execution time.'
    return
  }
  isCreatingTask.value = true
  errorMessage.value = null
  try {
    await createTask({
      title: newTaskTitle.value.trim(),
      instruction_source: newTaskInstructions.value.trim(),
      target_working_directory: newTaskTargetDirectory.value.trim(),
      executor: newTaskExecutor.value,
      planned_at: toIsoWithOffset(newTaskPlannedAt.value),
    })
    closeAddTaskModal()
    await refreshCalendar()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isCreatingTask.value = false
  }
}

function setViewMode(mode: CalendarViewMode) {
  viewMode.value = mode
}

function movePeriod(direction: -1 | 1) {
  if (viewMode.value === 'month') {
    anchorDate.value = addMonths(anchorDate.value, direction)
    return
  }
  anchorDate.value = addDays(anchorDate.value, direction * (viewMode.value === 'week' ? 7 : 1))
}

function moveToToday() {
  anchorDate.value = startOfDay(new Date())
}

function itemsForDay(day: CalendarDay): CalendarItem[] {
  return itemsByDay.value.get(day.key) ?? []
}

function itemsForHour(day: CalendarDay, hour: number): CalendarItem[] {
  return itemsByHour.value.get(`${day.key}-${hour}`) ?? []
}

function slotDate(day: CalendarDay, hour: number): Date {
  const date = new Date(day.date)
  date.setHours(hour, 0, 0, 0)
  return date
}

function defaultDaySlot(day: CalendarDay): Date {
  const date = new Date(day.date)
  date.setHours(9, 0, 0, 0)
  return date
}

function hourHasItems(hour: number): boolean {
  return timeGridDays.value.some((day) => itemsForHour(day, hour).length > 0)
}

function isCurrentHour(day: CalendarDay, hour: number): boolean {
  return day.isToday && hour === currentHour.value
}

function addTaskLabel(date: Date): string {
  return `Add task at ${formatDateTime(date.toISOString())}`
}

function overlapLabel(item: CalendarItem): string {
  const count = overlapCounts.value.get(item.occurrence_at) ?? 0
  return count > 1 ? `${count} overlapping` : 'No overlap'
}

function viewModeLabel(mode: CalendarViewMode): string {
  return mode.charAt(0).toUpperCase() + mode.slice(1)
}

function hourLabel(hour: number): string {
  const date = new Date()
  date.setHours(hour, 0, 0, 0)
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric' }).format(date)
}

function itemTime(item: CalendarItem): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(item.occurrence_at))
}

function dateKey(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function startOfWeek(date: Date): Date {
  const day = startOfDay(date)
  const offset = (day.getDay() + 6) % 7
  return addDays(day, -offset)
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

function addMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1)
}

function rangeForMode(mode: CalendarViewMode, date: Date): { start: Date; end: Date } {
  if (mode === 'day') {
    const start = startOfDay(date)
    return { start, end: addDays(start, 1) }
  }
  if (mode === 'week') {
    const start = startOfWeek(date)
    return { start, end: addDays(start, 7) }
  }

  const firstOfMonth = new Date(date.getFullYear(), date.getMonth(), 1)
  const lastOfMonth = new Date(date.getFullYear(), date.getMonth() + 1, 0)
  const start = startOfWeek(firstOfMonth)
  const end = addDays(startOfWeek(lastOfMonth), 7)
  return { start, end }
}

function daysBetween(start: Date, end: Date): Date[] {
  const days: Date[] = []
  for (let day = startOfDay(start); day < end; day = addDays(day, 1)) {
    days.push(day)
  }
  return days
}

function buildCalendarDay(date: Date, currentMonthDate: Date): CalendarDay {
  return {
    date,
    key: dateKey(date),
    label: new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date),
    weekday: new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(date),
    dayNumber: date.getDate(),
    isToday: dateKey(date) === currentDateKey.value,
    isOutsideMonth: date.getMonth() !== currentMonthDate.getMonth(),
  }
}

function labelForRange(
  mode: CalendarViewMode,
  range: { start: Date; end: Date },
  currentDate: Date,
): string {
  if (mode === 'month') {
    return new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' }).format(
      currentDate,
    )
  }
  if (mode === 'day') {
    return new Intl.DateTimeFormat(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    }).format(range.start)
  }
  const end = addDays(range.end, -1)
  return `${new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(
    range.start,
  )} - ${new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(end)}`
}

function sortedItems(calendarItems: CalendarItem[]): CalendarItem[] {
  return [...calendarItems].sort(
    (left, right) =>
      new Date(left.occurrence_at).getTime() - new Date(right.occurrence_at).getTime(),
  )
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
            Calendar
          </p>
          <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
            {{ rangeLabel }}
          </h2>
          <p class="m-0 text-sm text-slate-500 dark:text-slate-400">{{ total }} planned items</p>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <div
            class="inline-flex rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 p-1 shadow-xs"
          >
            <button
              v-for="mode in ['day', 'week', 'month'] as CalendarViewMode[]"
              :key="mode"
              class="min-h-9 cursor-pointer rounded px-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-55"
              :class="
                viewMode === mode
                  ? 'bg-teal-700 text-white'
                  : 'bg-transparent text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800'
              "
              :disabled="isLoading"
              type="button"
              @click="setViewMode(mode)"
            >
              {{ viewModeLabel(mode) }}
            </button>
          </div>
          <div class="flex items-center gap-2">
            <UiButton
              class="px-3"
              :disabled="isLoading"
              @click="movePeriod(-1)"
            >
              Previous
            </UiButton>
            <UiButton
              class="px-3"
              :disabled="isLoading"
              @click="moveToToday"
            >
              Today
            </UiButton>
            <UiButton
              class="px-3"
              :disabled="isLoading"
              @click="movePeriod(1)"
            >
              Next
            </UiButton>
          </div>
          <label
            class="flex min-h-10 items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-300"
          >
            <input v-model="includeCompleted" type="checkbox" />
            <span>Completed</span>
          </label>
          <UiButton
            :disabled="isLoading"
            @click="refreshCalendar"
          >
            Refresh
          </UiButton>
        </div>
      </div>

      <PageStatePanel v-if="isLoading" spacious title="Loading calendar items..." />
      <PageStatePanel
        v-else-if="items.length === 0"
        class="mb-4"
        title="No upcoming AI work scheduled"
      >
        <UiButton variant="primary" @click="openAddTaskModal(new Date())">
          Create Task
        </UiButton>
      </PageStatePanel>
      <div v-if="!isLoading" class="grid gap-4">
        <div
          v-if="viewMode === 'month'"
          class="hidden overflow-x-auto rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 md:block"
        >
          <div
            class="grid min-w-[920px] grid-cols-7 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50"
          >
            <div
              v-for="day in calendarDays.slice(0, 7)"
              :key="day.weekday"
              class="px-3 py-2 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400 uppercase"
            >
              {{ day.weekday }}
            </div>
          </div>
          <div
            v-for="(week, weekIndex) in monthRows"
            :key="weekIndex"
            class="grid min-w-[920px] grid-cols-7 border-b border-slate-200 dark:border-slate-700 last:border-b-0"
          >
            <div
              v-for="day in week"
              :key="day.key"
              class="min-h-36 cursor-pointer border-r border-slate-200 dark:border-slate-700 p-2 last:border-r-0 hover:bg-teal-50/40"
              :class="[
                day.isOutsideMonth
                  ? 'bg-slate-50/70 text-slate-400 dark:bg-slate-900/50 dark:text-slate-500'
                  : 'bg-white text-slate-950 dark:bg-slate-900 dark:text-slate-50',
                day.isToday
                  ? 'ring-2 ring-inset ring-teal-600 dark:ring-teal-400'
                  : '',
              ]"
              :data-testid="day.isToday ? 'calendar-today-cell' : undefined"
              :aria-label="addTaskLabel(defaultDaySlot(day))"
              role="button"
              tabindex="0"
              @click="openAddTaskModal(defaultDaySlot(day))"
              @keydown.enter.prevent="openAddTaskModal(defaultDaySlot(day))"
            >
              <div class="mb-2 flex items-center justify-between gap-2">
                <span
                  class="inline-flex size-7 items-center justify-center rounded-full text-sm font-bold"
                  :class="
                    day.isToday ? 'bg-teal-700 text-white' : 'text-slate-700 dark:text-slate-300'
                  "
                >
                  {{ day.dayNumber }}
                </span>
                <span class="flex items-center gap-1">
                  <span
                    v-if="day.isToday"
                    class="rounded-full bg-teal-50 dark:bg-teal-950/50 px-2 py-0.5 text-xs font-bold text-teal-800 dark:text-teal-300"
                    data-testid="calendar-current-time-label"
                  >
                    {{ currentClockLabel }}
                  </span>
                  <span class="text-xs text-slate-500 dark:text-slate-400">{{
                    itemsForDay(day).length || ''
                  }}</span>
                </span>
              </div>
              <div class="grid gap-1">
                <article
                  v-for="item in itemsForDay(day).slice(0, 3)"
                  :key="item.calendar_item_id"
                  class="rounded-md border px-2 py-1 text-xs shadow-xs transition hover:-translate-y-px hover:shadow-sm"
                  :class="executionModeCalendarClass(item.execution_mode)"
                  :aria-label="`${itemTime(item)} ${item.title}`"
                  role="button"
                  tabindex="0"
                  @click.stop="openItemModal(item)"
                  @keydown.enter.stop.prevent="openItemModal(item)"
                >
                  <div class="font-bold text-inherit wrap-anywhere">
                    {{ itemTime(item) }} {{ item.title }}
                  </div>
                  <span class="mt-1 flex flex-wrap gap-1">
                    <span
                      class="rounded bg-white/80 px-1.5 py-0.5 font-semibold dark:bg-slate-900/80"
                    >
                      {{ executionModeLabel(item.execution_mode) }}
                    </span>
                    <span
                      v-if="item.is_occurrence_override"
                      class="rounded bg-amber-100 dark:bg-amber-950/30 px-1.5 py-0.5 font-semibold text-amber-800 dark:text-amber-300"
                    >
                      Override
                    </span>
                  </span>
                </article>
                <span
                  v-if="itemsForDay(day).length > 3"
                  class="rounded-md bg-slate-100 dark:bg-slate-900/50 px-2 py-1 text-xs font-semibold text-slate-600 dark:text-slate-400"
                >
                  +{{ itemsForDay(day).length - 3 }} more
                </span>
              </div>
            </div>
          </div>
        </div>

        <div
          v-else
          class="hidden overflow-x-auto rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 md:block"
        >
          <div
            class="grid min-w-[980px] border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50"
            :style="{ gridTemplateColumns: `72px repeat(${timeGridDays.length}, minmax(0, 1fr))` }"
          >
            <div
              class="px-3 py-3 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400 uppercase"
            >
              Time
            </div>
            <div
              v-for="day in timeGridDays"
              :key="day.key"
              class="border-l border-slate-200 dark:border-slate-700 px-3 py-3"
              :class="
                day.isToday
                  ? 'bg-teal-50/80 dark:bg-teal-950/30'
                  : ''
              "
              :data-testid="day.isToday ? 'calendar-today-header' : undefined"
            >
              <div
                class="text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400 uppercase"
              >
                {{ day.weekday }}
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-bold text-slate-950 dark:text-slate-50">{{
                  day.label
                }}</span>
                <span
                  v-if="day.isToday"
                  class="rounded-full bg-teal-700 px-2 py-0.5 text-xs font-bold text-white dark:bg-teal-400 dark:text-slate-950"
                  data-testid="calendar-current-time-label"
                >
                  {{ currentClockLabel }}
                </span>
              </div>
            </div>
          </div>
          <div
            v-for="hour in hours"
            :key="hour"
            class="grid min-w-[980px] border-b border-slate-100 dark:border-slate-800 last:border-b-0"
            :class="hourHasItems(hour) ? 'min-h-20' : 'min-h-9'"
            :style="{ gridTemplateColumns: `72px repeat(${timeGridDays.length}, minmax(0, 1fr))` }"
          >
            <div
              class="bg-slate-50 dark:bg-slate-800/50 px-3 text-xs font-semibold text-slate-500 dark:text-slate-400"
              :class="[
                hourHasItems(hour) ? 'py-3' : 'py-2',
                visibleToday && hour === currentHour
                  ? 'text-teal-800 dark:text-teal-300'
                  : '',
              ]"
            >
              {{ hourLabel(hour) }}
            </div>
            <div
              v-for="day in timeGridDays"
              :key="`${day.key}-${hour}`"
              class="relative cursor-pointer border-l border-slate-100 dark:border-slate-800 transition hover:bg-teal-50/50"
              :class="[
                hourHasItems(hour) ? 'min-h-20 p-2' : 'min-h-9 px-2 py-1',
                day.isToday ? 'bg-teal-50/30 dark:bg-teal-950/10' : '',
                isCurrentHour(day, hour)
                  ? 'bg-teal-50/80 dark:bg-teal-950/30'
                  : '',
              ]"
              :aria-label="addTaskLabel(slotDate(day, hour))"
              role="button"
              tabindex="0"
              @click="openAddTaskModal(slotDate(day, hour))"
              @keydown.enter.prevent="openAddTaskModal(slotDate(day, hour))"
            >
              <div
                v-if="isCurrentHour(day, hour)"
                class="pointer-events-none absolute right-2 left-2 z-10 flex items-center"
                :style="{ top: currentMinuteOffset }"
                aria-label="Current time"
                data-testid="calendar-current-time-marker"
              >
                <span class="size-2 rounded-full bg-teal-700 dark:bg-teal-300"></span>
                <span class="h-0.5 flex-1 bg-teal-700 dark:bg-teal-300"></span>
              </div>
              <div class="grid gap-2">
                <article
                  v-for="item in itemsForHour(day, hour)"
                  :key="item.calendar_item_id"
                  class="rounded-md border p-2 shadow-xs transition hover:-translate-y-px hover:shadow-sm"
                  :class="executionModeCalendarClass(item.execution_mode)"
                  :aria-label="`${itemTime(item)} ${item.title}`"
                  role="button"
                  tabindex="0"
                  @click.stop="openItemModal(item)"
                  @keydown.enter.stop.prevent="openItemModal(item)"
                >
                  <div class="mb-2 flex flex-wrap items-center gap-1">
                    <span
                      class="rounded bg-white/80 px-2 py-0.5 text-xs font-bold dark:bg-slate-900/80"
                    >
                      {{ itemTime(item) }}
                    </span>
                    <span
                      class="rounded bg-white/80 px-2 py-0.5 text-xs font-bold dark:bg-slate-900/80"
                    >
                      {{ executionModeLabel(item.execution_mode) }}
                    </span>
                    <span
                      v-if="item.is_occurrence_override"
                      class="rounded bg-amber-100 dark:bg-amber-950/30 px-2 py-0.5 text-xs font-bold text-amber-800 dark:text-amber-300"
                    >
                      Override
                    </span>
                  </div>
                  <div class="mb-2 text-sm font-bold text-inherit wrap-anywhere">
                    {{ item.title }}
                  </div>
                  <div class="mb-2 text-xs font-semibold text-slate-600 dark:text-slate-400">
                    {{ item.state }} · {{ overlapLabel(item) }}
                  </div>
                </article>
              </div>
            </div>
          </div>
        </div>

        <div
          class="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 md:hidden"
        >
          <div
            class="flex items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 px-4 py-3"
          >
            <span class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-bold text-slate-950 dark:text-slate-50">Agenda</span>
              <span
                v-if="visibleToday"
                class="rounded-full bg-teal-50 dark:bg-teal-950/50 px-2 py-0.5 text-xs font-bold text-teal-800 dark:text-teal-300"
                data-testid="calendar-mobile-current-time-label"
              >
                {{ currentClockLabel }}
              </span>
            </span>
            <button
              class="min-h-8 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 text-xs font-semibold text-slate-700 dark:text-slate-300 transition hover:border-teal-700 dark:hover:border-teal-500 hover:text-teal-800"
              type="button"
              @click="openAddTaskModal(new Date())"
            >
              New
            </button>
          </div>
          <div class="grid divide-y divide-slate-200">
            <article
              v-for="item in sortedItems(items)"
              :key="item.calendar_item_id"
              class="grid cursor-pointer gap-2 bg-white dark:bg-slate-900 px-4 py-3 transition hover:bg-teal-50/50"
              :aria-label="item.title"
              role="button"
              tabindex="0"
              @click="openItemModal(item)"
              @keydown.enter.prevent="openItemModal(item)"
            >
              <span class="text-sm font-bold text-teal-800 dark:text-teal-300 wrap-anywhere">
                {{ item.title }}
              </span>
              <span class="text-xs font-semibold text-slate-600 dark:text-slate-400">
                {{ formatDateTime(item.occurrence_at) }} ·
                {{ executionModeLabel(item.execution_mode) }}
              </span>
            </article>
          </div>
        </div>
      </div>
    </section>

    <div
      v-if="selectedItem"
      class="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/40 p-4"
      @click.self="closeItemModal"
    >
      <section
        class="grid max-h-[90vh] w-full max-w-lg gap-4 overflow-y-auto rounded-md bg-white dark:bg-slate-900 p-5 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="calendar-item-title"
      >
        <div class="flex items-start justify-between gap-4">
          <div>
            <p
              class="m-0 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase"
            >
              {{ executionModeLabel(selectedItem.execution_mode) }}
            </p>
            <h3
              id="calendar-item-title"
              class="m-0 text-xl font-bold text-slate-950 dark:text-slate-50"
            >
              {{ selectedItem.title }}
            </h3>
          </div>
          <UiButton size="sm" @click="closeItemModal">
            Close
          </UiButton>
        </div>
        <dl class="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
          <dt class="font-semibold text-slate-500 dark:text-slate-400">Time</dt>
          <dd class="m-0 text-slate-950 dark:text-slate-50">
            {{ formatDateTime(selectedItem.occurrence_at) }}
          </dd>
          <dt class="font-semibold text-slate-500 dark:text-slate-400">State</dt>
          <dd class="m-0 text-slate-950 dark:text-slate-50">{{ selectedItem.state }}</dd>
          <dt class="font-semibold text-slate-500 dark:text-slate-400">Overlap</dt>
          <dd class="m-0 text-slate-950 dark:text-slate-50">{{ overlapLabel(selectedItem) }}</dd>
          <dt
            v-if="selectedItem.is_occurrence_override"
            class="font-semibold text-slate-500 dark:text-slate-400"
          >
            Override
          </dt>
          <dd
            v-if="selectedItem.is_occurrence_override"
            class="m-0 text-amber-800 dark:text-amber-300"
          >
            This occurrence has custom timing or instructions.
          </dd>
        </dl>
        <div class="flex flex-wrap gap-2">
          <UiButton variant="primary" @click="openSelectedTask">
            Detail
          </UiButton>
          <UiButton
            v-if="selectedItem.execution_mode === 'recurring'"
            :disabled="actionItemId === selectedItem.calendar_item_id"
            @click="editSelectedItem"
          >
            Edit Occurrence
          </UiButton>
          <UiButton
            v-if="selectedItem.execution_mode === 'recurring'"
            variant="danger"
            :disabled="actionItemId === selectedItem.calendar_item_id"
            @click="skipSelectedItem"
          >
            Skip Occurrence
          </UiButton>
        </div>
      </section>
    </div>

    <div
      v-if="editingItem"
      class="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/40 p-4"
      @click.self="editingItem = null"
    >
      <form
        class="grid max-h-[90vh] w-full max-w-lg gap-4 overflow-y-auto rounded-md bg-white dark:bg-slate-900 p-5 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-occurrence-title"
        @submit.prevent="submitOccurrenceEdit"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3
              id="edit-occurrence-title"
              class="m-0 text-lg font-bold text-slate-950 dark:text-slate-50"
            >
              Edit Recurring Task
            </h3>
            <p class="m-0 text-sm text-slate-500 dark:text-slate-400">
              {{ editingItem.title }} · {{ formatDateTime(editingItem.occurrence_at) }}
            </p>
          </div>
          <UiButton size="sm" @click="editingItem = null">
            Cancel
          </UiButton>
        </div>
        <fieldset class="m-0 grid gap-2 border-0 p-0">
          <legend class="font-semibold text-slate-700 dark:text-slate-300">Scope</legend>
          <div class="flex flex-wrap gap-2">
            <button
              class="min-h-9 rounded-md border px-3 text-sm font-semibold transition"
              :class="
                editScope === 'this_occurrence_only'
                  ? 'border-teal-700 bg-teal-50 text-teal-800 dark:border-teal-500 dark:bg-teal-950/30 dark:text-teal-300'
                  : 'border-slate-300 bg-white text-slate-700 hover:border-teal-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-teal-500'
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
                  ? 'border-teal-700 bg-teal-50 text-teal-800 dark:border-teal-500 dark:bg-teal-950/30 dark:text-teal-300'
                  : 'border-slate-300 bg-white text-slate-700 hover:border-teal-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-teal-500'
              "
              type="button"
              @click="editScope = 'this_and_future'"
            >
              This And Future
            </button>
          </div>
        </fieldset>
        <TextInput
          v-if="editScope === 'this_occurrence_only'"
          v-model="occurrencePlannedAt"
          label="Occurrence Time"
          type="datetime-local"
        />
        <TextArea v-model="occurrenceInstruction" label="Instructions" min-height />
        <UiButton
          variant="primary"
          :disabled="actionItemId === editingItem.calendar_item_id"
          type="submit"
        >
          Save
        </UiButton>
      </form>
    </div>

    <div
      v-if="newTaskPlannedAt"
      class="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/40 p-4"
      @click.self="closeAddTaskModal"
    >
      <form
        class="grid max-h-[90vh] w-full max-w-lg gap-4 overflow-y-auto rounded-md bg-white dark:bg-slate-900 p-5 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-calendar-task-title"
        @submit.prevent="submitNewTask"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p
              class="m-0 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase"
            >
              One-time task
            </p>
            <h3
              id="new-calendar-task-title"
              class="m-0 text-lg font-bold text-slate-950 dark:text-slate-50"
            >
              New Calendar Task
            </h3>
          </div>
          <UiButton size="sm" @click="closeAddTaskModal">
            Cancel
          </UiButton>
        </div>
        <TextInput v-model="newTaskTitle" label="Title" placeholder="Run benchmark report" />
        <TextArea
          v-model="newTaskInstructions"
          label="Instructions"
          min-height
          placeholder="Describe the AI work to run later..."
        />
        <TextInput v-model="newTaskPlannedAt" label="Execution Time" type="datetime-local" />
        <TextInput
          v-model="newTaskTargetDirectory"
          label="Target Directory"
          placeholder="/Users/you/project"
        />
        <SelectField v-model="newTaskExecutor" label="Executor" :options="executorOptions" />
        <UiButton
          variant="primary"
          :disabled="!canCreateTask || isCreatingTask"
          type="submit"
        >
          {{ isCreatingTask ? 'Saving...' : 'Save Task' }}
        </UiButton>
      </form>
    </div>
  </div>
</template>
