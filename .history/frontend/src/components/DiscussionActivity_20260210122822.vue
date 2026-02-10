<template v-if="discussionReady">
	<div v-if="discussion.data" class="grid grid-cols-[65%,35%] h-full" :class="{ 'border rounded-lg': !showTitle }">
		<div class="border-r p-5 overflow-y-auto h-[calc(100vh-3.2rem)]">
			<div v-if="showTitle" class="text-lg font-semibold mb-5 text-ink-gray-9">
				<div v-if="submissionName === 'new'">
					{{ __('Submission by') }} {{ user.data?.full_name }}
				</div>
				<div v-else>
					{{ __('Submission by') }} {{ submissionResource.doc?.member_name }}
				</div>
			</div>
			<div class="text-lg text-ink-gray-7 font-medium mb-2">
				{{ __('Discussion Prompt') }}:
			</div>
			<div v-html="discussion.data.prompt"
				class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"
				</div>

				<div v-if="
					all_discussions.data && (hasSavedSubmission || (!hasSavedSubmission && !post_before) || !isStudent)
				" class="flex-1 border-l p-5 overflow-y-auto h-[calc(100vh-3.2rem)]">
					<div v-if="!isStudent" class="mb-4 mt-4">
						<label for="groupFilter" class="block text-sm font-medium text-gray-700">
							{{ __('Filter by Group') }}
						</label>
						<select id="groupFilter" v-model="selectedGroupFilter"
							class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md">
							<option value="all">{{ __('All Groups') }}</option>
							<option v-for="group in studentGroups" :key="group.student_group"
								:value="group.student_group">
								{{ group.student_group || 'No group' }}
							</option>
						</select>
					</div>


					<div v-for="discussion in filteredDiscussions" :key="discussion.name"
						class="mb-6 border-round border-gray-300 p-4 bg-surface-white shadow-sm">
						<div class="original-post mb-4">
							<div class="font-semibold">{{ discussion.student_name }}</div>
							<div v-html="discussion.original_post" class="text-sm"></div>
							<div class="text-sm text-ink-gray-5 mt-1 mb-2">
								{{ formatDate(discussion.creation) }}
							</div>
							<a v-if="discussion.original_attachment" :href="discussion.original_attachment"
								target="_blank" class="text-blue-500 underline">
								{{ __('View Attachment') }}
							</a>
						</div>
						<div class="replies pl-4 border-l border-gray-300">
							<div v-for="reply in discussion.replies" :key="reply.creation" class="mb-2">
								<div class="font-semibold">{{ reply.member_name || reply.owner }}</div>
								<div class="text-sm text-ink-gray-5 mt-1 mb-2">
									{{ formatDate(reply.reply_dt) }}
								</div>
								<div v-html="reply.reply" class="text-sm"></div>
								<a v-if="reply.reply_attach" :href="reply.reply_attach" target="_blank"
									class="text-blue-500 underline">
									{{ __('View Attachment') }}
								</a>
							</div>
						</div>
						<div class="new-reply mt-4 space-y-2">
							<textarea v-model="discussion.new_reply" :placeholder="__('Write a reply...')"
								class="prose-sm max-w-none border border-outline-gray-3 bg-surface-gray-2 rounded-md py-2 px-3 min-h-[6rem] w-full focus:outline-none"></textarea>
							<div class="flex items-center justify-between">
								<div class="flex items-center space-x-3">
									<FileUploader v-if="!replyFiles[discussion.name]" :fileTypes="getType()"
										:validateFile="validateFile"
										@success="(file) => saveReplyAttachment(discussion.name, file)">
										<template #default="{ uploading, progress, openFileSelector }">
											<Button @click="openFileSelector" :loading="uploading" variant="outline">
												{{
													uploading
														? __('Uploading {0}%').format(progress)
														: __('Attach File')
												}}
											</Button>
										</template>
									</FileUploader>
									<div v-else class="flex items-center space-x-2 text-ink-gray-7">
										<div class="border rounded-md p-2">
											<FileText class="h-4 w-4" />
										</div>
										<div class="flex flex-col leading-5">
											<span class="text-sm">{{ replyFiles[discussion.name].file_name }}</span>
											<span class="text-xs text-ink-gray-5">
												{{ getFileSize(replyFiles[discussion.name].file_size) }}
											</span>
										</div>
										<Button variant="subtle" size="sm"
											@click="removeReplyAttachment(discussion.name)">
											{{ __('Remove') }}
										</Button>
									</div>
								</div>
								<Button variant="solid" :disabled="!canSubmitReply(discussion)"
									@click="handleReplySubmit(discussion)">
									{{ __('Post Reply') }}
								</Button>
							</div>
						</div>
					</div>
				</div>
				<div v-else-if="!hasSavedSubmission && post_before && isStudent" class="text-ink-gray-5 mt-5">
					{{ __('You have to make your original post before seeing other posts.') }}
				</div>
				<div v-else class="text-ink-gray-5 mt-5">
					{{ __('No discussions available yet.') }}
					{{ 'All discussions', all_discussions.data }}
					{{ 'hasSavedSubmission', hasSavedSubmission }}
				</div>
			</div>
			<div v-if="canGradeSubmission" class="mt-8 space-y-4">
				<div class="font-semibold mb-2 text-ink-gray-9">
					{{ __('Grading') }}
				</div>
				<FormControl v-if="submissionResource.doc" v-model="submissionResource.doc.status"
					:label="__('Grading Status')" type="select" :options="submissionStatusOptions" />
				<FormControl v-if="submissionResource.doc" v-model="submissionResource.doc.grade" :label="__('Score')"
					type="number" />
				<div>
					<div class="text-sm text-ink-gray-5 mb-1">
						{{ __('Comments') }}
					</div>
					<textarea v-model="comments" @input="isDirty = true"
						class="prose-sm max-w-none border border-outline-gray-3 bg-surface-gray-2 rounded-md py-2 px-3 min-h-[7rem] w-full focus:outline-none"></textarea>
				</div>
			</div>
			<div v-if="!hasSavedSubmission" class="text-md mb-4">
				<div class="flex flex-col">

					<div class="p-5">
						<div class="flex items-center justify-between mb-4">

							<div class="flex items-center space-x-2">
								<Badge v-if="isDirty" theme="orange">
									{{ __('Not Saved') }}
								</Badge>
								<Badge v-else-if="submissionResource.doc?.status" :theme="statusTheme" size="lg">
									{{ submissionResource.doc?.status }}
								</Badge>
								<Button variant="solid" @click="submitDiscussion()">
									{{ __('Save') }}
								</Button>
							</div>
						</div>

						<div v-if="!hasSavedSubmission" class="text-md mb-4">
							{{ __('Write your main post here') }}
							<textarea v-model="original_post" @input="isDirty = true"
								class="prose-sm max-w-none border border-outline-gray-3 bg-surface-gray-2 rounded-md py-2 px-3 min-h-[7rem] w-full focus:outline-none"></textarea>

							<div class="text-md text-ink-gray-5 mt-1 mb-2">
								{{ __('You may also add an attachment') }}
							</div>
							<FileUploader v-if="!submissionFile" :fileTypes="getType()" :validateFile="validateFile"
								@success="(file) => saveSubmission(file)">
								<template #default="{ uploading, progress, openFileSelector }">
									<Button @click="openFileSelector" :loading="uploading">
										{{
											uploading
												? __('Uploading {0}%').format(progress)
												: __('Upload File')
										}}
									</Button>
								</template>
							</FileUploader>
							<div v-else>
								<div class="flex text-ink-gray-7">
									<div class="border self-start rounded-md p-2 mr-2">
										<FileText class="h-5 w-5 stroke-1.5" />
									</div>
									<a :href="submissionFile.file_url" target="_blank"
										class="flex flex-col cursor-pointer !no-underline">
										<span class="text-sm leading-5">
											{{ submissionFile.file_name }}
										</span>
										<span class="text-sm text-ink-gray-5 mt-1">
											{{ getFileSize(submissionFile.file_size) }}
										</span>
									</a>
									<X v-if="canModifyDiscussion" @click="removeSubmission()"
										class="bg-surface-gray-3 rounded-md cursor-pointer stroke-1.5 w-5 h-5 p-1 ml-4" />
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div v-else class="text-md mb-4 ml-2">
				<div class="text-sm text-ink-gray-5 font-medium mb-2 mt-4">
					{{ __('Your submission has been saved:') }}
				</div>
				<div v-for="submission in savedsubmission.data" :key="submission.name || submission.creation">
					<div class="font-semibold mb-1">
						{{ formatDate(submission.creation) }}
					</div>
					<div>{{ submission.original_post }}</div>
					<a v-if="submission.original_attachment" :href="submission.original_attachment" target="_blank"
						class="text-blue-500 underline">
						{{ __('View Attachment') }}
					</a>
					<div class="replies pl-4 border-l border-gray-300">
						<div v-for="reply in submission.replies" :key="reply.creation" class="mb-2">
							<div class="font-semibold">{{ reply.member_name || reply.owner }}</div>
							<div class="text-sm text-ink-gray-5 mt-1 mb-2">
								{{ formatDate(reply.reply_dt) }}
							</div>
							<div v-html="reply.reply" class="text-sm"></div>
							<a v-if="reply.reply_attach" :href="reply.reply_attach" target="_blank"
								class="text-blue-500 underline">
								{{ __('View Attachment') }}
							</a>
						</div>
					</div>
					<div class="new-reply mt-4 space-y-2">
						<textarea v-model="submission.new_reply" :placeholder="__('Write a reply...')"
							class="prose-sm max-w-none border border-outline-gray-3 bg-surface-gray-2 rounded-md py-2 px-3 min-h-[6rem] w-full focus:outline-none"></textarea>
						<div class="flex items-center justify-between">
							<div class="flex items-center space-x-3">
								<FileUploader v-if="!replyFiles[submission.name]" :fileTypes="getType()"
									:validateFile="validateFile"
									@success="(file) => saveReplyAttachment(submission.name, file)">
									<template #default="{ uploading, progress, openFileSelector }">
										<Button @click="openFileSelector" :loading="uploading" variant="outline">
											{{
												uploading
													? __('Uploading {0}%').format(progress)
													: __('Attach File')
											}}
										</Button>
									</template>
								</FileUploader>
								<div v-else class="flex items-center space-x-2 text-ink-gray-7">
									<div class="border rounded-md p-2">
										<FileText class="h-4 w-4" />
									</div>
									<div class="flex flex-col leading-5">
										<span class="text-sm">{{ replyFiles[submission.name].file_name }}</span>
										<span class="text-xs text-ink-gray-5">
											{{ getFileSize(replyFiles[submission.name].file_size) }}
										</span>
									</div>
									<Button variant="subtle" size="sm" @click="removeReplyAttachment(submission.name)">
										{{ __('Remove') }}
									</Button>
								</div>
							</div>
							<Button variant="solid" :disabled="!canSubmitReply(submission)"
								@click="handleReplySubmit(submission)">
								{{ __('Post Reply') }}
							</Button>
						</div>
					</div>
				</div>
			</div>

			<div v-if="
				user.data?.name == submissionResource.doc?.owner &&
				submissionResource.doc?.comments
			" class="mt-8 p-3 bg-blue-200 rounded-md">
				<div class="text-sm text-ink-gray-5 font-medium mb-2">
					{{ __('Comments by') }}: {{ submissionResource.doc?.evaluator || __('Evaluator') }}
				</div>
				<div class="leading-5">
					<div v-html="submissionResource.doc.comments"></div>
				</div>
			</div>


		</div>

