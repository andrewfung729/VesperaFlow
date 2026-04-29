<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'

import ThemeToggle from '@/components/ThemeToggle.vue'
import { initThemeListener } from '@/composables/useTheme'

const isDark = ref(false)

let cleanup: (() => void) | null = null

onMounted(() => {
  cleanup = initThemeListener((dark) => {
    isDark.value = dark
  })
})

onUnmounted(() => {
  cleanup?.()
})
</script>

<template>
  <main
    :class="{ dark: isDark }"
    class="grid min-h-screen grid-cols-1 bg-slate-100 text-slate-950 md:grid-cols-[260px_minmax(0,1fr)] dark:bg-slate-950 dark:text-slate-50"
  >
    <aside class="flex flex-col gap-8 bg-slate-900 px-5 py-5 text-slate-50 md:py-7">
      <div>
        <p class="mb-2 text-xs font-bold tracking-wide text-teal-400 uppercase">VesperaFlow</p>
        <h1 class="m-0 text-2xl font-bold tracking-normal">Planned AI Work</h1>
      </div>
      <nav class="grid gap-2" aria-label="Primary">
        <RouterLink
          class="flex min-h-10 items-center rounded-md px-3 text-sm font-medium text-slate-300 no-underline transition hover:bg-slate-800 hover:text-white"
          active-class="bg-slate-800 text-white"
          :to="{ name: 'compose' }"
        >
          Composer
        </RouterLink>
        <RouterLink
          class="flex min-h-10 items-center rounded-md px-3 text-sm font-medium text-slate-300 no-underline transition hover:bg-slate-800 hover:text-white"
          active-class="bg-slate-800 text-white"
          :to="{ name: 'board' }"
        >
          One-Time Board
        </RouterLink>
        <RouterLink
          class="flex min-h-10 items-center rounded-md px-3 text-sm font-medium text-slate-300 no-underline transition hover:bg-slate-800 hover:text-white"
          active-class="bg-slate-800 text-white"
          :to="{ name: 'templates' }"
        >
          Templates
        </RouterLink>
        <RouterLink
          class="flex min-h-10 items-center rounded-md px-3 text-sm font-medium text-slate-300 no-underline transition hover:bg-slate-800 hover:text-white"
          active-class="bg-slate-800 text-white"
          :to="{ name: 'recurring-todo' }"
        >
          Recurring Todo
        </RouterLink>
        <RouterLink
          class="flex min-h-10 items-center rounded-md px-3 text-sm font-medium text-slate-300 no-underline transition hover:bg-slate-800 hover:text-white"
          active-class="bg-slate-800 text-white"
          :to="{ name: 'calendar' }"
        >
          Calendar
        </RouterLink>
        <RouterLink
          class="flex min-h-10 items-center rounded-md px-3 text-sm font-medium text-slate-300 no-underline transition hover:bg-slate-800 hover:text-white"
          active-class="bg-slate-800 text-white"
          :to="{ name: 'history' }"
        >
          History
        </RouterLink>
      </nav>
      <div class="mt-auto">
        <ThemeToggle />
      </div>
    </aside>

    <section class="p-5 md:p-8">
      <RouterView />
    </section>
  </main>
</template>
