<template>
	<div v-if="!url" class="text-sm text-ink-gray-5 p-4">
		{{ __('No document attached.') }}
	</div>
	<div v-else-if="!isDocx" class="border rounded-md p-4 bg-surface-white space-y-2">
		<div class="text-sm text-ink-gray-7">
			{{ __('Inline preview not supported for .doc — download to review.') }}
		</div>
		<a :href="url" target="_blank" rel="noopener" class="text-sm underline">
			{{ __('Download document') }}
		</a>
	</div>
	<div v-else>
		<div v-if="loading" class="text-sm text-ink-gray-5">
			{{ __('Converting document…') }}
		</div>
		<div v-else-if="loadError" class="text-sm text-ink-red-3 space-y-2">
			<div>{{ __('Could not render document.') }}</div>
			<a :href="url" target="_blank" rel="noopener" class="underline">
				{{ __('Download to review') }}
			</a>
		</div>
		<div v-else class="prose prose-sm max-w-none border rounded-md p-4 bg-surface-white"
			v-html="html"></div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { isDocxUrl } from '@/utils/assignmentRendering'

const props = defineProps({
	url: { type: String, default: '' },
	comments: { type: Array, default: () => [] },
	pendingAnchor: { type: Object, default: null },
	activeCommentId: { type: String, default: null },
	canComment: { type: Boolean, default: true },
})

defineEmits(['anchor-selected', 'active-changed'])
defineExpose({ jumpTo: () => {} })

const isDocx = computed(() => isDocxUrl(props.url))
const loading = ref(false)
const loadError = ref(false)
const html = ref('')

async function render() {
	if (!props.url || !isDocx.value) return
	loading.value = true
	loadError.value = false
	html.value = ''

	try {
		const mammoth = (await import('mammoth')).default || (await import('mammoth'))
		const response = await fetch(props.url)
		if (!response.ok) throw new Error(`HTTP ${response.status}`)
		const arrayBuffer = await response.arrayBuffer()
		const result = await mammoth.convertToHtml({ arrayBuffer })
		html.value = result.value
	} catch (err) {
		console.error('Docx render failed:', err)
		loadError.value = true
	} finally {
		loading.value = false
	}
}

onMounted(render)
watch(() => props.url, render)
</script>
