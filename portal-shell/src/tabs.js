// Secondary navigation (seminary ADR 075), a separate entry from index.js because it imports
// vue-router and frappe-ui. A bare import inside dist/ resolves from portal-shell's directory,
// where peer dependencies are never installed, so every app importing the main entry had to
// alias both — including frappe_giving, which has no frappe-ui at all. Only apps with tabbed
// pages import this one.
export { default as PageTabs } from './components/PageTabs.vue'
export { useTabParam } from './composables/useTabParam.js'
