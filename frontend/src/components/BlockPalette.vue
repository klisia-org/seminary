<template>
	<!-- Block palette: drag a tile into the editor, or click it to add at the end. -->
	<aside class="order-last lg:order-first lg:sticky lg:top-20 rounded-xl border border-outline-gray-2 bg-surface-white p-4">
		<h2 class="text-base font-semibold text-ink-gray-9">{{ __('Blocks') }}</h2>
		<p class="mt-0.5 text-xs text-ink-gray-5">
			{{ __('Drag into the lesson, or click to add at the end') }}
		</p>
		<div v-for="group in groups" :key="group.label" class="mt-4">
			<div class="mb-1.5 text-[11px] font-semibold uppercase tracking-wider" :class="group.text">
				{{ group.label }}
			</div>
			<div class="grid grid-cols-2 gap-1.5">
				<button v-for="block in group.blocks" :key="block.tool" type="button" draggable="true"
					:title="block.hint || block.label"
					class="flex flex-col items-start gap-1.5 rounded-lg border border-outline-gray-2 bg-surface-white p-2 text-left text-sm text-ink-gray-8 hover:border-outline-gray-3 hover:bg-surface-gray-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 cursor-grab active:cursor-grabbing"
					:class="{ 'opacity-50': drop.draggingTool.value === block.tool }"
					@click="drop.addBlock(block.tool)" @dragstart="drop.onTileDragStart($event, block.tool)"
					@dragend="drop.onTileDragEnd">
					<span class="flex h-7 w-7 items-center justify-center rounded-md" :class="group.icon">
						<component :is="block.icon" class="h-4 w-4" />
					</span>
					<span class="leading-tight">{{ block.label }}</span>
				</button>
			</div>
		</div>
		<p class="mt-4 rounded-lg bg-surface-gray-2 p-2.5 text-xs text-ink-gray-6">
			{{ __('Tip: in the lesson, type / to search blocks without leaving the keyboard.') }}
		</p>
	</aside>
</template>

<script setup>
// `drop` is what useBlockDrop() returns for the editor the tiles go into.
defineProps({
	groups: { type: Array, required: true },
	drop: { type: Object, required: true },
})
</script>
