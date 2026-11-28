<!--
	A video submission (privatedocs p029 §6): YouTubePlayer's twin for a video
	stored on this site. The recording's player shows the video with its
	transcript, suggested moments and score suggestions; timestamp comments are
	placed from here and listed in the submission's sidebar.
-->
<template>
	<div class="space-y-2">
		<div v-if="info.loading && !info.data" class="text-sm text-ink-gray-5 p-4">{{ __('Loading…') }}</div>
		<template v-else-if="info.data?.recording">
			<OralPlayer ref="player" :recording="info.data.recording" video :marking="false"
				@time="(t) => (now = t)" @changed="emit('comments-changed')" />
			<div class="flex items-center justify-between gap-2">
				<div class="text-xs text-ink-gray-5">
					{{ timestampedCount }}
					{{ timestampedCount === 1 ? __('timestamped comment') : __('timestamped comments') }}
				</div>
				<Button v-if="canComment && !info.data.deleted_on" variant="solid" theme="blue" @click="commentAtCurrentTime">
					💬 {{ __('Comment at current time') }}
				</Button>
			</div>
		</template>
		<!-- A video saved before its recording was made, or with none: play the file. -->
		<!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -- the transcript, when there is one, is shown beside it -->
		<video v-else-if="url" ref="plain" :src="url" controls preload="metadata" playsinline
			class="aspect-video w-full rounded-md bg-black" />
		<div v-else class="text-sm text-ink-gray-5 p-4">{{ __('No video was submitted.') }}</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, createResource } from 'frappe-ui'
import OralPlayer from '@/components/OralPlayer.vue'

const props = defineProps({
	url: { type: String, default: '' },
	submission: { type: String, default: '' },
	comments: { type: Array, default: () => [] },
	pendingAnchor: { type: Object, default: null },
	activeCommentId: { type: String, default: null },
	canComment: { type: Boolean, default: true },
})
const emit = defineEmits(['anchor-selected', 'active-changed', 'comments-changed'])

const player = ref(null)
const plain = ref(null)
const now = ref(0)

const info = createResource({
	url: 'seminary.seminary.video_submissions.video_of',
	makeParams: () => ({ submission: props.submission }),
	auto: !!props.submission,
})
watch(
	() => props.submission,
	(name) => name && info.reload()
)

const timestampedCount = computed(() => props.comments.filter((c) => c.anchor_type === 'Timestamp').length)

function commentAtCurrentTime() {
	emit('anchor-selected', { anchor_type: 'Timestamp', timestamp_s: Math.floor(now.value || 0) })
}

function jumpTo(comment) {
	if (!comment || comment.anchor_type !== 'Timestamp') return
	const t = parseInt(comment.timestamp_s) || 0
	if (player.value) player.value.seek(t)
	else if (plain.value) {
		plain.value.currentTime = t
		plain.value.play()
	}
}

defineExpose({ jumpTo })
</script>
