/**
 * The accessibility checker for content instructors write (102 §7).
 *
 * One pure function per input shape, importing only the media type list: `checkHtml` for the rich-text
 * editors, `checkBlocks` for the lesson's editorjs blocks, and `checkContent`
 * for either. Each returns a list of issues
 *
 *     { code, count, message }
 *
 * one per kind of problem, with how many times it occurs. The checker only
 * warns: callers show the list and let the instructor publish anyway.
 *
 * Kinds:
 *   image-alt       an image with no alt text
 *   heading-skip    a heading more than one level below the one before it
 *   link-empty      a link with no text
 *   link-vague      a link whose text says nothing of where it goes ("click here")
 *   table-header    a table with no header row
 *   video-captions  a video Seminary plays with no captions: in a lesson, an
 *                   uploaded or recorded video while the lesson has no caption
 *                   files; in HTML, a <video> that lists no captions (decision
 *                   109 §5) and has no captions <track>. YouTube and
 *                   Vimeo embeds carry their own captions and aren't counted.
 *
 * HTML is read with the browser's DOMParser, which builds an inert document:
 * nothing in it loads or runs. `__` is the portal's global translator, looked up
 * when a message is built.
 */

import { isImage, isVideo } from './mediaTypes.js'

// Link text that names no destination, in the portal's languages. Compared after
// lower-casing and dropping punctuation and surrounding space.
export const VAGUE_LINK_TEXT = new Set([
	// English
	'click here',
	'click',
	'here',
	'read more',
	'more',
	'link',
	'this link',
	'learn more',
	'this',
	// Portuguese
	'clique aqui',
	'clique',
	'aqui',
	'leia mais',
	'saiba mais',
	'mais',
	'este link',
	'esse link',
	// Spanish
	'haga clic aquí',
	'haz clic aquí',
	'clic aquí',
	'click aquí',
	'aquí',
	'leer más',
	'más',
	'este enlace',
	'enlace',
])


const MESSAGES = {
	'image-alt': (n) =>
		n === 1
			? __('An image has no alt text. Describe it for students who can’t see it.')
			: __('{0} images have no alt text. Describe them for students who can’t see them.').format(n),
	'heading-skip': (n) =>
		n === 1
			? __('A heading skips a level (for example, a heading 4 right after a heading 2).')
			: __('{0} headings skip a level (for example, a heading 4 right after a heading 2).').format(n),
	'link-empty': (n) =>
		n === 1
			? __('A link has no text, so a screen reader can’t say where it goes.')
			: __('{0} links have no text, so a screen reader can’t say where they go.').format(n),
	'link-vague': (n) =>
		n === 1
			? __('A link says only something like “click here”. Name where it goes instead.')
			: __('{0} links say only something like “click here”. Name where they go instead.').format(n),
	'table-header': (n) =>
		n === 1
			? __('A table has no header row.')
			: __('{0} tables have no header row.').format(n),
	'video-captions': (n) =>
		n === 1
			? __('A video has no captions.')
			: __('{0} videos have no captions.').format(n),
}

// Fixed order, so the list doesn't reshuffle as the instructor types.
const ORDER = Object.keys(MESSAGES)

function tally() {
	const counts = {}
	return {
		add(code, n = 1) {
			if (n > 0) counts[code] = (counts[code] || 0) + n
		},
		issues() {
			return ORDER.filter((code) => counts[code]).map((code) => ({
				code,
				count: counts[code],
				message: MESSAGES[code](counts[code]),
			}))
		},
	}
}

function parse(html) {
	if (typeof DOMParser === 'undefined') return null
	return new DOMParser().parseFromString(String(html ?? ''), 'text/html')
}

