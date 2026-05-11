export type TaskStatus =
  | 'scheduled'
  | 'paused'
  | 'running'
  | 'completed'
  | 'failed'
  | 'canceled'
  | 'archived'

export type ExecutionMode = 'one_time' | 'recurring'
export type RunStatus = 'planned' | 'queued' | 'running' | 'completed' | 'failed' | 'canceled'
export type ExecutorName = 'claude_code' | 'codex' | 'debug_printer' | 'kimi_code' | 'opencode'
export type ExecutorPreflightStatus = 'available' | 'unavailable' | 'warning'

export interface Task {
  task_id: string
  title: string
  instruction_source: string
  target_working_directory: string | null
  execution_mode: ExecutionMode
  task_status: TaskStatus
  template_id: string | null
  executor: ExecutorName
  executor_profile_id: string | null
  version: number
  created_at: string
  updated_at: string
  archived_at: string | null
}

export interface Schedule {
  schedule_id: string
  task_id: string
  schedule_type: 'single_run' | 'recurring_rule'
  schedule_status: 'pending' | 'active' | 'paused' | 'completed' | 'canceled'
  planned_at: string | null
  recurrence_rule?: string | null
  recurrence_timezone?: string | null
  next_run_at: string | null
  version: number
}

export interface Run {
  run_id: string
  task_id: string
  schedule_id: string | null
  run_status: RunStatus
  planned_start_at: string
  actual_start_at: string | null
  finished_at: string | null
  result_summary: string | null
  failure_reason: string | null
  occurrence_key: string | null
}

export interface RunEvent {
  run_event_id: string
  run_id: string
  task_id: string
  schedule_id: string | null
  event_type: string
  severity: 'info' | 'warning' | 'error' | string
  message: string
  details: Record<string, string | number | boolean | null>
  temporal_workflow_id: string | null
  temporal_workflow_run_id: string | null
  activity_type: string | null
  activity_attempt: number | null
  created_at: string
}

export interface RunPreview {
  run_id: string
  task_id: string
  schedule_id: string | null
  run_status: RunStatus
  planned_start_at: string
  actual_start_at: string | null
  finished_at: string | null
  occurrence_key: string | null
  created_at: string
  updated_at: string
  outcome_preview: string | null
  outcome_truncated: boolean
  outcome_source: 'result_summary' | 'failure_reason' | null
}

export interface TaskBundle {
  task: Task
  schedule: Schedule
  run: Run | null
}

export interface ExecutorPreflightResult {
  executor: ExecutorName
  status: ExecutorPreflightStatus
  code: string
  message: string
  details: Record<string, string | boolean | null>
}

export interface ExecutorProfile {
  profile_id: string
  name: string
  executor: ExecutorName
  is_enabled: boolean
  is_default: boolean
  default_model: string | null
  env: Record<string, string>
  secret_env_keys: string[]
  version: number
  created_at: string
  updated_at: string
  archived_at: string | null
}

export interface TaskDetail {
  task: Task
  schedule: Schedule | null
  latest_run: Run | null
}

export interface RunReaderRun extends Run {
  created_at: string
  updated_at: string
  external_execution_ref: string | null
}

export interface RunReaderDetail {
  task: Task
  schedule: Schedule | null
  run: RunReaderRun
  previous_run_id: string | null
  next_run_id: string | null
}

export interface KanbanCard {
  card_id: string
  task_id: string
  title: string
  kanban_column: string
  next_run_at: string | null
  latest_run_status: RunStatus | null
}

export interface KanbanBoard {
  columns: Record<string, KanbanCard[]>
}

export interface HistoryItem {
  history_item_id: string
  run_id: string
  task_id: string
  title: string
  execution_mode: ExecutionMode
  run_status: Extract<RunStatus, 'completed' | 'failed'>
  finished_at: string
  outcome_preview: string | null
  outcome_truncated: boolean
  outcome_source: 'result_summary' | 'failure_reason' | null
}

