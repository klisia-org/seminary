/**
 * The one place HTML is cleaned before it is rendered (p008 F1).
 *
 *   sanitize(html)             rich text: everything the editors produce
 *   sanitize(html, 'inline')   phrasing content only, for <span> contexts
 *   sanitize(html, 'docx')     mammoth output (same policy as rich)
 *   sanitize(html, 'svg')      a hand-written icon (Communication Channel)
 *   sanitize(html, 'code')     a highlighted code block: <span class> and breaks
 *
 * Use it through <SafeHtml>, or directly where a tool writes to the DOM itself
 * (the EditorJS blocks). Policy constants live in htmlPolicy.js.
 */
import DOMPurify from 'dompurify'
import { RENDER_FORBIDDEN_TAGS, FORBIDDEN_ATTR, filterStyle } from './htmlPolicy.js'

// Tighter than DOMPurify's default, which also admits cid:, xmpp:, sms: etc.
// Relative URLs, fragments and queries still pass. Note DOMPurify admits data:
// on <img>/<video>/<audio> regardless of this pattern; that is wanted -- an image
// pasted into the text editor IS a data: URI, as are mammoth's -- and no script
// runs in an image context. data: in an href is refused like any other scheme.
const URI = /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.:-]|$))/i

const RICH = {
	FORBID_TAGS: RENDER_FORBIDDEN_TAGS,
	FORBID_ATTR: FORBIDDEN_ATTR,
	// data-* stays (DOMPurify's default), as on the server: the text editor marks
	// checklists and mentions with it, and the attributes are inert.
	ALLOWED_URI_REGEXP: URI,
	ADD_ATTR: ['target'],
}

export const PROFILES = {
	rich: RICH,
	docx: RICH, // mammoth output; named so call sites say what they render
	inline: {
		ALLOWED_TAGS: ['b', 'strong', 'i', 'em', 'u', 's', 'sup', 'sub', 'span', 'code', 'br', 'a', 'mark', 'small'],
		ALLOWED_ATTR: ['href', 'target', 'rel', 'lang', 'dir', 'class', 'title', 'style'],
		ALLOWED_URI_REGEXP: URI,
	},
	svg: {
		USE_PROFILES: { svg: true, svgFilters: true },
		FORBID_TAGS: ['script', 'foreignObject', 'use', 'image', 'a', 'animate', 'animateTransform', 'animateMotion', 'set', 'style'],
		FORBID_ATTR: FORBIDDEN_ATTR,
		ALLOW_DATA_ATTR: false,
		ALLOWED_URI_REGEXP: URI,
	},
	code: {
		ALLOWED_TAGS: ['span', 'br', 'div'],
		ALLOWED_ATTR: ['class'],
	},
}

export function installHooks(purify) {
	purify.addHook('afterSanitizeAttributes', (node) => {
		if (!node.getAttribute) return
		const style = node.getAttribute('style')
		if (style !== null) {
			const kept = filterStyle(style)
			if (kept) node.setAttribute('style', kept)
			else node.removeAttribute('style')
		}
		if (node.tagName === 'A' && node.getAttribute('target')) {
			node.setAttribute('rel', 'noopener noreferrer')
		}
	})
}

let hooked = false

export function sanitize(html, profile = 'rich') {
	if (html === null || html === undefined || html === '') return ''
	if (!hooked) {
		installHooks(DOMPurify)
		hooked = true
	}
	return DOMPurify.sanitize(String(html), PROFILES[profile] || PROFILES.rich)
}
