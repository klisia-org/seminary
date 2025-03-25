<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<div
					v-if="!editMode"
					class="flex items-center text-xs text-ink-gray-7 space-x-5"
				>
					<div class="flex items-center space-x-2">
						<input
							type="radio"
							id="existing"
							value="existing"
							v-model="questionType"
							class="w-3 h-3 cursor-pointer"
						/>
						<label for="existing" class="cursor-pointer">
							{{ __('Add an existing question') }}
						</label>
					</div>

					<div class="flex items-center space-x-2">
						<input
							type="radio"
							id="new"
							value="new"
							v-model="questionType"
							class="w-3 h-3 cursor-pointer"
						/>
						<label for="new" class="cursor-pointer">
							{{ __('Create a new question') }}
						</label>
					</div>
				</div>
				<div v-if="questionType == 'new' || editMode" class="space-y-2">
					<div>
						<label class="block text-xs text-ink-gray-5 mb-1">
							{{ __('Question') }}
						</label>
						<TextEditor
							:content="question.question"
							@change="(val) => (question.question = val)"
							:editable="true"
							:fixedMenu="true"                    
							editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
						/>
					</div>
                    <div>
						<label class="block text-xs text-ink-gray-5 mb-1">
							{{ __('Explanation for this Question') }}
						</label>
						<TextEditor
							:content="question.explanation"
							@change="(val) => (question.explanation = val)"
							:editable="true"
							:fixedMenu="true"
							editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
						/>
					</div>
					<FormControl
						v-model="question.points"
						:label="__('Points')"
						type="number"
					/>
					
				
				</div>
				<div v-else-if="questionType == 'existing'" class="space-y-2">
					<Link
						v-model="existingQuestion.question"
						:label="__('Select a question')"
						doctype="Open Question"
					/>
					<FormControl
						v-model="existingQuestion.points"
						:label="__('Points')"
						type="number"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, FormControl, TextEditor, createResource } from 'frappe-ui'
import { computed, watch, reactive, ref } from 'vue'
import Link from '@/components/Controls/Link.vue'
import { showToast } from '@/utils'

const show = defineModel()
const exam = defineModel('exam')
const questionType = ref(null)
const editMode = ref(false)

const existingQuestion = reactive({
	question: '',
	points: 0,
})
const question = reactive({
	question: '',
	points: 0,
})



const props = defineProps({
	title: {
		type: String,
		default: __('Add a new question'),
	},
	questionDetail: {
		type: [Object, null],
		required: true,
	},
})

const questionData = createResource({
	url: 'frappe.client.get',
	makeParams() {
		return {
			doctype: 'Open Question',
			name: props.questionDetail.question,
		}
	},
	auto: false,
	onSuccess(data) {
		
		editMode.value = true
	
		question.points = props.questionDetail.points
	},
})

watch(show, () => {
	if (show.value) {
		editMode.value = false
		if (props.questionDetail.question) questionData.fetch()
		else {
			;(question.question = ''), (question.points = 0)
			
			existingQuestion.question = ''
			existingQuestion.points = 0
			questionType.value = null
			
		}

		if (props.questionDetail.points) question.points = props.questionDetail.points
	}
})

const questionRow = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Exam Question',
				parent: exam.value.data.name,
				parentfield: 'questions',
				parenttype: 'Exam Activity',
                points: values.points,
				...values,
			},
		}
	},
})

const questionCreation = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Open Question',
				...question,
			},
		}
	},
})

const submitQuestion = (close) => {
	if (props.questionDetail?.question) updateQuestion(close)
	else addQuestion(close)
}

const addQuestion = (close) => {
	if (questionType.value == 'existing') {
		addQuestionRow(
			{
				question: existingQuestion.question,
				points: existingQuestion.points,
			},
			close
		)
	} else {
		questionCreation.submit(
			{},
			{
				onSuccess(data) {
					addQuestionRow(
						{
							question: data.name,
							points: question.points,
						},
						close
					)
				},
				onError(err) {
					showToast(__('Error'), __(err.messages?.[0] || err), 'x')
				},
			}
		)
	}
}

const addQuestionRow = (question, close) => {
    console.log("Submitting Question Row:", question); // Debug the question object

    questionRow.submit(
        {
            ...question,
        },
        {
            onSuccess() {
                show.value = false;
                showToast(__('Success'), __('Question added successfully'), 'check');
                exam.value.reload(); // Reload the exam to reflect the changes
                close();
            },
            onError(err) {
                showToast(__('Error'), __(err.messages?.[0] || err), 'x');
                close();
            },
        }
    );
};

const questionUpdate = createResource({
	url: 'frappe.client.set_value',
	auto: false,
	makeParams(values) {
		return {
			doctype: 'Open Question',
			name: questionData.data?.name,
			fieldname: {
				...question,
			},
		}
	},
})

const pointsUpdate = createResource({
	url: 'frappe.client.set_value',
	auto: false,
	makeParams(values) {
		return {
			doctype: 'Exam Question',
			name: props.questionDetail.name,
			fieldname: {
				points: question.points,
			},
		}
	},
})

const updateQuestion = (close) => {
	questionUpdate.submit(
		{},
		{
			onSuccess() {
				pointsUpdate.submit(
					{},
					{
						onSuccess() {
							show.value = false
							showToast(
								__('Success'),
								__('Question updated successfully'),
								'check'
							)
							exam.value.reload()
							close()
						},
					}
				)
			},
			onError(err) {
				showToast(__('Error'), __(err.messages?.[0] || err), 'x')
			},
		}
	)
}

const dialogOptions = computed(() => {
	return {
		title: __(props.title),
		size: 'xl',
		actions: [
			{
				label: __('Submit'),
				variant: 'solid',
				onClick: (close) => {
					submitQuestion(close)
				},
			},
		],
	}
})
</script>
<style>
input[type='radio']:checked {
	background-color: theme('colors.gray.900') !important;
	border-color: theme('colors.gray.900') !important;
	--tw-ring-color: theme('colors.gray.900') !important;
}
</style>