</template>
<script setup>
import {
	Badge,
	Button,
	call,
	createResource,
	createDocumentResource,
	FileUploader,
	FormControl,
	toast
} from 'frappe-ui'
import { computed, inject, onMounted, onBeforeUnmount, ref, watch, toRaw } from 'vue'
import dayjsModule from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import { FileText, X } from 'lucide-vue-next'
import { getFileSize } from '@/utils'
import { useRouter } from 'vue-router'



const dayjs = typeof dayjsModule === 'function' ? dayjsModule : dayjsModule.default
dayjs.extend(relativeTime)

const submissionFile = ref(null)
const original_post = ref('')
const comments = ref('')
const router = useRouter()
const user = inject('$user')
const showTitle = router.currentRoute.value.name == 'DiscussionActivitySubmission'
const isDirty = ref(false)
const replyFiles = ref({})
const isStudent = computed(() => user.data?.is_student || false)
const studentGroups = ref([]);
const selectedGroupFilter = ref('all')
const Student = ref('');
const courseName = computed(() => router.currentRoute.value.params.courseName)
const discussionID = computed(() => props.discussionID)
const owner = computed(() => user.data?.name)


const saveReplyAttachment = (itemName, file) => {
	replyFiles.value = {
		...replyFiles.value,
		[itemName]: file,
	}
}

