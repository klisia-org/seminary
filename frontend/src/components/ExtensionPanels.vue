<template>
	<div v-if="rows.length" class="space-y-3">
		<section v-for="(row, i) in rows" :key="i"
			class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-4 py-3">
			<h2 v-if="row.title" class="text-base font-semibold text-ink-gray-9">{{ row.title }}</h2>
			<SafeHtml :html="row.html" class="prose prose-sm max-w-none text-ink-gray-8" />
		</section>
	</div>
</template>

<script setup>
// Panels another installed app adds to a page (privatedocs p028 §2): rows of
// {title, html} from a seminary endpoint that collects them. Nothing to show
// when no app answers.
import { computed, inject, watch } from 'vue'
import { createResource } from 'frappe-ui'
import SafeHtml from '@/components/SafeHtml.vue'

const props = defineProps({
	url: { type: String, required: true },
	params: { type: Object, required: true },
})
const user = inject('$user')
const enabled = computed(() => Boolean(user?.data?.has_aretenic))

const panels = createResource({
	url: props.url,
	makeParams: () => props.params,
	onError: () => {},
})
watch(
	() => [enabled.value, JSON.stringify(props.params)],
	([on]) => {
		if (on) panels.reload()
	},
	{ immediate: true },
)
const rows = computed(() => (enabled.value && Array.isArray(panels.data) ? panels.data : []))
</script>
