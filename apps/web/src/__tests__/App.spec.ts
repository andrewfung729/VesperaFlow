import { afterEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '../App.vue'
import { routes } from '../router'

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the composer route', async () => {
    const { wrapper } = await mountAppAt('/compose')

    expect(wrapper.text()).toContain('Create One-Time Task')
    expect(wrapper.get('nav').text()).toContain('One-Time Board')
    expect(wrapper.find('select').text()).toContain('Debug Printer')
    expect(wrapper.find('select').text()).toContain('Claude Code')
  })

  it('renders the board route and fetches kanban data', async () => {
    const fetchMock = stubFetch()

    const { wrapper } = await mountAppAt('/board')

    expect(wrapper.text()).toContain('One-Time Tasks')
    expect(wrapper.text()).toContain('Board Task')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/views/kanban'),
      expect.any(Object),
    )
  })

  it('renders a direct task detail route', async () => {
    const fetchMock = stubFetch()

    const { wrapper } = await mountAppAt('/tasks/task-1')

    expect(wrapper.text()).toContain('Detailed Task')
    expect(wrapper.text()).toContain('Executor: debug_printer')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-1/detail'),
      expect.any(Object),
    )
  })

  it('navigates to task detail after creating a task', async () => {
    stubFetch()
    const { router, wrapper } = await mountAppAt('/compose')

    await wrapper.get('input[type="text"]').setValue('Created Task')
    await wrapper.get('textarea').setValue('Run this later.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('task-detail')
    expect(router.currentRoute.value.params.taskId).toBe('task-1')
    expect(wrapper.text()).toContain('Detailed Task')
  })

  it('navigates to task detail from a board card', async () => {
    stubFetch()
    const { router, wrapper } = await mountAppAt('/board')

    const boardTaskButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Board Task'))
    if (!boardTaskButton) throw new Error('Expected board task button to render')

    await boardTaskButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('task-detail')
    expect(router.currentRoute.value.params.taskId).toBe('task-1')
    expect(wrapper.text()).toContain('Detailed Task')
  })
})

async function mountAppAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })
  const wrapper = mount(App, {
    global: {
      plugins: [router],
    },
  })

  await router.push(path)
  await router.isReady()
  await flushPromises()

  return { router, wrapper }
}

function stubFetch() {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'

    if (url.endsWith('/views/kanban')) {
      return jsonResponse({
        columns: {
          upcoming: [
            {
              card_id: 'card-1',
              task_id: 'task-1',
              title: 'Board Task',
              kanban_column: 'upcoming',
              next_run_at: '2026-04-25T10:00:00+08:00',
              latest_run_status: null,
              result_summary: null,
            },
          ],
          running: [],
          completed: [],
          failed: [],
          canceled: [],
        },
      })
    }

    if (url.endsWith('/tasks') && method === 'POST') {
      return jsonResponse({
        task: {
          task_id: 'task-1',
          title: 'Created Task',
          instruction_source: 'Run this later.',
          execution_mode: 'one_time',
          task_status: 'scheduled',
          executor: 'debug_printer',
          version: 1,
          created_at: '2026-04-25T09:00:00+08:00',
          updated_at: '2026-04-25T09:00:00+08:00',
          archived_at: null,
        },
        schedule: null,
        run: null,
      })
    }

    if (url.endsWith('/tasks/task-1/detail')) {
      return jsonResponse({
        task: {
          task_id: 'task-1',
          title: 'Detailed Task',
          instruction_source: 'Run this later.',
          execution_mode: 'one_time',
          task_status: 'scheduled',
          executor: 'debug_printer',
          version: 1,
          created_at: '2026-04-25T09:00:00+08:00',
          updated_at: '2026-04-25T09:00:00+08:00',
          archived_at: null,
        },
        schedule: {
          schedule_id: 'schedule-1',
          task_id: 'task-1',
          schedule_type: 'single_run',
          schedule_status: 'pending',
          planned_at: '2026-04-25T10:00:00+08:00',
          next_run_at: '2026-04-25T10:00:00+08:00',
          version: 1,
        },
        latest_run: null,
        runs: [],
      })
    }

    return new Response(JSON.stringify({ error: { message: `Unhandled ${url}` } }), {
      status: 404,
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify({ data }), { status: 200 })
}
