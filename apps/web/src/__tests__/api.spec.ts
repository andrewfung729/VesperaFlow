import { describe, expect, it, vi } from 'vitest'

import { createTask } from '../api'

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
})
