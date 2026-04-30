import { afterEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import { routes } from '@/router'
import RunOutcomeReaderView from '@/views/RunOutcomeReaderView.vue'

function stubFetch() {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = String(input)
    if (url.includes('/tasks/task-recurring-1/runs/run-recurring-1/reader')) {
      return new Response(
        JSON.stringify({
          data: {
            task: {
              task_id: 'task-recurring-1',
              title: 'Active Recurring',
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
            },
            schedule: {
              schedule_id: 'schedule-task-recurring-1',
              task_id: 'task-recurring-1',
              schedule_type: 'recurring_rule',
              schedule_status: 'active',
              planned_at: null,
              recurrence_rule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
              recurrence_timezone: 'Asia/Hong_Kong',
              next_run_at: '2026-04-26T08:00:00+08:00',
              version: 2,
            },
            run: {
              run_id: 'run-recurring-1',
              task_id: 'task-recurring-1',
              schedule_id: 'schedule-task-recurring-1',
              run_status: 'completed',
              planned_start_at: '2026-04-26T08:00:00+08:00',
              actual_start_at: '2026-04-26T08:01:00+08:00',
              finished_at: '2026-04-26T08:30:00+08:00',
              result_summary: 'Daily recurring completed',
              failure_reason: null,
              occurrence_key: '20260426T000000Z',
            },
            previous_run_id: null,
            next_run_id: null,
          },
        }),
        { status: 200 },
      )
    }
    if (url.includes('/tasks/task-recurring-1/runs/run-recurring-2/reader')) {
      return new Response(
        JSON.stringify({
          data: {
            task: {
              task_id: 'task-recurring-1',
              title: 'Active Recurring',
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
            },
            schedule: {
              schedule_id: 'schedule-task-recurring-1',
              task_id: 'task-recurring-1',
              schedule_type: 'recurring_rule',
              schedule_status: 'active',
              planned_at: null,
              recurrence_rule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
              recurrence_timezone: 'Asia/Hong_Kong',
              next_run_at: '2026-04-27T08:00:00+08:00',
              version: 2,
            },
            run: {
              run_id: 'run-recurring-2',
              task_id: 'task-recurring-1',
              schedule_id: 'schedule-task-recurring-1',
              run_status: 'failed',
              planned_start_at: '2026-04-25T08:00:00+08:00',
              actual_start_at: '2026-04-25T08:01:00+08:00',
              finished_at: '2026-04-25T08:30:00+08:00',
              result_summary: null,
              failure_reason: 'Recurring executor failed',
              occurrence_key: '20260425T000000Z',
            },
            previous_run_id: 'run-recurring-1',
            next_run_id: null,
          },
        }),
        { status: 200 },
      )
    }
    return new Response(JSON.stringify({ error: { message: 'Unhandled' } }), { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('RunOutcomeReaderView', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('renders a wider markdown container instead of max-w-prose', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(RunOutcomeReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const markdownContainer = wrapper.find('[data-testid="reader-body"]')
    expect(markdownContainer.exists()).toBe(true)
    const classAttr = markdownContainer.attributes('class') ?? ''
    expect(classAttr).not.toContain('max-w-prose')
    expect(classAttr).toContain('max-w-[88ch]')
  })

  it('updates markdown size class when font size buttons are clicked', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(RunOutcomeReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const markdownContainer = wrapper.find('[data-testid="reader-body"]')
    expect(markdownContainer.classes()).toContain('reader-font-md')

    const increaseButton = wrapper.find('button[aria-label="Increase font size"]')
    expect(increaseButton.exists()).toBe(true)
    await increaseButton.trigger('click')
    await flushPromises()

    expect(markdownContainer.classes()).toContain('reader-font-lg')
  })

  it('persists font size preference through remount', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })

    const wrapper1 = mount(RunOutcomeReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    // Reset to a known state by decreasing to sm, then increase to lg
    const decreaseButton = wrapper1.find('button[aria-label="Decrease font size"]')
    for (let i = 0; i < 3; i++) {
      if (decreaseButton.attributes('disabled') !== undefined) break
      await decreaseButton.trigger('click')
      await flushPromises()
    }

    const increaseButton = wrapper1.find('button[aria-label="Increase font size"]')
    await increaseButton.trigger('click')
    await flushPromises()
    await increaseButton.trigger('click')
    await flushPromises()

    expect(localStorage.getItem('vesperaflow.reader.fontSize')).toBe('lg')

    const wrapper2 = mount(RunOutcomeReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const markdownContainer = wrapper2.find('[data-testid="reader-body"]')
    expect(markdownContainer.classes()).toContain('reader-font-lg')
  })
})
