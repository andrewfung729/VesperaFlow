export type TaskStatus =
  | 'scheduled'
  | 'paused'
  | 'running'
  | 'completed'
  | 'failed'
  | 'canceled'
  | 'archived'

export type RunStatus = 'planned' | 'queued' | 'running' | 'completed' | 'failed' | 'canceled'
export type ExecutorName = 'claude_code' | 'debug_printer'

export interface Task {
  task_id: string
  title: string
  instruction_source: string
  execution_mode: 'one_time'
  task_status: TaskStatus
  executor: ExecutorName
  version: number
  created_at: string
  updated_at: string
  archived_at: string | null
}

export interface Schedule {
  schedule_id: string
  task_id: string
  schedule_type: 'single_run'
  schedule_status: 'pending' | 'active' | 'paused' | 'completed' | 'canceled'
  planned_at: string | null
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
}

export interface TaskBundle {
  task: Task
  schedule: Schedule
  run: Run | null
}

export interface TaskDetail {
  task: Task
  schedule: Schedule | null
  latest_run: Run | null
  runs: Run[]
}

export interface KanbanCard {
  card_id: string
  task_id: string
  title: string
  kanban_column: string
  next_run_at: string | null
  latest_run_status: RunStatus | null
  result_summary: string | null
}

export interface KanbanBoard {
  columns: Record<string, KanbanCard[]>
}

interface Envelope<T> {
  data: T
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export async function createTask(payload: {
  title: string
  instruction_source: string
  executor: ExecutorName
  planned_at: string
}): Promise<TaskBundle> {
  return request<TaskBundle>('/tasks', {
    method: 'POST',
    body: JSON.stringify({
      title: payload.title,
      instruction_source: payload.instruction_source,
      execution_mode: 'one_time',
      executor: payload.executor,
      schedule: {
        schedule_type: 'single_run',
        planned_at: payload.planned_at,
      },
    }),
  })
}

export async function getKanban(): Promise<KanbanBoard> {
  return request<KanbanBoard>('/views/kanban')
}

export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(`/tasks/${taskId}/detail`)
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

export async function cancelTask(taskId: string, version: number): Promise<TaskBundle> {
  return request<TaskBundle>(`/tasks/${taskId}/schedule/cancel`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
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
  return (payload as Envelope<T>).data
}
