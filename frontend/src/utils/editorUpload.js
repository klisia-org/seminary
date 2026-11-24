/**
 * Uploads from the rich-text editors, with progress (decision 109).
 *
 * frappe-ui's editors upload through `/api/method/upload_file` and say nothing until
 * the file is in: a lecture video could take minutes with no sign that anything was
 * happening. This is the same route SmartFileUploader takes: straight to object
 * storage where the site has it (`uploadDirect`), otherwise through the server, and
 * it reports progress either way. The size is checked first, so a file that is too
 * big is refused before the wait rather than after it.
 */
import { getCsrfToken } from './csrf'
import { uploadDirect } from './directUpload'
import { uploadLimits, validateFileSize } from './index'

function serverMessage(payload, status) {
	try {
		const messages = JSON.parse(payload?._server_messages || '[]')
		const first = messages.length ? JSON.parse(messages[0]) : null
		if (first?.message) return first.message
	} catch {
		/* fall through */
	}
	if (status === 413) return __('This file is too large for the server to accept.')
	return payload?.exception || __('Error Uploading File')
}

function uploadThroughServer(file, onProgress) {
	return new Promise((resolve, reject) => {
		const form = new FormData()
		form.append('file', file, file.name)
		form.append('is_private', '0')
		form.append('folder', 'Home')
		const xhr = new XMLHttpRequest()
		xhr.open('POST', '/api/method/upload_file', true)
		xhr.withCredentials = true
		const token = getCsrfToken()
		if (token) xhr.setRequestHeader('X-Frappe-CSRF-Token', token)
		xhr.upload.onprogress = (event) => {
			if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100))
		}
		xhr.onload = () => {
			let payload = {}
			try {
				payload = JSON.parse(xhr.responseText)
			} catch {
				/* fall through to the status check */
			}
			if (xhr.status >= 200 && xhr.status < 300) return resolve(payload.message)
			reject(new Error(serverMessage(payload, xhr.status)))
		}
		xhr.onerror = () => reject(new Error(__('Could not reach the server. Please check your connection.')))
		xhr.send(form)
	})
}

/** Upload `file` for an editor; resolves to the File ({ file_url, ... }). */
export async function uploadForEditor(file, { onProgress } = {}) {
	if (!uploadLimits.data && !uploadLimits.loading) await uploadLimits.reload().catch(() => {})
	const tooBig = validateFileSize(file, { allowDirect: true })
	if (tooBig) throw new Error(tooBig)
	// Editor uploads are public, as frappe-ui's own were: an announcement's video is
	// opened from an email by people who may not be signed in.
	const direct = await uploadDirect(file, { isPrivate: false, folder: 'Home', onProgress })
	return direct ?? (await uploadThroughServer(file, onProgress))
}
