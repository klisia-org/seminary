import { ref } from 'vue'

const STORAGE_KEY = 'seminary-theme'

function resolveInitialTheme() {
	const stored = localStorage.getItem(STORAGE_KEY)
	if (stored === 'light' || stored === 'dark') return stored
	return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const theme = ref(resolveInitialTheme())
document.documentElement.setAttribute('data-theme', theme.value)

export function applyInitialTheme() {
	return theme.value
}

function setTheme(next) {
	if (next !== 'light' && next !== 'dark') return
	theme.value = next
	document.documentElement.setAttribute('data-theme', next)
	localStorage.setItem(STORAGE_KEY, next)
}

function toggleTheme() {
	setTheme(theme.value === 'dark' ? 'light' : 'dark')
}

export function useTheme() {
	return { theme, setTheme, toggleTheme }
}
