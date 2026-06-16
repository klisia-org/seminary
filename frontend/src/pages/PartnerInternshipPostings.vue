<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<h2 class="text-xl font-bold text-ink-gray-8">{{ __('Internships') }}</h2>
		<Button variant="solid" @click="$router.push({ name: 'PartnerInternshipPostingNew' })">{{ __('Add internship') }}</Button>
	</header>

	<div v-if="postings.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="postings.error" class="p-5 text-ink-red-4">{{ postings.error.messages?.[0] || __('Not authorized.') }}</div>

	<div v-else-if="!postings.data?.length" class="mt-24 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5">
		<GraduationCap class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No internships yet') }}</div>
		<div>{{ __('Post your first internship — it goes live after a quick staff review.') }}</div>
	</div>

	<ul v-else class="mx-auto w-full max-w-3xl divide-y divide-outline-gray-1 px-3 sm:px-5">
		<li v-for="job in postings.data" :key="job.name" class="flex items-center justify-between gap-3 py-4">
			<router-link :to="{ name: 'PartnerInternshipPosting', params: { name: job.name } }" class="min-w-0 flex-1">
				<div class="flex flex-wrap items-center gap-2">
					<span class="font-semibold text-ink-gray-8">{{ job.title }}</span>
					<Badge :theme="stateTheme(job.state)" variant="subtle">{{ __(job.state) }}</Badge>
				</div>
				<div class="mt-0.5 text-xs text-ink-gray-5">
					<span v-if="job.internship_type">{{ job.internship_type }}</span>
					<span> &middot; {{ __('{0} of {1} placed').format(job.placements_filled || 0, job.planned_placements || 0) }}</span>
					<span> &middot; {{ __('{0} applicant(s)').format(job.application_count || 0) }}</span>
				</div>
			</router-link>
			<Button variant="ghost" @click="$router.push({ name: 'PartnerInternshipPostingEdit', params: { name: job.name } })">
				{{ __('Edit') }}
			</Button>
		</li>
	</ul>
</template>

<script setup>
import { watch } from 'vue'
import { createResource, Button, Badge } from 'frappe-ui'
import { GraduationCap } from 'lucide-vue-next'
import { usePartnerOrg } from '@/composables/usePartnerOrg'

const { activeOrg } = usePartnerOrg()

const postings = createResource({
	url: 'seminary.partner.internship_portal.list_internship_postings',
	makeParams: () => ({ org: activeOrg.value }),
	auto: true,
})
watch(activeOrg, () => postings.reload())

function stateTheme(state) {
	if (state === 'Live') return 'green'
	if (state === 'Closed') return 'gray'
	return 'orange'
}
</script>
