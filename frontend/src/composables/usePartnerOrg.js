import { ref, computed } from 'vue'
import { createResource } from 'frappe-ui'

// Shared, app-wide state for the partner portal's "active organization". A partner
// user can be a contact on several Partner Organizations; this is the one all
// partner pages currently act on. Persisted so the choice survives reloads.
const STORAGE_KEY = 'partner_active_org'

const activeOrg = ref(localStorage.getItem(STORAGE_KEY) || '')

// One shared resource lists every org the user may act on (for the picker), and
// repairs the selection: default to the first org when nothing is chosen yet or
// the stored choice is no longer valid (e.g. access was removed).
const orgsResource = createResource({
	url: 'seminary.partner.portal.list_my_orgs',
	onSuccess(orgs) {
		const names = (orgs || []).map((o) => o.name)
		if (!activeOrg.value || !names.includes(activeOrg.value)) {
			setActiveOrg(names[0] || '')
		}
	},
})

function setActiveOrg(name) {
	activeOrg.value = name || ''
	if (name) {
		localStorage.setItem(STORAGE_KEY, name)
	} else {
		localStorage.removeItem(STORAGE_KEY)
	}
}

export function usePartnerOrg() {
	const orgs = computed(() => orgsResource.data || [])
	const activeOrgName = computed(() => {
		const found = orgs.value.find((o) => o.name === activeOrg.value)
		return found?.organization_name || ''
	})
	const hasMultiple = computed(() => orgs.value.length > 1)

	function ensureLoaded() {
		if (!orgsResource.data && !orgsResource.loading) orgsResource.reload()
	}

	return {
		activeOrg,
		orgs,
		activeOrgName,
		hasMultiple,
		setActiveOrg,
		orgsResource,
		ensureLoaded,
	}
}
