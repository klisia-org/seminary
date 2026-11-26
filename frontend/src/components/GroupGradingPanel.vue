<template>
	<!-- Group work beside the grade (decisions/120 §4, §6, §7). -->
	<div v-if="d && (d.group || d.review_share || d.reviews_received.length || d.topic)" class="space-y-3 border-t pt-4 text-sm">
		<div v-if="d.topic" class="text-ink-gray-7"><span class="font-medium">{{ __('Topic') }}:</span> {{ d.topic }}</div>

		<div v-if="d.group" class="space-y-2">
			<div class="font-medium text-ink-gray-8">{{ d.group.group_name }}</div>
			<p class="text-xs text-ink-gray-5">
				{{ __('Grading this work grades every member who is not graded separately.') }}
			</p>
			<div v-for="mbr in d.group.members" :key="mbr.student" class="text-ink-gray-7">
				<div class="flex items-center justify-between">
					<span>{{ mbr.name }}</span>
					<span class="text-xs">
						<template v-if="mbr.submission?.grade_override">{{ __('Separate') }} · </template>
						{{ mbr.submission?.grade ?? '–' }}
					</span>
				</div>
				<div v-if="d.group.ratings[mbr.student]" class="text-xs text-ink-gray-5">
					{{ __('Rated {0} of 5 by teammates (spread {1})').format(d.group.ratings[mbr.student].average, d.group.ratings[mbr.student].spread) }}
				</div>
				<div v-for="(c, i) in d.group.ratings[mbr.student]?.comments || []" :key="i" class="text-xs text-ink-gray-6">
					“{{ c.comment }}” <span class="text-ink-gray-5">· {{ c.rater }}</span>
				</div>
			</div>
			<FormControl v-if="submissionDoctype === 'Assignment Submission'" type="checkbox"
				:modelValue="!!d.grade_override" :label="__('Grade this member separately')"
				@update:modelValue="setSeparate" />
		</div>

		<div v-if="d.review_share" class="space-y-1">
			<div class="text-ink-gray-7">
				{{ __('Reviews and ratings: {0}% done on time, counting for {1}% of the grade.').format(d.review_credit ?? '–', d.review_share) }}
			</div>
			<div class="flex items-end gap-2">
				<FormControl v-model="credit" type="number" min="0" max="100" class="w-28" :label="__('Set the review part (%)')" />
				<Button size="sm" @click="saveCredit(credit)">{{ __('Set') }}</Button>
				<Button v-if="d.review_credit_override" size="sm" variant="ghost" @click="saveCredit(null)">
					{{ __('Use the computed part') }}
				</Button>
			</div>
		</div>

		<div v-if="d.reviews_received.length" class="space-y-1">
			<div class="font-medium text-ink-gray-8">{{ __('Peer reviews of this work') }}</div>
			<div v-for="r in d.reviews_received" :key="r.name" class="flex items-center justify-between text-xs">
				<span>{{ r.reviewer_name }}<template v-if="r.hidden"> · {{ __('hidden') }}</template></span>
				<router-link :to="{ name: 'PeerReview', params: { courseName: course, review: r.name } }" class="text-ink-blue-3 underline">
					{{ __('Read') }}
				</router-link>
			</div>
		</div>
	</div>
</template>
<script setup>
import { Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
	submissionDoctype: { type: String, required: true },
	submission: { type: String, required: true },
	course: { type: String, default: '' },
})
const emit = defineEmits(['changed'])

const res = createResource({
	url: 'seminary.seminary.peer_reviews.get_grading',
	makeParams: () => ({ submission_doctype: props.submissionDoctype, submission: props.submission }),
	auto: true,
})
const d = computed(() => res.data)
const credit = ref(null)
watch(d, (v) => {
	credit.value = v?.review_credit_override ? v.stored_credit : null
})

const setSeparate = async (on) => {
	try {
		await call('seminary.seminary.peer_reviews.set_separate_grade', { submission: props.submission, separate: on ? 1 : 0 })
		await res.reload()
		emit('changed')
	} catch (e) {
		toast.error(e.messages?.[0] || __('That did not work.'))
	}
}
const saveCredit = async (value) => {
	try {
		await call('seminary.seminary.peer_reviews.set_review_credit', {
			submission_doctype: props.submissionDoctype,
			submission: props.submission,
			credit_value: value === null || value === '' ? null : value,
		})
		await res.reload()
		emit('changed')
	} catch (e) {
		toast.error(e.messages?.[0] || __('That did not work.'))
	}
}
defineExpose({ reload: () => res.reload() })
</script>
