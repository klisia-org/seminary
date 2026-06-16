<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<h2 class="text-xl font-bold text-ink-gray-8">{{ __('Our Interns') }}</h2>
	</header>

	<div v-if="placements.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="placements.error" class="p-5 text-ink-red-4">{{ placements.error.messages?.[0] || __('Not authorized.') }}</div>

	<div v-else-if="!visible.length" class="mt-24 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5">
		<UserCheck class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No interns yet') }}</div>
		<div>{{ __('Interns appear here once you accept an application.') }}</div>
	</div>

	<div v-else class="mx-auto w-full max-w-3xl px-3 sm:px-5">
		<div class="flex items-center gap-2 py-3">
			<label class="flex items-center gap-1.5 text-sm text-ink-gray-6">
				<input type="checkbox" v-model="activeOnly" class="rounded border-outline-gray-3" />{{ __('Active only') }}
			</label>
		</div>
		<ul class="divide-y divide-outline-gray-1">
			<li v-for="p in visible" :key="p.name" class="py-4">
				<router-link :to="{ name: 'PartnerInternshipApplicant', params: { name: p.internship_position, appName: p.internship_application } }" class="block">
					<div class="flex flex-wrap items-center gap-2">
						<span class="font-semibold text-ink-gray-8">{{ p.student_name || p.student }}</span>
						<Badge :theme="statusTheme(p.placement_status)" variant="subtle">{{ __(p.placement_status) }}</Badge>
					</div>
					<div class="mt-0.5 text-xs text-ink-gray-5">
						<span v-if="p.supervisor_name">{{ __('Supervisor: {0}').format(p.supervisor_name) }} &middot; </span>
						<span>{{ __('{0} / {1} hours').format(p.hours_logged || 0, p.hours_allocated || 0) }}</span>
					</div>
				</router-link>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { createResource, Badge } from 'frappe-ui'
import { UserCheck } from 'lucide-vue-next'
import { usePartnerOrg } from '@/composables/usePartnerOrg'

const { activeOrg } = usePartnerOrg()
const activeOnly = ref(false)

const placements = createResource({
	url: 'seminary.partner.internship_portal.list_placements',
	makeParams: () => ({ org: activeOrg.value }),
	auto: true,
})
watch(activeOrg, () => placements.reload())

const visible = computed(() => {
	const rows = placements.data || []
	if (!activeOnly.value) return rows
	return rows.filter((p) => ['Proposed', 'Active'].includes(p.placement_status))
})

function statusTheme(s) {
	if (s === 'Active' || s === 'Completed') return 'green'
	if (s === 'Terminated') return 'red'
	return 'gray'
}
</script>
