<template>
	<header
		class="sticky top-0 z-10 flex flex-col gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
			<h2 class="text-xl font-bold text-ink-gray-8">{{ __('Organizations') }}</h2>
			<div class="relative w-full sm:w-72">
				<Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-gray-4" />
				<input
					v-model="query"
					type="search"
					class="w-full rounded-md border border-outline-gray-2 bg-surface-white py-1.5 pl-8 pr-3 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none"
					:placeholder="__('Search name, type, city')"
				/>
			</div>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<select v-model="partnerType" class="filter-select">
				<option value="">{{ __('All types') }}</option>
				<option v-for="pt in partnerTypes.data || []" :key="pt" :value="pt">{{ pt }}</option>
			</select>
		</div>
	</header>

	<div class="mx-auto flex w-full max-w-6xl flex-col gap-5 p-3 sm:p-5 lg:flex-row lg:items-start">
		<main class="min-w-0 flex-1">
			<div v-if="directory.loading" class="text-ink-gray-5">{{ __('Loading organizations...') }}</div>

			<div
				v-else-if="!directory.data?.length"
				class="mt-16 md:mt-28 mx-auto w-3/4 md:w-1/2 space-y-2 text-center text-ink-gray-5"
			>
				<Building2 class="mx-auto size-10 stroke-1 text-ink-gray-4" />
				<div class="text-xl font-medium">{{ __('No organizations found') }}</div>
				<div class="leading-5">{{ __('Try a different search or clear the filters.') }}</div>
			</div>

			<ul v-else class="grid grid-cols-1 gap-3 xl:grid-cols-2">
				<li v-for="org in directory.data" :key="org.name">
					<router-link
						:to="{ name: 'PartnerOrganizationDetail', params: { name: org.name } }"
						class="flex h-full flex-col gap-2 rounded-lg border border-outline-gray-2 bg-surface-white p-4 transition hover:border-outline-gray-3 hover:shadow-sm"
					>
						<div class="flex items-start justify-between gap-2">
							<span class="font-semibold text-ink-gray-8">{{ org.organization_name }}</span>
							<Badge v-if="org.partner_type" theme="blue" variant="subtle">
								{{ org.partner_type }}
							</Badge>
						</div>
						<div class="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-gray-5">
							<span v-if="org.city" class="flex items-center gap-1">
								<MapPin class="size-3.5" />{{ org.city }}
							</span>
							<span v-if="org.state">&middot; {{ org.state }}</span>
							<span v-if="org.country">&middot; {{ org.country }}</span>
						</div>
					</router-link>
				</li>
			</ul>
		</main>

		<aside class="w-full shrink-0 lg:w-80">
			<MyOrganizationsPanel @created="directory.reload()" />
		</aside>
	</div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource, debounce, Badge } from 'frappe-ui'
import { Search, Building2, MapPin } from 'lucide-vue-next'
import MyOrganizationsPanel from '@/components/MyOrganizationsPanel.vue'

const query = ref('')
const partnerType = ref('')

const partnerTypes = createResource({
	url: 'seminary.partner.api.get_partner_types',
	auto: true,
})

const directory = createResource({
	url: 'seminary.partner.api.get_partner_directory',
	makeParams: () => ({
		query: query.value,
		partner_type: partnerType.value,
	}),
	auto: true,
})

const refetch = debounce(() => directory.reload(), 250)
watch([query, partnerType], refetch)

// The "My Organizations" panel and its Add dialog live in
// components/MyOrganizationsPanel.vue — AlumniHome shows the same thing, and a
// second copy here would be one to keep in step.
</script>

<style scoped>
.filter-select {
	@apply rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none;
}
</style>
