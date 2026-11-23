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
				<Button variant="solid" @click="submitActivity()">
					{{ __('Save') }}
				</Button>
			</div>
		</template>
	</PageHeader>
	<div class="w-3/4 mx-auto py-5">
		<div class="mb-8 space-y-4">
			<div class="font-semibold">{{ __('Details') }}</div>
			<FormControl v-model="activity.title" :label="activityDetails.data?.title
				? __('Title')
				: __('Enter a title and save the activity to proceed')" :required="true" />
			<Link v-model="activity.course" doctype="Course"
				:label="__('Course where this activity will be used - you may reuse it in other scheduled courses')"
				:placeholder="__('Select a course')" :required="true" />
		</div>

		<div class="mb-8 space-y-4">
			<div class="font-semibold">{{ __('Settings') }}</div>
			<FormControl v-model="activity.mode" type="select" :label="__('Mode')" :options="[
				{ label: __('Individual: each student records alone'), value: 'Individual' },
				{ label: __('Conversation: a group records one conversation together'), value: 'Conversation' },
			]" />
			<FormControl v-if="activity.mode === 'Conversation'" v-model.number="activity.group_size" type="number"
				min="0" :label="__('Group size')"
				:description="__('On a section without student groups, groups of this size are made the first time the activity is opened. Leave 0 to let students choose classmates from the whole section.')" />
			<FormControl v-model.number="activity.max_minutes" type="number" min="1"
				:label="__('Maximum length (minutes)')" />
			<FormControl v-model="activity.capture" type="select" :label="__('Recorded')" :options="[
				{ label: __('By students, in the browser'), value: 'Browser' },
				{ label: __('From online class meetings'), value: 'Virtual meeting' },
			]"
				:description="activity.capture === 'Virtual meeting' ? __('On each section, choose the class meetings to capture from the activity\'s Submissions page.') : ''" />
			<FormControl v-if="activity.capture !== 'Virtual meeting'" v-model="activity.allow_upload" type="checkbox"
				:label="__('Students may upload a file recorded elsewhere, such as on a phone in a classroom')" />
		</div>

		<div class="mb-8">
			<div class="font-semibold mb-2">{{ __('Processing') }}</div>
			<p class="text-sm text-ink-gray-6 mb-3">
				{{ __('Steps run on each recording. Without any, you listen and grade from the audio.') }}
			</p>
			<div v-if="stepChoices.data?.length" class="flex flex-wrap gap-y-2">
				<FormControl v-for="c in stepChoices.data" :key="c.step" type="checkbox" :label="c.label" class="mr-6"
					:modelValue="chosenSteps.includes(c.step)" @update:modelValue="(v) => toggleStep(c.step, v)" />
			</div>
			<p v-else class="text-sm text-ink-gray-5">
				{{ __('No processing steps are available on this site.') }}
			</p>
		</div>

		<!-- Not a <label>: the editor is not a form field a label can point to. -->
		<div id="oral-prompt-label" class="block text-lg font-medium text-ink-gray-7 mb-4">
			{{ __('Prompt') }}
		</div>
		<RichTextEditor :teleport="false" id="oral-prompt" labelledby="oral-prompt-label" :content="activity.prompt || ''"
			@change="(val) => (activity.prompt = val)"
			:placeholder="__('What should the students talk about?')" />
		<ContentIssues ref="promptChecker" class="mt-2" :issues="promptIssues" :actionLabel="__('Save anyway')" />
		<RubricEditor v-if="activityDetails.data?.name" class="mt-8" activity-doctype="Oral Activity"
			:activity="activityDetails.data.name" />
	</div>
</template>
<script setup>
// Create and edit an oral activity (decisions/100b).
import PageHeader from '@/components/PageHeader.vue'
import ContentIssues from '@/components/ContentIssues.vue'
import { useContentCheck } from '@/composables/useContentCheck'
import { Breadcrumbs, createResource, FormControl, Button, toast } from 'frappe-ui'
import { computed, reactive, onMounted, inject, onBeforeUnmount, watch } from 'vue'
import { updateDocumentTitle } from '@/utils'
import { useRouter } from 'vue-router'
import Link from '@/components/Controls/Link.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import RubricEditor from '@/components/RubricEditor.vue'
import { examStore } from '@/stores/exam'
import { useActivityReturn } from '@/composables/useActivityReturn'

