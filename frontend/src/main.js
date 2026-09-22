import './index.css'
import '@seminary/portal-shell/style.css'
import { applyInitialTheme } from './composables/useTheme'
import { createApp } from 'vue'

applyInitialTheme()

import router from './router'
import App from './App.vue'
import { createPinia } from 'pinia'
import dayjs from '@/utils/dayjs'
import { createDialog } from '@/utils/dialogs'
import translationPlugin from './translation'
import { usersStore } from './stores/user'
import { initSocket } from './socket'
import { FrappeUI, setConfig, frappeRequest, pageMetaPlugin } from 'frappe-ui'
import { configurePortals, SEMINARY_PORTALS } from '@seminary/portal-shell'
import { uploadLimits } from '@/utils'
import SafeHtml from '@/components/SafeHtml.vue'

// Fetch system date format early so formatDate() works everywhere
frappeRequest({ url: '/api/method/seminary.seminary.api.get_school_abbr_logo' }).then(data => {
	window.__dateFormat = data.date_format || 'yyyy-mm-dd'
})

let pinia = createPinia()
let app = createApp(App)
setConfig('resourceFetcher', frappeRequest)
uploadLimits.fetch()

// The only component allowed to render author HTML (p008 F1). Registered
// globally so migrating a v-html site is a tag swap, not an import per file.
app.component('SafeHtml', SafeHtml)

app.use(FrappeUI)
app.use(pinia)
app.use(router)
app.use(translationPlugin)
app.use(pageMetaPlugin)
app.provide('$dayjs', dayjs)
app.provide('$socket', initSocket())
app.mount('#app')

const { userResource, allUsers } = usersStore()

configurePortals({
	brand: {
		name: 'Seminary',
		color: '#0D3049',
		logoUrl: '/assets/seminary/images/klisia_icon.png',
	},
	// ADR 074: one portal per deployed SPA. The examiner/alumni/partner/community
	// entries that used to live here were all `/seminary/...` routes of this very
	// app — the sidebar reaches them without a page reload.
	portals: SEMINARY_PORTALS,
	sessionFetcher: async () => {
		await userResource.promise
		const u = userResource.data
		if (!u) return null
		return {
			user: u.email,
			full_name: u.full_name,
			email: u.email,
			image: u.user_image,
			roles: u.roles || [],
			// Whether the optional Aretenic app is installed (ADR 030); gates the
			// Aretenic entry in the portal switcher via its `when` predicate.
			has_aretenic: !!u.has_aretenic,
			// Likewise frappe_giving (ADR 074): without it /donate/donorportal has
			// no website route at all and the tile led to a 404.
			has_giving: !!u.has_giving,
		}
	},
})
app.provide('$user', userResource)
app.provide('$allUsers', allUsers)

app.config.globalProperties.$user = userResource
app.config.globalProperties.$dialog = createDialog