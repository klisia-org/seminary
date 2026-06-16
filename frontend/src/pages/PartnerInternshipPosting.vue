<template>
	<header class="sticky top-0 z-10 flex flex-col gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<div class="flex items-center justify-between gap-2">
			<router-link :to="{ name: 'PartnerInternshipPostings' }" class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
				<ArrowLeft class="size-4" />{{ __('Internships') }}
			</router-link>
			<router-link :to="{ name: 'PartnerInternshipPostingEdit', params: { name } }" class="text-sm text-ink-blue-6 hover:underline">
				{{ __('Edit internship') }}
			</router-link>
		</div>
		<div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
			<h1 class="text-lg font-semibold text-ink-gray-9">{{ apps.data?.title || name }}</h1>
			<span v-if="apps.data" class="text-sm text-ink-gray-5">
				{{ apps.data.total === 1 ? __('1 application received') : __('{0} applications received').format(apps.data.total) }}
			</span>
		</div>
		<div>
			<select v-model="status" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:outline-none">
				<option value="">{{ __('All statuses') }}</option>
				<option v-for="s in STATUSES" :key="s" :value="s">{{ __(s) }}</option>
			</select>
		</div>
	</header>

	<div v-if="apps.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="apps.error" class="p-5 text-ink-red-4">{{ apps.error.messages?.[0] || __('Not authorized.') }}</div>
	<div v-else-if="!apps.data?.applications?.length" class="mt-20 text-center text-ink-gray-5">
		{{ apps.data?.total ? __('No applications match this filter.') : __('No applications yet.') }}
	</div>

	<ul v-else class="mx-auto w-full max-w-3xl divide-y divide-outline-gray-1 px-3 sm:px-5">
		<li v-for="a in apps.data.applications" :key="a.name" class="flex items-center gap-3 py-4">
			<router-link :to="{ name: 'PartnerInternshipApplicant', params: { name, appName: a.name } }" class="min-w-0 flex-1">
				<div class="flex flex-wrap items-center gap-2">
					<span class="font-semibold text-ink-gray-8">{{ a.student_name || a.student }}</span>
					<Badge :theme="statusTheme(a.status)" variant="subtle">{{ __(a.status) }}</Badge>
				</div>
				<div class="mt-0.5 text-xs text-ink-gray-5">
					{{ __('{0} / {1} hours logged').format(a.total_hours_logged || 0, a.hours_target || 0) }}
				</div>
				<div v-if="a.academics && Object.keys(a.academics).length" class="mt-0.5 flex flex-wrap gap-x-2 text-xs text-ink-gray-6">
					<span v-if="a.academics.program">{{ a.academics.program }}</span>
					<span v-if="a.academics.credits_passed != null">&middot; {{ __('{0} cr').format(a.academics.credits_passed) }}</span>
					<span v-if="a.academics.gpa != null">&middot; {{ __('GPA {0}').format(a.academics.gpa) }}</span>
					<span v-if="a.academics.expected_graduation">&middot; {{ __('grad {0}').format(a.academics.expected_graduation) }}</span>
				</div>
			</router-link>
			<div v-if="a.status === 'Submitted' || a.status === 'Under Review'" class="flex items-center gap-1.5">
				<Button variant="outline" theme="green" :loading="acting === a.name" @click="setStatus(a, 'Accepted')">{{ __('Accept') }}</Button>
				<Button variant="ghost" theme="red" :loading="acting === a.name" @click="setStatus(a, 'Rejected')">{{ __('Reject') }}</Button>
			</div>
		</li>
	</ul>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource, Button, Badge, toast } from 'frappe-ui'
import { ArrowLeft } from 'lucide-vue-next'
import { usePartnerOrg } from '@/composables/usePartnerOrg'

const props = defineProps({ name: { type: String, required: true } })
const { activeOrg } = usePartnerOrg()

const STATUSES = ['Submitted', 'Under Review', 'Accepted', 'Rejected', 'Active', 'Completed', 'Withdrawn']
const status = ref('')
const acting = ref(null)

const apps = createResource({
	url: 'seminary.partner.internship_portal.list_internship_applications',
	makeParams: () => ({ position: props.name, status: status.value || undefined, org: activeOrg.value }),
	auto: true,
})
watch([status, activeOrg], () => apps.reload())

const statusRes = createResource({ url: 'seminary.partner.internship_portal.set_internship_application_status' })
function setStatus(a, newStatus) {
	acting.value = a.name
	statusRes.submit(
		{ name: a.name, status: newStatus, org: activeOrg.value },
		{
			onSuccess() { acting.value = null; toast.success(__('Application updated.')); apps.reload() },
			onError(err) { acting.value = null; toast.error(err.messages?.[0] || __('Could not update.')) },
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
