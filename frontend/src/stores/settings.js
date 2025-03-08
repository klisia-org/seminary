import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createResource } from 'frappe-ui'
import { sessionStore } from './session'

export const useSettings = defineStore('settings', () => {
	const { isLoggedIn } = sessionStore()
	const isSettingsOpen = ref(false)
	const activeTab = ref(null)

	



	/* const onboardingDetails = createResource({
		url: 'lms.lms.utils.is_onboarding_complete',
		auto: isLoggedIn ? true : false,
		cache: ['onboardingDetails'],
	}) */

	return {
		isSettingsOpen,
		activeTab,
		
		
	}
})
