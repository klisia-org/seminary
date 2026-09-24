export {
  configurePortals,
  getPortalConfig,
  defaultSessionFetcher,
  visiblePortalsFor,
} from './config.js'
export { SEMINARY_PORTALS } from './portals.js'
export { useSession } from './composables/useSession.js'
export { useTheme } from './composables/useTheme.js'
// Secondary navigation and the page frame (seminary ADR 075). They live here rather than in
// seminary's own frontend because ADR 075's whole thesis is one primitive, not nine — and the
// accreditation SPA needs the same ones. Seminary's original paths are re-export shims.
export { default as PageHeader } from './components/PageHeader.vue'
export { default as PageTabs } from './components/PageTabs.vue'
export { useTabParam } from './composables/useTabParam.js'
export { default as PortalHeader } from './components/PortalHeader.vue'
export { default as PortalSwitcher } from './components/PortalSwitcher.vue'
export { default as UserMenu } from './components/UserMenu.vue'
