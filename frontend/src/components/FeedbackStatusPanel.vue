<template>
	<!--
		Optional Aretenic surface (ADR 030), for the instructor of record (decisions/035 §9, §10).

		While the window is open this shows the response *rate* and nothing else. That asymmetry is
		the design: a professor who can see the rate will chase it, and encouragement from the
		instructor is by far the largest lever on response rate — while showing them any content
		mid-window is exactly the harm the release timing exists to prevent, since they still hold
		grading power over the respondents.
	-->
	<div v-if="hasAretenic && campaign" class="mt-6">
		<div class="mb-1 text-lg font-semibold text-ink-gray-9">{{ __('Student feedback') }}</div>

		<!-- Collection in progress -->
		<div v-if="campaign.status === 'Open'"
			class="rounded border border-outline-gray-2 bg-surface-white px-3 py-2.5">
			<div class="flex items-baseline gap-2">
				<span class="text-2xl font-semibold text-ink-gray-9">
					{{ campaign.responded_n }}<span class="text-base text-ink-gray-5">/{{ campaign.invited_n }}</span>
				</span>
				<span class="text-sm text-ink-gray-6">{{ __('have answered') }}</span>
			</div>
			<div class="mt-2 h-1.5 w-full overflow-hidden rounded bg-surface-gray-2">
				<div class="h-full bg-blue-500" :style="{ width: pct + '%' }" />
			</div>
			<p class="mt-2 text-xs text-ink-gray-5">
				{{ __('Closes {0}. You will see the results once grades are submitted.', [campaign.closes_on]) }}
			</p>
			<p class="mt-1 text-xs text-ink-gray-5">
				{{ __('Mentioning it in class raises the response rate more than any reminder email does.') }}
			</p>
		</div>

		<!-- Collected, not yet released -->
		<div v-else-if="!aggregate"
			class="rounded border border-dashed border-outline-gray-2 px-3 py-2.5 text-sm text-ink-gray-6">
			{{ __('Feedback for this offering closed with {0} response(s). Results become visible once grades have been submitted.', [campaign.responded_n]) }}
		</div>

		<!-- Released -->
		<div v-else class="rounded border border-outline-gray-2 bg-surface-white px-3 py-3">
			<div class="flex flex-wrap items-baseline gap-x-6 gap-y-1">
				<div>
					<span class="text-2xl font-semibold text-ink-gray-9">{{ aggregate.responded_n }}</span>
					<span class="ml-1 text-sm text-ink-gray-6">
						{{ __('of {0} responded', [aggregate.invited_n]) }}
					</span>
				</div>
				<div v-if="aggregate.overall_mean">
					<span class="text-sm text-ink-gray-6">{{ __('Overall') }}</span>
					<span class="ml-1 text-lg font-semibold text-ink-gray-9">{{ aggregate.overall_mean }}</span>
				</div>
				<Badge v-if="aggregate.presentation_mode !== 'Statistical'" theme="orange" size="sm">
					{{ __(aggregate.presentation_mode) }}
				</Badge>
			</div>

			<!--
				Stated rather than left as an empty panel. Silence reads as a bug; a reason reads as
				a policy, and this one is a policy.
			-->
			<p v-if="aggregate.reason" class="mt-1.5 text-xs text-ink-gray-5">{{ aggregate.reason }}</p>

			<div v-if="aggregate.items?.length" class="mt-3 space-y-2">
				<div v-for="item in aggregate.items" :key="item.question_code"
					class="border-t border-outline-gray-1 pt-2 first:border-0 first:pt-0">
					<div class="text-sm text-ink-gray-8">{{ item.prompt }}</div>
					<div class="mt-1 flex flex-wrap items-center gap-x-4 text-xs text-ink-gray-6">
						<span v-if="item.mean">{{ __('Mean') }} <b>{{ item.mean }}</b></span>
						<span v-if="item.top_box_pct">{{ __('Top box') }} <b>{{ item.top_box_pct }}%</b></span>
						<!--
							A single number is uninterpretable without one: 4.1 is good or bad only
							relative to what every other course scored.
						-->
						<span v-if="item.benchmark_mean" class="text-ink-gray-5">
							{{ __('institution {0}', [item.benchmark_mean]) }}
						</span>
						<span>n = {{ item.responded_n }}</span>
					</div>
					<div v-if="item.distribution" class="mt-1.5 flex items-end gap-1">
						<div v-for="(count, point) in parsed(item.distribution)" :key="point"
							class="flex flex-col items-center">
							<div class="w-6 rounded-t bg-blue-400"
								:style="{ height: barHeight(count, item.responded_n) }" />
							<span class="mt-0.5 text-[10px] text-ink-gray-5">{{ point }}</span>
						</div>
					</div>
				</div>
			</div>

			<div v-if="aggregate.free_text?.length" class="mt-4 border-t border-outline-gray-1 pt-3">
				<div class="mb-1.5 text-sm font-medium text-ink-gray-8">{{ __('Comments') }}</div>
				<div v-for="(t, i) in aggregate.free_text" :key="i"
					class="mb-1.5 rounded bg-surface-gray-1 px-2.5 py-1.5 text-sm text-ink-gray-7">
					{{ t.text }}
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, watch } from 'vue'
import { Badge, createResource } from 'frappe-ui'

const props = defineProps({
	courseSchedule: { type: String, required: true },
})

const user = inject('$user')
const hasAretenic = computed(() => !!user?.data?.has_aretenic)

const feedback = createResource({
	url: 'aretenic.feedback_api.get_offering_feedback',
	makeParams: () => ({ course_schedule: props.courseSchedule }),
	// Someone with no access to this offering's feedback is a normal case, not an error worth a
	// toast — the panel simply stays hidden.
	onError: () => {},
})

const campaign = computed(() => feedback.data?.campaign || null)
const aggregate = computed(() => feedback.data?.aggregate || null)

const pct = computed(() => {
	const c = campaign.value
	if (!c?.invited_n) return 0
	return Math.round((100 * c.responded_n) / c.invited_n)
})

function parsed(distribution) {
	try {
		return JSON.parse(distribution)
	} catch {
		return {}
	}
}

function barHeight(count, total) {
	if (!total) return '2px'
	return `${Math.max(2, Math.round((36 * count) / total))}px`
}

watch(
	() => [hasAretenic.value, props.courseSchedule],
	([enabled, schedule]) => {
		if (enabled && schedule) feedback.reload()
	},
	{ immediate: true }
)
</script>
