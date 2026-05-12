import DOMPurify from 'dompurify'
import { marked } from 'marked'

export function renderMarkdown(content: string | null | undefined): string {
  if (!content || content.trim().length === 0) return ''
  const raw = marked.parse(content, {
    async: false,
    breaks: true,
    gfm: true,
  }) as string
  return DOMPurify.sanitize(raw)
}
