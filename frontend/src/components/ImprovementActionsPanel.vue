<template>
	<div v-if="hasAretenic && (accountable.length || context.length)" class="mt-6">
		<div class="text-lg font-semibold text-ink-gray-9 mb-1">
			{{ __('Improvement actions') }}
		</div>
		<div class="text-sm text-ink-gray-6 mb-4">
			{{ __('Carried into this offering from earlier outcome reports.') }}
		</div>

		<!--
			Two registers, deliberately distinct (decisions/034 section 8). An inherited course-wide
			action that reads like a personal reprimand, or departmental work that looks like
			homework, teaches faculty to ignore this panel — and the panel is the mechanism the
			whole improvement cycle depends on.
		-->
		<div v-if="accountable.length" class="mb-5">
			<div class="text-sm font-medium text-ink-gray-8 mb-2">
				{{ __('You will account for these in your next report') }}
			</div>
			<div class="space-y-2">
				<div v-for="action in accountable" :key="action.name"
					class="rounded border border-outline-gray-2 bg-surface-white px-3 py-2.5">
					<div class="flex items-start justify-between gap-3">
						<div class="font-medium text-ink-gray-8">{{ action.title }}</div>
						<div class="flex shrink-0 items-center gap-1.5">
							<Badge v-if="action.inherited" theme="blue" size="sm">
								{{ __('Course-wide') }}
							</Badge>
							<Badge v-if="action.modality && action.modality !== 'All'" theme="gray" size="sm">
								{{ __(action.modality) }}
							</Badge>
						</div>
					</div>
					<div v-if="action.description" class="mt-1 text-sm text-ink-gray-6">
						{{ action.description }}
					</div>
					<div v-if="action.inherited" class="mt-1.5 text-xs text-ink-gray-5">
						{{ __('Agreed for this course by the department. You report on your own section only.') }}
					</div>
				</div>
			</div>
		</div>

		<div v-if="context.length">
			<div class="text-sm font-medium text-ink-gray-8 mb-2">
				{{ __('Underway in your department') }}
			</div>
			<div class="space-y-2">
				<div v-for="action in context" :key="action.name"
					class="rounded border border-dashed border-outline-gray-2 px-3 py-2.5">
					<div class="font-medium text-ink-gray-7">{{ action.title }}</div>
					<div v-if="action.description" class="mt-1 text-sm text-ink-gray-6">
						{{ action.description }}
					</div>
				</div>
			</div>
			<div class="mt-1.5 text-xs text-ink-gray-5">
				{{ __('For your information — nothing here is yours to close.') }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, watch } from 'vue'
import { createResource, Badge } from 'frappe-ui'

// Optional surface — only when the Aretenic app is installed (ADR 030). Seminary stays fully
// functional without it, so every call site here is behind hasAretenic.
const props = defineProps({
	courseSchedule: { type: String, required: true },
})

const user = inject('$user')
const hasAretenic = computed(() => !!user?.data?.has_aretenic)

const actions = createResource({
	url: 'aretenic.improvement_api.get_offering_actions',
	makeParams: () => ({ course_schedule: props.courseSchedule }),
	// A professor with no access to this offering's outcome data is a normal case, not an error
	// worth a toast — the panel simply stays hidden.
	onError: () => {},
})

const accountable = computed(() => actions.data?.accountable || [])
const context = computed(() => actions.data?.context || [])

watch(
	() => [hasAretenic.value, props.courseSchedule],
	([enabled, schedule]) => {
		if (enabled && schedule) actions.reload()
	},
	{ immediate: true }
)
</script>
