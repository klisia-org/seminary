/**
 * The media types Seminary plays and shows (decision 109 §2).
 *
 * One list for the upload pickers and the blocks that render the files, so a file the
 * picker takes is never one the page can't play. A type is a file's extension, as
 * Frappe records it in `File.file_type`, matched without regard to case.
 */
export const VIDEO_TYPES = ['mp4', 'm4v', 'webm', 'mov', 'ogv']
export const AUDIO_TYPES = ['mp3', 'm4a', 'aac', 'wav', 'ogg', 'oga', 'opus', 'flac']
export const IMAGE_TYPES = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'avif', 'svg', 'bmp']

const has = (list) => (type) => list.includes(String(type || '').toLowerCase().replace(/^\./, ''))

export const isVideo = has(VIDEO_TYPES)
export const isAudio = has(AUDIO_TYPES)
export const isImage = has(IMAGE_TYPES)
export const isPdf = has(['pdf'])

const dotted = (list) => list.map((t) => `.${t}`)

/** For a file input's `accept`, or SmartFileUploader's `fileTypes`. */
export const VIDEO_ACCEPT = dotted(VIDEO_TYPES)
export const AUDIO_ACCEPT = dotted(AUDIO_TYPES)
export const IMAGE_ACCEPT = dotted(IMAGE_TYPES)
export const LESSON_UPLOAD_ACCEPT = [...VIDEO_ACCEPT, ...AUDIO_ACCEPT, ...IMAGE_ACCEPT, '.pdf']

/** The extension of a file name or URL, without the dot. */
export const fileType = (name) => {
	const base = String(name || '').split('?')[0].split('#')[0].split('/').pop()
	const dot = base.lastIndexOf('.')
	return dot > 0 ? base.slice(dot + 1).toLowerCase() : ''
}
