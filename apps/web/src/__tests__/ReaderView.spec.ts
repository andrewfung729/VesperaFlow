import { afterEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import { routes } from '@/router'
import ReaderView from '@/views/ReaderView.vue'

function stubFetch() {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = String(input)
    if (url.includes('/tasks/task-recurring-1/runs/run-recurring-1')) {
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
              executor_profile_id: 'debug_printer',
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
              instruction_source_snapshot: '# Snapshot\n\nRun this on a recurring schedule.',
              result_summary: 'Daily recurring completed',
              failure_reason: null,
              external_execution_ref: 'workflow-1',
              occurrence_key: '20260426T000000Z',
              created_at: '2026-04-26T08:00:00+08:00',
              updated_at: '2026-04-26T08:30:00+08:00',
            },
            previous_run_id: null,
            next_run_id: 'run-recurring-2',
          },
        }),
        { status: 200 },
      )
    }
    if (url.includes('/tasks/task-recurring-1/runs/run-recurring-2')) {
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
              executor_profile_id: 'debug_printer',
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
              instruction_source_snapshot: 'Previous snapshot',
              result_summary: null,
              failure_reason: 'Recurring executor failed',
              external_execution_ref: 'workflow-2',
              occurrence_key: '20260425T000000Z',
              created_at: '2026-04-25T08:00:00+08:00',
              updated_at: '2026-04-25T08:30:00+08:00',
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

describe('ReaderView', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('renders a markdown container aligned to max-w-5xl outer wrapper', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const article = wrapper.find('article.max-w-5xl')
    expect(article.exists()).toBe(true)

    const markdownContainer = wrapper.find('[data-testid="reader-body"]')
    expect(markdownContainer.exists()).toBe(true)
    const classAttr = markdownContainer.attributes('class') ?? ''
    expect(classAttr).not.toContain('max-w-prose')

    wrapper.unmount()
  })

  it('defaults to lg font size and updates when buttons are clicked', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const markdownContainer = wrapper.find('[data-testid="reader-body"]')
    expect(markdownContainer.classes()).toContain('reader-font-lg')

    const increaseButton = wrapper.find('button[aria-label="Increase font size"]')
    expect(increaseButton.exists()).toBe(true)
    await increaseButton.trigger('click')
    await flushPromises()

    expect(markdownContainer.classes()).toContain('reader-font-xl')

    wrapper.unmount()
  })

  it('persists font size preference through remount', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })

    const wrapper1 = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    // Reset to a known state by decreasing to sm, then increase to md
    const decreaseButton = wrapper1.find('button[aria-label="Decrease font size"]')
    for (let i = 0; i < 4; i++) {
      if (decreaseButton.attributes('disabled') !== undefined) break
      await decreaseButton.trigger('click')
      await flushPromises()
    }

    const increaseButton = wrapper1.find('button[aria-label="Increase font size"]')
    await increaseButton.trigger('click')
    await flushPromises()

    expect(localStorage.getItem('vesperaflow.reader.fontSize')).toBe('md')

    const wrapper2 = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const markdownContainer = wrapper2.find('[data-testid="reader-body"]')
    expect(markdownContainer.classes()).toContain('reader-font-md')

    wrapper1.unmount()
    wrapper2.unmount()
  })

  it('renders instruction and result without the run timeline', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).not.toContain('Timeline')
    expect(wrapper.text()).toContain('Snapshot')
    expect(wrapper.text()).toContain('Daily recurring completed')
    expect(wrapper.text()).not.toContain('Executor invocation completed successfully.')

    wrapper.unmount()
  })

  it('returns to the matching run detail route', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const backButton = wrapper.findAll('button').find((button) => button.text() === 'Back to Run')
    if (!backButton) throw new Error('Expected Back to Run button')
    await backButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('run-detail')
    expect(router.currentRoute.value.params.taskId).toBe('task-recurring-1')
    expect(router.currentRoute.value.params.runId).toBe('run-recurring-1')

    wrapper.unmount()
  })

  it('shows metadata summary by default and toggles details on click', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const summary = wrapper.find('[data-testid="metadata-summary"]')
    expect(summary.exists()).toBe(true)

    const details = wrapper.find('[data-testid="metadata-details"]')
    expect(details.exists()).toBe(false)

    const toggle = wrapper.find('[data-testid="metadata-details-toggle"]')
    expect(toggle.exists()).toBe(true)
    expect(toggle.text()).toBe('Details')

    await toggle.trigger('click')
    await flushPromises()

    const expandedDetails = wrapper.find('[data-testid="metadata-details"]')
    expect(expandedDetails.exists()).toBe(true)
    expect(toggle.text()).toBe('Hide Details')

    // Check the 5-column grid labels
    expect(expandedDetails.text()).toContain('Planned')
    expect(expandedDetails.text()).toContain('Started')
    expect(expandedDetails.text()).toContain('Finished')
    expect(expandedDetails.text()).toContain('Duration')
    expect(expandedDetails.text()).toContain('Status')

    wrapper.unmount()
  })

  it('hides toolbar on scroll down and shows on scroll up', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const toolbar = wrapper.find('[data-testid="reader-toolbar"]')
    expect(toolbar.exists()).toBe(true)
    expect(toolbar.attributes('data-hidden')).toBe('false')

    // Scroll down past threshold
    Object.defineProperty(window, 'scrollY', { value: 100, writable: true })
    window.dispatchEvent(new Event('scroll'))
    await new Promise((r) => requestAnimationFrame(r))

    Object.defineProperty(window, 'scrollY', { value: 120, writable: true })
    window.dispatchEvent(new Event('scroll'))
    await new Promise((r) => requestAnimationFrame(r))
    await flushPromises()

    expect(toolbar.attributes('data-hidden')).toBe('true')

    // Scroll up
    Object.defineProperty(window, 'scrollY', { value: 110, writable: true })
    window.dispatchEvent(new Event('scroll'))
    await new Promise((r) => requestAnimationFrame(r))
    await flushPromises()

    expect(toolbar.attributes('data-hidden')).toBe('false')

    wrapper.unmount()
  })

  it('changes font size with +/- keyboard shortcuts', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    const body = wrapper.find('[data-testid="reader-body"]')

    // Reset to a known state (sm) by decreasing until disabled
    const decreaseButton = wrapper.find('button[aria-label="Decrease font size"]')
    for (let i = 0; i < 4; i++) {
      if (decreaseButton.attributes('disabled') !== undefined) break
      await decreaseButton.trigger('click')
      await flushPromises()
    }
    expect(body.classes()).toContain('reader-font-sm')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: '+' }))
    await flushPromises()
    expect(body.classes()).toContain('reader-font-md')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: '-' }))
    await flushPromises()
    expect(body.classes()).toContain('reader-font-sm')

    wrapper.unmount()
  })

  it('navigates to next run with ArrowRight keyboard shortcut', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('run-reader')
    expect(router.currentRoute.value.params.runId).toBe('run-recurring-2')

    wrapper.unmount()
  })

  it('navigates to previous run with ArrowLeft keyboard shortcut', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-2' },
    })
    await flushPromises()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }))
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('run-reader')
    expect(router.currentRoute.value.params.runId).toBe('run-recurring-1')

    wrapper.unmount()
  })

  it('goes back to run detail with Escape keyboard shortcut', async () => {
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('run-detail')
    expect(router.currentRoute.value.params.runId).toBe('run-recurring-1')

    wrapper.unmount()
  })

  it('copies outcome with c keyboard shortcut', async () => {
    const writeText = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    stubFetch()
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(ReaderView, {
      global: { plugins: [router] },
      props: { taskId: 'task-recurring-1', runId: 'run-recurring-1' },
    })
    await flushPromises()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'c' }))
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('Daily recurring completed')

    wrapper.unmount()
  })
})
