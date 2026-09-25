export {
  configurePortals,
  getPortalConfig,
  defaultSessionFetcher,
  visiblePortalsFor,
} from './config.js'
export { SEMINARY_PORTALS } from './portals.js'
export { useSession } from './composables/useSession.js'
export { useTheme } from './composables/useTheme.js'
// The page frame (seminary ADR 075). It lives here rather than in seminary's own frontend
// because ADR 075's whole thesis is one primitive, not nine — and the accreditation SPA needs
// the same one. Seminary's original path is a re-export shim. The tabs half of ADR 075 is in
// ./tabs.js, a separate entry (`@seminary/portal-shell/tabs`).
export { default as PageHeader } from './components/PageHeader.vue'
export { default as PortalHeader } from './components/PortalHeader.vue'
export { default as PortalSwitcher } from './components/PortalSwitcher.vue'
export { default as UserMenu } from './components/UserMenu.vue'
