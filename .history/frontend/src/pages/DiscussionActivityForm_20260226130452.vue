<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
		<Breadcrumbs :items="breadcrumbs" />
		<div class="space-x-2">

			<router-link v-if="discussionDetails.data?.name" :to="{
				name: 'DiscussionActivitySubmissionList',
				params: {
					discussionID: discussionDetails.data.name,
				},
			}">
				<Button>
					{{ __('Submission List') }}
				</Button>
			</router-link>
			<Button variant="solid" @click="submitDiscussion()">
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
			<FormControl v-model="discussion.discussion_name" :label="discussionDetails.data?.discussion_name
				? __('Title')
				: __('Enter a title and save the discussion to proceed')
				" :required="true" />
			<br />
			<Link v-model="discussion.course" doctype="Course"
				:label="__('Course where this discussion will be used - you may reuse this discussion in other scheduled courses')"
				:placeholder="__('Select a course')" :required="true" />



			<!-- Settings -->
			<div class="mb-8">
				<div class="font-semibold mb-4 mt-4">
					{{ __('Settings') }}
				</div>


				<div class="checkbox-container">
					<FormControl v-model="discussion.use_studentgroup" type="checkbox"
						:label="__('Check this if you want discussion to be done in student groups. Otherwise, all students will participate in the same thread.')" />
					<FormControl v-model="discussion.post_before" type="checkbox"
						:label="__('Check this if you want students to post before seeing other posts.')" />
				</div>
			</div>
			<!-- Prompt -->
			<!-- <TextEditor
				:content="discussion.prompt || ''"
				@change="(val) => (discussion.prompt = val)"
				:editable="true"
				:fixedMenu="true"
                :placeholder="__('Enter prompt for the discussion activity...')"
				editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
			/> -->
			<label for="discussion-prompt" class="block text-lg font-medium text-gray-700 mb-4">
				{{ __('Discussion Prompt') }}
			</label>
			<FormControl v-model="discussion.prompt" type="textarea" :label="__('Discussion Prompt')"
				:placeholder="__('Enter a prompt for the discussion.')" :rows="6" />
		</div>


</template>
<script setup>
import {
	Breadcrumbs,
	createResource,
	FormControl,
	Button,
	TextEditor,
	toast,
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

import { updateDocumentTitle } from '@/utils'
import { useRouter } from 'vue-router'
import Link from '@/components/Controls/Link.vue'




const user = inject('$user')
const router = useRouter()
const promptReady = ref(false)
const props = defineProps({
	discussionID: {
		type: String,
		required: false,
	},
})

const discussion = reactive({
	discussion_name: '',
	course: '',
	post_before: false,
	use_studentgroup: false,
	prompt: '',
})


onMounted(() => {
	if (
		props.discussionID == 'new' &&
		!user.data?.is_moderator &&
		!user.data?.is_instructor
	) {
		router.push({ name: 'Courses' })
	}

	if (props.discussionID !== 'new') {
		discussionDetails.reload()
	} else {
		promptReady.value = true
	}

	window.addEventListener('keydown', keyboardShortcut)
})

const keyboardShortcut = (e) => {
	if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
		submitDiscussion()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})

watch(
	() => props.discussionID !== 'new',
	(newVal) => {
		if (newVal) {
			discussionDetails.reload()

		}
	}
)



const discussionDetails = createResource({
	url: 'frappe.client.get',
	makeParams(values) {
		return { doctype: 'Discussion Activity', name: props.discussionID }
	},
	auto: false,
	onSuccess(data) {
		Object.keys(data).forEach((key) => {
			if (Object.hasOwn(discussion, key)) discussion[key] = data[key]
		})

		let checkboxes = ['post_before', 'use_studentgroup']
		for (let idx in checkboxes) {
			let key = checkboxes[idx]
			discussion[key] = discussion[key] ? true : false
		}

		promptReady.value = true
	},
})

const discussionCreate = createResource({
	url: 'frappe.client.insert',
	auto: false,
	makeParams(values) {
		return {
			doc: {
				doctype: 'Discussion Activity',
				...discussion,
			},
		}
	},
})

const discussionUpdate = createResource({
	url: 'frappe.client.set_value',
	auto: false,
	makeParams(values) {
		return {
			doctype: 'Discussion Activity',
			name: values.discussionID,
			fieldname: {

				...discussion,
			},
		}
	},
})

const submitDiscussion = () => {
	if (discussionDetails.data?.name) updateDiscussion()
	else createDiscussion()
}

const createDiscussion = () => {
	discussionCreate.submit(
		{},
		{
			onSuccess(data) {
				toast.success(__('Discussion created successfully'));
				router.replace({
					name: 'DiscussionActivityForm',
					params: { discussionID: data.name },
				})
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const updateDiscussion = () => {
	discussionUpdate.submit(
		{ discussionID: discussionDetails.data?.name },
		{
			onSuccess(data) {

				toast.success(__('Discussion updated successfully'));
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}



const breadcrumbs = computed(() => {
	let crumbs = [
		{
			label: __('Discussion Activities'),
			route: { name: 'DiscussionActivities' },
		},
	]
	crumbs.push({
		label: props.discussionID === 'new'
			? __('New Discussion')
			: discussion.discussion_name,
		route: {
			name: 'DiscussionActivityForm',
			params: { discussionID: props.discussionID },
		},
	})
	return crumbs
})

const pageMeta = computed(() => {
	return {
		title: props.discussionID == 'new' ? __('New Discussion') : discussion.discussion_name,
		description: __('Form to create and edit discussions'),
	}
})

updateDocumentTitle(pageMeta)
</script>

<style scoped>
.checkbox-container {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}
</style>
