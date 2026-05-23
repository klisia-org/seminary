<template>
	<div v-if="!videoId" class="text-sm text-ink-red-3 p-4">
		{{ __('Not a valid YouTube link.') }}
		<a v-if="url" :href="url" target="_blank" rel="noopener" class="underline ml-1">
			{{ __('Open link') }}
		</a>
	</div>
	<div v-else class="space-y-2">
		<div ref="playerHost" class="aspect-video w-full bg-black rounded-md overflow-hidden"></div>
		<div class="flex items-center justify-between gap-2">
			<div class="text-xs text-ink-gray-5">
				{{ timestampedCount }} {{ timestampedCount === 1 ? __('timestamped comment') : __('timestamped comments') }}
			</div>
			<Button
				v-if="canComment"
				variant="solid"
				theme="blue"
				:disabled="!playerReady"
				@click="commentAtCurrentTime"
			>
				💬 {{ __('Comment at current time') }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { parseYouTubeId } from '@/utils/assignmentRendering'

const props = defineProps({
	url: { type: String, default: '' },
	comments: { type: Array, default: () => [] },
	pendingAnchor: { type: Object, default: null },
	activeCommentId: { type: String, default: null },
	canComment: { type: Boolean, default: true },
})

const emit = defineEmits(['anchor-selected', 'active-changed'])

const playerHost = ref(null)
const videoId = computed(() => parseYouTubeId(props.url))
const playerReady = ref(false)
const timestampedCount = computed(
	() => props.comments.filter((c) => c.anchor_type === 'Timestamp').length
)
let player = null

function loadYouTubeIframeAPI() {
	if (window.YT && window.YT.Player) return Promise.resolve()
	if (window.__ytIframeApiPromise) return window.__ytIframeApiPromise

	window.__ytIframeApiPromise = new Promise((resolve) => {
		const prev = window.onYouTubeIframeAPIReady
		window.onYouTubeIframeAPIReady = () => {
			if (typeof prev === 'function') prev()
			resolve()
		}
		const tag = document.createElement('script')
		tag.src = 'https://www.youtube.com/iframe_api'
		document.head.appendChild(tag)
	})
	return window.__ytIframeApiPromise
}

async function mountPlayer() {
	if (!videoId.value || !playerHost.value) return
	await loadYouTubeIframeAPI()
	destroyPlayer()
	playerReady.value = false
	player = new window.YT.Player(playerHost.value, {
		videoId: videoId.value,
		width: '100%',
		height: '100%',
		playerVars: { rel: 0, modestbranding: 1 },
		events: {
			onReady: () => {
				playerReady.value = true
			},
		},
	})
}

function destroyPlayer() {
	if (player && typeof player.destroy === 'function') {
		try {
			player.destroy()
		} catch (_) {
			/* ignore */
		}
	}
	player = null
	playerReady.value = false
}

function commentAtCurrentTime() {
	if (!player || typeof player.getCurrentTime !== 'function') return
	const t = Math.floor(player.getCurrentTime() || 0)
	emit('anchor-selected', { anchor_type: 'Timestamp', timestamp_s: t })
}

function jumpTo(comment) {
	if (!comment || comment.anchor_type !== 'Timestamp') return
	if (!player || typeof player.seekTo !== 'function') return
	player.seekTo(parseInt(comment.timestamp_s) || 0, true)
	if (typeof player.playVideo === 'function') player.playVideo()
}

defineExpose({ jumpTo })

onMounted(mountPlayer)
watch(videoId, mountPlayer)
onBeforeUnmount(destroyPlayer)
</script>
