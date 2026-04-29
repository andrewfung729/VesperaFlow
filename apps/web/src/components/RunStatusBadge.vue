<script setup lang="ts">
import type { RunStatus } from '@/api'
import { runStatusLabel, statusBadgeClass } from '@/lib/runDisplay'

defineProps<{
  status: RunStatus
}>()
</script>

<template>
  <span
    class="inline-flex rounded-md border px-2 py-1 text-xs font-bold uppercase"
    :class="statusBadgeClass(status)"
  >
    {{ runStatusLabel(status) }}
  </span>
</template>