export interface RecurringTodoItem {
  item_id: string
  task_id: string
  title: string
  recurrence_rule: string
  recurrence_timezone: string
  next_run_at: string | null
  schedule_status: 'active' | 'paused'
  task_status: TaskStatus
  schedule_version: number
  latest_run_id: string | null
  latest_run_outcome: RunStatus | null
  latest_run_finished_at: string | null
  result_summary: string | null
  failure_reason: string | null
}

export interface CalendarItem {
  calendar_item_id: string
  task_id: string
  schedule_id: string
  title: string
  execution_mode: ExecutionMode
  occurrence_at: string
  original_occurrence_at: string | null
  state: TaskStatus
  is_occurrence_override: boolean
  schedule_version: number
}

export interface OccurrenceOverride {
  occurrence_override_id: string
  task_id: string
  schedule_id: string
  original_occurrence_at: string
  override_occurrence_at: string | null
  override_instruction_delta: string | null
  override_status: 'active' | 'canceled'
  created_at: string
  updated_at: string
}

export interface TemplateScheduleConfig {
  schedule_type: 'single_run' | 'recurring_rule'
  planned_at: string | null
  recurrence_rule: string | null
  recurrence_timezone: string | null
}

export interface TaskTemplate {
  template_id: string
  name: string
  description: string | null
  instruction_source: string
  default_task_title: string | null
  default_target_working_directory: string | null
  default_execution_mode: ExecutionMode
  default_schedule_config: TemplateScheduleConfig
  default_executor: ExecutorName | null
  default_executor_profile_id: string | null
  version: number
  created_at: string
  updated_at: string
  archived_at: string | null
}

interface Envelope<T> {
  data: T
}

interface ListEnvelope<T> extends Envelope<T[]> {
  meta: {
    total: number
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

type CreateTaskPayloadBase = {
  title: string
  instruction_source: string
  target_working_directory: string
  executor?: ExecutorName
  executor_profile_id?: string | null
  template_id?: string | null
}

type CreateTaskPayload =
  | (CreateTaskPayloadBase & {
      execution_mode?: 'one_time'
      planned_at: string
    })
  | (CreateTaskPayloadBase & {
      execution_mode: 'recurring'
      recurrence_rule: string
      recurrence_timezone: string
    })

export async function createTask(payload: CreateTaskPayload): Promise<TaskBundle> {
  const schedule =
    payload.execution_mode === 'recurring'
      ? {
          schedule_type: 'recurring_rule',
          recurrence_rule: payload.recurrence_rule,
          recurrence_timezone: payload.recurrence_timezone,
        }
      : {
          schedule_type: 'single_run',
          planned_at: payload.planned_at,
        }

  return request<TaskBundle>('/tasks', {
    method: 'POST',
    body: JSON.stringify({
      title: payload.title,
      instruction_source: payload.instruction_source,
      target_working_directory: payload.target_working_directory,
      execution_mode: payload.execution_mode ?? 'one_time',
      executor: payload.executor ?? null,
      executor_profile_id: payload.executor_profile_id ?? null,
      template_id: payload.template_id ?? null,
      schedule,
    }),
  })
}

export async function preflightExecutor(params: {
  executor?: ExecutorName
  executor_profile_id?: string
  target_working_directory?: string
}): Promise<ExecutorPreflightResult> {
  const search = new URLSearchParams()
  if (params.executor) search.set('executor', params.executor)
  if (params.executor_profile_id) search.set('executor_profile_id', params.executor_profile_id)
  if (params.target_working_directory) {
    search.set('target_working_directory', params.target_working_directory)
  }
  return request<ExecutorPreflightResult>(`/executors/preflight?${search}`)
}

export async function listExecutorProfiles(
  params: { include_archived?: boolean; limit?: number; offset?: number } = {},
): Promise<ListEnvelope<ExecutorProfile>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      search.set(key, String(value))
    }
  }
  const suffix = search.size > 0 ? `?${search}` : ''
  return requestList<ExecutorProfile>(`/executor-profiles${suffix}`)
}

