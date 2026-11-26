<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
		<template #actions>
			<div class="space-x-2">
				<Button v-if="showBackToLesson" variant="outline" @click="backToLesson()">
					{{ __('Back to lesson') }}
				</Button>
				<router-link v-if="assignment.doc?.name" :to="{
					name: 'AssignmentSubmissionList',
					query: {
						assignmentID: assignment.doc.name,
					},
				}">
					<Button>
						{{ __('Submission List') }}
					</Button>
				</router-link>
				<Button variant="solid" @click="saveAssignment()">
					{{ __('Save') }}
				</Button>
			</div>
		</template>
	</PageHeader>
	<div class="w-3/4 mx-auto py-5">
		<div class="font-semibold mb-4">
			{{ __('Assignment Details') }}
		</div>
		<div class="grid grid-cols-2 gap-5 mt-4 mb-8">
			<FormControl v-model="model.title" :label="__('Title')" :required="true" />

			<FormControl v-model="model.type" type="select" :options="assignmentOptions" :label="__('Type')"
				:required="true" />
		</div>
		<div class="mb-8">
			<LinkControl v-model="model.course" doctype="Course"
				:label="__('Course where this assignment will be used. You may reuse this assignment in other course offerings')"
				:required="true" />
		</div>
		<div>
			<div class="text-xs text-ink-gray-5 mb-2">
				{{ __('Question') }}
				<span class="text-ink-red-3">*</span>
			</div>
			<TextEditor v-if="model.question !== undefined" :content="model.question || ''"
				@change="(val) => (model.question = val)" :editable="true" :fixedMenu="true"
				editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]" />
			<ContentIssues ref="questionChecker" class="mt-2" :issues="questionIssues" :actionLabel="__('Save anyway')" />
		</div>
		<div v-if="defensible" class="mt-8 space-y-4">
			<div class="font-semibold">{{ __('Oral Defense') }}</div>
			<FormControl v-model="model.oral_defense" type="checkbox"
				:label="__('After submitting, the student answers a few questions about the paper aloud')" />
			<template v-if="model.oral_defense">
				<div class="grid grid-cols-3 gap-5">
					<FormControl v-model.number="model.defense_questions" type="number" min="1" :label="__('Questions')" />
					<FormControl v-model.number="model.defense_answer_s" type="number" min="30"
						:label="__('Seconds per answer')" />
					<div class="flex items-end gap-2">
						<FormControl v-model.number="windowAmount" type="number" min="1" class="flex-1"
							:label="__('Due within')" />
						<FormControl v-model="windowUnit" type="select" class="w-28" :options="[
							{ label: __('minutes'), value: 60 },
							{ label: __('hours'), value: 3600 },
							{ label: __('days'), value: 86400 },
						]" />
					</div>
				</div>
				<p class="text-xs text-ink-gray-5">
					{{ __('Counted from when the defense opens, once its questions are ready: an hour for a defense straight after the paper, or days for one taken later.') }}
				</p>
				<div class="flex flex-wrap gap-y-2">
					<FormControl v-model="model.defense_follow_up" type="checkbox" class="mr-6"
						:label="__('Ask a follow-up question on each answer')" />
					<FormControl v-model="model.defense_review" type="checkbox" class="mr-6"
						:label="__('Review the questions before the defense opens')" />
				</div>
				<div>
					<div class="text-sm text-ink-gray-7 mb-1">{{ __('Processing of each answer') }}</div>
					<div v-if="stepChoices.data?.length" class="flex flex-wrap gap-y-2">
						<FormControl v-for="c in stepChoices.data" :key="c.step" type="checkbox" :label="c.label"
							class="mr-6" :modelValue="chosenSteps.includes(c.step)"
							@update:modelValue="(v) => toggleStep(c.step, v)" />
					</div>
					<p v-else class="text-sm text-ink-gray-5">{{ __('No processing steps are available on this site.') }}</p>
				</div>
			</template>
		</div>
		<PeerWorkSettings class="mt-8" :model="model" kind="assignment" />
		<RubricEditor v-if="assignment.doc?.name" class="mt-8" activity-doctype="Assignment Activity"
			:activity="assignment.doc.name" :defense="!!(defensible && model.oral_defense)"
			@saved="outcomesPanel?.reload()" />
		<ActivityOutcomesPanel v-if="assignment.doc?.name && user?.data?.has_aretenic" ref="outcomesPanel"
			class="mt-6" activity-doctype="Assignment Activity" :activity="assignment.doc.name" />
	</div>
</template>
<script setup>
import PageHeader from '@/components/PageHeader.vue'
import ContentIssues from '@/components/ContentIssues.vue'
import { useContentCheck } from '@/composables/useContentCheck'
import {
	Breadcrumbs,
	Button,
	createDocumentResource,
	createResource,
	FormControl,
	TextEditor,
	toast,
} from 'frappe-ui'
import {
	computed,
	inject,
	onMounted,
	onBeforeUnmount,
	reactive,
	watch,
	ref
} from 'vue'
import { useRouter } from 'vue-router'
import { examStore } from '@/stores/exam'
import LinkControl from '@/components/Controls/Link.vue'
import RubricEditor from '@/components/RubricEditor.vue'
import PeerWorkSettings from '@/components/PeerWorkSettings.vue'
import ActivityOutcomesPanel from '@/components/ActivityOutcomesPanel.vue'
import { useActivityReturn } from '@/composables/useActivityReturn'

