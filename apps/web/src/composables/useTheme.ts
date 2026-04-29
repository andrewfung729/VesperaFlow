import { computed, ref, watch } from 'vue'

export type ThemeMode = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'vesperaflow.theme'

function getInitialTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'system' || stored === 'light' || stored === 'dark') {
      return stored
    }
  } catch {
    // ignore
  }
  return 'system'
}

function getSystemIsDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

const themeMode = ref<ThemeMode>(getInitialTheme())

export function useTheme() {
  const isDark = computed(() => {
    if (themeMode.value === 'dark') return true
    if (themeMode.value === 'light') return false
    return getSystemIsDark()
  })

  function setMode(mode: ThemeMode) {
    themeMode.value = mode
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      // ignore
    }
  }

  return {
    themeMode,
    isDark,
    setMode,
  }
}

function computeIsDark(): boolean {
  if (themeMode.value === 'dark') return true
  if (themeMode.value === 'light') return false
  return getSystemIsDark()
}

export function initThemeListener(callback: (isDark: boolean) => void) {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

  const handleChange = () => {
    if (themeMode.value === 'system') {
      callback(getSystemIsDark())
    }
  }

  mediaQuery.addEventListener('change', handleChange)

  const unwatch = watch(
    themeMode,
    () => {
      callback(computeIsDark())
    },
    { immediate: true },
  )

  return () => {
    mediaQuery.removeEventListener('change', handleChange)
    unwatch()
  }
}
