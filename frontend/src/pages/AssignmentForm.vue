<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<div class="space-x-2">
			<router-link
				v-if="assignment.doc?.name"
				:to="{
					name: 'AssignmentSubmissionList',
					query: {
						assignmentID: assignment.doc.name,
					},
				}"
			>
				<Button>
					{{ __('Submission List') }}
				</Button>
			</router-link>
			<Button variant="solid" @click="saveAssignment()">
				{{ __('Save') }}
			</Button>
		</div>
	</header>
	<div class="w-3/4 mx-auto py-5">
		<div class="font-semibold mb-4">
			{{ __('Assignment Details') }}
		</div>
		<div class="grid grid-cols-2 gap-5 mt-4 mb-8">
			<FormControl
				v-model="model.title"
				:label="__('Title')"
				:required="true"
			/>

			<FormControl
				v-model="model.type"
				type="select"
				:options="assignmentOptions"
				:label="__('Type')"
				:required="true"
			/>
		</div>
		<div class="mb-8">
			<LinkControl
				v-model="model.course"
				doctype="Course"
				:label="__('Course where this assignment will be used. You may reuse this assignment in other course offerings')"
				:required="true"
			/>
		</div>
		<div>
			<div class="text-xs text-ink-gray-5 mb-2">
				{{ __('Question') }}
				<span class="text-ink-red-3">*</span>
			</div>
			<TextEditor
				v-if="model.question !== undefined"
				:content="model.question || ''"
				@change="(val) => (model.question = val)"
				:editable="true"
				:fixedMenu="true"
				editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
			/>
		</div>
	</div>
</template>
<script setup>
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

const user = inject('$user')
const router = useRouter()
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

const saveAssignment = () => {
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
		{ label: 'Image', value: 'Image' },
		{ label: 'Document', value: 'Document' },
		{ label: 'Text', value: 'Text' },
		{ label: 'URL', value: 'URL' },
	]
})
</script>
