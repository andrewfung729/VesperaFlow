import { describe, expect, it, vi } from 'vitest'

import { archiveTemplate, createTask, createTemplate, getHistory, listTemplates, updateTemplate } from '../api'

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
