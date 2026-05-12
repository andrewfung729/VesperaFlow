import { onBeforeUnmount, onMounted } from 'vue'

export interface ReaderShortcutCallbacks {
  onPrev?: () => void
  onNext?: () => void
  onFontInc?: () => void
  onFontDec?: () => void
  onBack?: () => void
  onCopy?: () => void
}

export function useReaderShortcuts(callbacks: ReaderShortcutCallbacks) {
  function onKeydown(event: KeyboardEvent) {
    const target = event.target as HTMLElement | null
    if (target) {
      const tag = target.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable) {
        return
      }
    }

    if (event.metaKey || event.ctrlKey || event.altKey) return

    switch (event.key) {
      case 'ArrowLeft':
        event.preventDefault()
        callbacks.onPrev?.()
        return
      case 'ArrowRight':
        event.preventDefault()
        callbacks.onNext?.()
        return
      case '+':
      case '=':
        event.preventDefault()
        callbacks.onFontInc?.()
        return
      case '-':
      case '_':
        event.preventDefault()
        callbacks.onFontDec?.()
        return
      case 'Escape':
        event.preventDefault()
        callbacks.onBack?.()
        return
      case 'c':
      case 'C':
        event.preventDefault()
        callbacks.onCopy?.()
        return
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeydown)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', onKeydown)
  })
}
