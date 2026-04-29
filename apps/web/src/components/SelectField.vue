<script setup lang="ts">
import FormField from '@/components/FormField.vue'

defineOptions({
  inheritAttrs: false,
})

defineProps<{
  label: string
  options: Array<{ label: string; value: string }>
  emptyLabel?: string
  emptyValue?: string
  compact?: boolean
}>()

const model = defineModel<string>({ required: true })
</script>

<template>
  <FormField :label="label" :compact="compact">
    <select
      v-model="model"
      class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-slate-950 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-50"
      :class="{ 'min-h-10 py-0': compact }"
      v-bind="$attrs"
    >
      <option v-if="emptyLabel" :value="emptyValue ?? ''">{{ emptyLabel }}</option>
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
  </FormField>
</template>
