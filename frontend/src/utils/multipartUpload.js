/**
 * A video sent to object storage in parts (privatedocs p029 §4).
 *
 * The recorder pushes its data as it records; this fills fixed-size parts (R2
 * refuses a join of unequal parts) and sends each one as soon as it is full, so
 * a dropped connection costs one part, which is retried, never the recording.
 * The server lists the parts itself when it joins them, so nothing here needs
 * a part's ETag.
 *
 *   const up = await MultipartUpload.start({ fileName, contentType, assignment })
 *   up.push(blob) ... await up.finish()   // -> the File row
 *
 * `uploadVideoFile(file, assignment, onProgress)` sends a chosen file the same way.
 */

import { getCsrfToken } from './csrf'

const RETRIES = 4

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

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function putPart(url, blob, onProgress) {
	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest()
		xhr.open('PUT', url, true)
		xhr.upload.onprogress = (event) => {
			if (event.lengthComputable && onProgress) onProgress(event.loaded)
		}
		xhr.onload = () =>
			xhr.status >= 200 && xhr.status < 300
				? resolve()
				: reject(new Error(`Storage rejected the upload (${xhr.status})`))
		xhr.onerror = () => reject(new Error('Could not reach storage.'))
		xhr.onabort = () => reject(new Error('Upload cancelled'))
		xhr.send(blob)
	})
}

export class MultipartUpload {
	static async start({ fileName, contentType, assignment }) {
		const out = await callMethod('seminary.storage.direct.start_multipart', {
			file_name: fileName,
			content_type: contentType,
			assignment,
		})
		return new MultipartUpload(out)
	}

	constructor({ key, part_size, max_bytes }) {
		this.key = key
		this.partSize = part_size
		this.maxBytes = max_bytes
		this.buffer = []
		this.buffered = 0
		this.partNumber = 0
		this.sent = 0
		this.inFlight = 0
		this.received = 0
		// Parts go one at a time, in order; each waits for the one before it.
		this.queue = Promise.resolve()
		this.error = null
		this.onProgress = null
	}

	/** Bytes received so far, sent or not. */
	get size() {
		return this.received
	}

	push(blob) {
		if (!blob || !blob.size) return
		this.buffer.push(blob)
		this.buffered += blob.size
		this.received += blob.size
		while (this.buffered >= this.partSize) {
			const whole = new Blob(this.buffer)
			this._send(whole.slice(0, this.partSize))
			const rest = whole.slice(this.partSize)
			this.buffer = rest.size ? [rest] : []
			this.buffered = rest.size
		}
	}

	_send(blob) {
		const number = ++this.partNumber
		this.queue = this.queue.then(async () => {
			if (this.error) return
			for (let attempt = 1; ; attempt++) {
				try {
					const { url } = await callMethod('seminary.storage.direct.presign_part', {
						key: this.key,
						part_number: number,
					})
					await putPart(url, blob, (loaded) => {
						this.inFlight = loaded
						this.onProgress?.(this.sent + loaded)
					})
					this.sent += blob.size
					this.inFlight = 0
					this.onProgress?.(this.sent)
					return
				} catch (e) {
					if (attempt >= RETRIES) {
						this.error = e
						return
					}
					await wait(1000 * 2 ** attempt)
				}
			}
		})
	}

	/** Send what is left and join the parts. Returns the File row. */
	async finish() {
		if (this.buffered) {
			this._send(new Blob(this.buffer))
			this.buffer = []
			this.buffered = 0
		}
		await this.queue
		if (this.error) throw this.error
		return await callMethod('seminary.storage.direct.complete_multipart', { key: this.key })
	}

	async abort() {
		this.error = this.error || new Error('Upload cancelled')
		try {
			await callMethod('seminary.storage.direct.abort_multipart', { key: this.key })
		} catch (e) {
			/* swept within a day anyway */
		}
	}
}

/** Send a chosen video file in parts. */
export async function uploadVideoFile(file, assignment, onProgress) {
	const up = await MultipartUpload.start({
		fileName: file.name,
		contentType: file.type || '',
		assignment,
	})
	if (file.size > up.maxBytes) {
		await up.abort()
		throw new Error(
			__('This video is too large ({0} MB). This assignment takes up to {1} MB.').format(
				Math.round(file.size / 1048576),
				Math.round(up.maxBytes / 1048576)
			)
		)
	}
	up.onProgress = (sent) => onProgress?.(Math.min(100, Math.round((sent / file.size) * 100)))
	for (let offset = 0; offset < file.size; offset += up.partSize) {
		up.push(file.slice(offset, offset + up.partSize))
		// Keep at most two parts in memory ahead of the network.
		if (up.partNumber - Math.floor(up.sent / up.partSize) > 2) await up.queue
	}
	return await up.finish()
}
