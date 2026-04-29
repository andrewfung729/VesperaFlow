<script setup lang="ts">
import type { ExecutionMode } from '@/api'
import { executionModeBadgeClass, executionModeLabel } from '@/lib/executionModeDisplay'

defineProps<{
  mode: ExecutionMode
}>()
</script>

<template>
  <span
    class="inline-flex rounded-md border px-2 py-1 text-xs font-bold uppercase"
    :class="executionModeBadgeClass(mode)"
  >
    {{ executionModeLabel(mode) }}
  </span>
</template>
