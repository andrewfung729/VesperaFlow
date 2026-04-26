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
    stubFetch()
    const { wrapper } = await mountAppAt('/compose')

    expect(wrapper.text()).toContain('Create One-Time Task')
    expect(wrapper.get('nav').text()).toContain('One-Time Board')
    expect(wrapper.get('nav').text()).toContain('Templates')
    expect(wrapper.get('nav').text()).toContain('History')
    expect(wrapper.text()).toContain('Debug Printer')
    expect(wrapper.text()).toContain('Claude Code')
  })

  it('prefills the composer from a selected template', async () => {
    stubFetch()

    const { wrapper } = await mountAppAt('/compose?templateId=tpl-1')

    expect((wrapper.find('select').element as HTMLSelectElement).value).toBe('tpl-1')
    expect(
      (wrapper.find('input[placeholder="Nightly Deep Research"]').element as HTMLInputElement)
        .value,
    ).toBe('Template Task')
    expect(
      (wrapper.find('input[placeholder="/Users/you/project"]').element as HTMLInputElement)
        .value,
    ).toBe('/tmp')
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe(
      'Template instructions',
    )
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

  it('renders the history route and fetches terminal runs', async () => {
    const fetchMock = stubFetch()

    const { wrapper } = await mountAppAt('/history')

    expect(wrapper.text()).toContain('Run History')
    expect(wrapper.text()).toContain('Failed Task')
    expect(wrapper.text()).toContain('Executor failed')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/views/history?limit=50'),
      expect.any(Object),
    )
  })

  it('renders the empty history state', async () => {
    stubFetch({ historyItems: [] })

    const { wrapper } = await mountAppAt('/history')

    expect(wrapper.text()).toContain('No completed or failed runs')
  })

  it('renders the templates route and links templates into the composer', async () => {
    const fetchMock = stubFetch()

    const { router, wrapper } = await mountAppAt('/templates')

    expect(wrapper.text()).toContain('Task Templates')
    expect(wrapper.text()).toContain('Research Template')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/templates?limit=100'),
      expect.any(Object),
    )

    const useButton = wrapper.findAll('button').find((button) => button.text() === 'Use')
    if (!useButton) throw new Error('Expected Use button to render')

    await useButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('compose')
    expect(router.currentRoute.value.query.templateId).toBe('tpl-1')
    expect(wrapper.text()).toContain('Create One-Time Task')
  })

  it('navigates to task detail after creating a task', async () => {
    stubFetch()
    const { router, wrapper } = await mountAppAt('/compose')

    await wrapper.get('input[type="text"]').setValue('Created Task')
    await wrapper.get('textarea').setValue('Run this later.')
    const targetInput = wrapper
      .findAll('input[type="text"]')
      .find((input) => input.attributes('placeholder') === '/Users/you/project')
    if (!targetInput) throw new Error('Expected target directory input to render')
    await targetInput.setValue('/tmp')
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

  it('navigates to task detail from a history item with run context', async () => {
    stubFetch()
    const { router, wrapper } = await mountAppAt('/history')

    const historyItemButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Failed Task'))
    if (!historyItemButton) throw new Error('Expected history item button to render')

    await historyItemButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('task-detail')
    expect(router.currentRoute.value.params.taskId).toBe('task-1')
    expect(router.currentRoute.value.query.runId).toBe('run-1')
    expect(wrapper.text()).toContain('Selected Run')
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

function stubFetch(options: { historyItems?: unknown[] } = {}) {
  const historyItems = options.historyItems ?? [
    {
      history_item_id: 'hist_run-1',
      run_id: 'run-1',
      task_id: 'task-1',
      title: 'Failed Task',
      execution_mode: 'one_time',
      run_status: 'failed',
      finished_at: '2026-04-25T11:00:00+08:00',
      result_summary: null,
      failure_reason: 'Executor failed',
    },
  ]

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

    if (url.includes('/views/history')) {
      return jsonResponse(historyItems, { total: historyItems.length })
    }

    if (url.includes('/templates') && method === 'GET') {
      return jsonResponse([templateResponse()], { total: 1 })
    }

    if (url.endsWith('/templates') && method === 'POST') {
      return jsonResponse(templateResponse())
    }

    if (url.includes('/templates/tpl-1') && method === 'PATCH') {
      return jsonResponse({ ...templateResponse(), name: 'Updated Template', version: 2 })
    }

    if (url.includes('/templates/tpl-1/archive') && method === 'POST') {
      return jsonResponse({
        ...templateResponse(),
        archived_at: '2026-04-25T10:00:00+08:00',
      })
    }

    if (url.endsWith('/tasks') && method === 'POST') {
      return jsonResponse({
        task: {
          task_id: 'task-1',
          title: 'Created Task',
          instruction_source: 'Run this later.',
          target_working_directory: '/tmp',
          execution_mode: 'one_time',
          task_status: 'scheduled',
          template_id: null,
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
          target_working_directory: '/tmp',
          execution_mode: 'one_time',
          task_status: 'scheduled',
          template_id: null,
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
        latest_run: {
          run_id: 'run-1',
          task_id: 'task-1',
          schedule_id: 'schedule-1',
          run_status: 'failed',
          planned_start_at: '2026-04-25T10:00:00+08:00',
          actual_start_at: '2026-04-25T10:01:00+08:00',
          finished_at: '2026-04-25T11:00:00+08:00',
          result_summary: null,
          failure_reason: 'Executor failed',
        },
        runs: [
          {
            run_id: 'run-1',
            task_id: 'task-1',
            schedule_id: 'schedule-1',
            run_status: 'failed',
            planned_start_at: '2026-04-25T10:00:00+08:00',
            actual_start_at: '2026-04-25T10:01:00+08:00',
            finished_at: '2026-04-25T11:00:00+08:00',
            result_summary: null,
            failure_reason: 'Executor failed',
          },
        ],
      })
    }

    return new Response(JSON.stringify({ error: { message: `Unhandled ${url}` } }), {
      status: 404,
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function templateResponse() {
  return {
    template_id: 'tpl-1',
    name: 'Research Template',
    description: 'Reusable research',
    instruction_source: 'Template instructions',
    default_task_title: 'Template Task',
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

function jsonResponse(data: unknown, meta?: { total: number }) {
  return new Response(JSON.stringify({ data, ...(meta ? { meta } : {}) }), {
    status: 200,
  })
}
