<template>
	<!-- Group work, topics, peer review and teammate ratings on an activity
	     (decisions/120 §1). Edits the parent form's model in place. -->
	<section class="space-y-4">
		<div class="font-semibold">{{ __('Group Work, Topics and Peer Review') }}</div>

		<div v-if="kind === 'assignment'" class="space-y-3">
			<FormControl v-model="model.group_work" type="checkbox"
				:label="__('Group work: each group hands in one piece of work, graded once for every member')" />
		</div>
		<div v-if="groupWork" class="grid grid-cols-2 gap-5">
			<FormControl v-model="model.group_source" type="select" :label="__('Groups')" :options="sourceOptions" />
			<FormControl v-if="kind === 'assignment' && ['Random', 'Self sign-up'].includes(model.group_source)"
				v-model.number="model.group_size" type="number" min="2"
				:label="model.group_source === 'Random' ? __('Group size') : __('Most students in a group')" />
		</div>

		<div class="grid grid-cols-2 gap-5">
			<FormControl v-model="model.topic_mode" type="select" :label="__('Topics')" :options="topicOptions" />
		</div>
		<p v-if="model.topic_mode" class="text-xs text-ink-gray-5">
			{{ __('Each section lists its own topics, on the activity\'s group work page. A course template import copies them.') }}
		</p>

		<FormControl v-model="model.peer_review" type="checkbox"
			:label="__('Peer review: students review classmates\' work after the due date')" />
		<div v-if="model.peer_review" class="grid grid-cols-3 gap-5">
			<FormControl v-model.number="model.reviews_per_student" type="number" min="1" :label="__('Reviews per student')" />
			<FormControl v-model="model.review_opens" type="select" :label="__('Reviews open')" :options="opensOptions" />
			<FormControl v-model="model.review_form" type="select" :label="__('Review form')" :options="formOptions" />
		</div>
		<FormControl v-if="model.peer_review" v-model="model.review_anonymous" type="checkbox"
			:label="__('Anonymous: students do not see whose work they review, or who reviewed theirs')" />

		<template v-if="groupWork">
			<FormControl v-model="model.teammate_ratings" type="checkbox"
				:label="__('Teammate ratings: after the due date, each member rates the others\' contribution')" />
			<div v-if="model.teammate_ratings" class="grid grid-cols-2 gap-5">
				<FormControl v-model="model.ratings_shown" type="select" :label="__('Ratings shown')"
					:options="shownOptions" />
			</div>
		</template>

		<div v-if="model.peer_review || model.teammate_ratings" class="grid grid-cols-2 gap-5">
			<FormControl v-model.number="model.review_due_days" type="number" min="1"
				:label="__('Days to review and rate')" />
			<FormControl v-model.number="model.review_share" type="number" min="0" max="100"
				:label="__('Share of the grade for reviews and ratings (%)')" />
		</div>
		<p v-if="(model.peer_review || model.teammate_ratings) && Number(model.review_share) > 0"
			class="text-xs text-ink-gray-5">
			{{ __('{0}% of the grade is earned by completing the assigned reviews and ratings on time; the rest is your grade on the work.').format(model.review_share) }}
		</p>
	</section>
</template>
<script setup>
import { FormControl } from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
	model: { type: Object, required: true },
	// 'assignment' or 'oral'
	kind: { type: String, default: 'assignment' },
})

const groupWork = computed(() =>
	props.kind === 'assignment' ? !!props.model.group_work : props.model.mode === 'Conversation'
)

const sourceOptions = computed(() => [
	...(props.kind === 'oral' ? [{ label: __('The section\'s groups, else random'), value: '' }] : []),
	{ label: __('The section\'s student groups'), value: 'Section groups' },
	{ label: __('Made by hand'), value: 'By hand' },
	{ label: __('Random'), value: 'Random' },
	{ label: __('Students sign up'), value: 'Self sign-up' },
])
const topicOptions = [
	{ label: __('No topics'), value: '' },
	{ label: __('Given by the instructor'), value: 'By hand' },
	{ label: __('Drawn at random'), value: 'Random' },
	{ label: __('Students choose'), value: 'Students choose' },
]
const opensOptions = [
	{ label: __('At the due date'), value: 'At the due date' },
	{ label: __('At the cut-off'), value: 'At the cut-off' },
	{ label: __('When I open them'), value: 'By hand' },
]
const formOptions = [
	{ label: __('The activity\'s rubric'), value: 'Rubric' },
	{ label: __('Comments only'), value: 'Comments only' },
]
const shownOptions = [
	{ label: __('To the teammate, with names'), value: 'Named' },
	{ label: __('To the teammate, without names'), value: 'Anonymous' },
	{ label: __('To the instructor only'), value: 'Instructor only' },
]
</script>
