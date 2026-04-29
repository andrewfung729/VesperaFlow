<script setup lang="ts">
import FormField from '@/components/FormField.vue'

defineOptions({
  inheritAttrs: false,
})

withDefaults(
  defineProps<{
    label: string
    placeholder?: string
    rows?: string | number
    minHeight?: boolean
  }>(),
  {
    placeholder: undefined,
    rows: undefined,
    minHeight: false,
  },
)

const model = defineModel<string>({ required: true })
</script>

<template>
  <FormField :label="label">
    <textarea
      v-model="model"
      class="w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-50"
      :class="{ 'min-h-24': minHeight }"
      :placeholder="placeholder"
      :rows="rows"
      v-bind="$attrs"
    />
  </FormField>
</template>