export function normaliseLinkText(text) {
	return String(text ?? '')
		.toLowerCase()
		.replace(/[\s ]+/g, ' ')
		.replace(/^[\s.,:;!?…»«"'“”‘’()[\]-]+|[\s.,:;!?…»«"'“”‘’()[\]-]+$/g, '')
}

function linkName(anchor) {
	const label = anchor.getAttribute('aria-label') || anchor.getAttribute('title')
	if (label && label.trim()) return label
	const alts = Array.from(anchor.querySelectorAll('img[alt]')).map((img) => img.getAttribute('alt'))
	return [anchor.textContent, ...alts].join(' ')
}

/** Headings in order -> how many skip a level. The page title above is a level 1. */
function countSkips(levels, start = 1) {
	let previous = start
	let skips = 0
	for (const level of levels) {
		if (level > previous + 1) skips++
		previous = level
	}
	return skips
}

/** Everything but headings, which the callers count across the whole content. */
function tallyFragment(doc, t) {
	doc.querySelectorAll('img').forEach((img) => {
		if (!(img.getAttribute('alt') || '').trim()) t.add('image-alt')
	})
	doc.querySelectorAll('a[href]').forEach((anchor) => {
		const name = normaliseLinkText(linkName(anchor))
		if (!name) t.add('link-empty')
		else if (VAGUE_LINK_TEXT.has(name)) t.add('link-vague')
	})
	doc.querySelectorAll('table').forEach((table) => {
		const firstRow = table.querySelector('tr')
		const hasHeader =
			table.querySelector('thead th, thead td') ||
			(firstRow && firstRow.querySelector('th'))
		if (!hasHeader) t.add('table-header')
	})
	doc.querySelectorAll('video').forEach((video) => {
		if (!listsCaptions(video) && !video.querySelector('track[kind="captions"], track[kind="subtitles"]'))
			t.add('video-captions')
	})
}

// A rich-text video keeps its caption files in `data-captions` (decision 109 §5).
function listsCaptions(video) {
	try {
		const list = JSON.parse(video.getAttribute('data-captions') || '[]')
		return Array.isArray(list) && list.some((c) => c && c.src)
	} catch {
		return false
	}
}

/** Issues in an HTML fragment (the rich-text editors). */
export function checkHtml(html) {
	const t = tally()
	const doc = parse(html)
	if (!doc) return []
	tallyFragment(doc, t)
	const levels = Array.from(doc.querySelectorAll('h1, h2, h3, h4, h5, h6')).map((h) => Number(h.tagName[1]))
	t.add('heading-skip', countSkips(levels))
	return t.issues()
}

function listHtml(items) {
	return (items || [])
		.map((item) => {
			const content = typeof item === 'string' ? item : item?.content || ''
			return content + listHtml(item?.items)
		})
		.join(' ')
}

/**
 * Issues in editorjs blocks (the lesson editor).
 * `options.captions`: the lesson's caption rows; any one counts for its videos.
 */
export function checkBlocks(blocks, options = {}) {
	const t = tally()
	const hasCaptions = (options.captions || []).some((row) => row && (row.caption_file || row.file))
	const levels = []
	const inline = []

	for (const block of blocks || []) {
		const data = block?.data || {}
		switch (block?.type) {
			case 'header':
				if (String(data.text || '').trim()) levels.push(Number(data.level) || 2)
				break
			case 'paragraph':
			case 'markdown':
				inline.push(data.text || '')
				break
			case 'list':
				inline.push(listHtml(data.items))
				break
			case 'image':
				if (!String(data.caption || '').replace(/<[^>]*>/g, '').trim()) t.add('image-alt')
				break
			case 'upload': {
				if (isVideo(data.file_type)) {
					if (!hasCaptions) t.add('video-captions')
				} else if (data.file_url && isImage(data.file_type) && !String(data.alt || '').trim()) {
					t.add('image-alt')
				}
				break
			}
			case 'recordVideo':
				if (data.file_url && !hasCaptions) t.add('video-captions')
				break
			case 'table':
				if ((data.content || []).length && !data.withHeadings) t.add('table-header')
				break
			default:
				break
		}
	}

	const doc = parse(inline.join('\n'))
	if (doc) tallyFragment(doc, t)
	t.add('heading-skip', countSkips(levels))
	return t.issues()
}

/** Either shape: HTML, editorjs JSON (string or object), or a block list. */
export function checkContent(content, options = {}) {
	if (Array.isArray(content)) return checkBlocks(content, options)
	if (content && typeof content === 'object') return checkBlocks(content.blocks, options)
	const text = String(content ?? '').trim()
	if (text.startsWith('{')) {
		try {
			const parsed = JSON.parse(text)
			if (Array.isArray(parsed?.blocks)) return checkBlocks(parsed.blocks, options)
		} catch {
			/* not JSON: read it as HTML */
		}
	}
	return checkHtml(text)
}