const discussionReady = computed(() => {
	courseName.value && discussionID.value && owner.value
})

const removeReplyAttachment = (itemName) => {
	const { [itemName]: _removed, ...rest } = replyFiles.value
	replyFiles.value = rest
}

const canSubmitReply = (item) => {
	return Boolean(item?.new_reply && item.new_reply.toString().trim().length)
}

const props = defineProps({
	discussionID: {
		type: String,
		required: true,
	},
	submissionName: {
		type: String,
		default: 'new',
	},
	canGradeSubmission: {
		type: Boolean,
		default: false,
		required: false,
	},
})

onMounted(() => {
	window.addEventListener('keydown', keyboardShortcut)
	console.log('User: ', user.data?.name)
	console.log('Discussion ID: ', props.discussionID)
	console.log("Course Name: ", router.currentRoute.value.params.courseName)
	reloadDiscussionLists()
	StudentData.reload().then(() => {
		console.log('Student data after reload:', Student.value)
		console.log('Student group:', Student.value?.student_group)
	})
	console.log('Saved Submission Data on Mount:', savedsubmission.data)
	console.log('hasSavedSubmission:', hasSavedSubmission.value)
	fetchStudentGroups()
	filteredDiscussions.value; // Trigger initial computation


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

const discussion = createResource({
	url: 'frappe.client.get',
	params: {
		doctype: 'Discussion Activity',
		name: props.discussionID,
	},
	auto: true,
	onSuccess(data) {
		if (props.submissionName != 'new') {
			submissionResource.reload()
		}
	},
})

console.log("Submission Name: ", props.submissionName)
const post_before = computed(() => {
	return discussion.data?.post_before
})

const formatDate = (dateString) => {
	if (dateString && dateString.includes('.')) {
		return dayjs(dateString.split('.')[0]).fromNow();
	}
	return dayjs(dateString).fromNow();
};

function getFrappeDateTime() {
	const now = new Date();
	// Get microseconds (JavaScript only provides milliseconds, so we multiply by 1000)
	const microseconds = Math.floor(now.getMilliseconds() * 1000);

	// Format with padStart for proper zero-padding
	const formatted = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}.${String(microseconds).padStart(6, '0')}`;

	return formatted;
}
const handleReplySubmit = (item) => {
	if (!canSubmitReply(item)) {
		return
	}

	const attachment = replyFiles.value[item.name]
	const studentid = Student.value?.student || null
	const member_name = Student.value?.student_name || user.data?.full_name
	const reply_dt = getFrappeDateTime()
	replyResource.submit(
		{
			name: item.name,
			reply: item.new_reply,
			reply_attach: attachment,
			student: studentid,
			member_name: member_name,
			parent: item.name,
			reply_dt: reply_dt,
			parentfield: 'replies',
			parenttype: 'Discussion Submission'
		},
		{
			onSuccess() {
				toast.success(__('Reply posted successfully'))
				item.new_reply = ''
				if (attachment) {
					removeReplyAttachment(item.name)
				}
				refreshDiscussionLists()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

//Logic for fetching all discussions and their replies
const all_discussions = createResource({
	url: 'seminary.seminary.api.get_discussion_submissions',
	makeParams(values) {
		return {
			course_name: router.currentRoute.value.params.courseName,
			discussion_id: props.discussionID,
		}
	},
	auto: false,
	onSuccess(data) {
		data?.forEach((discussion) => {
			if (discussion && typeof discussion.new_reply === 'undefined') {
				discussion.new_reply = ''
			}
		})
		console.log("All Discussions Data Fetched: ", data)

	},
})

//Get student data from user to avoid errors with instructor and get other fields

const StudentData = createResource({
	url: 'seminary.seminary.api.get_student_group',
	makeParams(values) {
		return {
			course_name: router.currentRoute.value.params.courseName,
			user: user.data?.name,
		}
	},
	auto: false,
	onSuccess(data) {
		Student.value = data
		console.log('Student fetched:', Student.value)
	}
})



// Fetch the saved discussion by the user if it exists
const savedsubmission = createResource({
	url: 'seminary.seminary.api.get_user_discussion_submission',
	makeParams(values) {
		return {
			course_name: router.currentRoute.value.params.courseName,
			discussion_id: props.discussionID,
			owner: user.data?.name,
		}
	},
	auto: false,
	onSuccess(data) {
		console.log('Saved submission fetched:', data)
	}
})

const hasSavedSubmission = computed(() =>
	Array.isArray(savedsubmission.data) && savedsubmission.data.length > 0
)


// Watch for when all required data becomes available
watch(discussionReady, async (hasData) => {
	if (hasData) {
		await reloadDiscussionLists()
	}
})

const reloadDiscussionLists = async () => {
	try {
		// No need for null checks since we know data exists
		await all_discussions.reload({
			course_name: courseName.value,
			discussion_id: discussionID.value,
		})

		await savedsubmission.reload({
			course_name: courseName.value,
			discussion_id: discussionID.value,
			owner: owner.value,
		})
	} catch (error) {
		console.error("Error reloading discussion lists:", error)
	}
}



const filteredDiscussions = computed(() => {

	let filter_discussions = toRaw(all_discussions.data)
	console.log("Discussions before filtering: ", filter_discussions)
	// For students - show only their group if use_studentgroup is enabled

	if (isStudent.value) {
		if (discussion.data?.use_studentgroup) {
			let selectedGroupFilter = studentGroup
			return filter_discussions.filter(discussion =>
				discussion.student_group === selectedGroupFilter.value
			)
		} else {
			return filter_discussions
		}
	} else {
		// For instructors - apply group filter
		if (!isStudent.value && selectedGroupFilter.value !== 'all') {
			return filter_discussions.filter(discussion =>
				discussion.student_group === selectedGroupFilter.value
			)
		}
		return filter_discussions
	}
})


const refreshDiscussionLists = () => {
	reloadDiscussionLists()
}



const newSubmission = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		let doc = {
			doctype: 'Discussion Submission',
			disc_activity: props.discussionID,
			disc_title: discussion.data?.discussion_name,
			member: user.data?.name,
			coursesc: router.currentRoute.value.params.courseName,
			original_post: original_post.value,
			original_attachment: submissionFile.value?.file_url || null,
			student_name: Student.value?.student_name || user.data?.full_name,
			student: Student.value?.student || null,
		}
		return {
			doc: doc,
		}
	},
})

const replyResource = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		const attachment = values.reply_attach
		return {
			doc: {
				doctype: 'Discussion Submission Replies',
				member: user.data?.name,
				reply: values.reply,
				student: values.student,
				member_name: values.member_name || user.data?.full_name,
				reply_dt: values.reply_dt,
				parent: values.name,
				parentfield: 'replies',
				parenttype: 'Discussion Submission',
				reply_attach: attachment?.file_url || null,
			},
		}
	},
	auto: false,
})

const imageResource = createResource({
	url: 'seminary.seminary.api.get_file_info',
	makeParams(values) {
		return {
			file_url: values.image,
		}
	},
	auto: false,
	onSuccess(data) {
		submissionFile.value = data
	},
})

const submissionResource = createDocumentResource({
	doctype: 'Discussion Submission',
	name: props.submissionName,
	onError(err) {
		toast.error(err.messages?.[0] || err)
	},
	auto: false,
	cache: [user.data?.name, props.discussionID],
})

watch(submissionResource, () => {
	if (submissionResource.doc) {
		if (submissionResource.doc.original_attachment) {
			imageResource.reload({
				image: submissionResource.doc.original_attachment,
			})
		}
		original_post.value = submissionResource.doc.original_post || ''
		console.log("Original Post: ", original_post.value)
		comments.value = submissionResource.doc.comments || ''
		const hasFile = Boolean(submissionFile.value)
		const hasOriginalPost = Boolean(original_post.value)

		if (submissionResource.isDirty) {
			isDirty.value = true
		} else if (!hasFile && !hasOriginalPost) {
			isDirty.value = true
		} else {
			isDirty.value = false
		}
	}
})


watch(submissionFile, () => {
	if (props.submissionName == 'new' && submissionFile.value) {
		isDirty.value = true
	}
})

watch(
	() => submissionResource.doc?.grade,
	(newGrade, oldGrade) => {
		if (newGrade !== oldGrade && submissionResource.doc) {
			submissionResource.doc.status = 'Graded'; // Automatically set status to "Graded"
			isDirty.value = true; // Mark the form as dirty to indicate unsaved changes
		}
	}
);

const submitDiscussion = () => {
	if (props.submissionName != 'new') {
		let evaluator =
			submissionResource.doc && submissionResource.doc.owner != user.data?.name
				? user.data?.name
				: null

		submissionResource.setValue.submit(
			{
				...submissionResource.doc,
				original_attachment: submissionFile.value?.file_url,
				evaluator: evaluator,
				comments: comments.value,
				original_post: original_post.value,

			},
			{
				onSuccess(data) {
					toast.success(__('Changed successfully'))
					isDirty.value = false;
					refreshDiscussionLists()
				},
			}
		)
	} else {
		addNewSubmission()
	}
}

const addNewSubmission = () => {
	newSubmission.submit(
		{},
		{
			onSuccess(data) {
				toast.success(__('Discussion submitted successfully'))
				if (router.currentRoute.value.name == 'DiscussionSubmission') {
					router.push({
						name: 'DiscussionSubmission',
						params: {
							discussionID: props.discussionID,
							submissionName: data.name,
						},
					})
				} else {
					markLessonProgress()
					router.go()
				}
				submissionResource.name = data.name
				isDirty.value = false;
				submissionResource.reload()
				refreshDiscussionLists()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const saveSubmission = (file) => {
	isDirty.value = true
	submissionFile.value = file
}

const markLessonProgress = () => {
	if (router.currentRoute.value.name == 'Lesson') {
		let courseName = router.currentRoute.value.params.courseName
		let chapterNumber = router.currentRoute.value.params.chapterNumber
		let lessonNumber = router.currentRoute.value.params.lessonNumber
		console.log("Chapter Number: ", chapterNumber)
		console.log("Lesson Number: ", lessonNumber)

		call('seminary.seminary.api.mark_lesson_progress', {
			course: courseName,
			chapter_number: chapterNumber,
			lesson_number: lessonNumber,
		})
	}
}

const getType = () => {
	return [
		'image/*',
		'.pdf',
		'.doc',
		'.docx',
		'.xml',
		'application/msword',
		'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	]
}

const validateFile = (file) => {
	const extension = file.name.split('.').pop()?.toLowerCase()
	const allowedExtensions = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xml']
	const isImage = file.type?.startsWith('image/')
	if (isImage) {
		return
	}
	if (!extension || !allowedExtensions.includes(extension)) {
		return __('Only images, PDF, or Word documents are allowed.')
	}
}

const removeSubmission = () => {
	isDirty.value = true
	submissionFile.value = null
}

const canGradeSubmission = computed(() => {
	return (
		(user.data?.is_moderator ||
			user.data?.is_evaluator ||
			user.data?.is_instructor) &&
		props.submissionName != 'new' &&
		router.currentRoute.value.name == 'DiscussionActivitySubmission'
	)
})

const canModifyDiscussion = computed(() => {
	return (
		!submissionResource.doc ||
		(submissionResource.doc?.owner == user.data?.name &&
			submissionResource.doc?.status == 'Not Graded')
	)
})

const submissionStatusOptions = computed(() => {
	return [
		{ label: 'Not Graded', value: 'Not Graded' },
		{ label: 'Graded', value: 'Graded' },
		{ label: 'Pass', value: 'Pass' },
		{ label: 'Fail', value: 'Fail' },
	]
})

const statusTheme = computed(() => {
	if (!submissionResource.doc) {
		return 'orange'
	} else if (submissionResource.doc.status == 'Pass' || submissionResource.doc.status == 'Graded') {
		return 'green'
	} else if (submissionResource.doc.status == 'Not Graded') {
		return 'blue'
	} else {
		return 'red'
	}
})

const fetchStudentGroups = () => {
	if (!router.currentRoute.value.params.courseName) {
		console.warn('Cannot fetch student groups: Missing course name.');
		return;
	}

	call('seminary.seminary.api.get_student_groups_simple', {
		course_name: router.currentRoute.value.params.courseName,
	})
		.then((response) => {
			studentGroups.value = response || [];
			console.log('Student groups fetched:', studentGroups.value);
		})
		.catch((error) => {
			console.error('Error fetching student groups:', error);
		});
};

const studentGroup = computed(() => {
	if (StudentData.loading) {
		return __('Loading...');
	}
	return Student.value?.student_group || __('No group assigned');
});

watch(
	() => StudentData.loading,
	(loading) => {
		if (!loading) {
			console.log('Student data loaded on watch:', StudentData.data);
		}
	}
);

watch(
	() => selectedGroupFilter.value,
	(newGroup) => {
		console.log('Selected group changed to:', newGroup);
		filteredDiscussions.value; // Trigger recomputation
	}
);

//watch for changes in all_discussions to recalculate filteredDiscussions
// watch(
//   () => all_discussions.data,
//   (newData) => {
// 	console.log('All discussions data changed:', newData);
// 	filteredDiscussions.value; // Trigger recomputation
//   }
// );

</script>
