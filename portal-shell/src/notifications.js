// Notifications on the person's devices (seminary decisions/121 and its addendum), a separate
// entry from index.js because it imports frappe-ui, like ./tabs.js. Any portal on the site can
// show the section; one service worker at /sw.js serves them all.
export { default as DeviceNotifications } from './components/DeviceNotifications.vue'
export {
  currentSubscription,
  endpointHash,
  needsHomeScreen,
  permission,
  pushSupported,
  turnOff,
  turnOn,
} from './webPush.js'