const user = inject('$user')
const router = useRouter()
const { showBackToLesson, backToLesson } = useActivityReturn(() => activityDetails.data?.name)

const props = defineProps({
	activityID: { type: String, required: false },
})

const activity = reactive({
	title: '',
	course: '',
	mode: 'Individual',
	group_size: 0,
	max_minutes: 10,
	allow_upload: false,
	capture: 'Browser',
	oral_steps: '[]',
	prompt: '',
})

const stepChoices = createResource({ url: 'seminary.seminary.oral.step_choices', auto: true })
const chosenSteps = computed(() => {
	try {
		return JSON.parse(activity.oral_steps || '[]')
	} catch (e) {
		return []
	}
})
const toggleStep = (step, on) => {
	const set = new Set(chosenSteps.value)
	on ? set.add(step) : set.delete(step)
	activity.oral_steps = JSON.stringify([...set])
}

onMounted(() => {
	if (props.activityID == 'new' && !user.data?.is_moderator && !user.data?.is_instructor) {
		router.push({ name: 'Courses' })
	}
	if (props.activityID !== 'new') {
		activityDetails.reload()
	} else {
		if (examStore.prefillData.course) activity.course = examStore.prefillData.course
		if (examStore.prefillData.title) activity.title = examStore.prefillData.title
		examStore.clearPrefillData()
	}
	window.addEventListener('keydown', keyboardShortcut)
})

const keyboardShortcut = (e) => {
	if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
		submitActivity()
		e.preventDefault()
	}
}
onBeforeUnmount(() => window.removeEventListener('keydown', keyboardShortcut))

watch(
	() => props.activityID !== 'new',
	(isSaved) => {
		if (isSaved) activityDetails.reload()
	}
)

const activityDetails = createResource({
	url: 'frappe.client.get',
	makeParams: () => ({ doctype: 'Oral Activity', name: props.activityID }),
	auto: false,
	onSuccess(data) {
		Object.keys(data).forEach((key) => {
			if (Object.hasOwn(activity, key)) activity[key] = data[key]
		})
		activity.allow_upload = !!activity.allow_upload
	},
})

const activityCreate = createResource({
	url: 'frappe.client.insert',
	makeParams: () => ({ doc: { doctype: 'Oral Activity', ...activity } }),
})
const activityUpdate = createResource({
	url: 'frappe.client.set_value',
	makeParams: (values) => ({ doctype: 'Oral Activity', name: values.activityID, fieldname: { ...activity } }),
})

// The accessibility checker on the prompt students read (102 §7).
const {
	checker: promptChecker,
	issues: promptIssues,
	confirmSave: confirmPrompt,
} = useContentCheck(() => activity.prompt)

const submitActivity = async () => {
	if (!(await confirmPrompt())) return
	if (activityDetails.data?.name) {
		activityUpdate.submit(
			{ activityID: activityDetails.data.name },
			{
				onSuccess: () => toast.success(__('Oral activity updated')),
				onError: (err) => toast.error(err.messages?.[0] || err),
			}
		)
	} else {
		activityCreate.submit(
			{},
			{
				onSuccess(data) {
					toast.success(__('Oral activity created'))
					router.replace({ name: 'OralActivityForm', params: { activityID: data.name } })
				},
				onError: (err) => toast.error(err.messages?.[0] || err),
			}
		)
	}
}

const breadcrumbs = computed(() => [
	{ label: __('Oral Activities'), route: { name: 'OralActivities' } },
	{
		label: props.activityID === 'new' ? __('New Oral Activity') : activity.title,
		route: { name: 'OralActivityForm', params: { activityID: props.activityID } },
	},
])

updateDocumentTitle(
	computed(() => ({
		title: props.activityID == 'new' ? __('New Oral Activity') : activity.title,
		description: __('Form to create and edit oral activities'),
	}))
)
</script>
