<template>
	<header
		class="sticky top-0 z-10 flex flex-col gap-2 border-b bg-surface-white px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:px-5"
	>
		<h2 class="text-xl font-bold text-ink-gray-8">
			{{ __('Alumni Directory') }}
		</h2>
		<div class="relative w-full sm:w-72">
			<Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-gray-4" />
			<input
				v-model="query"
				type="search"
				class="w-full rounded-md border border-outline-gray-2 bg-surface-white py-1.5 pl-8 pr-3 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none"
				:placeholder="__('Search by name, role, organization, city')"
			/>
		</div>
	</header>

	<div v-if="results.loading" class="p-5 text-ink-gray-5">
		{{ __('Searching...') }}
	</div>

	<div
		v-else-if="!results.data?.length"
		class="mt-24 md:mt-40 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5"
	>
		<Users class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No alumni found') }}</div>
		<div class="leading-5">
			{{ __('Try a broader search term.') }}
		</div>
	</div>

	<ul v-else class="mx-auto w-full max-w-4xl divide-y divide-outline-gray-1 px-3 sm:px-5">
		<li
			v-for="alum in results.data"
			:key="alum.name"
			class="flex items-start gap-4 py-4"
		>
			<div
				class="grid size-12 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-base font-semibold text-ink-gray-7"
			>
				{{ initials(alum.full_name) }}
			</div>
			<div class="min-w-0 flex-1">
				<div class="flex flex-wrap items-baseline gap-2">
					<span class="font-semibold text-ink-gray-8">{{ alum.full_name }}</span>
					<span v-if="alum.class_year" class="text-xs text-ink-gray-5">
						{{ __('Class of') }} {{ alum.class_year }}
					</span>
				</div>
				<div v-if="alum.current_role || alum.current_organization" class="text-sm text-ink-gray-6">
					{{ alum.current_role }}
					<span v-if="alum.current_role && alum.current_organization">&nbsp;·&nbsp;</span>
					{{ alum.current_organization }}
				</div>
				<div v-if="alum.program_completed || alum.city" class="mt-1 text-xs text-ink-gray-5">
					<span v-if="alum.program_completed">{{ alum.program_completed }}</span>
					<span v-if="alum.program_completed && alum.city">&nbsp;·&nbsp;</span>
					<span v-if="alum.city">{{ alum.city }}</span>
				</div>
			</div>
			<a
				v-if="alum.linkedin_url"
				:href="alum.linkedin_url"
				target="_blank"
				rel="noopener"
				class="shrink-0 text-xs text-ink-blue-6 hover:underline"
			>
				LinkedIn
			</a>
		</li>
	</ul>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource, debounce } from 'frappe-ui'
import { Search, Users } from 'lucide-vue-next'

const query = ref('')

const results = createResource({
	url: 'seminary.alumni.api.directory_search',
	makeParams: () => ({ query: query.value, limit: 100 }),
	auto: true,
})

const refetch = debounce(() => results.reload(), 250)
watch(query, refetch)

function initials(name) {
	return (name || '')
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((part) => part[0].toUpperCase())
		.join('') || '?'
}
</script>
