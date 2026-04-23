<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<h2 class="text-xl font-bold text-ink-gray-8">
			{{ __('Announcements') }}
		</h2>
	</header>

	<div v-if="announcements.loading" class="p-5 text-ink-gray-5">
		{{ __('Loading announcements...') }}
	</div>

	<div
		v-else-if="!announcements.data?.length"
		class="mt-32 md:mt-52 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5"
	>
		<Megaphone class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No announcements') }}</div>
		<div class="leading-5">
			{{ __('When the registrar sends a seminary-wide announcement, it will appear here.') }}
		</div>
	</div>

	<div v-else class="mx-auto w-full max-w-3xl space-y-4 p-5">
		<article
			v-for="a in announcements.data"
			:key="a.name"
			class="rounded-lg border border-outline-gray-1 bg-surface-white p-4 shadow-sm"
		>
			<header class="mb-2 flex items-baseline justify-between gap-3">
				<h3 class="text-base font-semibold text-ink-gray-8">{{ a.subject }}</h3>
				<span class="shrink-0 text-xs text-ink-gray-5">
					{{ a.sent_datetime ? timeAgo(a.sent_datetime) : '' }}
				</span>
			</header>
			<div class="text-xs text-ink-gray-5 mb-3">{{ a.academic_term }}</div>
			<div
				class="prose prose-sm max-w-none text-ink-gray-7"
				v-html="a.message"
			></div>
		</article>
	</div>
</template>

<script setup>
import { createResource } from 'frappe-ui'
import { Megaphone } from 'lucide-vue-next'
import { timeAgo } from '@/utils'

const announcements = createResource({
	url: 'seminary.seminary.api.get_my_announcements',
	auto: true,
	cache: 'my-announcements',
})
</script>

<style scoped>
.prose :deep(p) {
	margin: 0 0 0.5rem;
}
</style>
