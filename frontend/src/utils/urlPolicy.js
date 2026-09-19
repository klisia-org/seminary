/**
 * URL scheme allow-list for user-authored links (p008 F7). Mirrors
 * seminary/seminary/url_policy.py.
 *
 * Bind `:href="safeUrl(x)"` wherever the value was typed by a user. Returns ''
 * for anything that is not http(s), mailto, tel, or a same-site relative path --
 * `javascript:`, `data:`, `vbscript:` and protocol-relative `//host` included.
 */
const SCHEME = /^([a-z][a-z0-9+.-]*):/i
const ALLOWED = new Set(['http', 'https', 'mailto', 'tel'])

// Browsers drop tabs, newlines and other control characters before resolving a
// scheme, so "java<newline>script:" IS javascript:. Strip them before looking.
function stripControls(s) {
	return Array.from(s)
		.filter((c) => {
			const n = c.charCodeAt(0)
			return n > 31 && n !== 127
		})
		.join('')
}

export function safeUrl(value) {
	const s = stripControls(String(value ?? '')).trim()
	if (!s || s.startsWith('//') || s.startsWith('\\')) return ''
	const m = SCHEME.exec(s)
	if (!m) return s // relative path, fragment or query
	return ALLOWED.has(m[1].toLowerCase()) ? s : ''
}

/** Absolute http(s) only, and not this site -- for embeds (iframes). */
export function safeEmbedUrl(value, origin = window.location.origin) {
	const s = safeUrl(value)
	if (!/^https?:\/\//i.test(s)) return ''
	try {
		const u = new URL(s)
		return u.origin === origin ? '' : u.href
	} catch {
		return ''
	}
}
