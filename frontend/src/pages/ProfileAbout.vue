<template>
	<div class="mt-7 mb-10">
		<h2 class="mb-3 text-lg font-semibold text-ink-gray-9">
			{{ __('About') }}
		</h2>
		<div
			v-if="profile.data.bio"
			v-html="profile.data.bio"
			class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"
		></div>
		<div v-else class="text-ink-gray-7 text-sm italic">
			{{ __('No introduction') }}
		</div>
	</div>
	
</template>
<script setup>
import { inject } from 'vue'
import { createResource, Popover, Button } from 'frappe-ui'
import { sessionStore } from '@/stores/session'

const dayjs = inject('$dayjs')
const { branding } = sessionStore()

const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})


</script>
