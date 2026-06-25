import { reactive } from 'vue'

const config = reactive({
  brand: { name: 'Portal', logoUrl: null, color: '#0D3049' },
  portals: [],
  sessionFetcher: defaultSessionFetcher,
  onSignOut: defaultSignOut,
})

export function configurePortals(options) {
  if (options.brand) Object.assign(config.brand, options.brand)
  if (options.portals) config.portals = options.portals
  if (options.sessionFetcher) config.sessionFetcher = options.sessionFetcher
  if (options.onSignOut) config.onSignOut = options.onSignOut
}

export function getPortalConfig() {
  return config
}

// Generic fallback: identifies the logged-in user. Roles come from the User doc's child table when
// readable (admins); regular users see it empty, so apps that gate on roles MUST supply their own
// sessionFetcher (e.g. a whitelisted current_user method). We deliberately do NOT query `Has Role`
// directly — that 403s for non-privileged users and surfaces a PermissionError in the console.
async function defaultSessionFetcher() {
  const userId = readCookie('user_id')
  if (!userId || userId === 'Guest') return null

  const res = await fetch('/api/method/frappe.client.get?doctype=User&name=' + encodeURIComponent(userId), {
    headers: { 'X-Frappe-CSRF-Token': window.csrf_token || '' },
    credentials: 'same-origin',
  })
  if (!res.ok) return null
  const { message } = await res.json()
  if (!message) return null

  const roles = (message.roles || []).map((r) => r.role)

  return {
    user: userId,
    full_name: message.full_name || userId,
    email: message.email || userId,
    image: message.user_image || null,
    roles,
  }
}

async function defaultSignOut() {
  await fetch('/api/method/logout', { credentials: 'same-origin' })
  window.location.href = '/login'
}

function readCookie(name) {
  const match = document.cookie.split('; ').find((c) => c.startsWith(name + '='))
  if (!match) return null
  return decodeURIComponent(match.split('=')[1])
}
