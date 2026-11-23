<template>
	<!-- What the accessibility checker found in the content above (102 §7). It
	     warns and never blocks: `confirm()` lets the instructor save anyway. -->
	<div>
		<div v-if="issues.length" role="status"
			class="rounded-lg border border-outline-amber-2 bg-surface-amber-1 px-3 py-2 text-sm text-ink-gray-8">
			<button type="button" class="flex w-full items-center gap-2 text-left"
				:aria-expanded="expanded" @click="expanded = !expanded">
				<TriangleAlert class="h-4 w-4 shrink-0 text-ink-amber-3" aria-hidden="true" />
				<span class="flex-1 font-medium">
					{{ total === 1 ? __('1 accessibility issue') : __('{0} accessibility issues').format(total) }}
				</span>
				<ChevronDown class="h-4 w-4 text-ink-gray-5 transition-transform"
					:class="{ 'rotate-180': expanded }" aria-hidden="true" />
			</button>
			<ul v-show="expanded" class="mt-2 list-disc space-y-1 pl-6 text-ink-gray-7">
				<li v-for="issue in issues" :key="issue.code">{{ issue.message }}</li>
			</ul>
		</div>
		<Dialog v-model="open" :options="{ title: __('Before students see this'), size: 'lg' }" @close="finish(false)">
			<template #body-content>
				<p class="mb-3 text-sm text-ink-gray-7">
					{{ __('Some students may not be able to use this content:') }}
				</p>
				<ul class="list-disc space-y-1.5 pl-5 text-sm text-ink-gray-8">
					<li v-for="issue in shown" :key="issue.code">{{ issue.message }}</li>
				</ul>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button @click="finish(false)">{{ __('Go back and fix') }}</Button>
					<Button variant="solid" @click="finish(true)">{{ actionLabel || __('Publish anyway') }}</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { Button, Dialog } from 'frappe-ui'
import { ChevronDown, TriangleAlert } from 'lucide-vue-next'

const props = defineProps({
	// From utils/contentCheck: [{ code, count, message }].
	issues: { type: Array, default: () => [] },
	// The dialog's go-ahead button; "Publish anyway" when not given.
	actionLabel: { type: String, default: '' },
})

const expanded = ref(false)
const open = ref(false)
const shown = ref([])
let resolver = null

const total = computed(() => props.issues.reduce((sum, issue) => sum + (issue.count || 1), 0))

const finish = (proceed) => {
	open.value = false
	if (resolver) resolver(proceed)
	resolver = null
}

/** Resolves true when the save may go ahead: no issues, or "anyway" chosen. */
const confirm = (issues = props.issues) => {
	if (!issues?.length) return Promise.resolve(true)
	shown.value = issues
	open.value = true
	return new Promise((resolve) => {
		resolver = resolve
	})
}

defineExpose({ confirm })
</script>
