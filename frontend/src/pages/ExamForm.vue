<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<div class="space-x-2">
			<router-link
				v-if="examDetails.data?.name"
				:to="{
					name: 'ExamPage',
					params: {
						examID: examDetails.data.name,
					},
				}"
			>
				<Button>
					{{ __('Open') }}
				</Button>
			</router-link>
			<router-link
				v-if="examDetails.data?.name"
				:to="{
					name: 'ExamSubmissionList',
					params: {
						examID: examDetails.data.name,
					},
				}"
			>
				<Button>
					{{ __('Submission List') }}
				</Button>
			</router-link>
			<Button variant="solid" @click="submitExam()">
				{{ __('Save') }}
			</Button>
		</div>
	</header>
	<div class="w-3/4 mx-auto py-5">
		<!-- Details -->
		<div class="mb-8">
			<div class="font-semibold mb-4">
				{{ __('Details') }}
			</div>
			<FormControl
				v-model="exam.title"
				:label="
					examDetails.data?.name
						? __('Title')
						: __('Enter a title and save the exam to proceed')
				"
				:required="true"
			/>
			<br />
			<Link
				v-model="exam.course"
				doctype="Course"
				:label="__('Course where this exam will be used - you may reuse this exam in other scheduled courses')"
				:placeholder="__('Select a course')"
				:required="true"
			
			/>
			<div v-if="examDetails.data?.name">
				<div class="grid grid-cols-2 gap-5 mt-4 mb-8">
					
					<FormControl
						type="number"
						v-model="exam.duration"
						:label="__('Duration (in minutes)')"
					/>
					<FormControl
						v-model="exam.total_points"
						:label="__('Total Points')"
						disabled
					/>
					
				</div>

				<!-- Settings -->
				<div class="mb-8">
					<div class="font-semibold mb-4">
						{{ __('Settings') }}
					</div>
					
					
						<FormControl
							v-model="exam.qbyquestion"
							type="checkbox"
							:label="__('Force student to answer a question before moving on? Each question will have its own page and a next button')"
						/>
					
				</div>

				<div class="mb-8">
					<div class="font-semibold mb-4">
						{{ __('Shuffle Settings') }}
					</div>
					<div class="grid grid-cols-3">
						<FormControl
							v-model="exam.shuffle_questions"
							type="checkbox"
							:label="__('Shuffle Questions')"
						/>
						<FormControl
							v-if="exam.shuffle_questions"
							v-model="exam.limit_questions_to"
							:label="__('Limit Questions To (on shuffle)')"
						/>
					</div>
				</div>

				<!-- Questions -->
				<div>
					<div class="flex items-center justify-between mb-4">
						<div class="font-semibold">
							{{ __('Questions') }}
						</div>
						<Button @click="openOpenQuestionModal()">
							<template #prefix>
								<Plus class="w-4 h-4" />
							</template>
							{{ __('New Question') }}
						</Button>
					</div>
					<ListView
						:columns="questionColumns"
						:rows="exam.questions"
						row-key="name"
						:options="{
							showTooltip: false,
						}"
					>
						<ListHeader
							class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
						>
							<ListHeaderItem :item="item" v-for="item in questionColumns" />
						</ListHeader>
						<ListRows>
							<ListRow
								:row="row"
								v-slot="{ idx, column, item }"
								v-for="row in exam.questions"
								@click="openOpenQuestionModal(row)"
								class="cursor-pointer"
							>
								<ListRowItem :item="item">
									<div
										v-if="column.key == 'question_detail'"
										class="text-xs truncate h-4"
										v-html="item"
									></div>
									<div v-else class="text-xs">
										{{ item }}
									</div>
								</ListRowItem>
							</ListRow>
						</ListRows>
						<ListSelectBanner>
							<template #actions="{ unselectAll, selections }">
								<div class="flex gap-2">
									<Button
										variant="ghost"
										@click="deleteQuestions(selections, unselectAll)"
									>
										<Trash2 class="h-4 w-4 stroke-1.5" />
									</Button>
								</div>
							</template>
						</ListSelectBanner>
					</ListView>
				</div>
			</div>
		</div>
	</div>
	<OpenQuestion
		v-model="showOpenQuestionModal"
		:questionDetail="currentQuestion"
		v-model:exam="examDetails"
		:title="
			currentQuestion.question
				? __('Edit the question')
				: __('Add a new question')
		"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	createResource,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
	ListSelectBanner,
	Button,
} from 'frappe-ui'
import {
	computed,
	reactive,
	ref,
	onMounted,
	inject,
	onBeforeUnmount,
	watch,
} from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import OpenQuestion from '@/components/Modals/OpenQuestion.vue'
import { showToast, updateDocumentTitle } from '@/utils'
import { useRouter } from 'vue-router'
import Link from '@/components/Controls/Link.vue'
import { examStore } from '@/stores/exam'


const showOpenQuestionModal = ref(false)
const currentQuestion = reactive({
	question: '',
	points: 0,
	name: '',
})
const user = inject('$user')
const router = useRouter()

const props = defineProps({
	examID: {
		type: String,
		required: false,
	},
})

