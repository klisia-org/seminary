// The portals share one translation plugin (aretenic decision 071); seminary's original
// moved to portal-shell. Kept as a module so `main.js` and any direct import still resolve.
export { translationPlugin as default } from '@seminary/portal-shell'
