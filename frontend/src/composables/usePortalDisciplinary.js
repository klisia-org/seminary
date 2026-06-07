// composables/usePortalDisciplinary.js
// Exposes the `portal_disciplinary` Seminary Settings flag (ADR 032). Fetched
// once and shared across every entry point (course card, grading views, To-Do).
import { createResource } from 'frappe-ui'
import { computed } from 'vue'

const settings = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Seminary Settings',
    fieldname: 'portal_disciplinary',
  },
  cache: 'portal_disciplinary',
  auto: true,
})

export function usePortalDisciplinary() {
  const portalDisciplinary = computed(
    () => settings.data?.portal_disciplinary === 1
  )
  return { portalDisciplinary }
}