const exam = reactive({
	title: '',
	course: '',
	total_points: 0,
	duration: 0,
	qbyquestion: false,
	limit_questions_to: 0,
	show_answers: true,
	shuffle_questions: false,
	questions: [],
})

onMounted(() => {


	if (
		props.examID == 'new' &&
		!user.data?.is_moderator &&
		!user.data?.is_instructor
	) {
		router.push({ name: 'Courses' })
	}
	if (props.examID === 'new') {
	
		if (examStore.prefillData.title) {
       	 exam.title = examStore.prefillData.title; // Pre-fill the title if provided
    	}
		if (examStore.prefillData.course) {
        exam.course = examStore.prefillData.course; // Pre-fill the course if provided
    }
}
	if (props.examID !== 'new') {
		examDetails.reload()
	}
	window.addEventListener('keydown', keyboardShortcut)
})

const keyboardShortcut = (e) => {
	if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
		submitExam()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})

watch(
	() => props.examID !== 'new',
	(newVal) => {
		if (newVal) {
			examDetails.reload()
			examStore.clearPrefillData()
		}
	}
)

const examDetails = createResource({
	url: 'frappe.client.get',
	makeParams(values) {
		return { doctype: 'Exam Activity', name: props.examID }
	},
	auto: false,
	onSuccess(data) {
		Object.keys(data).forEach((key) => {
			if (Object.hasOwn(exam, key)) exam[key] = data[key]
		})

		let checkboxes = [
			'show_answers',
			'show_submission_history',
			'shuffle_questions',
		]
		for (let idx in checkboxes) {
			let key = checkboxes[idx]
			exam[key] = exam[key] ? true : false
		}
	},
})

const examCreate = createResource({
	url: 'frappe.client.insert',
	auto: false,
	makeParams(values) {
		return {
			doc: {
				doctype: 'Exam Activity',
				...exam,
			},
		}
	},
})

const examUpdate = createResource({
	url: 'frappe.client.set_value',
	auto: false,
	makeParams(values) {
		return {
			doctype: 'Exam Activity',
			name: values.examID,
			fieldname: {
				total_points: calculateTotalpoints(),
				...exam,
			},
		}
	},
})

const submitExam = () => {
	if (examDetails.data?.name) updateExam()
	else createExam()
}

const createExam = () => {
	examCreate.submit(
		{},
		{
			onSuccess(data) {
				showToast(__('Success'), __('Exam created successfully'), 'check')
				router.push({
					name: 'ExamForm',
					params: { examID: data.name },
				})
			},
			onError(err) {
				showToast(__('Error'), __(err.messages?.[0] || err), 'x')
			},
		}
	)
}

const updateExam = () => {
	examUpdate.submit(
		{ examID: examDetails.data?.name },
		{
			onSuccess(data) {
				exam.total_points = data.total_points
				showToast(__('Success'), __('Exam updated successfully'), 'check')
			},
			onError(err) {
				showToast(__('Error'), __(err.messages?.[0] || err), 'x')
			},
		}
	)
}

const calculateTotalpoints = () => {
	let totalpoints = 0
	if (exam.limit_questions_to && exam.questions.length > 0)
		return exam.questions[0].points * exam.limit_questions_to
	exam.questions.forEach((question) => {
		totalpoints += question.points
	})
	return totalpoints
}

const questionColumns = computed(() => {
	return [
		{
			label: __('ID'),
			key: 'question',
			width: '10rem',
		},
		{
			label: __('Question'),
			key: __('question_detail'),
			width: '40rem',
		},
		{
			label: __('Points'),
			key: 'points',
			width: '5rem',
		},
	]
})

const openOpenQuestionModal = (question = null) => {
	if (question) {
		currentQuestion.question = question.question
		currentQuestion.points = question.points
		currentQuestion.name = question.name
	} else {
		currentQuestion.question = ''
		currentQuestion.points = 0
		currentQuestion.name = ''
	}
	showOpenQuestionModal.value = true
}

const deleteQuestionResource = createResource({
	url: 'seminary.seminary.api.delete_documents',
	makeParams(values) {
		return {
			doctype: 'Exam Question',
			documents: values.questions,
		}
	},
})

const deleteQuestions = (selections, unselectAll) => {
	deleteQuestionResource.submit(
		{
			questions: Array.from(selections),
		},
		{
			onSuccess() {
				showToast(__('Success'), __('Questions deleted successfully'), 'check')
				examDetails.reload()
				unselectAll()
			},
		}
	)
}

const breadcrumbs = computed(() => {
	let crumbs = [
		{
			label: __('Exams'),
			route: {
				name: 'Exams',
			},
		},
	]
	/* if (examDetails.data) {
		crumbs.push({
			label: exam.title,
		})
	} */
	crumbs.push({
		label: props.examID == 'new' ? __('New Exam') : examDetails.data?.title,
		route: { name: 'ExamForm', params: { examID: props.examID } },
	})
	return crumbs
})

const pageMeta = computed(() => {
	return {
		title: props.examID == 'new' ? __('New Exam') : examDetails.data?.title,
		description: __('Form to create and edit exams'),
	}
})

updateDocumentTitle(pageMeta)
</script>