export async function createExecutorProfile(payload: {
  name: string
  executor: ExecutorName
  is_enabled: boolean
  is_default: boolean
  default_model: string | null
  env: Record<string, string>
  secret_env: Record<string, string>
}): Promise<ExecutorProfile> {
  return request<ExecutorProfile>('/executor-profiles', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateExecutorProfile(
  profileId: string,
  payload: {
    version: number
    name?: string
    is_enabled?: boolean
    is_default?: boolean
    default_model?: string | null
    env?: Record<string, string>
    secret_env?: Record<string, string | null>
  },
): Promise<ExecutorProfile> {
  return request<ExecutorProfile>(`/executor-profiles/${profileId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function archiveExecutorProfile(
  profileId: string,
  version: number,
): Promise<ExecutorProfile> {
  return request<ExecutorProfile>(`/executor-profiles/${profileId}/archive`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export async function getKanban(includeCanceled: boolean = false): Promise<KanbanBoard> {
  const params = new URLSearchParams()
  if (includeCanceled) {
    params.append('include_canceled', 'true')
  }
  const query = params.toString()
  return request<KanbanBoard>(`/views/kanban${query ? `?${query}` : ''}`)
}

export async function listTasks(
  params: {
    execution_mode?: ExecutionMode | ''
    status?: TaskStatus | ''
    include_archived?: boolean
    limit?: number
    offset?: number
  } = {},
): Promise<ListEnvelope<Task>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const suffix = search.size > 0 ? `?${search}` : ''
  return requestList<Task>(`/tasks${suffix}`)
}

export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(`/tasks/${taskId}/detail`)
}

export async function getTaskRuns(
  taskId: string,
  params: {
    status?: RunStatus | ''
    limit?: number
    offset?: number
  } = {},
): Promise<ListEnvelope<RunPreview>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const suffix = search.size > 0 ? `?${search}` : ''
  return requestList<RunPreview>(`/tasks/${taskId}/runs${suffix}`)
}

export async function getRun(runId: string): Promise<Run> {
  return request<Run>(`/runs/${runId}`)
}

export async function getRunEvents(
  runId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<ListEnvelope<RunEvent>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      search.set(key, String(value))
    }
  }
  const suffix = search.size > 0 ? `?${search}` : ''
  return requestList<RunEvent>(`/runs/${runId}/events${suffix}`)
}

export async function getRunReaderDetail(taskId: string, runId: string): Promise<RunReaderDetail> {
  return request<RunReaderDetail>(`/tasks/${taskId}/runs/${runId}/reader`)
}

export async function getHistory(
  params: {
    status?: HistoryItem['run_status'] | ''
    execution_mode?: ExecutionMode | ''
    from?: string
    to?: string
    limit?: number
    offset?: number
  } = {},
): Promise<ListEnvelope<HistoryItem>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const suffix = search.size > 0 ? `?${search}` : ''
  return requestList<HistoryItem>(`/views/history${suffix}`)
}

export async function getRecurringTodo(
  params: {
    status?: RecurringTodoItem['schedule_status'] | ''
    include_paused?: boolean
    limit?: number
    offset?: number
  } = {},
): Promise<ListEnvelope<RecurringTodoItem>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const suffix = search.size > 0 ? `?${search}` : ''
  return requestList<RecurringTodoItem>(`/views/recurring-todo${suffix}`)
}

export async function getCalendar(params: {
  from: string
  to: string
  include_completed?: boolean
  limit?: number
  offset?: number
}): Promise<ListEnvelope<CalendarItem>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  return requestList<CalendarItem>(`/views/calendar?${search}`)
}

export async function updateOccurrence(
  taskId: string,
  payload: {
    version: number
    original_occurrence_at: string
    scope: 'this_occurrence_only' | 'this_and_future'
    planned_at?: string | null
    instruction_source?: string | null
    recurrence_rule?: string | null
    recurrence_timezone?: string | null
  },
): Promise<TaskBundle | OccurrenceOverride> {
  return request<TaskBundle | OccurrenceOverride>(`/tasks/${taskId}/occurrences/update`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function cancelOccurrence(
  taskId: string,
  version: number,
  originalOccurrenceAt: string,
): Promise<OccurrenceOverride> {
  return request<OccurrenceOverride>(`/tasks/${taskId}/occurrences/cancel`, {
    method: 'POST',
    body: JSON.stringify({
      version,
      original_occurrence_at: originalOccurrenceAt,
      scope: 'this_occurrence_only',
    }),
  })
}

export async function listTemplates(
  params: { include_archived?: boolean; limit?: number; offset?: number } = {},
): Promise<ListEnvelope<TaskTemplate>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      search.set(key, String(value))
    }
  }
  const suffix = search.size > 0 ? `?${search}` : ''
  return requestList<TaskTemplate>(`/templates${suffix}`)
}

export async function createTemplate(payload: {
  name: string
  description: string | null
  instruction_source: string
  default_task_title: string | null
  default_target_working_directory: string | null
  default_executor: ExecutorName | null
  default_executor_profile_id?: string | null
}): Promise<TaskTemplate> {
  return request<TaskTemplate>('/templates', {
    method: 'POST',
    body: JSON.stringify({
      ...payload,
      default_execution_mode: 'one_time',
      default_schedule_config: {
        schedule_type: 'single_run',
        planned_at: null,
        recurrence_rule: null,
        recurrence_timezone: null,
      },
    }),
  })
}

export async function updateTask(
  taskId: string,
  payload: {
    version: number
    title?: string
    instruction_source?: string
  },
): Promise<Task> {
  return request<Task>(`/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function updateTemplate(
  templateId: string,
  payload: {
    version: number
    name?: string
    description?: string | null
    instruction_source?: string
    default_task_title?: string | null
    default_target_working_directory?: string | null
    default_executor?: ExecutorName | null
    default_executor_profile_id?: string | null
  },
): Promise<TaskTemplate> {
  return request<TaskTemplate>(`/templates/${templateId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function archiveTemplate(templateId: string, version: number): Promise<TaskTemplate> {
  return request<TaskTemplate>(`/templates/${templateId}/archive`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export async function rescheduleTask(
  taskId: string,
  version: number,
  plannedAt: string,
): Promise<TaskBundle> {
  return request<TaskBundle>(`/tasks/${taskId}/schedule`, {
    method: 'PATCH',
    body: JSON.stringify({ version, planned_at: plannedAt }),
  })
}

export async function updateRecurringSchedule(
  taskId: string,
  version: number,
  recurrenceRule: string,
  recurrenceTimezone: string,
  taskUpdates: {
    title?: string
    instruction_source?: string
    target_working_directory?: string
    executor?: ExecutorName
    executor_profile_id?: string | null
  } = {},
): Promise<TaskBundle> {
  return request<TaskBundle>(`/tasks/${taskId}/schedule`, {
    method: 'PATCH',
    body: JSON.stringify({
      version,
      ...taskUpdates,
      recurrence_rule: recurrenceRule,
      recurrence_timezone: recurrenceTimezone,
    }),
  })
}

export async function cancelTask(taskId: string, version: number): Promise<TaskBundle> {
  return request<TaskBundle>(`/tasks/${taskId}/schedule/cancel`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export async function archiveTask(taskId: string, version: number): Promise<Task> {
  return request<Task>(`/tasks/${taskId}/archive`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export async function unarchiveTask(taskId: string, version: number): Promise<TaskBundle> {
  return request<TaskBundle>(`/tasks/${taskId}/unarchive`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export async function pauseRecurringTask(taskId: string, version: number): Promise<TaskBundle> {
  return request<TaskBundle>(`/tasks/${taskId}/schedule/pause`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export async function resumeRecurringTask(taskId: string, version: number): Promise<TaskBundle> {
  return request<TaskBundle>(`/tasks/${taskId}/schedule/resume`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export async function runTaskNow(taskId: string): Promise<Run> {
  return request<Run>(`/tasks/${taskId}/run-now`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

async function requestList<T>(path: string, init: RequestInit = {}): Promise<ListEnvelope<T>> {
  const response = await rawRequest(path, init)
  return response as ListEnvelope<T>
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const payload = await rawRequest(path, init)
  return (payload as Envelope<T>).data
}

async function rawRequest(path: string, init: RequestInit = {}): Promise<unknown> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const message = payload?.error?.message ?? `Request failed with ${response.status}`
    throw new Error(message)
  }
  return payload
}
