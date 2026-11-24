/**
 * Frames and caption tracks the page builds itself (decision 109 §1, §5).
 *
 * Nothing here comes from the author's markup. An embed is saved as a link,
 *
 *     <figure data-embed="URL"><a href="URL">title</a></figure>
 *
 * and a rich-text video lists its captions in `data-captions` (JSON). Both survive
 * the sanitisers, which refuse <iframe> and <track>. `buildRichMedia` runs on the
 * already-sanitised DOM and builds the frame and the tracks from checked values.
 */
import { safeEmbedUrl } from './urlPolicy.js'

/** The responsive 16:9 frame for a checked embed URL, built node by node. */
export function buildEmbed(url, title = '') {
	const outer = document.createElement('div')
	outer.style.width = '100%'
	const ratio = document.createElement('div')
	ratio.style.position = 'relative'
	ratio.style.paddingBottom = '56.25%'
	ratio.style.height = '0'
	const frame = document.createElement('iframe')
	frame.setAttribute('src', url)
	if (title) frame.setAttribute('title', title)
	frame.setAttribute('frameborder', '0')
	frame.setAttribute('scrolling', 'yes')
	frame.setAttribute('allowfullscreen', 'true')
	frame.setAttribute('loading', 'lazy')
	frame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin')
	frame.style.position = 'absolute'
	frame.style.top = '0'
	frame.style.left = '0'
	frame.style.width = '100%'
	frame.style.height = '100%'
	ratio.appendChild(frame)
	outer.appendChild(ratio)
	return outer
}

// A caption file must be one uploaded to this site: on disk, or in object storage
// (seminary/storage/backend.py FILE_URL_RE).
const SITE_FILE =
	/^(?:\/(?:private\/)?files\/[^?#"'<>\s]+|\/api\/method\/seminary\.storage\.api\.download_file\?key=[A-Za-z0-9/._-]+)$/

/** The captions a rich-text video lists, keeping only files on this site. */
export function readCaptions(value) {
	let list
	try {
		list = JSON.parse(value || '[]')
	} catch {
		return []
	}
	if (!Array.isArray(list)) return []
	return list
		.filter((c) => c && typeof c.src === 'string' && SITE_FILE.test(c.src))
		.map((c) => ({
			src: c.src,
			srclang: String(c.srclang || '').slice(0, 20),
			label: String(c.label || c.srclang || '').slice(0, 80),
		}))
}

// Text blocks a line's own script sets the direction of (decision 109 §4). The editor
// saves `dir="auto"`; this covers text saved before it did.
const TEXT_BLOCKS = 'p, h1, h2, h3, h4, h5, h6, li, blockquote, td, th'

/** Build the frames and caption tracks inside a sanitised fragment, in place. */
export function buildRichMedia(root) {
	root.querySelectorAll(TEXT_BLOCKS).forEach((el) => {
		if (!el.hasAttribute('dir')) el.setAttribute('dir', 'auto')
	})
	root.querySelectorAll('figure[data-embed]').forEach((figure) => {
		const url = safeEmbedUrl(figure.getAttribute('data-embed'))
		if (!url) return
		const link = figure.querySelector('a')
		const title = (link?.textContent || '').trim()
		const frame = buildEmbed(url, title)
		frame.className = 'rich-embed'
		figure.replaceChildren(frame)
	})
	root.querySelectorAll('video[data-captions]').forEach((video) => {
		video.querySelectorAll('track').forEach((t) => t.remove())
		readCaptions(video.getAttribute('data-captions')).forEach((c, i) => {
			const track = document.createElement('track')
			track.setAttribute('kind', 'captions')
			track.setAttribute('src', c.src)
			if (c.srclang) track.setAttribute('srclang', c.srclang)
			if (c.label) track.setAttribute('label', c.label)
			if (i === 0) track.setAttribute('default', '')
			video.appendChild(track)
		})
	})
	return root
}
