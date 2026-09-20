/**
 * The one place portal-shell reads the CSRF token (p005a A07-4).
 *
 * Its own copy rather than an import from the SPA: portal-shell is a separate
 * package, built on its own and consumed through `link:../portal-shell`, so it
 * cannot reach into `frontend/src`. The contract test therefore requires one
 * reader *per package* rather than one overall.
 *
 * Same chain as `frontend/src/utils/csrf.js`. The previous inline read here was
 * `window.csrf_token || ''` -- the fallbacks are a superset, so no request that
 * worked before stops working.
 */
export function getCsrfToken() {
  if (typeof window === 'undefined') return ''
  return (
    window.csrf_token ||
    window.frappe?.csrf_token ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
    ''
  )
}
