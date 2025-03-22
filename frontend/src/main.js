import './index.css'

import { createApp } from 'vue'
import router from './router'
import App from './App.vue'
import { createPinia } from 'pinia'
import { usersStore } from './stores/user'
import translationPlugin from './translation'
import dayjs from '@/utils/dayjs'


import {
  Button,
  Card,
  Input,
  setConfig,
  frappeRequest,
  resourcesPlugin,
} from 'frappe-ui'

const pinia = createPinia()
let app = createApp(App)


setConfig('resourceFetcher', frappeRequest)

app.use(router)
app.use(resourcesPlugin)
app.use(pinia)
app.use(translationPlugin)

app.component('Button', Button)
app.component('Card', Card)
app.component('Input', Input)

app.mount('#app')

const { userResource, allUsers } = usersStore()
app.provide('$dayjs', dayjs)
app.provide('$user', userResource)
app.provide('$allUsers', allUsers)
app.config.globalProperties.$user = userResource
