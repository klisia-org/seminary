import { ref } from 'vue'

// Must match the key used by @seminary/portal-shell's own theme watcher.
// The portal-shell bundle registers a module-level watchEffect that rewrites
// document.documentElement on load from this key; if we persist under a
// different key the shell resets the theme on every reload (the "dark mode
// doesn't stick" bug). Sharing the key keeps the two writers in agreement.
const STORAGE_KEY = 'portal-shell:theme'
// Older builds stored the choice here; read it once so existing users don't
// lose their preference on upgrade.
const LEGACY_KEY = 'seminary-theme'

function resolveInitialTheme() {
	const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_KEY)
	if (stored === 'light' || stored === 'dark') return stored
	return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(value) {
	document.documentElement.setAttribute('data-theme', value)
	// portal-shell also toggles this class; keep it in sync so the two never drift.
	document.documentElement.classList.toggle('dark', value === 'dark')
}

const theme = ref(resolveInitialTheme())
applyTheme(theme.value)
// Seed the shared key immediately (and migrate the legacy key) so the
// portal-shell watcher — which evaluates after this module — reads the same
// value instead of falling back to the system preference.
try {
	localStorage.setItem(STORAGE_KEY, theme.value)
} catch {
	/* localStorage unavailable */
}

export function applyInitialTheme() {
	return theme.value
}

function setTheme(next) {
	if (next !== 'light' && next !== 'dark') return
	theme.value = next
	applyTheme(next)
	localStorage.setItem(STORAGE_KEY, next)
}

function toggleTheme() {
	setTheme(theme.value === 'dark' ? 'light' : 'dark')
}

export function useTheme() {
	return { theme, setTheme, toggleTheme }
}
