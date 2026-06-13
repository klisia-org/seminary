// composables/usePortalDisciplinary.js
// Exposes the `portal_disciplinary` Seminary Settings flag (ADR 032). Shared
// across every entry point (course card, grading views, To-Do).
//
// The resource is created and fetched LAZILY on first use inside a component
// setup() — NOT at module import time. A module-level `auto: true` resource
// fires its one-shot fetch during app bootstrap, before the session/CSRF layer
// is ready; that request resolves to the SPA index HTML, the fetch fails, and
// since it never retries the flag reads false forever (hiding the disciplinary
// UI everywhere). Deferring to setup() mirrors how the other settings-backed
// resources fetch reliably.
import { createResource } from 'frappe-ui'
import { computed } from 'vue'

let settings = null

function ensureSettings() {
  if (!settings) {
    settings = createResource({
      url: 'frappe.client.get_value',
      params: {
        doctype: 'Seminary Settings',
        fieldname: 'portal_disciplinary',
      },
      cache: 'portal_disciplinary',
    })
  }
  if (settings.data == null && !settings.loading) {
    settings.fetch()
  }
  return settings
}

export function usePortalDisciplinary() {
  const s = ensureSettings()
  const portalDisciplinary = computed(() => s.data?.portal_disciplinary === 1)
  return { portalDisciplinary }
}
