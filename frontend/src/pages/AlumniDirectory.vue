<template>
	<header
		class="sticky top-0 z-10 flex flex-col gap-2 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
			<h2 class="text-xl font-bold text-ink-gray-8">
				{{ __('Alumni Directory') }}
			</h2>
			<div class="relative w-full sm:w-80">
				<Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-gray-4" />
				<input
					v-model="query"
					type="search"
					class="w-full rounded-md border border-outline-gray-2 bg-surface-white py-1.5 pl-8 pr-3 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none"
					:placeholder="__('Search')"
				/>
			</div>
		</div>

		<!-- The hint used to live in the placeholder, where the input clipped it. -->
		<p class="text-xs text-ink-gray-5">
			{{ __('Search by name, role, organization or city. Use the filters for program and graduation years.') }}
		</p>

		<div class="flex flex-wrap items-end gap-2 pb-0.5">
			<label class="flex flex-col gap-1">
				<span class="text-xs text-ink-gray-5">{{ __('Program') }}</span>
				<select v-model="program" class="filter-select">
					<option value="">{{ __('Any program') }}</option>
					<option v-for="p in programs.data || []" :key="p.name" :value="p.name">
						{{ p.program_name || p.name }}
					</option>
				</select>
			</label>

			<label class="flex flex-col gap-1">
				<span class="text-xs text-ink-gray-5">{{ __('Class year from') }}</span>
				<input
					v-model="classYearFrom"
					type="number"
					inputmode="numeric"
					class="filter-select w-24"
					:placeholder="__('Any')"
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-ink-gray-5">{{ __('to') }}</span>
				<input
					v-model="classYearTo"
					type="number"
					inputmode="numeric"
					class="filter-select w-24"
					:placeholder="__('Any')"
				/>
			</label>

			<label class="flex items-center gap-1.5 pb-1.5 text-sm text-ink-gray-7">
				<input v-model="openToInvites" type="checkbox" class="rounded border-outline-gray-3" />
				{{ __('Open to cohort invitations') }}
			</label>

			<Button v-if="anyFilter" variant="subtle" size="sm" :label="__('Clear')" @click="clearFilters" />
		</div>
	</header>

	<div v-if="results.loading" class="p-5 text-ink-gray-5">
		{{ __('Searching...') }}
	</div>

	<div
		v-else-if="!rows.length"
		class="mt-24 md:mt-40 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5"
	>
		<Users class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No alumni found') }}</div>
		<div class="leading-5">
			{{ __('Try a broader search term, or widen the class years.') }}
		</div>
	</div>

	<div v-else class="mx-auto w-full max-w-4xl px-3 sm:px-5">
		<p class="py-3 text-xs text-ink-gray-5">
			{{ __('{0} of {1}').format(rows.length, total) }}
		</p>

		<ul class="divide-y divide-outline-gray-1">
			<li
				v-for="alum in rows"
				:key="alum.name"
				class="flex cursor-pointer items-start gap-4 py-4 hover:bg-surface-gray-1"
				@click="openProfile(alum)"
			>
				<img
					v-if="alum.image"
					:src="alum.image"
					:alt="alum.full_name"
					class="size-12 shrink-0 rounded-full object-cover"
				/>
				<div
					v-else
					class="grid size-12 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-base font-semibold text-ink-gray-7"
				>
					{{ initials(alum.full_name) }}
				</div>

				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-baseline gap-2">
						<span class="font-semibold text-ink-gray-8">{{ alum.full_name }}</span>
						<span v-if="alum.graduations?.length" class="text-xs text-ink-gray-5">
							{{ __('Class of') }}
							{{ alum.graduations.map((g) => g.class_year).filter(Boolean).join(', ') }}
						</span>
					</div>

					<div
						v-if="alum.current_role || alum.current_organization || alum.partner_organization"
						class="flex flex-wrap items-center gap-x-1 gap-y-1 text-sm text-ink-gray-6"
					>
						<span v-if="alum.current_role">{{ alum.current_role }}</span>
						<span v-if="alum.current_role && (alum.current_organization || alum.partner_organization)">
							&nbsp;·&nbsp;
						</span>
						<!-- A badge only where the seminary knows the organization
						     and lists it; otherwise the person's own words. -->
						<router-link
							v-if="alum.partner_organization"
							:to="`/alumni/organizations/${alum.partner_organization.name}`"
							class="rounded bg-surface-blue-2 px-1.5 py-0.5 text-xs font-medium text-ink-blue-3 hover:underline"
							@click.stop
						>
							{{ alum.partner_organization.organization_name }}
						</router-link>
						<span v-else-if="alum.current_organization">{{ alum.current_organization }}</span>
					</div>

					<div v-if="alum.graduations?.length || alum.city" class="mt-1 text-xs text-ink-gray-5">
						<span v-if="alum.graduations?.length">
							{{ alum.graduations.map((g) => g.program).join(' · ') }}
						</span>
						<span v-if="alum.graduations?.length && alum.city">&nbsp;·&nbsp;</span>
						<span v-if="alum.city">{{ alum.city }}</span>
					</div>
				</div>

				<a
					v-if="alum.linkedin_url"
					:href="alum.linkedin_url"
					target="_blank"
					rel="noopener"
					class="shrink-0 text-xs text-ink-blue-6 hover:underline"
					@click.stop
				>
					LinkedIn
				</a>
			</li>
		</ul>

		<div v-if="total > pageSize" class="flex items-center justify-between gap-3 py-4">
			<Button variant="subtle" :disabled="offset === 0" :label="__('Previous')" @click="page(-1)" />
			<Button
				variant="subtle"
				:disabled="offset + pageSize >= total"
				:label="__('Next')"
				@click="page(1)"
			/>
		</div>
	</div>

	<AlumniDirectoryProfile v-model="openProfileName" />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Button, createResource, debounce } from 'frappe-ui'
