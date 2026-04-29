import { afterEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'

describe('App dark mode', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('applies dark class to main element when theme is set to dark', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(App, {
      global: { plugins: [router] },
    })
    await router.isReady()
    await flushPromises()

    const darkButton = wrapper.find('button[aria-label="Set theme to Dark"]')
    expect(darkButton.exists()).toBe(true)
    await darkButton.trigger('click')
    await flushPromises()

    const main = wrapper.find('main')
    expect(main.classes()).toContain('dark')
  })

  it('does not apply dark class when theme is set to light', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    const wrapper = mount(App, {
      global: { plugins: [router] },
    })
    await router.isReady()
    await flushPromises()

    const lightButton = wrapper.find('button[aria-label="Set theme to Light"]')
    expect(lightButton.exists()).toBe(true)
    await lightButton.trigger('click')
    await flushPromises()

    const main = wrapper.find('main')
    expect(main.classes()).not.toContain('dark')
  })
})
