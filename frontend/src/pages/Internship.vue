<template>
	<header class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<router-link :to="{ name: 'Internships' }" class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
			<ArrowLeft class="size-4" />{{ __('Internships') }}
		</router-link>
	</header>

	<div v-if="info.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="info.error" class="p-5 text-ink-red-4">{{ info.error.messages?.[0] || __('Not found.') }}</div>

	<div v-else-if="info.data" class="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
		<div class="flex flex-wrap items-center gap-2">
			<h1 class="text-2xl font-bold text-ink-gray-9">{{ info.data.title }}</h1>
			<Badge theme="blue" variant="subtle">{{ info.data.internship_type }}</Badge>
		</div>
		<div class="mt-1 text-ink-gray-6">{{ info.data.organization?.organization_name }}</div>
		<div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-ink-gray-5">
			<span v-if="info.data.location?.location_name">{{ info.data.location.location_name }}</span>
			<span v-if="info.data.ministry_setting">{{ __(info.data.ministry_setting) }}</span>
			<span v-if="info.data.type_info?.total_hours_required">{{ __('{0} hours required').format(info.data.type_info.total_hours_required) }}</span>
			<span v-if="info.data.min_hours_per_week">{{ __('{0} h/week').format(info.data.min_hours_per_week) }}</span>
		</div>

		<div class="mt-5 flex items-center gap-2">
			<Button v-if="info.data.can_apply" variant="solid" @click="confirmApply">{{ __('Apply') }}</Button>
			<Badge v-else-if="info.data.already_applied" theme="green" variant="subtle">{{ __('Already applied') }}</Badge>
			<div v-else-if="!info.data.eligible" class="rounded-md bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3">
				{{ __('You are not currently eligible for this internship (it must satisfy an open program requirement).') }}
			</div>
			<router-link v-if="info.data.already_applied" :to="{ name: 'MyInternships' }" class="text-sm text-ink-blue-6 hover:underline">{{ __('View in My Internships') }}</router-link>
		</div>

		<section v-if="hasSchedule" class="mt-6">
			<h2 class="mb-1 text-sm font-semibold text-ink-gray-7">{{ __('Schedule') }}</h2>
			<ul class="text-sm text-ink-gray-6">
				<li v-for="(s, i) in info.data.weekly_schedule" :key="i">{{ __(s.day_of_week) }} {{ s.start_time }}–{{ s.end_time }}</li>
			</ul>
			<p v-if="info.data.schedule_notes" class="mt-1 text-sm text-ink-gray-6">{{ info.data.schedule_notes }}</p>
		</section>

		<section v-if="info.data.description" class="prose prose-sm mt-6 max-w-none text-ink-gray-8" v-html="info.data.description" />
		<section v-if="info.data.qualifications" class="mt-6">
			<h2 class="mb-1 text-sm font-semibold text-ink-gray-7">{{ __('Qualifications') }}</h2>
			<div class="prose prose-sm max-w-none text-ink-gray-8" v-html="info.data.qualifications" />
		</section>

		<section v-if="info.data.organization?.about_us" class="mt-6">
			<h2 class="mb-1 text-sm font-semibold text-ink-gray-7">{{ __('About {0}').format(info.data.organization.organization_name) }}</h2>
			<div class="prose prose-sm max-w-none text-ink-gray-8" v-html="info.data.organization.about_us" />
		</section>
	</div>

	<Dialog v-model="dialog.show" :options="{ title: dialog.title, message: dialog.message, actions: dialog.actions }" />
</template>

<script setup>
import { computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { createResource, Badge, Button, Dialog, toast } from 'frappe-ui'
import { ArrowLeft } from 'lucide-vue-next'

const props = defineProps({ name: { type: String, required: true } })
const router = useRouter()

const info = createResource({
	url: 'seminary.partner.internship_api.get_internship',
	makeParams: () => ({ name: props.name }),
	auto: true,
})
const hasSchedule = computed(() => !info.data?.flexible_schedule && info.data?.weekly_schedule?.length)

const applyRes = createResource({ url: 'seminary.partner.internship_api.apply_to_internship' })
const dialog = reactive({ show: false, title: '', message: '', actions: [] })
function confirmApply() {
	dialog.title = __('Apply for this internship')
	dialog.message = __('Have you prayed and felt God leading you this way?')
	dialog.actions = [
		{ label: __('Not yet'), variant: 'outline', onClick: () => (dialog.show = false) },
		{
			label: __('Yes, apply'), variant: 'solid',
			onClick: () => applyRes.submit({ internship_position: props.name, submit: '1' }, {
				onSuccess: () => { dialog.show = false; toast.success(__('Application submitted.')); router.push({ name: 'MyInternships' }) },
				onError: (err) => toast.error(err.messages?.[0] || __('Could not apply.')),
			}),
		},
	]
	dialog.show = true
}
</script>
