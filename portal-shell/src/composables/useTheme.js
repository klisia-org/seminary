import { ref, watchEffect } from 'vue'

const STORAGE_KEY = 'portal-shell:theme'
const theme = ref(readInitial())

function readInitial() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    /* localStorage unavailable */
  }
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

watchEffect(() => {
  document.documentElement.dataset.theme = theme.value
  document.documentElement.classList.toggle('dark', theme.value === 'dark')
  try {
    localStorage.setItem(STORAGE_KEY, theme.value)
  } catch {
    /* ignore */
  }
})

export function useTheme() {
  return {
    theme,
    toggleTheme: () => {
      theme.value = theme.value === 'dark' ? 'light' : 'dark'
    },
    setTheme: (next) => {
      theme.value = next === 'dark' ? 'dark' : 'light'
    },
  }
}
