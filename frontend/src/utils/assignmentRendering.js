// Helpers for rendering Assignment Submissions in the grading view.

/**
 * Pull a YouTube video id from a URL.
 * Handles youtube.com/watch?v=, youtu.be/, youtube.com/embed/, with optional
 * leading whitespace, query strings, and time fragments. Returns null when the
 * input isn't recognisably a YouTube link.
 */
export function parseYouTubeId(url) {
	if (!url || typeof url !== 'string') return null
	const trimmed = url.trim()

	// a bare 11-character video id pasted on its own
	if (/^[A-Za-z0-9_-]{11}$/.test(trimmed)) return trimmed

	// youtu.be/<id>, /embed/<id>, /live/<id>, /shorts/<id>, watch?v=<id>
	const patterns = [
		/youtu\.be\/([A-Za-z0-9_-]{6,})/,
		/youtube\.com\/embed\/([A-Za-z0-9_-]{6,})/,
		/youtube\.com\/live\/([A-Za-z0-9_-]{6,})/,
		/youtube\.com\/shorts\/([A-Za-z0-9_-]{6,})/,
		/[?&]v=([A-Za-z0-9_-]{6,})/,
	]
	for (const re of patterns) {
		const m = trimmed.match(re)
		if (m) return m[1]
	}
	return null
}

/**
 * Mammoth can only convert .docx in the browser; .doc (legacy binary) falls
 * back to a download link.
 */
export function isDocxUrl(url) {
	if (!url || typeof url !== 'string') return false
	return url.toLowerCase().split('?')[0].endsWith('.docx')
}
