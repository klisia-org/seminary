<template>
	<!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a drop target for dragged blocks only; keyboard users add the same blocks by activating them in the palette or typing / in the editor -->
	<div :ref="(el) => (drop.dropZone.value = el)" class="relative rounded-lg transition-colors"
		:class="{ 'lesson-dropzone--active bg-surface-blue-1': drop.draggingTool.value }"
		@dragover.capture="drop.onDragOver" @dragleave="drop.onDragLeave" @drop.capture="drop.onDrop">
		<div v-if="drop.dropIndicatorTop.value !== null"
			class="pointer-events-none absolute left-0 right-0 z-10 h-0.5 rounded bg-surface-blue-3"
			:style="{ top: drop.dropIndicatorTop.value + 'px' }"></div>
		<slot />
	</div>
</template>

<script setup>
// Where palette tiles land: wraps the editor's element (see useBlockDrop).
defineProps({
	drop: { type: Object, required: true },
})
</script>

<style>
.lesson-dropzone--active {
	outline: 2px dashed var(--outline-blue-1, #93c5fd);
	outline-offset: 4px;
}

.lesson-dropzone--active iframe {
	pointer-events: none;
}
</style>
