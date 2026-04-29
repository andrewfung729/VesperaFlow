<script setup lang="ts">
import { computed } from 'vue'

defineOptions({
  inheritAttrs: false,
})

const props = withDefaults(
  defineProps<{
    type?: 'button' | 'submit' | 'reset'
    variant?: 'primary' | 'secondary' | 'danger'
    size?: 'sm' | 'md'
  }>(),
  {
    type: 'button',
    variant: 'secondary',
    size: 'md',
  },
)

const buttonClass = computed(() => {
  const sizeClass =
    props.size === 'sm'
      ? 'min-h-9 px-3 text-sm'
      : 'min-h-10 px-4'
  const baseClass =
    'cursor-pointer rounded-md border font-semibold transition disabled:cursor-not-allowed disabled:opacity-55'

  if (props.variant === 'primary') {
    return `${baseClass} ${sizeClass} border-transparent bg-teal-700 text-white hover:bg-teal-800`
  }
  if (props.variant === 'danger') {
    return `${baseClass} ${sizeClass} border-red-300 bg-red-50 text-red-700 hover:bg-red-100 dark:border-red-700 dark:bg-red-950/30 dark:text-red-300`
  }
  return `${baseClass} ${sizeClass} border-slate-300 bg-white text-slate-700 shadow-xs hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300`
})
</script>

<template>
  <button :class="buttonClass" :type="type" v-bind="$attrs">
    <slot />
  </button>
</template>
