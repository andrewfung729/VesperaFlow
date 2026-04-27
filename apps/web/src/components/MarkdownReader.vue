<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = withDefaults(
  defineProps<{
    content: string | null | undefined
    expandable?: boolean
    previewLines?: number
  }>(),
  {
    expandable: true,
    previewLines: 5,
  },
)

const isExpanded = ref(false)

const hasContent = computed(() => !!props.content && props.content.trim().length > 0)

const safeHtml = computed(() => {
  if (!hasContent.value) return ''
  const raw = marked.parse(props.content!, {
    async: false,
    breaks: true,
    gfm: true,
  }) as string
  return DOMPurify.sanitize(raw)
})
</script>

<template>
  <div v-if="hasContent" class="markdown-reader">
    <div
      class="markdown-body"
      :class="{ 'is-clamped': expandable && !isExpanded }"
      :style="expandable && !isExpanded ? { '--clamp-lines': previewLines } : {}"
      v-html="safeHtml"
    />
    <button
      v-if="expandable"
      type="button"
      class="mt-1.5 cursor-pointer border-0 bg-transparent p-0 text-xs font-semibold text-teal-700 transition hover:text-teal-900"
      @click="isExpanded = !isExpanded"
    >
      {{ isExpanded ? 'Show less' : 'Show more' }}
    </button>
  </div>
  <span v-else class="text-slate-400 italic">No content</span>
</template>

<style scoped>
.markdown-body {
  font-size: 0.875rem;
  line-height: 1.6;
  color: #334155;
}

.markdown-body.is-clamped {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: var(--clamp-lines, 5);
  overflow: hidden;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: 0.75em 0 0.35em;
  font-weight: 700;
  line-height: 1.3;
  color: #0f172a;
}

.markdown-body :deep(h1) {
  font-size: 1.25rem;
}
.markdown-body :deep(h2) {
  font-size: 1.125rem;
}
.markdown-body :deep(h3) {
  font-size: 1rem;
}
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  font-size: 0.9375rem;
}

.markdown-body :deep(p) {
  margin: 0.5em 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.markdown-body :deep(li) {
  margin: 0.15em 0;
}

.markdown-body :deep(code) {
  background: #f1f5f9;
  padding: 0.125em 0.375em;
  border-radius: 0.25rem;
  font-size: 0.8125em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #be123c;
}

.markdown-body :deep(pre) {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 0.75em;
  border-radius: 0.375rem;
  overflow-x: auto;
  margin: 0.75em 0;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
  font-size: 0.8125em;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #cbd5e1;
  padding-left: 0.875em;
  margin: 0.75em 0;
  color: #64748b;
  font-style: italic;
}

.markdown-body :deep(a) {
  color: #0f766e;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-body :deep(a:hover) {
  color: #115e59;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.75em 0;
  font-size: 0.8125rem;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 0.375em 0.625em;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f8fafc;
  font-weight: 600;
}

.markdown-body :deep(hr) {
  border: 0;
  border-top: 1px solid #e2e8f0;
  margin: 1em 0;
}

.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 0.375rem;
  margin: 0.5em 0;
}

.markdown-body :deep(strong) {
  font-weight: 700;
  color: #0f172a;
}
</style>
