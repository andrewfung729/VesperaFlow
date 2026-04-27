import { test, expect } from '@playwright/test'

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
  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible()
  await expect(page.getByLabel('From')).toBeVisible()
  await expect(page.getByLabel('To', { exact: true })).toBeVisible()
})
