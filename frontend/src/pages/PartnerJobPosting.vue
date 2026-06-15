<template>
	<header class="sticky top-0 z-10 flex flex-col gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<div class="flex items-center justify-between gap-2">
			<router-link :to="{ name: 'PartnerJobPostings' }" class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
				<ArrowLeft class="size-4" />{{ __('Job Postings') }}
			</router-link>
			<router-link :to="{ name: 'PartnerJobPostingEdit', params: { name } }" class="text-sm text-ink-blue-6 hover:underline">
				{{ __('Edit posting') }}
			</router-link>
		</div>
		<div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
			<h1 class="text-lg font-semibold text-ink-gray-9">{{ apps.data?.job_title || name }}</h1>
			<span v-if="apps.data" class="text-sm text-ink-gray-5">
				{{ apps.data.total === 1 ? __('1 application received') : __('{0} applications received').format(apps.data.total) }}
			</span>
		</div>
		<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
			<div class="relative w-full sm:w-64">
				<Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-gray-4" />
				<input v-model="query" type="search" :placeholder="__('Search applicant')"
					class="w-full rounded-md border border-outline-gray-2 bg-surface-white py-1.5 pl-8 pr-3 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none" />
			</div>
			<select v-model="status" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:outline-none">
				<option value="">{{ __('All statuses') }}</option>
				<option v-for="s in STATUSES" :key="s" :value="s">{{ __(s) }}</option>
			</select>
			<select v-model="evaluated" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:outline-none">
				<option value="">{{ __('All evaluations') }}</option>
				<option value="no">{{ __('Needs my evaluation') }}</option>
				<option value="yes">{{ __('Evaluated by me') }}</option>
			</select>
		</div>
	</header>

	<div v-if="apps.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="apps.error" class="p-5 text-ink-red-4">{{ apps.error.messages?.[0] || __('Not authorized.') }}</div>
	<div v-else-if="!apps.data?.applications?.length" class="mt-20 text-center text-ink-gray-5">
		{{ apps.data?.total ? __('No applications match these filters.') : __('No applications yet.') }}
	</div>

	<div v-else class="mx-auto w-full max-w-3xl px-3 py-3 sm:px-5">
		<div class="mb-2 flex items-center gap-3 px-2 text-xs font-medium text-ink-gray-5">
			<button class="flex items-center gap-1 hover:text-ink-gray-7" @click="setSort('applicant')">
				{{ __('Applicant') }}<component :is="sortIcon('applicant')" class="size-3" />
			</button>
			<div class="ml-auto flex items-center gap-4">
				<div class="w-20 text-center">{{ __('Evaluated') }}</div>
				<div class="w-16 text-right">{{ __('Contacts') }}</div>
				<button class="flex w-12 items-center justify-end gap-1 hover:text-ink-gray-7" @click="setSort('average_rating')">
					{{ __('Rating') }}<component :is="sortIcon('average_rating')" class="size-3" />
				</button>
				<button class="flex w-24 items-center justify-end gap-1 hover:text-ink-gray-7" @click="setSort('submission_date')">
					{{ __('Submitted') }}<component :is="sortIcon('submission_date')" class="size-3" />
				</button>
			</div>
		</div>
		<ul class="divide-y divide-outline-gray-1">
			<li v-for="a in apps.data.applications" :key="a.name">
				<router-link :to="{ name: 'PartnerApplication', params: { name, appName: a.name } }"
					class="flex items-center gap-3 px-2 py-3 hover:bg-surface-gray-1">
					<div class="min-w-0 flex-1">
						<div class="font-medium text-ink-gray-8">{{ a.full_name }}</div>
						<Badge :theme="statusTheme(a.status)" variant="subtle">{{ __(a.status) }}</Badge>
					</div>
					<div class="flex w-20 justify-center">
						<Badge :theme="a.evaluated_by_me ? 'green' : 'red'" variant="subtle">
							{{ a.evaluated_by_me ? __('Yes') : __('No') }}
						</Badge>
					</div>
					<div class="w-16 text-right text-sm text-ink-gray-6">{{ a.contact_count || 0 }}</div>
					<div class="flex w-12 items-center justify-end gap-1 text-sm text-ink-gray-6">
						<Star class="size-3.5 text-ink-amber-3" />{{ stars(a.average_rating) }}
					</div>
					<div class="w-24 text-right text-xs text-ink-gray-5">{{ formatDate(a.submission_date) }}</div>
				</router-link>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource, debounce, Badge } from 'frappe-ui'
import { ArrowLeft, Search, Star, ChevronUp, ChevronDown } from 'lucide-vue-next'
import { statusTheme } from '@/utils/statusTheme'

const props = defineProps({ name: { type: String, required: true } })
const STATUSES = ['Open', 'Replied', 'Shortlisted', 'Hold', 'Rejected', 'Accepted', 'Withdrawn']

const query = ref('')
const status = ref('')
const evaluated = ref('')
const sortBy = ref('submission_date')
const sortDir = ref('desc')

const apps = createResource({
	url: 'seminary.partner.portal.list_applications',
	makeParams: () => ({ opening: props.name, status: status.value, evaluated: evaluated.value, sort_by: sortBy.value, sort_dir: sortDir.value, query: query.value }),
	auto: true,
})
const refetch = debounce(() => apps.reload(), 250)
watch([query, status, evaluated, sortBy, sortDir], refetch)

function setSort(col) {
	if (sortBy.value === col) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
	else {
		sortBy.value = col
		sortDir.value = col === 'applicant' ? 'asc' : 'desc'
	}
}
function sortIcon(col) {
	if (sortBy.value !== col) return ChevronDown
	return sortDir.value === 'asc' ? ChevronUp : ChevronDown
}
function stars(v) {
	return (Math.round((v || 0) * 5 * 10) / 10).toFixed(1)
}
function formatDate(v) {
	if (!v) return ''
	return new Date(v).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
</script>
