import { describe, expect, it, vi } from 'vitest'

import {
  archiveTemplate,
  cancelOccurrence,
  createTask,
  createTemplate,
  getCalendar,
  getHistory,
  getRecurringTodo,
  listTemplates,
  pauseRecurringTask,
  preflightExecutor,
  resumeRecurringTask,
  updateOccurrence,
  updateRecurringSchedule,
  updateTask,
  updateTemplate,
} from '../api'

describe('api', () => {
  it('sends the selected executor when creating a task', async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ data: { task: null, schedule: null, run: null } }), {
          status: 200,
        }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await createTask({
      title: 'Debug task',
      instruction_source: 'Print the snapshot.',
      target_working_directory: '/tmp',
      executor: 'debug_printer',
      planned_at: '2026-04-25T10:00:00+08:00',
    })

    const init = fetchMock.mock.calls[0]?.[1]
    expect(init).toBeDefined()
    const body = JSON.parse(String(init?.body))
    expect(body.executor).toBe('debug_printer')
    expect(body.target_working_directory).toBe('/tmp')
    expect(body.execution_mode).toBe('one_time')
    expect(body.schedule).toEqual({
      schedule_type: 'single_run',
      planned_at: '2026-04-25T10:00:00+08:00',
    })
  })

  it('sends recurrence fields when creating a recurring task', async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ data: { task: null, schedule: null, run: null } }), {
          status: 200,
        }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await createTask({
      title: 'Daily task',
      instruction_source: 'Run every day.',
      target_working_directory: '/tmp',
      executor: 'debug_printer',
      execution_mode: 'recurring',
      recurrence_rule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
      recurrence_timezone: 'Asia/Hong_Kong',
    })

    const init = fetchMock.mock.calls[0]?.[1]
    const body = JSON.parse(String(init?.body))
    expect(body.execution_mode).toBe('recurring')
    expect(body.schedule).toEqual({
      schedule_type: 'recurring_rule',
      recurrence_rule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
      recurrence_timezone: 'Asia/Hong_Kong',
    })
  })

  it('requests executor preflight with the target workspace', async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(
          JSON.stringify({
            data: {
              executor: 'claude_code',
              status: 'available',
              code: 'executor_preflight_passed',
              message: 'Claude Code target workspace is available',
              details: { live: false },
            },
          }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await preflightExecutor({
      executor: 'claude_code',
      target_working_directory: '/tmp/project',
    })

    expect(result.status).toBe('available')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        '/executors/preflight?executor=claude_code&target_working_directory=%2Ftmp%2Fproject',
      ),
      expect.any(Object),
    )
  })

  it('sends history filters as query parameters', async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ data: [], meta: { total: 0 } }), {
          status: 200,
        }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const history = await getHistory({
      status: 'failed',
      execution_mode: 'one_time',
      limit: 25,
    })

    expect(history.meta.total).toBe(0)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/views/history?status=failed&execution_mode=one_time&limit=25'),
      expect.any(Object),
    )
  })

  it('sends recurring todo and lifecycle requests', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input)
      if (url.includes('/views/recurring-todo')) {
        return new Response(JSON.stringify({ data: [], meta: { total: 0 } }), {
          status: 200,
        })
      }
      return new Response(
        JSON.stringify({
          data: { task: null, schedule: null, run: null },
        }),
        { status: 200 },
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const todo = await getRecurringTodo({ include_paused: false, limit: 20 })
    await pauseRecurringTask('task-1', 3)
    await resumeRecurringTask('task-1', 4)
    await updateRecurringSchedule(
      'task-1',
      5,
      'RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=30',
      'Asia/Hong_Kong',
    )

    expect(todo.meta.total).toBe(0)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/views/recurring-todo?include_paused=false&limit=20'),
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-1/schedule/pause'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ version: 3 }),
      }),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-1/schedule/resume'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ version: 4 }),
      }),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-1/schedule'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          version: 5,
          recurrence_rule: 'RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=30',
          recurrence_timezone: 'Asia/Hong_Kong',
        }),
      }),
    )
  })

  it('sends calendar and occurrence scoped edit requests', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input)
      if (url.includes('/views/calendar')) {
        return new Response(JSON.stringify({ data: [], meta: { total: 0 } }), {
          status: 200,
        })
      }
      return new Response(
        JSON.stringify({
          data: {
            occurrence_override_id: 'ovr-1',
            task_id: 'task-1',
            schedule_id: 'sch-1',
            original_occurrence_at: '2026-04-28T00:00:00Z',
            override_occurrence_at: null,
            override_instruction_delta: null,
            override_status: 'active',
            created_at: '2026-04-27T00:00:00Z',
            updated_at: '2026-04-27T00:00:00Z',
          },
        }),
        { status: 200 },
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const calendar = await getCalendar({
      from: '2026-04-28T00:00:00+00:00',
      to: '2026-04-29T00:00:00+00:00',
      include_completed: true,
    })
    await updateOccurrence('task-1', {
      version: 3,
      original_occurrence_at: '2026-04-28T00:00:00+00:00',
      scope: 'this_occurrence_only',
      planned_at: '2026-04-28T02:00:00+00:00',
      instruction_source: 'Override',
    })
    await cancelOccurrence('task-1', 4, '2026-04-28T00:00:00+00:00')

    expect(calendar.meta.total).toBe(0)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/views/calendar?from=2026-04-28T00%3A00%3A00%2B00%3A00'),
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-1/occurrences/update'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          version: 3,
          original_occurrence_at: '2026-04-28T00:00:00+00:00',
          scope: 'this_occurrence_only',
          planned_at: '2026-04-28T02:00:00+00:00',
          instruction_source: 'Override',
        }),
      }),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-1/occurrences/cancel'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          version: 4,
          original_occurrence_at: '2026-04-28T00:00:00+00:00',
          scope: 'this_occurrence_only',
        }),
      }),
    )
  })

  it('sends task update requests', async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(
          JSON.stringify({
            data: {
              task_id: 'task-1',
              title: 'Updated Task',
              instruction_source: 'Updated instructions.',
              target_working_directory: '/tmp',
              execution_mode: 'one_time',
              task_status: 'scheduled',
              template_id: null,
              executor: 'debug_printer',
              version: 2,
              created_at: '2026-04-25T09:00:00+08:00',
              updated_at: '2026-04-25T09:00:00+08:00',
              archived_at: null,
            },
          }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await updateTask('task-1', {
      version: 1,
      title: 'Updated Task',
      instruction_source: 'Updated instructions.',
    })

    expect(result.title).toBe('Updated Task')
    expect(result.instruction_source).toBe('Updated instructions.')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-1'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          version: 1,
          title: 'Updated Task',
          instruction_source: 'Updated instructions.',
        }),
      }),
    )
  })

  it('sends template lifecycle requests', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input)
      if (url.includes('/templates') && (init?.method ?? 'GET') === 'GET') {
        return new Response(JSON.stringify({ data: [], meta: { total: 0 } }), { status: 200 })
      }
      return new Response(JSON.stringify({ data: templateResponse() }), { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const templates = await listTemplates({ limit: 100 })
    const created = await createTemplate({
      name: 'Research',
      description: null,
      instruction_source: 'Find updates',
      default_task_title: 'Research run',
      default_target_working_directory: '/tmp',
      default_executor: 'debug_printer',
    })
    await updateTemplate(created.template_id, {
      version: created.version,
      name: 'Updated research',
    })
    await archiveTemplate(created.template_id, created.version)

    expect(templates.meta.total).toBe(0)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/templates?limit=100'),
      expect.any(Object),
    )
    const createBody = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))
    expect(createBody.default_schedule_config.schedule_type).toBe('single_run')
    expect(createBody.default_target_working_directory).toBe('/tmp')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/templates/tpl-1/archive'),
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

function templateResponse() {
  return {
    template_id: 'tpl-1',
    name: 'Research',
    description: null,
    instruction_source: 'Find updates',
    default_task_title: 'Research run',
    default_target_working_directory: '/tmp',
    default_execution_mode: 'one_time',
    default_schedule_config: {
      schedule_type: 'single_run',
      planned_at: null,
      recurrence_rule: null,
      recurrence_timezone: null,
    },
    default_executor: 'debug_printer',
    version: 1,
    created_at: '2026-04-25T09:00:00+08:00',
    updated_at: '2026-04-25T09:00:00+08:00',
    archived_at: null,
  }
}
