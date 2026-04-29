<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    message?: string
    spacious?: boolean
  }>(),
  {
    message: undefined,
    spacious: false,
  },
)
</script>

<template>
  <div
    class="rounded-md border border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400"
    :class="spacious ? 'p-7' : 'p-5'"
  >
    <h3 class="m-0 text-lg font-bold text-slate-950 dark:text-slate-50">{{ title }}</h3>
    <p v-if="message" class="m-0 mt-1 text-sm">{{ message }}</p>
    <div v-if="$slots.default" class="mt-4">
      <slot />
    </div>
  </div>
</template>
