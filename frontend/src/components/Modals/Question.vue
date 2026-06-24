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
						:options="['Choices', 'User Input', 'Reading Report', 'Scripture Matching', 'Scripture Memorization']"
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
								:label="__('Correct Answer')"
								v-model="question[`is_correct_${n}`]"
								type="checkbox"
							/>
							<!-- Only correct options' explanations are shown to students,
							     so the field appears only once an option is marked correct. -->
							<FormControl
								v-if="question[`is_correct_${n}`]"
								:label="__('Explanation')"
								v-model="question[`explanation_${n}`]"
								:description="__('Shown to students when reviewing this correct answer.')"
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
					<div
						v-else-if="question.type == 'Reading Report'"
						class="space-y-2 border-t pt-2"
					>
						<FormControl
							:label="__('Pages Total')"
							v-model="question.pages_total"
							type="number"
							:required="true"
						/>
						<p class="text-xs text-ink-gray-5">
							{{ __('Students enter how many pages they read; the score is that fraction of the points.') }}
						</p>
					</div>
					<div
						v-else-if="question.type == 'Scripture Matching'"
						class="space-y-3 border-t pt-2"
					>
						<FormControl
							:label="__('Bible ID Override (optional)')"
							v-model="question.scripture_bible_id"
							:description="__('Leave blank to use the language default from Bible API Settings.')"
						/>
						<div class="space-y-2">
							<label class="block text-xs text-ink-gray-5">
								{{ __('References to match') }} ({{ question.matching_items.length }})
							</label>
							<div
								v-for="(item, idx) in question.matching_items"
								:key="idx"
								class="flex items-center gap-2"
							>
								<FormControl
									v-model="item.reference"
									:placeholder="__('e.g. Jn 3:16')"
									class="flex-1"
								/>
								<Button variant="ghost" @click="removeMatchingItem(idx)" :label="__('Remove')" />
							</div>
							<Button variant="subtle" @click="addMatchingItem" :label="__('Add reference')" />
							<p class="text-xs text-ink-gray-5">
								{{ __('Verse texts will be fetched from api.bible on save. Need at least 2.') }}
							</p>
						</div>
					</div>
					<div
						v-else-if="question.type == 'Scripture Memorization'"
						class="space-y-2 border-t pt-2"
					>
						<FormControl
							:label="__('Bible ID Override (optional)')"
							v-model="question.scripture_bible_id"
							:description="__('Leave blank to use the language default from Bible API Settings.')"
						/>
						<FormControl
							:label="__('Reference')"
							v-model="question.memorization_ref"
							:placeholder="__('e.g. Jn 3:16')"
							:required="true"
						/>
						<FormControl
							:label="__('Words to Hide')"
							v-model="question.hide_word_count"
							type="number"
						/>
						<FormControl
							:label="__('Minimum Word Length')"
							v-model="question.min_word_length"
							type="number"
							:description="__('Only words at least this long are eligible to be blanked. 4 skips most articles in EN/PT.')"
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
import { Button, Dialog, FormControl, TextEditor, call, createResource, toast } from 'frappe-ui'
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
	pages_total: 0,
	scripture_bible_id: '',
	matching_items: [],
	memorization_ref: '',
	hide_word_count: 3,
	min_word_length: 4,
})

const addMatchingItem = () => {
	question.matching_items.push({ reference: '' })
}
const removeMatchingItem = (idx) => {
	question.matching_items.splice(idx, 1)
}

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
				} else if (key === 'matching_items' && Array.isArray(data[key])) {
					// Strip child-row metadata; the editor only cares about the reference.
					question.matching_items = data[key].map((it) => ({
						reference: it.reference || '',
					}))
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
		// set_value can't handle child tables; matching_items is updated
		// separately via replace_matching_items below.
		const fields = { ...question }
		delete fields.matching_items
		return {
			doctype: 'Question',
			name: questionData.data?.name,
			fieldname: fields,
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
	const finishUpdate = () => {
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
	}
	questionUpdate.submit(
		{},
		{
			onSuccess() {
				// Scripture Matching: separately swap the child rows, which
				// triggers validate() server-side to re-fetch verse texts.
				if (question.type === 'Scripture Matching') {
					call(
						'seminary.seminary.doctype.question.question.replace_matching_items',
						{
							question: questionData.data?.name,
							items: JSON.stringify(question.matching_items),
						}
					)
						.then(finishUpdate)
						.catch((err) => {
							toast.error(err.messages?.[0] || err.message || err)
						})
				} else {
					finishUpdate()
				}
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
