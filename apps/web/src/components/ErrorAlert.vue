<script setup lang="ts">
defineProps<{
  message: string | null | undefined
}>()
</script>

<template>
  <div
    v-if="message"
    class="mb-5 max-w-5xl rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300"
    role="alert"
  >
    {{ message }}
  </div>
</template>
