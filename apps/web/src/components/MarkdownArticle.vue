<script setup lang="ts">
import { computed } from 'vue'

import { renderMarkdown } from '@/lib/markdown'

const props = defineProps<{
  content: string | null | undefined
}>()

const hasContent = computed(() => !!props.content && props.content.trim().length > 0)
const safeHtml = computed(() => renderMarkdown(props.content))
</script>

<template>
  <div v-if="hasContent" class="markdown-article" data-testid="markdown-article">
    <div class="markdown-body" v-html="safeHtml" />
  </div>
  <span v-else class="text-slate-400 italic dark:text-slate-500">No content</span>
</template>

<style scoped>
.markdown-article {
  --reader-prose-width: 75ch;
  --reader-breakout-width: 64rem;
  --reader-line-height: 1.75;
  overflow-wrap: break-word;
  word-break: normal;
}

.markdown-body {
  font-size: 1em;
  line-height: var(--reader-line-height);
  color: #334155;
}

.dark .markdown-body {
  color: #cbd5e1;
}

.markdown-body > * {
  max-width: var(--reader-prose-width);
  margin-inline: auto;
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

.dark .markdown-body :deep(h1),
.dark .markdown-body :deep(h2),
.dark .markdown-body :deep(h3),
.dark .markdown-body :deep(h4),
.dark .markdown-body :deep(h5),
.dark .markdown-body :deep(h6) {
  color: #f1f5f9;
}

.markdown-body :deep(h1) {
  font-size: 1.75em;
}
.markdown-body :deep(h2) {
  font-size: 1.5em;
}
.markdown-body :deep(h3) {
  font-size: 1.25em;
}
.markdown-body :deep(h4) {
  font-size: 1.125em;
}
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  font-size: 1em;
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
  font-size: 0.85em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #be123c;
  overflow-wrap: anywhere;
}

.dark .markdown-body :deep(code) {
  background: #1e293b;
  color: #fb7185;
}

.markdown-body :deep(pre) {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 0.75em;
  border-radius: 0.375rem;
  overflow-x: auto;
  margin: 0.75em 0;
  max-width: var(--reader-breakout-width);
}

.dark .markdown-body :deep(pre) {
  background: #0f172a;
  border-color: #334155;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
  font-size: 0.85em;
  overflow-wrap: anywhere;
}

.dark .markdown-body :deep(pre code) {
  color: #e2e8f0;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #cbd5e1;
  padding-left: 0.875em;
  margin: 0.75em 0;
  color: #64748b;
  font-style: italic;
}

.dark .markdown-body :deep(blockquote) {
  border-left-color: #475569;
  color: #94a3b8;
}

.markdown-body :deep(a) {
  color: #0f766e;
  text-decoration: underline;
  text-underline-offset: 2px;
  overflow-wrap: anywhere;
}

.dark .markdown-body :deep(a) {
  color: #2dd4bf;
}

.markdown-body :deep(a:hover) {
  color: #115e59;
}

.dark .markdown-body :deep(a:hover) {
  color: #5eead4;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.75em 0;
  font-size: 0.95em;
  max-width: var(--reader-breakout-width);
  display: block;
  overflow-x: auto;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 0.375em 0.625em;
  text-align: left;
}

.dark .markdown-body :deep(th),
.dark .markdown-body :deep(td) {
  border-color: #334155;
}

.markdown-body :deep(th) {
  background: #f8fafc;
  font-weight: 600;
}

.dark .markdown-body :deep(th) {
  background: #1e293b;
}

.markdown-body :deep(hr) {
  border: 0;
  border-top: 1px solid #e2e8f0;
  margin: 1em 0;
}

.dark .markdown-body :deep(hr) {
  border-top-color: #334155;
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

.dark .markdown-body :deep(strong) {
  color: #f1f5f9;
}
</style>
