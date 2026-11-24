<!--
	Caption files for a video, one per language, in WebVTT (102 §6, 109 §5).

	<CaptionsEditor :captions="rows" @add="(row) => rows.push(row)" @remove="(i) => rows.splice(i, 1)" />

	A row is { language, label, caption_file }. The lesson form keeps the rows on the lesson;
	a rich-text video keeps them on the video.
-->
<template>
	<div>
		<ul v-if="captions.length"
			class="divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-2">
			<li v-for="(row, index) in captions" :key="row.name || row.caption_file"
				class="flex items-center gap-3 px-3 py-2 text-sm">
				<span class="font-medium text-ink-gray-9">{{ row.label || row.language }}</span>
				<span class="text-xs text-ink-gray-5">{{ row.language }}</span>
				<a :href="row.caption_file" target="_blank" rel="noopener"
					class="min-w-0 flex-1 truncate text-ink-gray-6 underline">{{ fileName(row.caption_file) }}</a>
				<Button variant="ghost" :aria-label="__('Remove captions')" @click="emit('remove', index)">
					<template #icon>
						<X class="h-4 w-4" />
					</template>
				</Button>
			</li>
		</ul>
		<div :class="[captions.length ? 'mt-4' : '', 'grid items-end gap-3', compact ? '' : 'sm:grid-cols-[12rem,minmax(0,1fr),auto]']">
			<Link doctype="Language" v-model="newCaption.language" :label="__('Language')"
				:filters="{ enabled: 1 }" :placeholder="__('Choose a language')" />
			<FormControl v-model="newCaption.label" :label="__('Label (optional)')"
				:placeholder="__('Shown in the player\'s captions menu')" />
			<SmartFileUploader :fileTypes="['.vtt', 'text/vtt']" :validateFile="validateVtt"
				@success="add">
				<template #default="{ uploading, progress, openFileSelector }">
					<Button :disabled="!newCaption.language" :loading="uploading" @click="openFileSelector">
						{{ uploading ? __('Uploading {0}%').format(progress) : __('Upload .vtt file') }}
					</Button>
				</template>
			</SmartFileUploader>
		</div>
	</div>
</template>

<script setup>
import { reactive } from 'vue'
import { Button, FormControl } from 'frappe-ui'
import { X } from 'lucide-vue-next'
import Link from '@/components/Controls/Link.vue'
import SmartFileUploader from '@/components/SmartFileUploader.vue'

defineProps({
	captions: { type: Array, default: () => [] },
	// One field per line, for narrow places such as a video inside the text editor.
	compact: { type: Boolean, default: false },
})

const emit = defineEmits(['add', 'remove'])

const newCaption = reactive({ language: '', label: '' })

const fileName = (url) => decodeURIComponent(String(url || '').split('?')[0].split('/').pop())

const validateVtt = async (file) => {
	if (!file.name.toLowerCase().endsWith('.vtt')) {
		return __('Captions must be a WebVTT (.vtt) file.')
	}
	const head = (await file.slice(0, 16).text()).replace(/^﻿/, '')
	if (!head.startsWith('WEBVTT')) {
		return __('This file does not start with WEBVTT, so players can\'t read it. Export the captions as WebVTT.')
	}
}

const add = (file) => {
	emit('add', {
		language: newCaption.language,
		label: newCaption.label.trim(),
		caption_file: file.file_url,
	})
	newCaption.language = ''
	newCaption.label = ''
}
</script>
