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

	// youtu.be/<id>
	const short = trimmed.match(/youtu\.be\/([A-Za-z0-9_-]{6,})/)
	if (short) return short[1]

	// youtube.com/embed/<id>
	const embed = trimmed.match(/youtube\.com\/embed\/([A-Za-z0-9_-]{6,})/)
	if (embed) return embed[1]

	// youtube.com/watch?v=<id>
	const watch = trimmed.match(/[?&]v=([A-Za-z0-9_-]{6,})/)
	if (watch) return watch[1]

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
