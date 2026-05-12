import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

export function useScrollDirection(): {
  direction: Ref<'up' | 'down' | 'idle'>
  isAtTop: Ref<boolean>
} {
  const direction = ref<'up' | 'down' | 'idle'>('idle')
  const isAtTop = ref(true)

  let lastScrollY = 0
  let ticking = false
  const threshold = 8

  function update() {
    const currentScrollY = window.scrollY
    isAtTop.value = currentScrollY <= 0

    const delta = currentScrollY - lastScrollY
    if (Math.abs(delta) >= threshold) {
      direction.value = delta > 0 ? 'down' : 'up'
      lastScrollY = currentScrollY
    }
    ticking = false
  }

  function onScroll() {
    if (!ticking) {
      requestAnimationFrame(update)
      ticking = true
    }
  }

  onMounted(() => {
    lastScrollY = window.scrollY
    isAtTop.value = lastScrollY <= 0
    window.addEventListener('scroll', onScroll, { passive: true })
  })

  onBeforeUnmount(() => {
    window.removeEventListener('scroll', onScroll)
  })

  return { direction, isAtTop }
}
