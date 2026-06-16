<template>
	<header class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<router-link :to="{ name: 'PartnerInternshipPosting', params: { name } }" class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
			<ArrowLeft class="size-4" />{{ __('Applicants') }}
		</router-link>
	</header>

	<div v-if="app.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="app.error" class="p-5 text-ink-red-4">{{ app.error.messages?.[0] || __('Not authorized.') }}</div>

	<div v-else-if="app.data" class="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
		<div class="flex flex-wrap items-center gap-2">
			<h1 class="text-xl font-bold text-ink-gray-9">{{ app.data.student_name || app.data.student }}</h1>
			<Badge :theme="statusTheme(app.data.status)" variant="subtle">{{ __(app.data.status) }}</Badge>
		</div>
		<div class="mt-1 text-sm text-ink-gray-5">
			{{ app.data.position_title }} &middot; {{ __('{0} / {1} hours logged').format(app.data.total_hours_logged || 0, app.data.hours_target || 0) }}
		</div>
		<div v-if="app.data.academics && Object.keys(app.data.academics).length" class="mt-2 flex flex-wrap gap-x-3 gap-y-1 rounded-md bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-7">
			<span v-if="app.data.academics.program"><span class="text-ink-gray-5">{{ __('Program') }}:</span> {{ app.data.academics.program }}</span>
			<span v-if="app.data.academics.credits_passed != null"><span class="text-ink-gray-5">{{ __('Credits') }}:</span> {{ app.data.academics.credits_passed }}</span>
			<span v-if="app.data.academics.gpa != null"><span class="text-ink-gray-5">{{ __('GPA') }}:</span> {{ app.data.academics.gpa }}</span>
			<span v-if="app.data.academics.expected_graduation"><span class="text-ink-gray-5">{{ __('Expected graduation') }}:</span> {{ app.data.academics.expected_graduation }}</span>
		</div>

		<div v-if="app.data.status === 'Submitted' || app.data.status === 'Under Review'" class="mt-4 flex items-center gap-2">
			<Button variant="solid" theme="green" :loading="statusRes.loading" @click="setStatus('Accepted')">{{ __('Accept application') }}</Button>
			<Button variant="outline" theme="red" :loading="statusRes.loading" @click="setStatus('Rejected')">{{ __('Reject') }}</Button>
		</div>

		<div class="mt-6">
			<h2 class="mb-3 text-lg font-semibold text-ink-gray-8">{{ __('Placements') }}</h2>
			<div v-if="!app.data.placements?.length" class="text-sm text-ink-gray-5">
				{{ __('A placement is created when the application is accepted.') }}
			</div>
			<div v-else class="flex flex-col gap-4">
				<PartnerPlacementCard v-for="p in app.data.placements" :key="p.name" :placement="p" :supervisors="supervisors.data || []" :org="activeOrg" @changed="app.reload()" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { createResource, Button, Badge, toast } from 'frappe-ui'
import { ArrowLeft } from 'lucide-vue-next'
import { usePartnerOrg } from '@/composables/usePartnerOrg'
import PartnerPlacementCard from '@/components/PartnerPlacementCard.vue'

const props = defineProps({
	name: { type: String, required: true },
	appName: { type: String, required: true },
})
const { activeOrg } = usePartnerOrg()

const app = createResource({
	url: 'seminary.partner.internship_portal.get_internship_application',
	makeParams: () => ({ name: props.appName, org: activeOrg.value }),
	auto: true,
})
const supervisors = createResource({
	url: 'seminary.partner.internship_portal.get_org_supervisors',
	makeParams: () => ({ org: activeOrg.value }),
	auto: true,
})

const statusRes = createResource({ url: 'seminary.partner.internship_portal.set_internship_application_status' })
function setStatus(newStatus) {
	statusRes.submit(
		{ name: props.appName, status: newStatus, org: activeOrg.value },
		{
			onSuccess() { toast.success(__('Application updated.')); app.reload() },
			onError(err) { toast.error(err.messages?.[0] || __('Could not update.')) },
		},
	)
}

function statusTheme(s) {
	if (s === 'Accepted' || s === 'Active' || s === 'Completed') return 'green'
	if (s === 'Rejected' || s === 'Withdrawn') return 'red'
	if (s === 'Under Review') return 'blue'
	return 'gray'
}
</script>
