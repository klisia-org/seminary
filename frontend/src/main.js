import './index.css'

import { createApp } from 'vue'
import router from './router'
import App from './App.vue'
import { createPinia } from 'pinia'
import { usersStore } from './stores/user'
import translationPlugin from './translation'
import { initSocket } from './socket'
import dayjs from '@/utils/dayjs'
import { createDialog } from '@/utils/dialogs'


import {

  Button,
  Card,
  Input,
  setConfig,
  frappeRequest,
  resourcesPlugin,
  pageMetaPlugin
} from 'frappe-ui'

const pinia = createPinia()
let app = createApp(App)

setConfig('resourceFetcher', frappeRequest)


app.use(router)
app.use(resourcesPlugin)
app.use(pinia)
app.use(pageMetaPlugin)
app.use(translationPlugin)

app.component('Button', Button)
app.component('Card', Card)
app.component('Input', Input)
app.provide('$dayjs', dayjs)

const { userResource, allUsers } = usersStore()

// Initialize socket only after user is authenticated
let socket = null
const initializeSocket = () => {
  try {
    if (userResource.data && userResource.data.name !== 'Guest') {
      socket = initSocket()
      app.provide('$socket', socket)
      app.config.globalProperties.$socket = socket
      console.log('Socket initialized successfully')
    } else {
      console.warn('User not authenticated, skipping socket initialization')
    }
  } catch (err) {
    console.error('Failed to initialize socket:', err)
    // Don't throw - app can work without realtime updates
  }
}

// Wait for router and user to be ready before initializing socket
router.isReady().then(() => {
  userResource.promise
    .then(() => {
      initializeSocket()
    })
    .catch(err => {
      console.warn('User authentication check failed:', err)
    })
})

app.mount('#app')

app.provide('$user', userResource)
app.provide('$allUsers', allUsers)
app.config.globalProperties.$user = userResource
app.config.globalProperties.$dialog = createDialog