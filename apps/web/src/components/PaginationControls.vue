<script setup lang="ts">
import { computed } from 'vue'
import UiButton from '@/components/UiButton.vue'

const props = defineProps<{
  currentPage: number
  pageSize: number
  total: number
}>()

const emit = defineEmits<{
  (e: 'update:currentPage', page: number): void
}>()

const totalPages = computed(() => Math.ceil(props.total / props.pageSize) || 1)

const start = computed(() => {
  if (props.total === 0) return 0
  return (props.currentPage - 1) * props.pageSize + 1
})

const end = computed(() => {
  return Math.min(props.currentPage * props.pageSize, props.total)
})

function goToPrevious() {
  if (props.currentPage > 1) {
    emit('update:currentPage', props.currentPage - 1)
  }
}

function goToNext() {
  if (props.currentPage < totalPages.value) {
    emit('update:currentPage', props.currentPage + 1)
  }
}
</script>

<template>
  <div class="flex items-center justify-between gap-4 mt-4">
    <p class="text-sm text-slate-500 dark:text-slate-400">
      Showing {{ start }} - {{ end }} of {{ total }}
    </p>
    <div class="flex items-center gap-2">
      <UiButton size="sm" :disabled="currentPage <= 1" @click="goToPrevious"> Previous </UiButton>
      <span class="text-sm text-slate-700 dark:text-slate-300">
        Page {{ currentPage }} of {{ totalPages }}
      </span>
      <UiButton size="sm" :disabled="currentPage >= totalPages" @click="goToNext"> Next </UiButton>
    </div>
  </div>
</template>
