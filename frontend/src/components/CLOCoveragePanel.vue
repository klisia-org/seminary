<template>
	<div v-if="hasAretenic && coverage.data" class="mt-8 mb-10 px-5">
		<div class="text-lg font-semibold text-ink-gray-9 mb-1">
			{{ __('Outcome coverage') }}
		</div>
		<div class="text-sm text-ink-gray-6 mb-4">
			{{ __('Which learning outcomes this offering actually measures — and which nothing measures.') }}
		</div>

		<div v-if="unmappedClos" class="mb-4 rounded bg-surface-amber-1 px-3 py-2 text-sm text-ink-gray-8">
			<!--
				The mapping gap surfaces here because this is where it can still be fixed cheaply.
				Once grades are in, an unmapped outcome produces no attainment at all and becomes a
				hole in the record (decisions/034 section 4).
			-->
			{{ __('{0} outcome(s) have no assessment mapped in this offering. They will produce no attainment data.').format(unmappedClos) }}
		</div>

		<table class="min-w-full table-auto border-collapse">
			<thead>
				<tr>
					<th class="p-2 border text-left">{{ __('Outcome') }}</th>
					<th class="p-2 border text-left">{{ __('Statement') }}</th>
					<th class="p-2 border text-left">{{ __('Measured by') }}</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="clo in coverage.data.clos" :key="clo.name"
					:class="{ 'bg-surface-amber-1': !clo.mapped }">
					<td class="p-2 border align-top whitespace-nowrap font-medium">
						{{ clo.shorthand || clo.name }}
					</td>
					<td class="p-2 border align-top text-sm text-ink-gray-7">
						{{ clo.statement }}
					</td>
					<td class="p-2 border align-top text-sm">
						<span v-if="!clo.mapped" class="text-ink-amber-3 font-medium">
							{{ __('Nothing') }}
						</span>
						<span v-else class="flex flex-wrap gap-1">
							<Badge v-for="component in clo.components" :key="component.name" theme="green" size="sm">
								{{ component.title }}
							</Badge>
						</span>
					</td>
				</tr>
			</tbody>
		</table>

		<!--
			The inverse gap: a graded component measuring no outcome. Invisible from the outcome
			side alone, and just as much a mapping problem.
		-->
		<div v-if="coverage.data.unmapped_components?.length" class="mt-4">
			<div class="text-sm font-medium text-ink-gray-8 mb-2">
				{{ __('Components measuring no outcome') }}
			</div>
			<div class="flex flex-wrap gap-1.5">
				<Badge v-for="component in coverage.data.unmapped_components" :key="component.name"
					theme="orange" size="sm">
					{{ component.title }} ({{ component.type }})
				</Badge>
			</div>
			<div class="mt-1.5 text-xs text-ink-gray-5">
				{{ __('These are graded but contribute to no learning outcome. That may be intentional.') }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, watch } from 'vue'
import { createResource, Badge } from 'frappe-ui'

const props = defineProps({
	courseSchedule: { type: String, required: true },
	// Bumped by the parent after a mapping is saved, so the panel reflects the change.
	refreshKey: { type: [String, Number], default: 0 },
})

const user = inject('$user')
const hasAretenic = computed(() => !!user?.data?.has_aretenic)

const coverage = createResource({
	url: 'aretenic.improvement_api.get_clo_coverage',
	makeParams: () => ({ course_schedule: props.courseSchedule }),
	onError: () => {},
})

const unmappedClos = computed(() => coverage.data?.unmapped_clo_count || 0)

watch(
	() => [hasAretenic.value, props.courseSchedule, props.refreshKey],
	([enabled, schedule]) => {
		if (enabled && schedule) coverage.reload()
	},
	{ immediate: true }
)
</script>
