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
    expect(wrapper.get('nav').text()).toContain('Recurring Todo')
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

  it('renders the recurring todo route and pauses scheduled items', async () => {
    const fetchMock = stubFetch()

    const { wrapper } = await mountAppAt('/recurring')

    expect(wrapper.text()).toContain('Recurring Tasks')
    expect(wrapper.text()).toContain('Active Recurring')
    expect(wrapper.text()).toContain('Executor failed')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/views/recurring-todo?limit=100'),
      expect.any(Object),
    )

    const pauseButton = wrapper.findAll('button').find((button) => button.text() === 'Pause')
    if (!pauseButton) throw new Error('Expected Pause button to render')
    await pauseButton.trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-recurring-1/schedule/pause'),
      expect.objectContaining({ method: 'POST' }),
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

  it('creates a recurring daily task from the composer', async () => {
    const fetchMock = stubFetch()
    const { router, wrapper } = await mountAppAt('/compose?mode=recurring')

    await wrapper.get('input[placeholder="Nightly Deep Research"]').setValue('Daily Recurring')
    await wrapper.get('textarea').setValue('Run this daily.')
    const targetInput = wrapper
      .findAll('input[type="text"]')
      .find((input) => input.attributes('placeholder') === '/Users/you/project')
    if (!targetInput) throw new Error('Expected target directory input to render')
    await targetInput.setValue('/tmp')
    await wrapper.get('input[type="time"]').setValue('08:30')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input).endsWith('/tasks') && init?.method === 'POST',
    )
    if (!createCall) throw new Error('Expected task create request')
    const body = JSON.parse(String(createCall[1]?.body))
    expect(body.execution_mode).toBe('recurring')
    expect(body.schedule.schedule_type).toBe('recurring_rule')
    expect(body.schedule.recurrence_rule).toBe('RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=30')
    expect(body.schedule.recurrence_timezone).toBeTruthy()
    expect(body.schedule.planned_at).toBeUndefined()
    expect(router.currentRoute.value.name).toBe('task-detail')
    expect(router.currentRoute.value.params.taskId).toBe('task-recurring-created')
  })

  it('creates a recurring weekly task from the composer', async () => {
    const fetchMock = stubFetch()
    const { wrapper } = await mountAppAt('/compose?mode=recurring')

    await wrapper.get('input[placeholder="Nightly Deep Research"]').setValue('Weekly Recurring')
    await wrapper.get('textarea').setValue('Run this weekly.')
    const targetInput = wrapper
      .findAll('input[type="text"]')
      .find((input) => input.attributes('placeholder') === '/Users/you/project')
    if (!targetInput) throw new Error('Expected target directory input to render')
    await targetInput.setValue('/tmp')
    const cadenceSelect = wrapper.findAll('select')[1]
    if (!cadenceSelect) throw new Error('Expected cadence select to render')
    await cadenceSelect.setValue('weekly')
    const wedButton = wrapper.findAll('button').find((button) => button.text() === 'Wed')
    if (!wedButton) throw new Error('Expected Wed button to render')
    await wedButton.trigger('click')
    await wrapper.get('input[type="time"]').setValue('09:15')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input).endsWith('/tasks') && init?.method === 'POST',
    )
    if (!createCall) throw new Error('Expected task create request')
    const body = JSON.parse(String(createCall[1]?.body))
    expect(body.schedule.recurrence_rule).toBe(
      'RRULE:FREQ=WEEKLY;BYDAY=MO,WE;BYHOUR=9;BYMINUTE=15',
    )
  })

  it('checks Claude Code availability before creating a Claude task', async () => {
    const fetchMock = stubFetch()
    const { wrapper } = await mountAppAt('/compose')

    await wrapper.get('input[placeholder="Nightly Deep Research"]').setValue('Claude Task')
    await wrapper.get('textarea').setValue('Run this with Claude.')
    const targetInput = wrapper
      .findAll('input[type="text"]')
      .find((input) => input.attributes('placeholder') === '/Users/you/project')
    if (!targetInput) throw new Error('Expected target directory input to render')
    await targetInput.setValue('/tmp')
    const executorSelect = wrapper.findAll('select')[1]
    if (!executorSelect) throw new Error('Expected executor select to render')
    await executorSelect.setValue('claude_code')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        '/executors/preflight?executor=claude_code&target_working_directory=%2Ftmp',
      ),
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks'),
      expect.objectContaining({ method: 'POST' }),
    )
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

  it('links the empty recurring todo state to recurring composer mode', async () => {
    stubFetch({ recurringItems: [] })
    const { router, wrapper } = await mountAppAt('/recurring')

    expect(wrapper.text()).toContain('No recurring tasks yet')
    const createButton = wrapper
      .findAll('button')
      .find((button) => button.text() === 'Create Recurring Task')
    if (!createButton) throw new Error('Expected create recurring task button')

    await createButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('compose')
    expect(router.currentRoute.value.query.mode).toBe('recurring')
    expect(wrapper.text()).toContain('Create Recurring Task')
  })

  it('opens the recurring detail editor from recurring todo', async () => {
    stubFetch()
    const { router, wrapper } = await mountAppAt('/recurring')

    const editButton = wrapper.findAll('button').find((button) => button.text() === 'Edit')
    if (!editButton) throw new Error('Expected Edit button to render')

    await editButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('task-detail')
    expect(router.currentRoute.value.params.taskId).toBe('task-recurring-1')
    expect(router.currentRoute.value.query.edit).toBe('recurrence')
    expect(wrapper.text()).toContain('Save Recurrence')
  })

  it('updates a recurring schedule from task detail', async () => {
    const fetchMock = stubFetch()
    const { wrapper } = await mountAppAt('/tasks/task-recurring-1?edit=recurrence')

    await wrapper.get('input[type="time"]').setValue('10:15')
    const saveButton = wrapper
      .findAll('button')
      .find((button) => button.text() === 'Save Recurrence')
    if (!saveButton) throw new Error('Expected Save Recurrence button to render')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-recurring-1/schedule'),
      expect.objectContaining({
        method: 'PATCH',
        body: expect.stringContaining('RRULE:FREQ=DAILY;BYHOUR=10;BYMINUTE=15'),
      }),
    )
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

interface StubFetchOptions {
  historyItems?: unknown[]
  recurringItems?: unknown[]
}

function stubFetch(options: StubFetchOptions = {}) {
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
      occurrence_key: null,
    },
  ]
  const recurringItems = options.recurringItems ?? [
    {
      item_id: 'todo_task-recurring-1',
      task_id: 'task-recurring-1',
      title: 'Active Recurring',
      recurrence_rule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
      recurrence_timezone: 'Asia/Hong_Kong',
      next_run_at: '2026-04-26T08:00:00+08:00',
      schedule_status: 'active',
      task_status: 'scheduled',
      schedule_version: 2,
      latest_run_id: 'run-recurring-1',
      latest_run_outcome: 'failed',
      latest_run_finished_at: '2026-04-25T11:00:00+08:00',
      result_summary: null,
      failure_reason: 'Executor failed',
    },
    {
      item_id: 'todo_task-recurring-2',
      task_id: 'task-recurring-2',
      title: 'Paused Recurring',
      recurrence_rule: 'RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=30',
      recurrence_timezone: 'Asia/Hong_Kong',
      next_run_at: null,
      schedule_status: 'paused',
      task_status: 'paused',
      schedule_version: 4,
      latest_run_id: null,
      latest_run_outcome: null,
      latest_run_finished_at: null,
      result_summary: null,
      failure_reason: null,
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

    if (url.includes('/views/recurring-todo')) {
      return jsonResponse(recurringItems, { total: recurringItems.length })
    }

    if (url.includes('/executors/preflight')) {
      return jsonResponse({
        executor: 'claude_code',
        status: 'available',
        code: 'executor_preflight_passed',
        message: 'Claude Code target workspace is available',
        details: { live: false },
      })
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
      const requestBody = JSON.parse(String(init?.body))
      const isRecurring = requestBody.execution_mode === 'recurring'
      return jsonResponse({
        task: {
          task_id: isRecurring ? 'task-recurring-created' : 'task-1',
          title: requestBody.title ?? 'Created Task',
          instruction_source: 'Run this later.',
          target_working_directory: '/tmp',
          execution_mode: requestBody.execution_mode,
          task_status: 'scheduled',
          template_id: null,
          executor: 'debug_printer',
          version: 1,
          created_at: '2026-04-25T09:00:00+08:00',
          updated_at: '2026-04-25T09:00:00+08:00',
          archived_at: null,
        },
        schedule: isRecurring
          ? {
              schedule_id: 'schedule-recurring-created',
              task_id: 'task-recurring-created',
              schedule_type: 'recurring_rule',
              schedule_status: 'active',
              planned_at: null,
              recurrence_rule: requestBody.schedule.recurrence_rule,
              recurrence_timezone: requestBody.schedule.recurrence_timezone,
              next_run_at: '2026-04-26T08:00:00+08:00',
              version: 1,
            }
          : null,
        run: null,
      })
    }

    if (
      (url.includes('/tasks/task-recurring-1/schedule/pause') ||
        url.includes('/tasks/task-recurring-2/schedule/resume')) &&
      method === 'POST'
    ) {
      return jsonResponse({
        task: null,
        schedule: null,
        run: null,
      })
    }

    if (url.includes('/tasks/task-recurring-1/schedule') && method === 'PATCH') {
      return jsonResponse({
        task: recurringTaskResponse('task-recurring-1', 'Active Recurring'),
        schedule: recurringScheduleResponse('task-recurring-1', {
          version: 3,
          recurrence_rule: 'RRULE:FREQ=DAILY;BYHOUR=10;BYMINUTE=15',
        }),
        run: null,
      })
    }

    if (
      url.endsWith('/tasks/task-recurring-1/detail') ||
      url.endsWith('/tasks/task-recurring-created/detail')
    ) {
      const taskId = url.endsWith('/tasks/task-recurring-created/detail')
        ? 'task-recurring-created'
        : 'task-recurring-1'
      return jsonResponse({
        task: recurringTaskResponse(taskId, 'Active Recurring'),
        schedule: recurringScheduleResponse(taskId),
        latest_run: null,
        runs: [],
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
          occurrence_key: null,
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
            occurrence_key: null,
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

function recurringTaskResponse(taskId: string, title: string) {
  return {
    task_id: taskId,
    title,
    instruction_source: 'Run this on a recurring schedule.',
    target_working_directory: '/tmp',
    execution_mode: 'recurring',
    task_status: 'scheduled',
    template_id: null,
    executor: 'debug_printer',
    version: 1,
    created_at: '2026-04-25T09:00:00+08:00',
    updated_at: '2026-04-25T09:00:00+08:00',
    archived_at: null,
  }
}

function recurringScheduleResponse(
  taskId: string,
  overrides: Partial<Record<string, unknown>> = {},
) {
  return {
    schedule_id: `schedule-${taskId}`,
    task_id: taskId,
    schedule_type: 'recurring_rule',
    schedule_status: 'active',
    planned_at: null,
    recurrence_rule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
    recurrence_timezone: 'Asia/Hong_Kong',
    next_run_at: '2026-04-26T08:00:00+08:00',
    version: 2,
    ...overrides,
  }
}

function jsonResponse(data: unknown, meta?: { total: number }) {
  return new Response(JSON.stringify({ data, ...(meta ? { meta } : {}) }), {
    status: 200,
  })
}
