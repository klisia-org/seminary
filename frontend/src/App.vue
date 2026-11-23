<template>
	<FrappeUIProvider>
	<!-- 102 §9: a skip link to the page content, and one polite live region that
	     names each page as the router moves to it (toasts announce themselves). -->
	<a
		href="#scrollContainer"
		class="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded focus:bg-surface-white focus:px-3 focus:py-2 focus:text-base focus:text-ink-gray-9 focus:shadow-lg focus:outline focus:outline-2 focus:outline-outline-gray-5"
		@click.prevent="focusMain"
	>{{ __('Skip to content') }}</a>
	<div class="sr-only" aria-live="polite" aria-atomic="true">{{ announcement }}</div>
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
import { computed, nextTick, ref, watch } from 'vue'
import { pageTitle } from '@/utils/pageTitles'
import { useScreenSize } from './utils/composables'
import DesktopLayout from './components/DesktopLayout.vue'
import MobileLayout from './components/MobileLayout.vue'
import { useRouter } from 'vue-router'
import { posthogSettings } from '@/telemetry'

const router = useRouter()

// Page titles, the route announcement and focus on navigation (102 §9, WCAG 2.4.2,
// 2.4.3, 4.1.3). The first load keeps the browser's own focus; later navigations
// move focus to the content, as a full page load would, and name the new page.
const school = document.title
const announcement = ref('')
const focusMain = () => {
	const main = document.querySelector('main')
	if (main) main.focus({ preventScroll: true })
}
if (router.currentRoute.value.matched.length) document.title = pageTitle(router.currentRoute.value, school)
router.afterEach((to, from, failure) => {
	if (failure) return
	document.title = pageTitle(to, school)
	if (!from.matched.length || to.path === from.path) return
	nextTick(() => {
		setTimeout(() => {
			announcement.value = document.title
			focusMain()
		}, 50)
	})
})
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