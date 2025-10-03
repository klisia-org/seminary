<template>
	<Dialog
		v-model="show"
		:options="dialogOptions"
		:disableOutsideClickToClose="true"
	>
		<template #body-content>
			<div class="open-question-dialog space-y-4 max-h-[70vh] overflow-y-auto">
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
import { Dialog, FormControl, TextEditor, createResource, toast } from 'frappe-ui'
import { computed, watch, reactive, ref } from 'vue'
import Link from '@/components/Controls/Link.vue'


const show = defineModel()
const exam = defineModel('exam')
const questionType = ref('new')
const editMode = ref(false)

const existingQuestion = reactive({
	question: '',
	points: 0,
})
const question = reactive({
	question: '',
	explanation: '',
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
		question.question = data.question || ''
		question.explanation = data.explanation || ''
		question.points = props.questionDetail.points ?? data.points ?? 0
	},
})

watch(show, (value) => {
	if (value) {
		initializeState()
	} else {
		resetForms()
		editMode.value = false
		questionType.value = 'new'
	}
})

	const initializeState = () => {
		if (props.questionDetail.question) {
			editMode.value = true
			questionType.value = 'new'
			question.points = props.questionDetail.points ?? 0
			questionData.fetch()
		} else {
			editMode.value = false
			resetForms()
			questionType.value = 'new'
		}
	}

	const resetForms = () => {
		question.question = ''
		question.explanation = ''
		question.points = 0
		existingQuestion.question = ''
		existingQuestion.points = 0
	}

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
					toast.error(err.messages?.[0] || err)
				},
			}
		)
	}
}

const addQuestionRow = (question, close) => {
	questionRow.submit(
        {
            ...question,
        },
        {
            onSuccess() {
                show.value = false;
				toast.success(__('Question added successfully'))
                exam.value.reload(); // Reload the exam to reflect the changes
                close();
            },
            onError(err) {
                toast.error(err.messages?.[0] || err)
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
							toast.success(__('Question updated successfully'))
							exam.value.reload()
							close()
						},
					}
				)
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
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
			{
				label: __('Cancel'),
				variant: 'text',
				onClick: (close) => handleCancel(close),
			},
		],
	}
})

const handleCancel = (close) => {
	show.value = false
	close?.()
	resetForms()
	editMode.value = false
	questionType.value = 'new'
}
</script>
<style>
.open-question-dialog input[type='radio'],
.open-question-dialog input[type='checkbox'] {
	accent-color: theme('colors.gray.900');
	width: 0.75rem;
	height: 0.75rem;
	border-radius: theme('borderRadius.full');
}

.open-question-dialog input[type='radio']:focus,
.open-question-dialog input[type='radio']:focus-visible,
.open-question-dialog input[type='checkbox']:focus,
.open-question-dialog input[type='checkbox']:focus-visible {
	outline: 2px solid theme('colors.gray.400');
	outline-offset: 3px;
	box-shadow: none;
}

.open-question-dialog input[type='number']::-webkit-inner-spin-button,
.open-question-dialog input[type='number']::-webkit-outer-spin-button {
	-webkit-appearance: none;
	margin: 0;
}

.open-question-dialog input[type='number'] {
	appearance: textfield;
	-moz-appearance: textfield;
}
</style>
