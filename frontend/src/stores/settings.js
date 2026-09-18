import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createResource } from 'frappe-ui'
import { sessionStore } from './session'

export const useSettings = defineStore('settings', () => {
	const { isLoggedIn } = sessionStore()
	const isSettingsOpen = ref(false)
	const activeTab = ref(null)





	// An onboarding-complete check (`is_onboarding_complete`) was never built
	// server-side; see privatedocs/p007 §2.13 for the action item.

	return {
		isSettingsOpen,
		activeTab,


	}
})