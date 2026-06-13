<template>
	<div v-if="helpData" class="fixed right-6 z-50" :class="mobile ? 'bottom-20' : 'bottom-6'">
		<!-- Panel -->
		<transition name="help-fade">
			<div
				v-if="open"
				class="mb-3 w-80 max-w-[calc(100vw-3rem)] overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white shadow-2xl"
			>
				<div class="flex items-center justify-between border-b border-outline-gray-2 px-4 py-2.5">
					<span class="text-base font-semibold text-ink-gray-9">{{ __('Help') }}</span>
					<button class="text-ink-gray-5 hover:text-ink-gray-9" @click="open = false">
						<X class="h-4 w-4" />
					</button>
				</div>
				<div class="max-h-[60vh] overflow-auto px-4 py-3">
					<div
						v-if="helpData.local_notes"
						class="seminary-help-notes text-p-sm text-ink-gray-8"
						v-html="helpData.local_notes"
					/>
					<p v-else class="text-p-sm text-ink-gray-5">
						{{ __('No local notes for this page yet.') }}
					</p>
					<a
						v-if="helpData.mkdocs_url"
						:href="helpData.mkdocs_url"
						target="_blank"
						class="mt-3 inline-flex items-center gap-1.5 text-p-sm text-ink-blue-link hover:underline"
					>
						<BookOpen class="h-4 w-4" />
						{{ __('Open documentation') }}
					</a>
				</div>
			</div>
		</transition>

		<!-- Floating toggle -->
		<button
			class="ml-auto flex h-11 w-11 items-center justify-center rounded-full bg-surface-blue-1 text-ink-blue-2 shadow-lg transition hover:bg-surface-blue-2 active:scale-95"
			:title="__('Help')"
			@click="open = !open"
		>
			<HelpCircle class="h-5 w-5" />
		</button>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import { HelpCircle, BookOpen, X } from 'lucide-vue-next'
import { useHelp } from '@/utils/useHelp'

defineProps({
	// Lift the button above the mobile bottom-nav bar when true.
	mobile: { type: Boolean, default: false },
})

const { helpData } = useHelp()
const open = ref(false)
</script>

<style scoped>
.help-fade-enter-active,
.help-fade-leave-active {
	transition: opacity 0.12s ease, transform 0.12s ease;
}
.help-fade-enter-from,
.help-fade-leave-to {
	opacity: 0;
	transform: translateY(4px);
}

/* Rich-text (Quill) notes: keep readable spacing without global prose styles. */
.seminary-help-notes :deep(p) {
	margin-bottom: 0.5rem;
}
.seminary-help-notes :deep(p:last-child) {
	margin-bottom: 0;
}
.seminary-help-notes :deep(ul),
.seminary-help-notes :deep(ol) {
	margin: 0.5rem 0;
	padding-left: 1.25rem;
	list-style: revert;
}
.seminary-help-notes :deep(a) {
	color: var(--ink-blue-link, #2490ef);
	text-decoration: underline;
}
.seminary-help-notes :deep(.ql-editor) {
	padding: 0;
}
</style>
