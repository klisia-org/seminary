<template>
	<Dialog
		v-model="show"
		:options="dialogOptions"
		:disableOutsideClickToClose="true"
	>
		<template #body-content>
			<div class="question-dialog space-y-4 max-h-[70vh] overflow-y-auto">
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
					<FormControl
						v-model="question.points"
						:label="__('Points')"
						type="number"
					/>
					<FormControl
						:label="__('Type')"
						v-model="question.type"
						type="select"
						:options="['Choices', 'User Input']"
						class="pb-2"
						:required="true"
					/>
					<div v-if="question.type == 'Choices'" class="divide-y border-t">
						<div v-for="n in 4" class="space-y-4 py-2">
							<FormControl
								:label="__('Option') + ' ' + n"
								v-model="question[`option_${n}`]"
								:required="n <= 2 ? true : false"
							/>
							<FormControl
								:label="__('Explanation')"
								v-model="question[`explanation_${n}`]"
							/>
							<FormControl
								:label="__('Correct Answer')"
								v-model="question[`is_correct_${n}`]"
								type="checkbox"
							/>
						</div>
					</div>
					<div
						v-else-if="question.type == 'User Input'"
						v-for="n in 4"
						class="space-y-2"
					>
						<FormControl
							:label="__('Possibility') + ' ' + n"
							v-model="question[`possibility_${n}`]"
							:required="n == 1 ? true : false"
						/>
					</div>
				</div>
				<div v-else-if="questionType == 'existing'" class="space-y-2">
					<Link
						v-model="existingQuestion.question"
						:label="__('Select a question')"
						doctype="Question"
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
import { computed, reactive, ref, watch } from 'vue'
import Link from '@/components/Controls/Link.vue'

const show = defineModel()
const quiz = defineModel('quiz')

const defaultExistingQuestion = () => ({
	question: '',
	points: 0,
})

const defaultQuestionState = () => ({
	question: '',
	type: 'Choices',
	points: 0,
	option_1: '',
	option_2: '',
	option_3: '',
	option_4: '',
	explanation_1: '',
	explanation_2: '',
	explanation_3: '',
	explanation_4: '',
	is_correct_1: false,
	is_correct_2: false,
	is_correct_3: false,
	is_correct_4: false,
	possibility_1: '',
	possibility_2: '',
	possibility_3: '',
	possibility_4: '',
})

const questionType = ref('new')
const editMode = ref(false)

const existingQuestion = reactive(defaultExistingQuestion())
const question = reactive(defaultQuestionState())

const resetQuestionState = () => {
	Object.assign(question, defaultQuestionState())
}

const resetExistingQuestion = () => {
	Object.assign(existingQuestion, defaultExistingQuestion())
}

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
	auto: false,
	makeParams() {
		return {
			doctype: 'Question',
			name: props.questionDetail.question,
		}
	},
	onSuccess(data) {
		editMode.value = true
		questionType.value = 'new'
		resetQuestionState()
		Object.keys(question).forEach((key) => {
			if (Object.hasOwn(data, key)) {
				if (key.startsWith('is_correct_')) {
					question[key] = Boolean(data[key])
				} else if (data[key] !== undefined && data[key] !== null) {
					question[key] = data[key]
				}
			}
		})
		question.points = props.questionDetail.points ?? data.points ?? 0
	},
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
	resetQuestionState()
	resetExistingQuestion()
}

watch(show, (value) => {
	if (value) {
		initializeState()
	} else {
		resetForms()
		editMode.value = false
		questionType.value = 'new'
	}
})

const questionRow = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Quiz Question',
				parent: quiz.value.data.name,
				parentfield: 'questions',
				parenttype: 'Quiz',
				...values,
			},
		}
	},
})

const questionCreation = createResource({
	url: 'frappe.client.insert',
	makeParams() {
		return {
			doc: {
				doctype: 'Question',
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
	if (questionType.value === 'existing') {
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

const addQuestionRow = (questionValues, close) => {
	questionRow.submit(
		{
			...questionValues,
		},
		{
			onSuccess() {
				show.value = false
				toast.success(__('Question added successfully'))
				quiz.value.reload()
				resetForms()
				close()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
				close()
			},
		}
	)
}

const questionUpdate = createResource({
	url: 'frappe.client.set_value',
	auto: false,
	makeParams() {
		return {
			doctype: 'Question',
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
	makeParams() {
		return {
			doctype: 'Quiz Question',
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
							quiz.value.reload()
							resetForms()
							close()
						},
						onError(err) {
							toast.error(err.messages?.[0] || err)
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

const handleCancel = (close) => {
	show.value = false
	resetForms()
	editMode.value = false
	questionType.value = 'new'
	close?.()
}

const dialogOptions = computed(() => ({
	title: __(props.title),
	size: 'xl',
	actions: [
		{
			label: __('Submit'),
			variant: 'solid',
			onClick: (close) => submitQuestion(close),
		},
		{
			label: __('Cancel'),
			variant: 'text',
			onClick: (close) => handleCancel(close),
		},
	],
}))
</script>
<style>
.question-dialog input[type='radio'],
.question-dialog input[type='checkbox'] {
	accent-color: theme('colors.gray.900');
	width: 0.75rem;
	height: 0.75rem;
	border-radius: theme('borderRadius.full');
}

.question-dialog input[type='radio']:focus,
.question-dialog input[type='radio']:focus-visible,
.question-dialog input[type='checkbox']:focus,
.question-dialog input[type='checkbox']:focus-visible {
	outline: 2px solid theme('colors.gray.400');
	outline-offset: 3px;
	box-shadow: none;
}

.question-dialog input[type='number']::-webkit-inner-spin-button,
.question-dialog input[type='number']::-webkit-outer-spin-button {
	-webkit-appearance: none;
	margin: 0;
}

.question-dialog input[type='number'] {
	appearance: textfield;
	-moz-appearance: textfield;
}
</style>
