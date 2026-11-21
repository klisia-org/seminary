<template>
	<FrappeUIProvider>
	<Layout>

		<div class="text-base">
		<router-view :key="$route.fullPath" />
		</div>
	</Layout>

	<Dialogs /> <!-- Ensure this line is present -->

	</FrappeUIProvider>
</template>

<script setup>
// import Sidebar from '@/components/AppSidebar.vue'
// import Navbar from '@/components/Navbar.vue';
// import { RouterView } from 'vue-router';
import { FrappeUIProvider, call } from 'frappe-ui';
import { Dialogs } from '@/utils/dialogs'
import { usersStore } from '@/stores/user'
import { computed, watch} from 'vue'
import { useScreenSize } from './utils/composables'
import DesktopLayout from './components/DesktopLayout.vue'
import MobileLayout from './components/MobileLayout.vue'
import { useRouter } from 'vue-router'
import { posthogSettings } from '@/telemetry'

const router = useRouter()
const screenSize = useScreenSize()
const { userResource } = usersStore()

const Layout = computed(() => {
  if (screenSize.isMobile) return MobileLayout
  return DesktopLayout
})

watch(userResource, () => {
	if (userResource.data) {
		posthogSettings.reload()
		reportTimeZone()
	}
})

// The student's own time zone, from the browser (decisions/100d-a §9): written
// while they have none of their own, asked when it differs. Once a session.
const reportTimeZone = async () => {
	let tz = ''
	try {
		if (sessionStorage.getItem('seminary_tz_reported')) return
		sessionStorage.setItem('seminary_tz_reported', '1')
		tz = Intl.DateTimeFormat().resolvedOptions().timeZone
	} catch (e) {
		return
	}
	if (!tz) return
	try {
		const out = await call('seminary.seminary.time_zones.report', { tz })
		if (out?.ask && window.confirm(
			__('Your device says your time zone is {0}, but your profile has {1}. Use {0}?').format(out.browser, out.time_zone)
		)) {
			await call('seminary.seminary.time_zones.set_my_time_zone', { tz: out.browser })
		}
	} catch (e) {
		// Not worth troubling anyone over.
	}
}

</script>