import { Search, Users } from 'lucide-vue-next'
import AlumniDirectoryProfile from '@/components/AlumniDirectoryProfile.vue'

const pageSize = 50

const query = ref('')
const program = ref('')
const classYearFrom = ref('')
const classYearTo = ref('')
const openToInvites = ref(false)
const offset = ref(0)
const openProfileName = ref(null)

const programs = createResource({
	url: 'frappe.client.get_list',
	params: {
		doctype: 'Program',
		fields: ['name', 'program_name'],
		order_by: 'program_name asc',
		limit_page_length: 0,
	},
	auto: true,
	onError() {},
})

const results = createResource({
	url: 'seminary.alumni.api.directory_search',
	makeParams: () => ({
		query: query.value,
		program: program.value || '',
		class_year_from: classYearFrom.value || null,
		class_year_to: classYearTo.value || null,
		open_to_invites: openToInvites.value ? 1 : 0,
		limit: pageSize,
		offset: offset.value,
	}),
	auto: true,
})

const rows = computed(() => results.data?.results || [])
const total = computed(() => results.data?.total || 0)

const anyFilter = computed(
	() =>
		!!program.value || !!classYearFrom.value || !!classYearTo.value || openToInvites.value
)

const refetch = debounce(() => results.reload(), 250)

// Any change to what is being asked for resets to the first page: paging is a
// position in one result set, and keeping an offset across a narrower filter
// lands on an empty page that reads as "no alumni found".
watch([query, program, classYearFrom, classYearTo, openToInvites], () => {
	offset.value = 0
	refetch()
})
watch(offset, () => results.reload())

function page(direction) {
	offset.value = Math.max(0, offset.value + direction * pageSize)
}

function clearFilters() {
	program.value = ''
	classYearFrom.value = ''
	classYearTo.value = ''
	openToInvites.value = false
}

function openProfile(alum) {
	openProfileName.value = alum.name
}

function initials(name) {
	return (
		(name || '')
			.split(/\s+/)
			.filter(Boolean)
			.slice(0, 2)
			.map((part) => part[0].toUpperCase())
			.join('') || '?'
	)
}
</script>

<style scoped>
.filter-select {
	@apply rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none;
}
</style>
