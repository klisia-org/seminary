<template>
	<div v-if="!url" class="text-sm text-ink-gray-5 p-4">
		{{ __('No link submitted.') }}
	</div>
	<a
		v-else
		:href="url"
		target="_blank"
		rel="noopener"
		class="block border rounded-lg p-4 bg-surface-white hover:bg-surface-gray-2 transition-colors"
	>
		<div class="text-sm text-ink-gray-9 font-medium break-all">{{ url }}</div>
		<div class="text-xs text-ink-gray-5 mt-1">
			{{ __('Opens in a new tab') }}
		</div>
	</a>
</template>

<script setup>
defineProps({
	url: { type: String, default: '' },
	comments: { type: Array, default: () => [] },
	pendingAnchor: { type: Object, default: null },
	activeCommentId: { type: String, default: null },
	canComment: { type: Boolean, default: true },
})

defineEmits(['anchor-selected', 'active-changed'])
defineExpose({ jumpTo: () => {} })
</script>
