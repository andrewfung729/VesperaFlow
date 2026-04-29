import { afterEach, describe, expect, it, vi } from 'vitest'

import { mount } from '@vue/test-utils'

import ThemeToggle from '@/components/ThemeToggle.vue'

describe('ThemeToggle', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('renders system, light, and dark buttons', () => {
    const wrapper = mount(ThemeToggle)
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(3)
    expect(buttons[0]?.text()).toBe('System')
    expect(buttons[1]?.text()).toBe('Light')
    expect(buttons[2]?.text()).toBe('Dark')
  })

  it('defaults to system mode', () => {
    const wrapper = mount(ThemeToggle)
    const buttons = wrapper.findAll('button')
    expect(buttons[0]?.classes()).toContain('bg-slate-700')
    expect(buttons[1]?.classes()).not.toContain('bg-slate-700')
    expect(buttons[2]?.classes()).not.toContain('bg-slate-700')
  })

  it('switches to dark mode when dark button is clicked', async () => {
    const wrapper = mount(ThemeToggle)
    const buttons = wrapper.findAll('button')
    await buttons[2]?.trigger('click')
    expect(buttons[2]?.classes()).toContain('bg-slate-700')
    expect(buttons[0]?.classes()).not.toContain('bg-slate-700')
  })

  it('switches to light mode when light button is clicked', async () => {
    const wrapper = mount(ThemeToggle)
    const buttons = wrapper.findAll('button')
    await buttons[1]?.trigger('click')
    expect(buttons[1]?.classes()).toContain('bg-slate-700')
    expect(buttons[0]?.classes()).not.toContain('bg-slate-700')
  })

  it('persists theme choice to localStorage', async () => {
    const wrapper = mount(ThemeToggle)
    const buttons = wrapper.findAll('button')
    await buttons[2]?.trigger('click')
    expect(localStorage.getItem('vesperaflow.theme')).toBe('dark')
  })
})
