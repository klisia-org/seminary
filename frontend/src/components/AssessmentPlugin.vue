<template>
	<Dialog v-model="show" :options="{
		size: 'xl',
	}">
		<template #body>
			<button style="opacity: 0; position: absolute;">Fallback Focus</button>
			<div class="p-5 space-y-4">
				<div v-if="type == 'quiz'" class="text-lg font-semibold">
					{{ __('Add a quiz to your lesson') }}
				</div>
				<div v-else-if="type == 'exam'" class="text-lg font-semibold">
					{{ __('Add an exam to your lesson') }}
				</div>
				<div v-else-if="type == 'discussionactivity'" class="text-lg font-semibold">
					{{ __('Add a discussion activity to your lesson') }}
				</div>
				<div v-else class="text-lg font-semibold">
					{{ __('Add an assignment to your lesson') }}
				</div>
				<div>
					<Link v-if="type == 'quiz'" v-model="quiz" doctype="Quiz" :label="__('Select a quiz')"
						:filters="course ? { course: course } : {}" :onCreate="(value, close) => redirectToForm(close)" />
					<Link v-else-if="type == 'exam'" v-model="exam" doctype="Exam Activity"
						:filters="course ? { course: course } : {}" :label="__('Select an exam')"
						:onCreate="(value, close) => redirectToForm(close)" />
					<Link v-else-if="type == 'discussionactivity'" v-model="discussionactivity"
						doctype="Discussion Activity" :label="__('Select a discussion activity')"
						:filters="course ? { course: course } : {}" :onCreate="(value, close) => redirectToForm(close)" />
					<Link v-else v-model="assignment" doctype="Assignment Activity" :label="__('Select an assignment')"
						:filters="course ? { course: course } : {}" :onCreate="(value, close) => redirectToForm(close)" />
				</div>
				<div class="flex justify-end space-x-2">
					<Button variant="solid" @click="addAssessment()">
						{{ __('Save') }}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, Button } from 'frappe-ui'
import { onMounted, ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import Link from '@/components/Controls/Link.vue'
import { examStore } from '@/stores/exam'

const router = useRouter()

// Maps the plugin type to the activity form route and the editor block type
// LessonForm should insert when the user returns from creating the activity.
const FORM_BY_TYPE = {
	quiz: { name: 'QuizForm', param: 'quizID', insertType: 'quiz' },
	exam: { name: 'ExamForm', param: 'examID', insertType: 'exam' },
	assignment: { name: 'AssignmentForm', param: 'assignmentID', insertType: 'assignment' },
	discussionactivity: { name: 'DiscussionActivityForm', param: 'discussionID', insertType: 'discussionActivity' },
}

const show = ref(false)
const quiz = ref(null)
const assignment = ref(null)
const exam = ref(null)
const discussionactivity = ref(null)

const props = defineProps({
	type: {
		type: String,
		required: true,
	},
	course: { type: String, default: null },
	onAddition: {
		type: Function,
		required: true,
	},
})


onMounted(async () => {
	console.log('AssessmentPlugin mounted with type:', props.type, 'and course:', props.course) // Debugging
	await nextTick()
	show.value = true
})

const addAssessment = () => {
	if (props.type == 'quiz') {
		props.onAddition(quiz.value)
	} else if (props.type == 'exam') {
		props.onAddition(exam.value)
	} else if (props.type == 'discussionactivity') {
		props.onAddition(discussionactivity.value)
	} else {
		props.onAddition(assignment.value)
	}
	show.value = false
}

// Navigate (same tab) to the activity form to create a new activity. We pre-fill
// the course and stash a return context so the form can offer a "Back to lesson"
// button that splices the created activity straight back into the lesson.
// LessonForm's route-leave guard saves the lesson first, so nothing is lost.
const redirectToForm = (close) => {
	const target = FORM_BY_TYPE[props.type] || FORM_BY_TYPE.assignment
	examStore.setPrefillData({ title: '', course: props.course || '' })
	examStore.setReturnContext({
		route: {
			name: router.currentRoute.value.name,
			params: { ...router.currentRoute.value.params },
		},
		insertType: target.insertType,
	})
	// Close this dialog (and the Link popover) first; otherwise its teleported
	// overlay lingers over the destination page and the redirect looks like a
	// no-op until the user dismisses the modal.
	close?.()
	show.value = false
	router.push({ name: target.name, params: { [target.param]: 'new' } })
}
</script>