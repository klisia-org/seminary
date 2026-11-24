<!--
	A video in the rich-text editor, with its caption files (decision 109 §5).

	The captions are saved on the video, as `data-captions`, because rich text has no lesson
	to hold a Captions table. The page turns them into <track>s when it shows the video.
-->
<template>
	<NodeViewWrapper class="my-2" data-drag-handle>
		<div v-if="uploading" contenteditable="false" role="status"
			class="rounded-md border border-outline-gray-2 bg-surface-gray-1 p-4 text-sm text-ink-gray-7">
			<div class="mb-2 truncate">
				{{ uploading.percent === null
					? __('Uploading {0}…').format(uploading.name)
					: __('Uploading {0}: {1}%').format(uploading.name, uploading.percent) }}
			</div>
			<div class="h-1.5 w-full overflow-hidden rounded bg-surface-gray-3">
				<div class="h-full rounded bg-surface-gray-7 transition-all"
					:class="uploading.percent === null ? 'w-1/3 animate-pulse' : ''"
					:style="uploading.percent === null ? {} : { width: `${uploading.percent}%` }"></div>
			</div>
		</div>
		<div v-else class="relative">
			<video :src="node.attrs.src" controls class="w-full rounded">
				<track v-for="(c, i) in captions" :key="c.src" kind="captions" :src="c.src"
					:srclang="c.srclang" :label="c.label" :default="i === 0" />
			</video>
		</div>
		<div v-if="editor.isEditable && !uploading" contenteditable="false" class="mt-1">
			<Button size="sm" variant="subtle" :aria-expanded="open ? 'true' : 'false'" @click="open = !open">
				{{ captions.length ? __('Captions ({0})').format(captions.length) : __('Add captions') }}
			</Button>
			<div v-if="open" class="mt-2 rounded-md border border-outline-gray-2 p-3">
				<p class="mb-3 text-sm text-ink-gray-5">
					{{ __('One WebVTT (.vtt) file per language.') }}
				</p>
				<CaptionsEditor compact :captions="rows" @add="add" @remove="remove" />
			</div>
		</div>
	</NodeViewWrapper>
</template>

<script setup>
import { computed, ref } from 'vue'
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3'
import { Button } from 'frappe-ui'
import CaptionsEditor from '@/components/CaptionsEditor.vue'
import { readCaptions } from '@/utils/embed'
import { videoUploads } from '@/utils/richEditorNodes'

const props = defineProps(nodeViewProps)
const open = ref(false)

// While its file uploads the node is a placeholder (richEditorNodes uploadVideo).
const uploading = computed(() => (props.node.attrs.upload ? videoUploads[props.node.attrs.upload] || null : null))

const captions = computed(() => readCaptions(JSON.stringify(props.node.attrs.captions || [])))

// CaptionsEditor's rows: the same shape as a lesson's Captions table.
const rows = computed(() =>
	captions.value.map((c) => ({ language: c.srclang, label: c.label, caption_file: c.src }))
)

const add = (row) => {
	props.updateAttributes({
		captions: [
			...captions.value,
			{ src: row.caption_file, srclang: row.language, label: row.label || row.language },
		],
	})
}

const remove = (index) => {
	props.updateAttributes({ captions: captions.value.filter((_, i) => i !== index) })
}
</script>
