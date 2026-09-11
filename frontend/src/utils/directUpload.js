/**
 * Direct browser-to-object-storage upload.
 *
 * Frappe's `/api/method/upload_file` reads the whole request body into a worker
 * before a byte reaches storage, and nginx caps the body size on top of that.
 * A lecture recording cannot get through either. This path asks the server to
 * authorise one upload, PUTs the bytes straight to object storage, then asks the
 * server to verify and record it.
 *
 * The server chooses the object key and re-derives the file's size from storage,
 * so nothing here is trusted: see `seminary/storage/direct.py`. This module only
 * has to move bytes and report progress honestly.
 *
 * `uploadDirect` returns `null` when the server says this file is not eligible
 * (no object storage configured, or small enough that the ordinary upload path is
 * simpler). Callers fall back to `FileUploader` in that case rather than failing.
 */

const getCsrfToken = () => {
	if (typeof window === 'undefined') return null
	return (
		window.csrf_token ||
		window.frappe?.csrf_token ||
		document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
		null
	)
}

async function callMethod(method, body) {
	const headers = { 'Content-Type': 'application/json' }
	const token = getCsrfToken()
	if (token) headers['X-Frappe-CSRF-Token'] = token

	const response = await fetch(`/api/method/${method}`, {
		method: 'POST',
		headers,
		credentials: 'same-origin',
		body: JSON.stringify(body),
	})

	const payload = await response.json().catch(() => ({}))
	if (!response.ok) {
		// Frappe puts a thrown message in _server_messages as JSON-in-JSON.
		let message = payload.exception || payload.message || response.statusText
		try {
			const messages = JSON.parse(payload._server_messages || '[]')
			if (messages.length) message = JSON.parse(messages[0]).message || message
		} catch (e) {
			/* keep the fallback message */
		}
		throw new Error(message)
	}
	return payload.message
}

/**
 * PUT a file straight to storage, reporting progress.
 *
 * XHR rather than fetch because only XHR exposes upload progress, and a
 * multi-hundred-megabyte upload with no progress bar is indistinguishable from a
 * hung page.
 */
function putToStorage(url, file, contentType, onProgress) {
	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest()
		xhr.open('PUT', url, true)
		// Must match the type the presign signed, or the signature will not verify.
		xhr.setRequestHeader('Content-Type', contentType)

		xhr.upload.onprogress = (event) => {
			if (event.lengthComputable && onProgress) {
				onProgress(Math.round((event.loaded / event.total) * 100))
			}
		}
		xhr.onload = () =>
			xhr.status >= 200 && xhr.status < 300
				? resolve()
				: reject(new Error(`Storage rejected the upload (${xhr.status})`))
		xhr.onerror = () =>
			reject(
				new Error(
					'Could not reach storage. If this persists, the bucket may be missing a CORS rule for this site.'
				)
			)
		xhr.onabort = () => reject(new Error('Upload cancelled'))

		xhr.send(file)
	})
}

/**
 * @param {File} file
 * @param {object} [options]
 * @param {string} [options.doctype]   attach target, checked server-side
 * @param {string} [options.docname]
 * @param {string} [options.fieldname]
 * @param {boolean} [options.isPrivate=true]
 * @param {string} [options.folder]
 * @param {(percent: number) => void} [options.onProgress]
 * @returns {Promise<object|null>} the created File, or null if not eligible
 */
export async function uploadDirect(file, options = {}) {
	const presigned = await callMethod('seminary.storage.direct.presign_upload', {
		file_name: file.name,
		file_size: file.size,
		content_type: file.type || 'application/octet-stream',
		doctype: options.doctype,
		docname: options.docname,
		fieldname: options.fieldname,
		is_private: options.isPrivate === false ? 0 : 1,
		folder: options.folder,
	})

	if (!presigned || !presigned.direct) return null

	await putToStorage(
		presigned.upload_url,
		file,
		presigned.headers['Content-Type'],
		options.onProgress
	)

	return await callMethod('seminary.storage.direct.register_upload', {
		key: presigned.key,
	})
}
