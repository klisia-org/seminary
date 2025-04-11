<template>
    <div class="border-2 rounded-md min-w-80 p-5">
	<div v-if="communications.data?.length">
		<div v-for="comm in communications.data">
			<div class="mb-8">
				<div class="flex items-center justify-between mb-2">
					<div class="flex items-center">
						<Avatar :label="comm.sender_full_name" size="lg" />
						<div class="ml-2 text-ink-gray-7">
							{{ comm.sender_full_name }}
						</div>
					</div>
					<div class="text-sm">
						{{ timeAgo(comm.communication_date) }}
					</div>
				</div>
				<div
					class="prose prose-sm bg-surface-menu-bar !min-w-full px-4 py-2 rounded-md"
					v-html="comm.content"
				></div>
			</div>
		</div>
	</div>
	<div v-else class="text-sm italic text-ink-gray-5">
		{{ __('No announcements') }}
	</div>
</div>
</template>
<script setup>
import { createResource, Avatar } from 'frappe-ui'
import { timeAgo } from '@/utils'

const props = defineProps({
	cs: {
		type: String,
		required: true,
	},
})

const communications = createResource({
	url: 'seminary.seminary.api.get_announcements',
	makeParams(value) {
		return {
			cs: props.cs,
		}
	},
	auto: true,
	cache: ['announcement', props.cs],
})
</script>
<style>
.prose-sm p {
	margin: 0 0 0.5rem;
}
</style>