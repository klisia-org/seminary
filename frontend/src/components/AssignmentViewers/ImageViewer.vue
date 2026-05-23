<template>
	<div v-if="!url" class="text-sm text-ink-gray-5 p-4">
		{{ __('No image attached.') }}
	</div>
	<div v-else class="space-y-2">
		<div
			ref="wrapperEl"
			class="image-wrapper relative border rounded-md overflow-hidden bg-surface-white select-none"
			:class="canComment ? 'cursor-crosshair' : ''"
			@click="onCanvasClick"
		>
			<img :src="url" class="block max-w-full h-auto" :alt="__('Submission image')" />
			<!-- Existing pins -->
			<button
				v-for="(pin, i) in pins"
				:key="pin.name"
				type="button"
				class="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-surface-blue-1 border-2 border-outline-blue-1 text-xs font-semibold text-ink-blue-2 shadow flex items-center justify-center hover:scale-110 transition-transform"
				:class="{
					'ring-2 ring-outline-amber-2 animate-pulse': pulseId === pin.name,
					'ring-2 ring-outline-blue-3 scale-110': activeCommentId === pin.name && pulseId !== pin.name,
					'opacity-50': pin.resolved,
				}"
				:style="{ left: pin.x_pct + '%', top: pin.y_pct + '%' }"
				:title="textPreview(pin.comment)"
				@click.stop="emitJump(pin)"
				@mouseenter="$emit('active-changed', pin.name)"
				@mouseleave="$emit('active-changed', null)"
			>
				{{ i + 1 }}
			</button>
			<!-- Pending (not yet saved) anchor preview -->
			<div
				v-if="pendingMatch"
				class="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-surface-amber-1 border-2 border-outline-amber-2 ring-2 ring-outline-amber-2"
				:style="{ left: pendingMatch.x_pct + '%', top: pendingMatch.y_pct + '%' }"
			></div>
		</div>
		<div v-if="canComment" class="text-xs text-ink-gray-5">
			{{ __('Click the image to drop a pin and add a comment.') }}
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
	url: { type: String, default: '' },
	comments: { type: Array, default: () => [] },
	pendingAnchor: { type: Object, default: null },
	activeCommentId: { type: String, default: null },
	canComment: { type: Boolean, default: true },
})

const emit = defineEmits(['anchor-selected', 'active-changed'])

const wrapperEl = ref(null)
const pulseId = ref(null)

const pins = computed(() => props.comments.filter((c) => c.anchor_type === 'Region'))

const pendingMatch = computed(() => {
	const a = props.pendingAnchor
	if (!a || a.anchor_type !== 'Region') return null
	return a
})

function onCanvasClick(e) {
	// Students view their submission read-only — no fake pin on click.
	if (!props.canComment) return
	if (!wrapperEl.value) return
	const rect = wrapperEl.value.getBoundingClientRect()
	const x = ((e.clientX - rect.left) / rect.width) * 100
	const y = ((e.clientY - rect.top) / rect.height) * 100
	emit('anchor-selected', {
		anchor_type: 'Region',
		page: 1,
		x_pct: Math.max(0, Math.min(100, x)),
		y_pct: Math.max(0, Math.min(100, y)),
	})
}

function emitJump(pin) {
	// Local pulse + bubble up so sidebar/page can react too.
	pulseId.value = pin.name
	setTimeout(() => {
		if (pulseId.value === pin.name) pulseId.value = null
	}, 1500)
}

function jumpTo(comment) {
	if (!comment || comment.anchor_type !== 'Region') return
	pulseId.value = comment.name
	setTimeout(() => {
		if (pulseId.value === comment.name) pulseId.value = null
	}, 1500)
}

function textPreview(html) {
	const tmp = document.createElement('div')
	tmp.innerHTML = html || ''
	return (tmp.textContent || '').slice(0, 120)
}

defineExpose({ jumpTo })
</script>
