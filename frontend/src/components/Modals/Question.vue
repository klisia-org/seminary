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
						<div class="block text-xs text-ink-gray-5 mb-1">
							{{ __('Question') }}
						</div>
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
						<div v-for="(choice, n) in question.choices" :key="n" class="space-y-4 py-2">
							<div class="flex items-end gap-2">
								<FormControl
									:label="__('Option') + ' ' + (n + 1)"
									v-model="choice.option"
									:required="n < 2"
									class="flex-1"
								/>
								<Button
									v-if="question.choices.length > 2"
									variant="ghost"
									@click="question.choices.splice(n, 1)"
									:label="__('Remove')"
									:aria-label="__('Remove option {0}').format(n + 1)"
								/>
							</div>
							<FormControl
								:label="__('Correct Answer')"
								v-model="choice.is_correct"
								type="checkbox"
							/>
							<!-- Only correct options' explanations are shown to students,
							     so the field appears only once an option is marked correct. -->
							<FormControl
								v-if="choice.is_correct"
								:label="__('Explanation')"
								v-model="choice.explanation"
								:description="__('Shown to students when reviewing this correct answer.')"
							/>
						</div>
						<div class="pt-2">
							<Button variant="subtle" @click="question.choices.push(newChoice())" :label="__('Add option')" />
						</div>
					</div>
					<div v-else-if="question.type == 'User Input'" class="space-y-2">
						<div v-for="(row, n) in question.accepted_answers" :key="n" class="flex items-end gap-2">
							<FormControl
								:label="__('Possibility') + ' ' + (n + 1)"
								v-model="row.answer"
								:required="n == 0"
								class="flex-1"
							/>
							<Button
								v-if="question.accepted_answers.length > 1"
								variant="ghost"
								@click="question.accepted_answers.splice(n, 1)"
								:label="__('Remove')"
								:aria-label="__('Remove possibility {0}').format(n + 1)"
							/>
						</div>
						<Button variant="subtle" @click="question.accepted_answers.push({ answer: '' })" :label="__('Add possibility')" />
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
						<div class="space-y-2" role="group" :aria-labelledby="`${uid}-references`">
							<div :id="`${uid}-references`" class="block text-xs text-ink-gray-5">
								{{ __('References to match') }} ({{ question.matching_items.length }})
							</div>
							<div
								v-for="(item, idx) in question.matching_items"
								:key="idx"
								class="flex items-center gap-2"
							>
								<FormControl
									v-model="item.reference"
									:placeholder="__('e.g. Jn 3:16')"
									:aria-label="__('Reference {0}').format(idx + 1)"
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
import { Button, Dialog, FormControl, TextEditor, createResource, toast } from 'frappe-ui'
import { computed, reactive, ref, watch, useId } from 'vue'
import Link from '@/components/Controls/Link.vue'

const show = defineModel()
const quiz = defineModel('quiz')
const uid = useId()

const defaultExistingQuestion = () => ({
	question: '',
	points: 0,
})

const newChoice = () => ({ option: '', is_correct: false, explanation: '' })

const defaultQuestionState = () => ({
	question: '',
	type: 'Choices',
	points: 0,
	choices: [newChoice(), newChoice()],
	accepted_answers: [{ answer: '' }],
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
				if (key === 'choices' && Array.isArray(data[key])) {
					const rows = data[key].map((c) => ({
						option: c.option || '',
						is_correct: Boolean(c.is_correct),
						explanation: c.explanation || '',
					}))
					while (rows.length < 2) rows.push(newChoice())
					question.choices = rows
				} else if (key === 'accepted_answers' && Array.isArray(data[key])) {
					const rows = data[key].map((a) => ({ answer: a.answer || '' }))
					question.accepted_answers = rows.length ? rows : [{ answer: '' }]
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
				...questionValues(),
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

// Blank option and possibility rows are left out; the server keeps the order.
const questionValues = () => {
	const values = { ...question }
	delete values.points
	values.choices = question.choices
		.filter((c) => (c.option || '').trim())
		.map((c) => ({ ...c, is_correct: c.is_correct ? 1 : 0 }))
	values.accepted_answers = question.accepted_answers.filter((a) => (a.answer || '').trim())
	return values
}

// One save for the fields and every table: set_value can't update child tables.
const questionUpdate = createResource({
	url: 'seminary.seminary.doctype.question.question.save_question',
	auto: false,
	makeParams() {
		return {
			name: questionData.data?.name,
			values: JSON.stringify(questionValues()),
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
				finishUpdate()
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
