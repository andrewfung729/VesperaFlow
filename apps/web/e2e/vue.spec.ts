import { test, expect, type Page } from '@playwright/test'

// See here how to get started:
// https://playwright.dev/docs/intro
test('visits the app root url', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toHaveText('Planned AI Work')
  await expect(page.getByRole('link', { name: 'Composer' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Templates' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Recurring Todo' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Calendar' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'History' })).toBeVisible()
  await expect(page).toHaveURL(/\/compose$/)
})

test('renders the history route shell', async ({ page }) => {
  await page.goto('/history')
  await expect(page.getByRole('heading', { name: 'Run History' })).toBeVisible()
  await expect(page.getByLabel('Status')).toBeVisible()
  await expect(page.getByLabel('Mode')).toBeVisible()
})

test('renders the templates route shell', async ({ page }) => {
  await page.goto('/templates')
  await expect(page.getByRole('heading', { name: 'Task Templates' })).toBeVisible()
  await expect(page.getByLabel('Name')).toBeVisible()
  await expect(page.getByLabel('Instructions')).toBeVisible()
})

test('renders the recurring todo route shell', async ({ page }) => {
  await page.goto('/recurring')
  await expect(page.getByRole('heading', { name: 'Recurring Tasks', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Refresh' })).toBeVisible()
})

test('renders the calendar route shell', async ({ page }) => {
  await page.goto('/calendar')
  await expect(page.getByRole('button', { name: 'Day', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Week', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Month', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Today' })).toBeVisible()
})

test('covers the MVP navigation path', async ({ page }) => {
  await stubApi(page)

  await page.goto('/compose')
  await expect(page.getByRole('heading', { name: 'Create One-Time Task' })).toBeVisible()

  await page.getByRole('link', { name: 'One-Time Board' }).click()
  await expect(page.getByRole('heading', { name: 'One-Time Tasks' })).toBeVisible()
  await page.getByRole('button', { name: /Board Task/ }).click()
  await expect(page.getByRole('heading', { name: 'Detailed Task' })).toBeVisible()

  await page.getByRole('link', { name: 'History' }).click()
  await expect(page.getByRole('heading', { name: 'Run History' })).toBeVisible()
  await expect(page.getByText('Failed Task')).toBeVisible()

  await page.getByRole('link', { name: 'Templates' }).click()
  await expect(page.getByRole('heading', { name: 'Task Templates' })).toBeVisible()
  await expect(page.getByText('Research Template')).toBeVisible()

  await page.getByRole('link', { name: 'Recurring Todo' }).click()
  await expect(page.getByRole('heading', { name: 'Recurring Tasks', exact: true })).toBeVisible()
  await expect(page.getByText('Active Recurring')).toBeVisible()

  await page.getByRole('link', { name: 'Calendar' }).click()
  await expect(page.getByRole('button', { name: 'Day', exact: true })).toBeVisible()
  const oneTimeCalendarItem = page.locator('[role="button"][aria-label*="One-Time Calendar"]').first()
  const recurringCalendarItem = page
    .locator('[role="button"][aria-label*="Recurring Calendar"]')
    .first()
  await expect(oneTimeCalendarItem).toBeVisible()
  await expect(recurringCalendarItem).toBeVisible()
  await oneTimeCalendarItem.click()
  await expect(page.getByRole('dialog', { name: 'One-Time Calendar' })).toBeVisible()
  await page.getByRole('button', { name: 'Detail' }).click()
  await expect(page.getByRole('heading', { name: 'Detailed Task' })).toBeVisible()
})

async function stubApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = route.request().url()
    if (url.includes('/views/kanban')) {
      await route.fulfill({
        json: {
          data: {
            columns: {
              upcoming: [
                {
                  card_id: 'card-1',
                  task_id: 'task-1',
                  title: 'Board Task',
                  kanban_column: 'upcoming',
                  next_run_at: '2026-04-27T10:00:00+08:00',
                  latest_run_status: null,
                  result_summary: null,
                },
              ],
              running: [],
              completed: [],
              failed: [],
              canceled: [],
            },
          },
        },
      })
      return
    }
    if (url.includes('/tasks/task-1/detail')) {
      await route.fulfill({
        json: {
          data: {
            task: taskResponse('task-1', 'Detailed Task', 'one_time'),
            schedule: {
              schedule_id: 'schedule-1',
              task_id: 'task-1',
              schedule_type: 'single_run',
              schedule_status: 'pending',
              planned_at: '2026-04-27T10:00:00+08:00',
              next_run_at: '2026-04-27T10:00:00+08:00',
              version: 1,
            },
            latest_run: null,
            runs: [],
          },
        },
      })
      return
    }
    if (url.includes('/views/history')) {
      await route.fulfill({
        json: {
          data: [
            {
              history_item_id: 'hist-1',
              run_id: 'run-1',
              task_id: 'task-1',
              title: 'Failed Task',
              execution_mode: 'one_time',
              run_status: 'failed',
              finished_at: '2026-04-27T11:00:00+08:00',
              result_summary: null,
              failure_reason: 'Executor failed',
            },
          ],
          meta: { total: 1 },
        },
      })
      return
    }
    if (url.includes('/templates')) {
      await route.fulfill({
        json: {
          data: [
            {
              template_id: 'tpl-1',
              name: 'Research Template',
              description: null,
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
              created_at: '2026-04-27T09:00:00+08:00',
              updated_at: '2026-04-27T09:00:00+08:00',
              archived_at: null,
            },
          ],
          meta: { total: 1 },
        },
      })
      return
    }
    if (url.includes('/views/recurring-todo')) {
      await route.fulfill({
        json: {
          data: [
            {
              item_id: 'todo-1',
              task_id: 'task-recurring-1',
              title: 'Active Recurring',
              recurrence_rule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
              recurrence_timezone: 'Asia/Hong_Kong',
              next_run_at: '2026-04-28T08:00:00+08:00',
              schedule_status: 'active',
              task_status: 'scheduled',
              schedule_version: 1,
              latest_run_id: null,
              latest_run_outcome: null,
              latest_run_finished_at: null,
              result_summary: null,
              failure_reason: null,
            },
          ],
          meta: { total: 1 },
        },
      })
      return
    }
    if (url.includes('/views/calendar')) {
      await route.fulfill({
        json: {
          data: [
            {
              calendar_item_id: 'cal-one-time-1',
              task_id: 'task-1',
              schedule_id: 'schedule-1',
              title: 'One-Time Calendar',
              execution_mode: 'one_time',
              occurrence_at: '2026-04-28T10:00:00+08:00',
              original_occurrence_at: null,
              state: 'scheduled',
              is_occurrence_override: false,
              schedule_version: 1,
            },
            {
              calendar_item_id: 'cal-recurring-1',
              task_id: 'task-recurring-1',
              schedule_id: 'schedule-recurring-1',
              title: 'Recurring Calendar',
              execution_mode: 'recurring',
              occurrence_at: '2026-04-28T11:00:00+08:00',
              original_occurrence_at: '2026-04-28T11:00:00+08:00',
              state: 'scheduled',
              is_occurrence_override: false,
              schedule_version: 1,
            },
          ],
          meta: { total: 2 },
        },
      })
      return
    }
    await route.fulfill({ status: 404, json: { error: { message: 'Unhandled test route' } } })
  })
}

function taskResponse(taskId: string, title: string, executionMode: 'one_time' | 'recurring') {
  return {
    task_id: taskId,
    title,
    instruction_source: 'Run this later.',
    target_working_directory: '/tmp',
    execution_mode: executionMode,
    task_status: 'scheduled',
    template_id: null,
    executor: 'debug_printer',
    version: 1,
    created_at: '2026-04-27T09:00:00+08:00',
    updated_at: '2026-04-27T09:00:00+08:00',
    archived_at: null,
  }
}
