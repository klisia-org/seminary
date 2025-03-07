import './index.css'

import { createApp } from 'vue'
import router from './router'
import App from './App.vue'
import { createPinia } from 'pinia'
// import '../polyfills'
import dayjs from '@/utils/dayjs'
import { createDialog } from '@/utils/dialogs'

import { usersStore } from './stores/user'
import { initSocket } from './socket'
import { FrappeUI, pageMetaPlugin, Button, Card, Input, setConfig, frappeRequest, resourcesPlugin} from 'frappe-ui'

// create a pinia instance
let pinia = createPinia()

let app = createApp(App)

setConfig('resourceFetcher', frappeRequest)

//app.use(FrappeUI)
app.use(pinia)
app.use(router)
app.use(resourcesPlugin)

app.use(pageMetaPlugin)
app.provide('$dayjs', dayjs)
app.provide('$socket', initSocket())

app.component('Button', Button)
app.component('Card', Card)
app.component('Input', Input)

router.isReady().then(() => {
	app.mount("#app")
})

const { userResource, allUsers } = usersStore()
app.provide('$user', userResource)
app.provide('$allUsers', allUsers)
app.config.globalProperties.$user = userResource
app.config.globalProperties.$dialog = createDialog

