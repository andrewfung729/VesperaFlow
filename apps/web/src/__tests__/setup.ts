import { vi } from 'vitest'

const storage = new Map<string, string>()
const localStorageMock: Storage = {
  get length() {
    return storage.size
  },
  clear() {
    storage.clear()
  },
  getItem(key: string) {
    return storage.get(key) ?? null
  },
  key(index: number) {
    return Array.from(storage.keys())[index] ?? null
  },
  removeItem(key: string) {
    storage.delete(key)
  },
  setItem(key: string, value: string) {
    storage.set(key, value)
  },
}

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: localStorageMock,
})
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: localStorageMock,
})

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn<(query: string) => MediaQueryList>().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn<() => void>(),
    removeListener: vi.fn<() => void>(),
    addEventListener: vi.fn<() => void>(),
    removeEventListener: vi.fn<() => void>(),
    dispatchEvent: vi.fn<() => boolean>(),
  })),
})
