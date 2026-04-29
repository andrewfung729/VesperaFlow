<script setup lang="ts">
import { computed } from 'vue'

import FormField from '@/components/FormField.vue'

defineOptions({
  inheritAttrs: false,
})

const props = withDefaults(
  defineProps<{
    label: string
    type?: string
    placeholder?: string
    compact?: boolean
  }>(),
  {
    type: 'text',
    placeholder: undefined,
    compact: false,
  },
)

const model = defineModel<string>({ required: true })

const inputClass = computed(() =>
  props.compact
    ? 'min-h-10 rounded-md border border-slate-300 bg-white px-3 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-50'
    : 'w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-50',
)
</script>

<template>
  <FormField :label="label" :compact="compact">
    <input
      v-model="model"
      :class="inputClass"
      :placeholder="placeholder"
      :type="type"
      v-bind="$attrs"
    />
  </FormField>
</template>
