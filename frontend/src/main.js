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
import { configurePortals } from '@seminary/portal-shell'

// Fetch system date format early so formatDate() works everywhere
frappeRequest({ url: '/api/method/seminary.seminary.api.get_school_abbr_logo' }).then(data => {
	window.__dateFormat = data.date_format || 'yyyy-mm-dd'
})

let pinia = createPinia()
let app = createApp(App)
setConfig('resourceFetcher', frappeRequest)

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
	portals: [
		{ id: 'student', label: 'Courses', url: '/seminary', roles: ['Student', 'Academics User', 'Instructor'] },
		{ id: 'alumni', label: 'Alumni', url: '/seminary/alumni', roles: ['Alumni'] },
		{ id: 'donor', label: 'Donate', url: '/donate/donorportal' },
	],
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
		}
	},
})
app.provide('$user', userResource)
app.provide('$allUsers', allUsers)

app.config.globalProperties.$user = userResource
app.config.globalProperties.$dialog = createDialog