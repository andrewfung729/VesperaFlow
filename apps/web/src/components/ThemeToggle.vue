<script setup lang="ts">
import { useTheme, type ThemeMode } from '@/composables/useTheme'

const { themeMode, setMode } = useTheme()

const options: { value: ThemeMode; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]
</script>

<template>
  <div class="flex items-center gap-1.5">
    <span class="text-xs font-semibold text-slate-400 dark:text-slate-500">Theme</span>
    <div class="inline-flex rounded-md border border-slate-700 p-0.5">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="min-h-7 cursor-pointer rounded px-2 text-xs font-semibold transition"
        :class="
          themeMode === option.value
            ? 'bg-slate-700 text-white'
            : 'text-slate-400 dark:text-slate-500 hover:bg-slate-800 hover:text-slate-200'
        "
        :aria-label="`Set theme to ${option.label}`"
        @click="setMode(option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>
