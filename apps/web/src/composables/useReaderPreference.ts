import { ref, watch } from 'vue'

export type ReaderFontSize = 'sm' | 'md' | 'lg' | 'xl'

const FONT_SIZE_STORAGE_KEY = 'vesperaflow.reader.fontSize'

function getInitialFontSize(): ReaderFontSize {
  try {
    const stored = localStorage.getItem(FONT_SIZE_STORAGE_KEY)
    if (stored === 'sm' || stored === 'md' || stored === 'lg' || stored === 'xl') {
      return stored
    }
  } catch {
    // ignore
  }
  return 'md'
}

const fontSize = ref<ReaderFontSize>(getInitialFontSize())

export function useReaderPreference() {
  watch(fontSize, (value) => {
    try {
      localStorage.setItem(FONT_SIZE_STORAGE_KEY, value)
    } catch {
      // ignore
    }
  })

  return {
    fontSize,
  }
}
