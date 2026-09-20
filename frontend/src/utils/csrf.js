/**
 * The one place the CSRF token is read (p005a A07-4).
 *
 * This chain was copy-pasted into eight files, which had already drifted apart:
 * three guarded `typeof window`, five did not; three returned `null` when the
 * token was missing and five returned `''`. Neither difference changed whether
 * a request was accepted -- both are falsy, and an unconditional header of
 * "null" or "" fails Frappe's comparison identically -- but there was no
 * canonical copy left to model a ninth on.
 *
 * Returns `''` rather than `null` when absent: it is falsy for the
 * `if (token)` call sites, and it keeps the literal string "null" out of a
 * header on the sites that send it unconditionally.
 *
 * What this does NOT do is send the request. Each call site keeps its own
 * plumbing -- `fetch` vs `XMLHttpRequest` (two of them need upload progress,
 * which `fetch` cannot report), its own `credentials` mode and its own error
 * handling. Consolidating those is a separate, larger change.
 *
 * NOTE: enforcement does not depend on this function. Frappe skips CSRF
 * validation entirely when the session has no stored token
 * (`frappe/auth.py:87`), and that slot is filled lazily -- our SPA only gets
 * checked because `www/seminary.py` calls `get_csrf_token()` when it builds
 * the boot. `test_p010_boot.test_csrf_token_is_still_shipped` guards that line.
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
