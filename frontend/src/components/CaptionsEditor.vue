<!--
	Caption files for a video, one per language, in WebVTT (102 §6, 109 §5).

	<CaptionsEditor :captions="rows" @add="(row) => rows.push(row)" @remove="(i) => rows.splice(i, 1)" />

	A row is { language, label, caption_file, status }. The lesson form keeps the rows on the
	lesson; a rich-text video keeps them on the video. `status` is Draft for machine-generated
	captions nobody has reviewed (privatedocs p029 §7); `review` asks the parent to mark one.
	`videos` ([{ url, label }]) are the site's own videos the captions are for: where an app
	generates captions, the editor offers to draft them.
-->
<template>
	<div>
		<ul v-if="captions.length"
			class="divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-2">
			<li v-for="(row, index) in captions" :key="row.name || row.caption_file"
				class="flex items-center gap-3 px-3 py-2 text-sm">
				<span class="font-medium text-ink-gray-9">{{ row.label || row.language }}</span>
				<span class="text-xs text-ink-gray-5">{{ row.language }}</span>
				<Badge v-if="row.status === 'Draft'" theme="orange" size="sm">{{ __('Machine-generated') }}</Badge>
				<a :href="row.caption_file" target="_blank" rel="noopener"
					class="min-w-0 flex-1 truncate text-ink-gray-6 underline">{{ fileName(row.caption_file) }}</a>
				<Button v-if="row.status === 'Draft'" size="sm" variant="subtle" @click="emit('review', index)">
					{{ __('Mark reviewed') }}
				</Button>
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

		<div v-if="canGenerate" class="mt-4 rounded-lg border border-outline-gray-2 p-3 space-y-3">
			<div class="text-sm font-medium text-ink-gray-8">{{ __('Generate captions') }}</div>
			<p class="text-xs text-ink-gray-5">
				{{ __('Drafts captions from the speech in the video. Students see them labelled as machine-generated until you review them and mark them reviewed.') }}
			</p>
			<div :class="['grid items-end gap-3', compact ? '' : 'sm:grid-cols-[minmax(0,1fr),12rem,auto]']">
				<FormControl v-if="videos.length > 1" v-model="generate.video" type="select" :label="__('Video')"
					:options="videos.map((v) => ({ label: v.label || fileName(v.url), value: v.url }))" />
				<Link doctype="Language" v-model="generate.language" :label="__('Language spoken')"
					:filters="{ enabled: 1 }" :placeholder="__('Choose a language')" />
				<Button :disabled="!generate.language || !chosenVideo" :loading="requesting" @click="requestCaptions">
					{{ __('Generate') }}
				</Button>
			</div>
			<ul v-if="openRequests.length" class="space-y-1 text-sm">
				<li v-for="r in openRequests" :key="r.name" class="flex items-center gap-2">
					<span class="text-ink-gray-7">{{ fileName(r.video) }} · {{ r.language }}</span>
					<span v-if="r.status === 'Requested'" class="text-xs text-ink-gray-5" role="status">{{ __('Generating…') }}</span>
					<span v-else-if="r.status === 'Failed'" class="text-xs text-ink-red-4">{{ r.error || __('Failed') }}</span>
					<Button v-else size="sm" variant="solid" @click="addGenerated(r)">{{ __('Add draft captions') }}</Button>
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Badge, Button, FormControl, call, toast } from 'frappe-ui'
import { X } from 'lucide-vue-next'
import Link from '@/components/Controls/Link.vue'
import SmartFileUploader from '@/components/SmartFileUploader.vue'

const props = defineProps({
	captions: { type: Array, default: () => [] },
	// One field per line, for narrow places such as a video inside the text editor.
	compact: { type: Boolean, default: false },
	videos: { type: Array, default: () => [] },
})

const emit = defineEmits(['add', 'remove', 'review'])

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

// Draft captions from the app that provides them (privatedocs p029 §8).
const user = inject('$user', null)
const canGenerate = computed(() => !!user?.data?.caption_generation && props.videos.length > 0)
const generate = reactive({ video: '', language: '' })
const chosenVideo = computed(() => (props.videos.length > 1 ? generate.video : props.videos[0]?.url) || '')
const requesting = ref(false)
const requests = ref([])
let poll = null

// A request is open until its captions are in the list.
const openRequests = computed(() =>
	requests.value.filter(
		(r) => !(r.status === 'Ready' && props.captions.some((c) => c.caption_file === r.caption_file))
	)
)

const loadRequests = async () => {
	if (!canGenerate.value) return
	try {
		requests.value = await call('seminary.seminary.captions.caption_requests', {
			videos: props.videos.map((v) => v.url),
		})
	} catch (e) {
		requests.value = []
	}
	clearTimeout(poll)
	if (requests.value.some((r) => r.status === 'Requested')) poll = setTimeout(loadRequests, 10000)
}

watch(() => props.videos.map((v) => v.url).join('|'), loadRequests, { immediate: true })
onBeforeUnmount(() => clearTimeout(poll))

const requestCaptions = async () => {
	requesting.value = true
	try {
		await call('seminary.seminary.captions.request_captions', {
			video: chosenVideo.value,
			language: generate.language,
		})
		generate.language = ''
		await loadRequests()
	} catch (e) {
		toast.error(e.messages?.[0] || __('Captions could not be requested.'))
	}
	requesting.value = false
}

const addGenerated = (r) => {
	emit('add', { language: r.language, label: '', caption_file: r.caption_file, status: 'Draft' })
}
</script>
