<template>
	<Dialog
		v-model="show"
		:options="{
			size: 'xl',
		}"
	>
		<template #body>
			<div class="p-5 space-y-4">
				<div v-if="type == 'quiz'" class="text-lg font-semibold">
					{{ __('Add a quiz to your lesson') }}
				</div>
				<div v-else-if="type == 'exam'" class="text-lg font-semibold">
					{{ __('Add an exam to your lesson') }}
				</div>
				<div v-else class="text-lg font-semibold">
					{{ __('Add an assignment to your lesson') }}
				</div>
				<div>
					<Link
						v-if="type == 'quiz'"
						v-model="quiz"
						doctype="Quiz"
						:label="__('Select a quiz')"
						:onCreate="(value, close) => redirectToForm()"
					/>
					<Link
						v-else-if="type == 'exam'"
						v-model="exam"
						doctype="Exam Activity"
						:label="__('Select an exam')"
						:onCreate="(value, close) => redirectToForm()"
					/>
					<Link
						v-else
						v-model="assignment"
						doctype="Assignment Activity"
						:label="__('Select an assignment')"
						:onCreate="(value, close) => redirectToForm()"
					/>
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
import Link from '@/components/Controls/Link.vue'

const show = ref(false)
const quiz = ref(null)
const assignment = ref(null)
const exam = ref(null)

const props = defineProps({
	type: {
		type: String,
		required: true,
	},
	onAddition: {
		type: Function,
		required: true,
	},
})

onMounted(async () => {
	await nextTick()
	show.value = true
})

const addAssessment = () => {
	props.onAddition(props.type == 'quiz' ? quiz.value : assignment.value)
	show.value = false
}

const redirectToForm = () => {
	if (props.type == 'quiz') window.open('/seminary/quizzes/new', '_blank')
	else if (props.type == 'exam') window.open('/seminary/exams/new', '_blank')
	else window.open('/seminary/assignments/new', '_blank')
}
</script>
