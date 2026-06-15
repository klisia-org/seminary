<template>
	<header
		class="sticky top-0 z-10 flex flex-col gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
			<h2 class="text-xl font-bold text-ink-gray-8">{{ __('Jobs') }}</h2>
			<div class="relative w-full sm:w-72">
				<Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-gray-4" />
				<input
					v-model="query"
					type="search"
					class="w-full rounded-md border border-outline-gray-2 bg-surface-white py-1.5 pl-8 pr-3 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none"
					:placeholder="__('Search title, organization, city')"
				/>
			</div>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<select v-model="positionType" class="filter-select">
				<option value="">{{ __('All positions') }}</option>
				<option v-for="p in POSITION_TYPES" :key="p" :value="p">{{ __(p) }}</option>
			</select>
			<select v-model="employmentType" class="filter-select">
				<option value="">{{ __('All types') }}</option>
				<option v-for="t in EMPLOYMENT_TYPES" :key="t" :value="t">{{ __(t) }}</option>
			</select>
			<select v-model="ministrySetting" class="filter-select">
				<option value="">{{ __('All settings') }}</option>
				<option v-for="s in MINISTRY_SETTINGS" :key="s" :value="s">{{ __(s) }}</option>
			</select>
			<select v-model="partnerType" class="filter-select">
				<option value="">{{ __('All organizations') }}</option>
				<option v-for="pt in partnerTypes.data || []" :key="pt" :value="pt">
					{{ pt }}
				</option>
			</select>
			<label class="flex items-center gap-1.5 text-sm text-ink-gray-7">
				<input
					v-model="requiresDoctrinal"
					type="checkbox"
					class="rounded border-outline-gray-3 text-ink-gray-8 focus:ring-0"
				/>
				{{ __('Requires doctrinal agreement') }}
			</label>
		</div>
	</header>

	<div v-if="openings.loading" class="p-5 text-ink-gray-5">{{ __('Loading jobs...') }}</div>

	<div
		v-else-if="!openings.data?.length"
		class="mt-24 md:mt-40 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5"
	>
		<Briefcase class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No openings found') }}</div>
		<div class="leading-5">{{ __('Try a different search or clear the filters.') }}</div>
	</div>

	<ul v-else class="mx-auto grid w-full max-w-5xl grid-cols-1 gap-3 p-3 sm:grid-cols-2 sm:p-5">
		<li v-for="job in openings.data" :key="job.name">
			<router-link
				:to="{ name: 'JobOpening', params: { jobName: job.name } }"
				class="flex h-full flex-col gap-2 rounded-lg border border-outline-gray-2 bg-surface-white p-4 transition hover:border-outline-gray-3 hover:shadow-sm"
			>
				<div class="flex items-start justify-between gap-2">
					<span class="font-semibold text-ink-gray-8">{{ job.job_title }}</span>
					<Badge v-if="job.employment_type" theme="blue" variant="subtle">
						{{ __(job.employment_type) }}
					</Badge>
				</div>
				<div class="text-sm text-ink-gray-6">{{ job.organization_name }}</div>
				<div class="flex flex-wrap items-center gap-1.5">
					<Badge v-if="job.position_type" theme="gray" variant="subtle">
						{{ __(job.position_type) }}
					</Badge>
					<Badge v-if="job.require_doctrinal_alignment" theme="orange" variant="subtle">
						{{ __('Doctrinal agreement') }}
					</Badge>
				</div>
				<div class="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-gray-5">
					<span v-if="job.city" class="flex items-center gap-1">
						<MapPin class="size-3.5" />{{ job.city }}
					</span>
					<span v-if="job.ministry_setting">&middot; {{ __(job.ministry_setting) }}</span>
					<span v-if="job.posted_on">&middot; {{ formatDate(job.posted_on) }}</span>
				</div>
			</router-link>
		</li>
	</ul>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource, debounce, Badge } from 'frappe-ui'
import { Search, Briefcase, MapPin } from 'lucide-vue-next'

const EMPLOYMENT_TYPES = ['Full-time', 'Part-time', 'Contract', 'Salary with fundraising', 'Volunteer']
const MINISTRY_SETTINGS = ['Urban', 'Suburban', 'Rural', 'Campus']
const POSITION_TYPES = [
	'Pastoral / Preaching',
	'Teaching / Education',
	'Worship / Music',
	'Youth & Children',
	'Counseling / Care',
	'Missions / Outreach',
	'Administration / Operations',
	'Facilities / Support',
	'Other',
]

const query = ref('')
const employmentType = ref('')
const ministrySetting = ref('')
const positionType = ref('')
const partnerType = ref('')
const requiresDoctrinal = ref(false)

const partnerTypes = createResource({
	url: 'seminary.partner.api.get_partner_types',
	auto: true,
})

const openings = createResource({
	url: 'seminary.partner.api.get_job_openings',
	makeParams: () => ({
		query: query.value,
		employment_type: employmentType.value,
		ministry_setting: ministrySetting.value,
		position_type: positionType.value,
		partner_type: partnerType.value,
		requires_doctrinal: requiresDoctrinal.value ? '1' : '',
	}),
	auto: true,
})

const refetch = debounce(() => openings.reload(), 250)
watch([query, employmentType, ministrySetting, positionType, partnerType, requiresDoctrinal], refetch)

function formatDate(value) {
	if (!value) return ''
	return new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.filter-select {
	@apply rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none;
}
</style>
