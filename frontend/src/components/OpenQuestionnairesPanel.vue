<template>
	<!--
		Optional Aretenic surface (ADR 030), and the workhorse of decisions/035 §6: students do not
		browse course pages at the end of term, so the questionnaire has to meet them where they
		already land. This is a prompt, never a gate — there is deliberately no blocking interstitial
		on grades, because coerced feedback is worse data and withholding an academic record over a
		survey is not defensible practice.
	-->
	<div v-if="hasAretenic && open.length" class="mb-6">
		<h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Your feedback') }}</h2>
		<hr class="border-outline-gray-2 mb-3" />

		<div class="space-y-2">
			<div v-for="q in open" :key="q.name"
				class="rounded border border-outline-gray-2 bg-surface-white px-3 py-2.5">
				<div class="font-medium text-ink-gray-8">
					{{ q.course || q.campaign_title }}
				</div>
				<div class="mt-0.5 text-xs text-ink-gray-5">
					<span v-if="q.estimated_minutes">
						{{ __('About {0} minutes.', [q.estimated_minutes]) }}
					</span>
					<span v-if="q.closes_on">
						{{ __('Closes {0}.', [dayjs(q.closes_on).format('D MMM')]) }}
					</span>
				</div>
				<div class="mt-1 text-xs text-ink-gray-5">
					{{ __('Your instructor sees results only after grades are submitted.') }}
				</div>
				<Button class="mt-2" size="sm" variant="subtle" :label="__('Answer')"
					@click="answer(q)" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, createResource } from 'frappe-ui'
import dayjs from 'dayjs'

const router = useRouter()
const user = inject('$user')
const hasAretenic = computed(() => !!user?.data?.has_aretenic)

const questionnaires = createResource({
	url: 'aretenic.feedback_api.open_questionnaires',
	// A student with nothing open is the normal case, not an error worth a toast.
	onError: () => {},
})

const open = computed(() => questionnaires.data || [])

function answer(q) {
	// Course questionnaires answer in place. Anything without an offering would need its own
	// surface rather than being squeezed into the course route, and students have none yet.
	if (q.course_schedule) {
		router.push({ name: 'CourseFeedback', params: { courseName: q.course_schedule } })
	}
}

watch(
	() => hasAretenic.value,
	(enabled) => {
		if (enabled) questionnaires.reload()
	},
	{ immediate: true }
)
</script>
