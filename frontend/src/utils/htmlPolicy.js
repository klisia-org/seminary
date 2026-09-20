/**
 * The HTML policy shared by every client-side render (p008 F1).
 *
 * MIRRORS seminary/seminary/content_safety.py -- keep the two in step. The
 * server cleans what is stored; this cleans what is rendered, and it is the only
 * layer for content that never passed the server's sanitiser (EditorJS JSON,
 * mammoth's DOCX output, pasted HTML, anything stored before p008).
 */

// Builds a credential form or re-styles the page. None is producible by the
// editors; all survive Frappe's nh3 allow-list (p005a A05-6).
export const FORBIDDEN_TAGS = [
	'form',
	'input',
	'button',
	'textarea',
	'select',
	'option',
	'style',
	'base',
	'meta',
	'link',
]

// Additionally refused at render: active or foreign-namespace content. An
// embed is built by its own tool from a checked URL, never passed through.
export const RENDER_FORBIDDEN_TAGS = [...FORBIDDEN_TAGS, 'iframe', 'object', 'embed', 'svg', 'math']

export const FORBIDDEN_ATTR = ['srcdoc', 'formaction', 'ping', 'autofocus', 'xlink:href']

/**
 * A DENY-list of CSS properties, on purpose. Frappe's sanitiser permits ~726
 * properties and authored content relies on many of them (table widths, image
 * floats, alignment, RTL). What an attacker needs to cover the page with a fake
 * login is the short list below; everything else passes untouched.
 */
export const LAYOUT_ESCAPE = [
	'position',
	'z-index',
	'top',
	'right',
	'bottom',
	'left',
	'opacity',
	'transform',
	'pointer-events',
	'mix-blend-mode',
	'clip-path',
	'content',
	'behavior',
	'-moz-binding',
]

export function isLayoutEscape(property) {
	const p = (property || '').trim().toLowerCase()
	return LAYOUT_ESCAPE.includes(p) || p.startsWith('inset')
}

/** Keep every declaration except the layout-escape ones and any that fetches. */
export function filterStyle(style) {
	return (style || '')
		.split(';')
		.map((d) => d.trim())
		.filter(Boolean)
		.filter((d) => {
			const i = d.indexOf(':')
			if (i < 1) return false
			const value = d.slice(i + 1).toLowerCase()
			if (isLayoutEscape(d.slice(0, i))) return false
			return !/url\s*\(|expression\s*\(|javascript:/.test(value)
		})
		.join('; ')
}