const user = inject('$user')
const outcomesPanel = ref(null)
const router = useRouter()
const { showBackToLesson, backToLesson } = useActivityReturn(
	() => assignment.doc?.name
)
const props = defineProps({
	assignmentID: {
		type: String,
		required: false,
	},
})

const model = reactive({
	title: '',
	course: '',
	type: 'PDF',
	question: '',
	oral_defense: false,
	defense_questions: 3,
	defense_answer_s: 120,
	defense_follow_up: false,
	defense_window: 259200,
	defense_review: false,
	defense_steps: '[]',
	// decisions/120 §1
	group_work: false,
	group_source: 'By hand',
	group_size: 3,
	topic_mode: '',
	peer_review: false,
	reviews_per_student: 2,
	review_opens: 'At the due date',
	review_due_days: 7,
	review_anonymous: false,
	review_form: 'Rubric',
	teammate_ratings: false,
	ratings_shown: 'Named',
	review_share: 0,
})
const PEER_CHECKS = ['group_work', 'peer_review', 'review_anonymous', 'teammate_ratings']

// The oral defense (decisions/100c): only for papers whose text can be read.
const defensible = computed(() => ['PDF', 'Document', 'Text'].includes(model.type))
const stepChoices = createResource({ url: 'seminary.seminary.oral.step_choices', auto: true })
const chosenSteps = computed(() => {
	try {
		return JSON.parse(model.defense_steps || '[]')
	} catch (e) {
		return []
	}
})
const toggleStep = (step, on) => {
	const set = new Set(chosenSteps.value)
	on ? set.add(step) : set.delete(step)
	model.defense_steps = JSON.stringify([...set])
}
// The window is stored in seconds and shown in the largest unit that divides it.
const windowUnit = computed({
	get: () => [86400, 3600, 60].find((u) => (model.defense_window || 0) % u === 0) || 60,
	set: (unit) => {
		model.defense_window = windowAmount.value * Number(unit)
	},
})
const windowAmount = computed({
	get: () => Math.max(1, Math.round((model.defense_window || 0) / windowUnit.value)),
	set: (n) => {
		model.defense_window = Math.max(1, Number(n) || 1) * windowUnit.value
	},
})

onMounted(() => {
	if (
		props.assignmentID == 'new' &&
		!user.data?.is_moderator &&
		!user.data?.is_instructor
	) {
		router.push({ name: 'Courses' })
	}
	if (props.assignmentID === 'new') {

		if (examStore.prefillData.title) {
			model.title = examStore.prefillData.title; // Pre-fill the title if provided
		}
		if (examStore.prefillData.course) {
			model.course = examStore.prefillData.course; // Pre-fill the course if provided
		}
	}
	if (props.assignmentID !== 'new') {
		assignment.reload()
	}
	window.addEventListener('keydown', keyboardShortcut)
})

const keyboardShortcut = (e) => {
	if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
		saveAssignment()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})

const assignment = createDocumentResource({
	doctype: 'Assignment Activity',
	name: props.assignmentID,
	auto: false,
})

const newAssignment = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Assignment Activity',
				...values,
			},
		}
	},
	onSuccess(data) {
		toast.success(__('Assignment saved successfully'))
		router.push({ name: 'AssignmentForm', params: { assignmentID: data.name } })
	},
	onError(err) {
		toast.error(err.messages?.[0] || err)
	},
})

// The accessibility checker on the question students read (102 §7).
const {
	checker: questionChecker,
	issues: questionIssues,
	confirmSave: confirmQuestion,
} = useContentCheck(() => model.question)

const saveAssignment = async () => {
	if (!(await confirmQuestion())) return
	if (props.assignmentID == 'new') {
		newAssignment.submit({
			...model,
		})
	} else {
		assignment.setValue.submit(
			{
				...model,
			},
			{
				onSuccess(data) {
					toast.success(__('Assignment saved successfully'))
					assignment.reload()
				},
				onError(err) {
					toast.error(err.messages?.[0] || err)
				},
			}
		)
	}
}

watch(assignment, () => {
	if (assignment.doc) {
		Object.keys(assignment.doc).forEach((key) => {
			model[key] = assignment.doc[key];
		});
		model.oral_defense = !!model.oral_defense
		model.defense_follow_up = !!model.defense_follow_up
		model.defense_review = !!model.defense_review
		PEER_CHECKS.forEach((k) => (model[k] = !!model[k]))
		if (!model.group_source) model.group_source = 'By hand'
	}
});

const breadcrumbs = computed(() => {
	const items = [
		{
			label: __('Assignments'),
			route: { name: 'Assignments' },
		},
	]

	if (assignment.doc?.name) {
		items.push({
			label: assignment.doc.title,
			route: {
				name: 'AssignmentForm',
				params: { assignmentID: assignment.doc.name },
			},
		})
	} else {
		items.push({
			label: __('New Assignment'),
			route: {
				name: 'AssignmentForm',
				params: { assignmentID: props.assignmentID || 'new' },
			},
		})
	}

	return items
})

const assignmentOptions = computed(() => {
	return [
		{ label: 'PDF', value: 'PDF' },
		{ label: __('Image'), value: 'Image' },
		{ label: __('Document'), value: 'Document' },
		{ label: __('Text'), value: 'Text' },
		{ label: __('URL'), value: 'URL' },
		{ label: 'YouTube', value: 'YouTube' },
	]
})
</script>
