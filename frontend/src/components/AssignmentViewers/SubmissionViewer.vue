<template>
	<div v-if="viewerComponent" class="flex gap-3 items-start">
		<div class="flex-1 min-w-0">
			<component
				:is="viewerComponent"
				ref="viewerRef"
				v-bind="viewerProps"
				:comments="comments"
				:pending-anchor="pendingAnchor"
				:active-comment-id="activeCommentId"
				:can-comment="canComment"
				@anchor-selected="onAnchorSelected"
				@active-changed="setActive"
			/>
		</div>
		<div class="w-72 shrink-0" v-if="submission?.name">
			<CommentSidebar
				:submission-name="submission.name"
				:comments="comments"
				:pending-anchor="pendingAnchor"
				:active-comment-id="activeCommentId"
				:can-comment="canComment"
				:on-post="canComment ? postComment : null"
				@changed="loadComments"
				@cancel-pending="clearPending"
				@jump="onJump"
				@active-changed="setActive"
			/>
		</div>
	</div>
	<div v-else class="text-sm text-ink-gray-5 p-4">
		{{ __('Unknown submission type.') }}
	</div>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import CommentSidebar from './CommentSidebar.vue'

const props = defineProps({
	// `Assignment Submission` doc
	submission: { type: Object, default: () => ({}) },
	// `Assignment Activity.type`: PDF | Document | Image | URL | Text | YouTube
	type: { type: String, default: '' },
	// false for student-side read-only review of their own submission.
	canComment: { type: Boolean, default: true },
})

const emit = defineEmits(['comments-loaded'])

const fileTypes = ['PDF', 'Document', 'Image']

const viewerComponent = computed(() => {
	switch (props.type) {
		case 'PDF':
			return defineAsyncComponent(() => import('./PdfViewer.vue'))
		case 'Image':
			return defineAsyncComponent(() => import('./ImageViewer.vue'))
		case 'Document':
			return defineAsyncComponent(() => import('./DocxPreview.vue'))
		case 'Text':
			return defineAsyncComponent(() => import('./TextViewer.vue'))
		case 'URL':
			return defineAsyncComponent(() => import('./UrlCard.vue'))
		case 'YouTube':
			return defineAsyncComponent(() => import('./YouTubePlayer.vue'))
		default:
			return null
	}
})

const viewerProps = computed(() => {
	const isFile = fileTypes.includes(props.type)
	const url = isFile ? props.submission?.assignment_attachment : props.submission?.answer
	if (props.type === 'Text') {
		return { answer: props.submission?.answer || '' }
	}
	return { url: url || '' }
})

const comments = ref([])
const pendingAnchor = ref(null)
const activeCommentId = ref(null)
const viewerRef = ref(null)

function setActive(name) {
	activeCommentId.value = name || null
}

async function loadComments() {
	pendingAnchor.value = null
	if (!props.submission?.name) {
		comments.value = []
		return
	}
	try {
		const data = await call('seminary.seminary.api.get_submission_comments', {
			submission_name: props.submission.name,
		})
		comments.value = data || []
		emit('comments-loaded', comments.value)
	} catch (err) {
		console.error('Failed to load submission comments:', err)
		comments.value = []
	}
}

onMounted(loadComments)
watch(() => props.submission?.name, loadComments)

function onAnchorSelected(anchor) {
	pendingAnchor.value = anchor
}

function clearPending() {
	pendingAnchor.value = null
}

function onJump(comment) {
	viewerRef.value?.jumpTo?.(comment)
}

// Posting lives here (not in CommentSidebar) so the anchor is read from this
// component's own scope at the moment the API call is made — eliminating the
// prop-passing race that was dropping image/PDF pin anchors.
async function postComment(text) {
	if (!props.submission?.name || !text?.trim()) return
	const a = pendingAnchor.value
	await call('seminary.seminary.api.add_submission_comment', {
		submission_name: props.submission.name,
		anchor_type: a?.anchor_type || 'General',
		anchor_data: a ? JSON.stringify(a) : '{}',
		comment: text,
	})
	await loadComments()
}
</script>
