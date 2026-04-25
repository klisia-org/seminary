import { computed, shallowReactive, onMounted } from 'vue'
import { getPortalConfig } from '../config.js'

const state = shallowReactive({
  user: null,
  loading: false,
  error: null,
  hasLoaded: false,
})
let inflight = null

async function load() {
  if (inflight) return inflight
  state.loading = true
  state.error = null
  inflight = (async () => {
    try {
      state.user = await getPortalConfig().sessionFetcher()
    } catch (err) {
      state.error = err
      state.user = null
    } finally {
      state.loading = false
      state.hasLoaded = true
      inflight = null
    }
  })()
  return inflight
}

export function useSession({ autoLoad = true } = {}) {
  if (autoLoad && !state.hasLoaded && !state.loading) {
    onMounted(load)
  }

  return {
    user: computed(() => state.user),
    loading: computed(() => state.loading),
    error: computed(() => state.error),
    hasLoaded: computed(() => state.hasLoaded),
    reload: load,
    signOut: () => getPortalConfig().onSignOut(),
  }
}
