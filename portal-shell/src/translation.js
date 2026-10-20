import { shallowRef } from 'vue'
import { userLanguage } from './i18n.js'

/**
 * `__()` for every portal (aretenic decision 071). Moved from seminary's own plugin and
 * written on plain `fetch`, since koinonia's portal does not use frappe-ui.
 *
 * The catalogue comes from seminary's `get_translations`, which merges every installed
 * app's messages. It lives in a ref, so anything rendered before it arrives re-renders
 * translated; the last catalogue for the language is kept in localStorage, so a reload
 * shows translations from the first paint.
 */
const messages = shallowRef({})
const cacheKey = () => 'portal-shell:translations:' + userLanguage()

export function __(message) {
  const translated = messages.value[message] || message
  if (!/{\d+}/.test(message)) return translated
  return {
    format: (...args) =>
      translated.replace(/{(\d+)}/g, (match, n) => (typeof args[n] !== 'undefined' ? args[n] : match)),
  }
}

// One fetch per page: seminary mounts small sub-apps (editor tools) that each install the
// plugin, and every install shares this promise.
let loading = null

export function loadTranslations() {
  loading ||= fetchTranslations()
  return loading
}

async function fetchTranslations() {
  try {
    const cached = localStorage.getItem(cacheKey())
    if (cached) messages.value = JSON.parse(cached)
  } catch {
    // Private mode or blocked storage: fall through to the network.
  }
  try {
    const res = await fetch('/api/method/seminary.seminary.api.get_translations', {
      credentials: 'same-origin',
    })
    if (!res.ok) return
    const { message } = await res.json()
    if (!message) return
    messages.value = message
    try {
      localStorage.setItem(cacheKey(), JSON.stringify(message))
    } catch {
      // Over quota or blocked: the in-memory copy still serves this page.
    }
  } catch {
    // Offline or blocked: English (or the cached copy) stays.
  }
}

export const translationPlugin = {
  install(app) {
    app.config.globalProperties.__ = __
    window.__ = __
    loadTranslations()
  },
}
