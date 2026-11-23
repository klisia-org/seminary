<template>
	<Dialog v-model="show" :options="dialogOptions" :disableOutsideClickToClose="true">
		<template #body-content>
			<div class="open-question-dialog space-y-4 max-h-[70vh] overflow-y-auto">
				<div v-if="!editMode" class="flex items-center text-xs text-ink-gray-7 space-x-5">
					<div class="flex items-center space-x-2">
						<input type="radio" id="existing" value="existing" v-model="questionType"
							class="w-3 h-3 cursor-pointer" />
						<label for="existing" class="cursor-pointer">
							{{ __('Add an existing question') }}
						</label>
					</div>

					<div class="flex items-center space-x-2">
						<input type="radio" id="new" value="new" v-model="questionType"
							class="w-3 h-3 cursor-pointer" />
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
						<RichTextEditor :teleport="false" v-if="question.question !== undefined"
							:key="'question-' + (question.name || 'new')" :id="'question-' + (question.name || 'new')"
							:content="question.question || ''" @change="(val) => (question.question = val)"
							:editable="true" />
					</div>
					<div>
						<div class="block text-xs text-ink-gray-5 mb-1">
							{{ __('Explanation for this Question') }}
						</div>
						<RichTextEditor :teleport="false" v-if="question.question !== undefined" :key="'expl' + (question.name || 'new')"
							:id="'explanation-' + (question.name || 'new')" :content="question.explanation || ''"
							@change="(val) => (question.explanation = val)" :editable="true" />
					</div>
					<FormControl v-model="question.points" :label="__('Points')" type="number" />
					<FormControl v-model="oralSettings.response_mode" type="select" :label="__('How is it answered?')"
						:options="responseModes" />
					<div v-if="oralSettings.response_mode !== 'Written'" class="grid grid-cols-3 gap-3">
						<FormControl v-model="oralSettings.prepare_s" type="number" :label="__('Reading time (seconds)')" />
						<FormControl v-model="oralSettings.max_answer_s" type="number" :label="__('Longest answer (seconds)')" />
						<FormControl v-model="oralSettings.takes" type="number" :label="__('Takes')" />
					</div>


				</div>
				<div v-else-if="questionType == 'existing'" class="space-y-2">
					<Link v-model="existingQuestion.question" :label="__('Select a question')"
						doctype="Open Question" />
					<FormControl v-model="existingQuestion.points" :label="__('Points')" type="number" />
					<FormControl v-model="oralSettings.response_mode" type="select" :label="__('How is it answered?')"
						:options="responseModes" />
					<div v-if="oralSettings.response_mode !== 'Written'" class="grid grid-cols-3 gap-3">
						<FormControl v-model="oralSettings.prepare_s" type="number" :label="__('Reading time (seconds)')" />
						<FormControl v-model="oralSettings.max_answer_s" type="number" :label="__('Longest answer (seconds)')" />
						<FormControl v-model="oralSettings.takes" type="number" :label="__('Takes')" />
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, FormControl, createResource, toast } from 'frappe-ui'
import { computed, watch, reactive, ref } from 'vue'
import Link from '@/components/Controls/Link.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'


const show = defineModel()
const exam = defineModel('exam')
const questionType = ref('new')
const editMode = ref(false)

const existingQuestion = reactive({
	question: '',
	points: 0,
})
const question = reactive({
	name: '',
	question: '',
	explanation: '',
	points: 0,
})
// Oral answers (decisions/100a) are a setting of the question's row in this
// exam, not of the bank question, so they live apart from `question`.
const ORAL_DEFAULTS = { response_mode: 'Written', prepare_s: 30, max_answer_s: 180, takes: 1 }
const oralSettings = reactive({ ...ORAL_DEFAULTS })
const responseModes = [
	{ label: __('Written'), value: 'Written' },
	{ label: __('Aloud'), value: 'Oral' },
	{ label: __('The student chooses'), value: 'Student chooses' },
]
const oralFields = () => ({
	response_mode: oralSettings.response_mode,
	prepare_s: Number(oralSettings.prepare_s) || 0,
	max_answer_s: Number(oralSettings.max_answer_s) || 180,
	takes: Number(oralSettings.takes) || 1,
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
		question.name = data.name || ''
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
	Object.keys(ORAL_DEFAULTS).forEach((k) => {
		oralSettings[k] = props.questionDetail[k] ?? ORAL_DEFAULTS[k]
	})
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
				...oralFields(),
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
				...oralFields(),
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
