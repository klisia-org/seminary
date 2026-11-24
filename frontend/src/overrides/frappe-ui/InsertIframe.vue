<!--
	frappe-ui's "Insert Embed" dialog, patched (decision 109 §1).

	Changes from frappe-ui 0.1.261: the dialog asks for a title, which names the frame
	for screen readers and is the link text where no frame is shown; the address must
	pass safeEmbedUrl (http(s), another site), as the lesson iframe block requires;
	labels are tied to their fields and the strings are translated.
-->
<template>
	<div>
		<slot v-bind="{ onClick: openIframeDialog }"></slot>

		<Dialog v-model="showDialog" :options="{ title: __('Insert Embed'), size: 'md' }">
			<template #body-content>
				<div class="space-y-4">
					<div>
						<label :for="urlId" class="mb-2 block text-sm font-medium text-ink-gray-7">
							{{ __('URL or embed code') }}
						</label>
						<Textarea :id="urlId" ref="urlInput" v-model="embedUrl"
							:aria-invalid="urlError ? 'true' : undefined"
							:aria-describedby="urlError ? `${urlId}-error` : undefined"
							placeholder="https://youtube.com/watch?v=... or <iframe src=...>"
							@input="validateUrl" />
						<p v-if="urlError" :id="`${urlId}-error`" class="mt-1 text-sm text-ink-red-4">{{ urlError }}</p>
					</div>
					<div>
						<label :for="titleId" class="mb-2 block text-sm font-medium text-ink-gray-7">
							{{ __('Title') }} <span aria-hidden="true">*</span>
						</label>
						<TextInput :id="titleId" v-model="title" aria-required="true"
							:placeholder="__('What the embed shows, e.g. Lecture 3: the Exodus')"
							@keydown.enter.prevent="insertIframe" />
						<p class="mt-1 text-sm text-ink-gray-5">
							{{ __('Screen readers announce it, and it is the link text where the embed can\'t be shown.') }}
						</p>
					</div>
				</div>
			</template>

			<template #actions>
				<div class="flex justify-end space-x-2">
					<Button variant="subtle" @click="showDialog = false">{{ __('Cancel') }}</Button>
					<Button variant="solid" :disabled="!canInsert" @click="insertIframe">
						{{ __('Insert Embed') }}
					</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, useId } from 'vue'
import { Dialog, Button, TextInput, Textarea } from 'frappe-ui'
import {
	validateURL,
	processURL,
	getOptimalDimensions,
} from 'frappe-ui/src/components/TextEditor/extensions/iframe/utils'
import { safeEmbedUrl } from '../../utils/urlPolicy.js'

const props = defineProps({
	editor: { type: Object, required: true },
})

const urlId = useId()
const titleId = useId()
const showDialog = ref(false)
const embedUrl = ref('')
const urlError = ref('')
const title = ref('')
const urlInput = ref()

// The options the editor's iframe node was set up with (its allowed domains).
const nodeOptions = () =>
	props.editor.extensionManager.extensions.find((e) => e.name === 'iframe')?.options || {
		HTMLAttributes: {},
	}

// The address alone: a pasted snippet is read for its src, never kept.
const rawUrl = computed(() => {
	const value = embedUrl.value.trim()
	if (/^<\s*iframe/i.test(value)) {
		const frame = new DOMParser().parseFromString(value, 'text/html').querySelector('iframe')
		return frame?.getAttribute('src') || ''
	}
	return value
})

const processedUrl = computed(() => (rawUrl.value ? processURL(rawUrl.value) : ''))

const isValidUrl = computed(() => {
	if (!processedUrl.value) return false
	try {
		return Boolean(safeEmbedUrl(processedUrl.value)) && validateURL(processedUrl.value, nodeOptions())
	} catch {
		return false
	}
})

const canInsert = computed(() => isValidUrl.value && title.value.trim().length > 0)

function validateUrl() {
	urlError.value = ''
	if (embedUrl.value && !isValidUrl.value) {
		urlError.value = __('Enter an https:// address on another site, or an embed code whose src is one.')
	}
}

function openIframeDialog() {
	showDialog.value = true
	embedUrl.value = ''
	urlError.value = ''
	title.value = ''
	nextTick(() => urlInput.value?.el?.focus())
}

function insertIframe() {
	if (!canInsert.value) return
	const size = getOptimalDimensions(processedUrl.value, 800)
	const done = props.editor.commands.setIframe({
		src: processedUrl.value,
		width: size.width,
		height: size.height,
		title: title.value.trim(),
		align: 'center',
	})
	if (done) {
		showDialog.value = false
		props.editor.commands.focus()
	} else {
		urlError.value = __('The embed could not be inserted. Check the address and try again.')
	}
}

function handleSlashCommandInsert(event) {
	if (event.detail?.editor === props.editor) openIframeDialog()
}

onMounted(() => {
	props.editor.view.dom.addEventListener('iframe:open-dialog', handleSlashCommandInsert)
})

onUnmounted(() => {
	props.editor.view.dom.removeEventListener('iframe:open-dialog', handleSlashCommandInsert)
})
</script>
