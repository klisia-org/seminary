<!--
  Drop-in replacement for frappe-ui's `FileUploader` that sends large media
  straight to object storage instead of through a worker.

  It exposes the same slot contract the rest of the app already uses
  (`{ uploading, progress, openFileSelector }`) and emits the same `@success`
  payload, so adopting it at a call site is a change of tag name and nothing else.

  Per file it asks the server whether a direct upload applies. When it does not —
  no object storage configured, or the file is below the offload threshold — it
  uploads through `/api/method/upload_file` exactly as before. A site without
  object storage therefore behaves identically to today.

  It deliberately does *not* wrap `FileUploader`. The obvious way to do that is to
  hijack its `validateFile` hook, but frappe-ui assigns that hook's return value
  straight to `this.error` and shows it, so there is no way to cancel its upload
  without displaying a message to the user. Owning the input is simpler and honest.
-->
<template>
	<div>
		<input
			ref="input"
			type="file"
			class="hidden"
			:accept="acceptAttr"
			:multiple="false"
			@change="onFileSelected"
		/>
		<slot
			:uploading="uploading"
			:progress="progress"
			:uploaded="uploaded"
			:error="error"
			:success="success"
			:openFileSelector="openFileSelector"
		/>
		<ErrorMessage v-if="error" class="mt-2" :message="error" />
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ErrorMessage } from 'frappe-ui'
import { uploadDirect } from '@/utils/directUpload'

const props = defineProps({
	fileTypes: { type: [Array, String], default: undefined },
	uploadArgs: { type: Object, default: () => ({}) },
	validateFile: { type: Function, default: undefined },
	doctype: { type: String, default: undefined },
	docname: { type: String, default: undefined },
	fieldname: { type: String, default: undefined },
	folder: { type: String, default: undefined },
	isPrivate: { type: Boolean, default: undefined },
})

const emit = defineEmits(['success', 'failure'])

const input = ref(null)
const uploading = ref(false)
const progress = ref(0)
const uploaded = ref(0)
const success = ref(false)
const error = ref(null)

const acceptAttr = computed(() =>
	Array.isArray(props.fileTypes) ? props.fileTypes.join(',') : props.fileTypes
)

// `uploadArgs` is how most existing call sites pass the attach target, so read
// from it as well as from the explicit props.
const target = computed(() => ({
	doctype: props.doctype ?? props.uploadArgs?.doctype,
	docname: props.docname ?? props.uploadArgs?.docname,
	fieldname: props.fieldname ?? props.uploadArgs?.fieldname,
	folder: props.folder ?? props.uploadArgs?.folder,
	isPrivate: props.isPrivate ?? props.uploadArgs?.private ?? true,
}))

function openFileSelector() {
	error.value = null
	input.value?.click()
}

function getCsrfToken() {
	return (
		window.csrf_token ||
		window.frappe?.csrf_token ||
		document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
		null
	)
}

/**
 * Pull a readable sentence out of a Frappe error response.
 *
 * Frappe nests the real message two levels deep in `_server_messages` (a JSON
 * string holding an array of JSON strings) and writes it as HTML. Uploaders that
 * do not unwrap it fall back to "Error Uploading File", which is what made a size
 * rejection unactionable. A 413 never reaches Frappe at all — nginx refuses the
 * body itself — so that one has to be named explicitly.
 */
function serverMessage(payload, status) {
	if (status === 413) {
		return __('This file is too large for the server to accept.')
	}
	try {
		const messages = JSON.parse(payload._server_messages || '[]')
		if (messages.length) {
			const text = JSON.parse(messages[0]).message
			if (text) {
				// Frappe's messages carry markup (<br>, <b>); flatten it to text.
				const el = document.createElement('div')
				el.innerHTML = text
				return (el.textContent || '').trim()
			}
		}
	} catch (e) {
		/* fall through */
	}
	return payload?.exception || __('Error Uploading File')
}

/** The ordinary upload path, for files that do not qualify for a direct upload. */
function uploadThroughServer(file) {
	return new Promise((resolve, reject) => {
		const form = new FormData()
		form.append('file', file, file.name)
		form.append('is_private', target.value.isPrivate ? '1' : '0')
		form.append('folder', target.value.folder || 'Home')
		if (target.value.doctype) form.append('doctype', target.value.doctype)
		if (target.value.docname) form.append('docname', target.value.docname)
		if (target.value.fieldname) form.append('fieldname', target.value.fieldname)

		const xhr = new XMLHttpRequest()
		xhr.open('POST', '/api/method/upload_file', true)
		xhr.withCredentials = true
		const token = getCsrfToken()
		if (token) xhr.setRequestHeader('X-Frappe-CSRF-Token', token)

		xhr.upload.onprogress = (event) => {
			if (event.lengthComputable) {
				uploaded.value = event.loaded
				progress.value = Math.round((event.loaded / event.total) * 100)
			}
		}
		xhr.onload = () => {
			let payload = {}
			try {
				payload = JSON.parse(xhr.responseText)
			} catch (e) {
				/* fall through to the status check */
			}
			if (xhr.status >= 200 && xhr.status < 300) return resolve(payload.message)
			reject(new Error(serverMessage(payload, xhr.status)))
		}
		xhr.onerror = () =>
			reject(new Error(__('Could not reach the server. Please check your connection.')))
		xhr.send(form)
	})
}

async function onFileSelected(event) {
	const file = event.target.files?.[0]
	// Reset immediately so selecting the same file twice still fires `change`.
	event.target.value = ''
	if (!file) return

	error.value = null
	success.value = false
	progress.value = 0
	uploaded.value = 0

	if (props.validateFile) {
		try {
			const problem = await props.validateFile(file)
			if (problem) {
				error.value = problem
				return
			}
		} catch (e) {
			error.value = e.message || String(e)
			return
		}
	}

	uploading.value = true
	try {
		const direct = await uploadDirect(file, {
			...target.value,
			onProgress: (percent) => {
				progress.value = percent
				uploaded.value = Math.round((file.size * percent) / 100)
			},
		})
		// `null` means the server judged this file ineligible, not that anything
		// went wrong — upload it the ordinary way.
		const result = direct ?? (await uploadThroughServer(file))
		success.value = true
		emit('success', result)
	} catch (e) {
		error.value = e.message || String(e)
		emit('failure', e)
	} finally {
		uploading.value = false
	}
}

defineExpose({ openFileSelector })
</script>
