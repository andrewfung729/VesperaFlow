<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    compact?: boolean
  }>(),
  {
    compact: false,
  },
)
</script>

<template>
  <label
    class="grid font-semibold text-slate-700 dark:text-slate-300"
    :class="compact ? 'gap-1 text-sm' : 'gap-2'"
  >
    <span>{{ label }}</span>
    <slot />
  </label>
</template>
