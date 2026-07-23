<template>
	<div class="mt-2 flex flex-col gap-2">
		<YouTubePlayer ref="playerRef" :url="videoUrl" :comments="stamps" :can-comment="canComment"
			@anchor-selected="onAnchor" />

		<!-- pending comment at a captured time -->
		<div v-if="composing" class="flex items-center gap-2">
			<span class="whitespace-nowrap rounded bg-surface-gray-2 px-2 py-1 text-xs text-ink-gray-7">
				📍 {{ fmt(pendingTime) }}
			</span>
			<Input v-model="commentText" type="text" :placeholder="__('Add a note at this moment…')"
				class="flex-1" @keyup.enter="postComment" />
			<Button variant="solid" :loading="addComment.loading" @click="postComment">
				<Send class="h-4 w-4" />
			</Button>
			<button class="text-ink-gray-5" @click="composing = false"><X class="h-4 w-4" /></button>
		</div>

		<!-- timestamped comments -->
		<div v-if="stamps.length" class="flex flex-col gap-1">
			<div v-for="c in stamps" :key="c.name" class="flex items-start gap-2 text-sm">
				<button class="mt-0.5 whitespace-nowrap rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-7 hover:bg-surface-gray-3"
					@click="playerRef?.jumpTo(c)">📍 {{ fmt(c.timestamp_s) }}</button>
				<div>
					<span class="font-medium text-ink-gray-9">{{ c.author_name || c.author }}</span>
					<span class="prose-sm ml-1 text-ink-gray-8" v-html="c.content"></span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Input, createResource } from 'frappe-ui'
import { Send, X } from 'lucide-vue-next'
import YouTubePlayer from '@/components/AssignmentViewers/YouTubePlayer.vue'

const props = defineProps({
	postName: { type: String, required: true },
	videoUrl: { type: String, default: '' },
	canComment: { type: Boolean, default: true },
})

const playerRef = ref(null)
const composing = ref(false)
const pendingTime = ref(0)
const commentText = ref('')

const thread = createResource({
	url: 'seminary.seminary.discipleship.feed_api.get_thread',
	params: { post: props.postName },
	auto: true,
})
const addComment = createResource({ url: 'seminary.seminary.discipleship.feed_api.add_comment' })

const stamps = computed(() =>
	(thread.data?.comments || [])
		.filter((c) => c.anchor_type === 'Timestamp')
		.sort((a, b) => (a.timestamp_s || 0) - (b.timestamp_s || 0)),
)

function fmt(s) {
	s = parseInt(s) || 0
	const m = Math.floor(s / 60)
	return `${m}:${(s % 60).toString().padStart(2, '0')}`
}
function onAnchor(anchor) {
	pendingTime.value = anchor?.timestamp_s || 0
	commentText.value = ''
	composing.value = true
}
function postComment() {
	if (!commentText.value.trim()) return
	addComment
		.submit({
			post: props.postName,
			content: commentText.value,
			anchor_type: 'Timestamp',
			anchor_data: JSON.stringify({ timestamp_s: pendingTime.value }),
		})
		.then(() => { composing.value = false; commentText.value = ''; thread.reload() })
}
</script>
