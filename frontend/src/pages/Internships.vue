<template>
	<header class="sticky top-0 z-10 flex flex-col gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
			<h2 class="text-xl font-bold text-ink-gray-8">{{ __('Internships') }}</h2>
			<div class="flex items-center gap-2">
				<div class="relative w-full sm:w-64">
					<Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-gray-4" />
					<input v-model="query" type="search" :placeholder="__('Search title, organization, city')"
						class="w-full rounded-md border border-outline-gray-2 bg-surface-white py-1.5 pl-8 pr-3 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none" />
				</div>
				<Button variant="subtle" @click="$router.push({ name: 'MyInternships' })">{{ __('My Internships') }}</Button>
			</div>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<select v-model="ministrySetting" class="filter-select">
				<option value="">{{ __('All settings') }}</option>
				<option v-for="s in MINISTRY_SETTINGS" :key="s" :value="s">{{ __(s) }}</option>
			</select>
		</div>
	</header>

	<div class="mx-auto w-full max-w-5xl p-3 sm:p-5">
		<div v-if="positions.loading" class="text-ink-gray-5">{{ __('Loading internships...') }}</div>
		<div v-else-if="!positions.data?.length" class="mt-16 md:mt-28 mx-auto w-3/4 md:w-1/2 space-y-2 text-center text-ink-gray-5">
			<Handshake class="mx-auto size-10 stroke-1 text-ink-gray-4" />
			<div class="text-xl font-medium">{{ __('No internships available') }}</div>
			<div class="leading-5">{{ __('You only see internships your program requirements make you eligible for.') }}</div>
		</div>
		<ul v-else class="grid grid-cols-1 gap-3 xl:grid-cols-2">
			<li v-for="p in positions.data" :key="p.name">
				<router-link :to="{ name: 'Internship', params: { name: p.name } }"
					class="flex h-full flex-col gap-2 rounded-lg border border-outline-gray-2 bg-surface-white p-4 transition hover:border-outline-gray-3 hover:shadow-sm">
					<div class="flex items-start justify-between gap-2">
						<span class="font-semibold text-ink-gray-8">{{ p.title }}</span>
						<Badge theme="blue" variant="subtle">{{ p.internship_type }}</Badge>
					</div>
					<div class="text-sm text-ink-gray-6">{{ p.organization_name }}</div>
					<div class="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-gray-5">
						<span v-if="p.city" class="flex items-center gap-1"><MapPin class="size-3.5" />{{ p.city }}</span>
						<span v-if="p.ministry_setting">&middot; {{ __(p.ministry_setting) }}</span>
						<span v-if="p.min_hours_per_week">&middot; {{ __('{0} h/week').format(p.min_hours_per_week) }}</span>
					</div>
				</router-link>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource, debounce, Badge, Button } from 'frappe-ui'
import { Search, Handshake, MapPin } from 'lucide-vue-next'

const MINISTRY_SETTINGS = ['Urban', 'Suburban', 'Rural', 'Campus']
const query = ref('')
const ministrySetting = ref('')

const positions = createResource({
	url: 'seminary.partner.internship_api.get_internships',
	makeParams: () => ({ query: query.value, ministry_setting: ministrySetting.value }),
	auto: true,
})
const refetch = debounce(() => positions.reload(), 250)
watch([query, ministrySetting], refetch)
</script>

<style scoped>
.filter-select {
	@apply rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none;
}
</style>
