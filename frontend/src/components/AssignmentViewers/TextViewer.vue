<template>
	<div v-if="!answer" class="text-sm text-ink-gray-5 p-4">
		{{ __('No answer submitted.') }}
	</div>
	<!-- Pure read-only HTML render. ProseMirror/TextEditor is avoided here
	     because it crashes inside deeply-nested DOM (the AssignmentSubmission
	     grading page is exactly that). Phase 2's anchored text-selection
	     comments will swap this for a Teleport-mounted RichTextEditor with a
	     comment-mark extension — same renderer path used by the comments box. -->
	<div v-else v-html="answer"
		class="prose prose-sm max-w-none border rounded-md p-3 bg-surface-white"></div>
</template>

<script setup>
// `comments` / `pendingAnchor` are accepted (and ignored here) so that the
// shared SubmissionViewer dispatcher can hand them to every viewer
// uniformly. Phase 2's text-selection comments will use them when this view
// switches to a ProseMirror + comment-mark implementation.
defineProps({
	answer: { type: String, default: '' },
	comments: { type: Array, default: () => [] },
	pendingAnchor: { type: Object, default: null },
	activeCommentId: { type: String, default: null },
	canComment: { type: Boolean, default: true },
})

defineEmits(['anchor-selected', 'active-changed'])
defineExpose({ jumpTo: () => {} })
</script>
