<template v-if="discussionReady">
	<div v-if="discussion.doc" class="grid grid-cols-[65%,35%] h-full" :class="{ 'border rounded-lg': !showTitle }">
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
			<div v-html="discussion.doc.prompt"
				class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal">
			</div>

			<div v-if="
				all_discussions.data && (hasSavedSubmission || (!hasSavedSubmission && !post_before) || !isStudent)
			" class="flex-1 border-l p-5 overflow-y-auto h-[calc(100vh-3.2rem)]">
				<div v-if="!isStudent && studentGroups.length > 1" class="mb-4 mt-4">
					<label for="groupFilter" class="block text-sm font-medium text-gray-700">
						{{ __('Filter by Group') }}
					</label>
					<select id="groupFilter" v-model="selectedGroupFilter"
						class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md">
						<option value="all">{{ __('All Groups') }}</option>
						<option v-for="group in studentGroups" :key="group.student_group" :value="group.student_group">
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
						<a v-if="discussion.original_attachment" :href="discussion.original_attachment" target="_blank"
							class="text-blue-500 underline">
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
						<!-- This is the post below the discussion in the main area -->
						<LightEditor :id="'reply-saved-' + (editorKey[discussion.name])"
							:key="'reply-saved-' + (editorKey[discussion.name])" :content="discussion.new_reply || ''"
							:placeholder="__('Write a reply...')" :lazy="true"
							@change="(val) => { editorValues[discussion.name] = val }" />
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
									<Button variant="subtle" size="sm" @click="removeReplyAttachment(discussion.name)">
										{{ __('Remove') }}
									</Button>
								</div>
							</div>
							<Button variant="solid" @click="handleReplySubmit(discussion)">
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
			</div>
		</div>
		<!-- Right column wrapper -->
		<div class="p-5 overflow-y-auto h-[calc(100vh-3.2rem)]">
			<!-- Instructor Dashboard (only show when there are student submissions) -->
			<div v-if="isInstructorView && dashboardStats.submission_count > 0" class="mb-6">
				<h3 class="text-lg font-semibold mb-4 text-ink-gray-9">{{ __('Discussion Dashboard') }}</h3>
				<div class="grid grid-cols-2 gap-4 mb-4">
					<div class="border rounded-lg p-4 text-center">
						<div class="text-2xl font-bold text-ink-gray-9">{{ dashboardStats.submission_count }}</div>
						<div class="text-xs text-ink-gray-5 mt-1">{{ __('Students with Original Submissions') }}</div>
					</div>
					<div class="border rounded-lg p-4 text-center">
						<div class="text-2xl font-bold text-ink-gray-9">{{ dashboardStats.avg_replies }}</div>
						<div class="text-xs text-ink-gray-5 mt-1">{{ __('Average Number of Replies') }}</div>
					</div>
				</div>
				<router-link :to="{
					name: 'DiscussionActivitySubmissionCS',
					params: { courseName: props.courseName, discussionID: props.discussionID },
				}">
					<Button variant="solid" class="w-full">
						{{ __('Grade this Discussion') }}
					</Button>
				</router-link>
			</div>
			<!-- Edit link when no submissions yet -->
			<div v-else-if="isInstructorView" class="mb-6">
				<router-link :to="{
					name: 'DiscussionActivityForm',
					params: { discussionID: props.discussionID },
				}">
					<Button variant="outline" class="w-full">
						{{ __('Edit Discussion Activity') }}
					</Button>
				</router-link>
			</div>
			<!-- Instructor: Edit Course Assessments button (always available) -->
			<div v-if="isInstructorView" class="mb-6">
				<div v-if="!isGradedActivity"
					class="bg-blue-50 border border-blue-200 rounded-md p-3 mb-3 text-sm text-blue-800">
					{{ __('This Discussion Activity is currently not associated with a grading criteria.') }}
				</div>
				<router-link :to="{
					name: 'CourseAssessment',
					params: { courseName: props.courseName },
				}">
					<Button variant="outline" class="w-full">
						{{ __('Edit Course Assessments') }}
					</Button>
				</router-link>
			</div>
			<!-- Student Grade Display (only for graded activities) -->
			<div v-if="isStudent && isGradedActivity && submissionResource.doc?.status === 'Graded'"
				class="mb-4 p-4 border rounded-lg bg-surface-white">
				<div class="text-sm text-ink-gray-5">{{ __('Grade') }}</div>
				<div class="text-2xl font-bold text-ink-gray-9">{{ submissionResource.doc?.grade }}</div>
			</div>
			<!-- Grading Feedback Thread (only for graded activities) -->
			<div v-if="isStudent && isGradedActivity && (gradingComments.length > 0 || submissionResource.doc?.status === 'Graded')"
				class="mb-6 border rounded-lg p-4 bg-surface-white">
				<h3 class="text-md font-semibold mb-3 text-ink-gray-7">{{ __('Feedback') }}</h3>
				<div v-if="gradingComments.length" class="space-y-3 mb-4">
					<div v-for="c in gradingComments" :key="c.name" class="p-3 rounded-lg text-sm" :class="c.author === user.data?.name
						? 'bg-blue-50 border border-blue-200 ml-4'
						: 'bg-gray-50 border border-gray-200 mr-4'">
						<div class="flex items-center justify-between mb-1">
							<span class="font-medium text-ink-gray-7">{{ c.author_name }}</span>
							<span class="text-xs text-ink-gray-4">{{ formatDate(c.comment_dt) }}</span>
						</div>
						<div v-html="c.comment" class="prose-sm"></div>
					</div>
				</div>
				<div v-else class="text-sm text-ink-gray-4 mb-4">
					{{ __('No feedback yet.') }}
				</div>
				<LightEditor :id="'student-feedback-' + submissionResource.doc?.name"
					:key="'sf-' + submissionResource.doc?.name" ref="studentCommentEditor"
					:placeholder="__('Reply to feedback...')" @change="(val) => studentNewComment = val" />
				<Button variant="solid" size="sm" class="mt-2" @click="postStudentComment"
					:disabled="!studentNewComment || addStudentCommentResource.loading">
					{{ __('Send') }}
				</Button>
			</div>

			<div v-if="!hasSavedSubmission" class="text-md mb-4">
				<div class="flex flex-col">

					<div class="p-5">
						<div class="flex items-center justify-between mb-4">

							<div class="flex items-center space-x-2">
								<Badge v-if="isDirty" theme="orange">
									{{ __('Not Saved') }}
								</Badge>
								<Badge v-else-if="isGradedActivity && submissionResource.doc?.status" :theme="statusTheme" size="lg">
									{{ submissionResource.doc?.status }}
								</Badge>
								<Button variant="solid" @click="submitDiscussion()">
									{{ __('Save') }}
								</Button>
							</div>
						</div>

						<div v-if="!hasSavedSubmission" class="text-md mb-4">
							{{ __('Write your main post here') }}
							<RichTextEditor id="original-post" :content="original_post || ''"
								@change="(val) => { original_post = val; isDirty = true }" />

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
					{{ __('Your submission has been saved.') }}
					<br>

					{{ __('In this area, you can interact with replies to your submission')
					}}
				</div>
				<div v-for="submission in savedsubmission.data" :key="submission.name || submission.creation">
					<div class="font-semibold mb-2">
						{{ formatDate(submission.creation) }}
						<br>
						{{ __('Your Original Post') }}:
					</div>
					<div v-html="submission.original_post" class="text-sm"></div>

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
						<LightEditor :key="editorKey[submission.name]"
							:id="'original-post-' + (editorKey[submission.name])" :content="submission.new_reply || ''"
							@change="(val) => { editorValues[submission.name] = val }"
							:placeholder="__('Write a reply...')" :lazy="true" />
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
							<Button variant="solid" @click="handleReplySubmit(submission)">
								{{ __('Post Reply') }}
							</Button>
						</div>
					</div>
				</div>
			</div>

		</div>
		<!-- End right column wrapper -->
	</div>
	<div v-else class="p-5 text-center">
		{{ __('Loading discussion...') }}
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
	toast,
} from 'frappe-ui'
import { computed, inject, onMounted, onBeforeUnmount, ref, watch, toRaw } from 'vue'
import dayjsModule from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import { FileText, X } from 'lucide-vue-next'
import { getFileSize } from '@/utils'
import { useRouter } from 'vue-router'
import RichTextEditor from '@/components/RichTextEditor.vue'
import LightEditor from '@/components/LightEditor.vue'
import DiscussionModal from './Modals/DiscussionModal.vue'



let isReloading = false
const editorKey = ref({}); // This will hold unique keys for each editor instance
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
const isInstructorView = computed(() =>
	user.data?.is_moderator || user.data?.is_evaluator || user.data?.is_instructor
)
const studentGroups = ref([]);
const selectedGroupFilter = ref('all')
const Student = ref('');
const owner = computed(() => user.data?.name)
const dashboardStats = ref({ submission_count: null, avg_replies: null })
const showDiscussionModal = ref(false)
const editorValues = ref({})
const gradingComments = ref([])
const studentNewComment = ref('')
const studentCommentEditor = ref(null)



const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
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

// Check if this discussion is linked to a grading criteria
const gradingCriteriaResource = createResource({
	url: 'seminary.seminary.api.GradeableDiscussion',
	makeParams() {
		return {
			courseName: props.courseName,
			discussionID: props.discussionID,
		}
	},
	auto: true,
})
const isGradedActivity = computed(() => !!gradingCriteriaResource.data)

onMounted(() => {
	window.addEventListener('keydown', keyboardShortcut)
	reloadDiscussionLists()
	StudentData.reload()
	fetchStudentGroups()
	filteredDiscussions.value;
})

const saveReplyAttachment = (itemName, file) => {
	replyFiles.value = {
		...replyFiles.value,
		[itemName]: file,
	}
}

const discussionReady = computed(() => {
	return !!(props.courseName && props.discussionID && owner.value)
})
const removeReplyAttachment = (itemName) => {
	const { [itemName]: _removed, ...rest } = replyFiles.value
	replyFiles.value = rest
}

const keyboardShortcut = (e) => {
	if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
		submitDiscussion()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
	// Clear state to prevent stale data on remount
	gradingComments.value = []
	studentNewComment.value = ''
	studentCommentEditor.value?.clear()
	editorValues.value = {}
	editorKey.value = {}
	submissionResource.doc = null
	original_post.value = ''
	isDirty.value = false
	submissionFile.value = null
})

const discussion = createDocumentResource({
	doctype: 'Discussion Activity',
	name: props.discussionID,
	auto: true,
	onSuccess(data) {
		if (props.submissionName != 'new') {
			submissionResource.name = props.submissionName
			submissionResource.reload()
		}
		// Fetch dashboard stats for instructors
		dashboardResource.submit({
			course_name: props.courseName,
			discussion_id: props.discussionID,
		})
	},
})

const dashboardResource = createResource({
	url: 'seminary.seminary.api.get_discussion_dashboard',
	auto: false,
	onSuccess(data) {
		dashboardStats.value = data || { submission_count: 0, avg_replies: 0 }
	},
})

const post_before = computed(() => {
	return discussion.doc?.post_before
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
	const replyContent = editorValues.value[item.name]

	if (!replyContent || replyContent === '<p><br></p>') {
		toast.error(__('Please write a reply before posting.'))
		return
	}

	const attachment = replyFiles.value[item.name]
	const studentid = Student.value?.student || null
	const member_name = Student.value?.student_name || user.data?.full_name
	const reply_dt = getFrappeDateTime()

	replyResource.submit(
		{
			name: item.name,
			reply: replyContent,  // ← use editor value
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
				// Clear the editor after successful submit
				delete editorValues.value[item.name]
				editorKey.value[item.name] = Date.now(); // Update key to force re-render
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
			course_name: props.courseName,
			discussion_id: props.discussionID,
			member: user.data?.name,
		}
	},
	auto: false,
	onSuccess(data) {
		data?.forEach((discussion) => {
			if (discussion && typeof discussion.new_reply === 'undefined') {
				discussion.new_reply = ''
			}
		})

	},
})

//Get student data from user to avoid errors with instructor and get other fields

const StudentData = createResource({
	url: 'seminary.seminary.api.get_student_group',
	makeParams(values) {
		return {
			course_name: props.courseName,
			user: user.data?.name,
		}
	},
	auto: false,
	onSuccess(data) {
		Student.value = data
	}
})



// Fetch the saved discussion by the user if it exists
const savedsubmission = createResource({
	url: 'seminary.seminary.api.get_user_discussion_submission',
	makeParams(values) {
		return {
			course_name: props.courseName,
			discussion_id: props.discussionID,
			owner: user.data?.name,
		}
	},
	auto: false,
	onSuccess(data) {
	}
})

const hasSavedSubmission = computed(() =>
	Array.isArray(savedsubmission.data) && savedsubmission.data.length > 0
)


// When submissionName prop resolves late (parent fetches it async), sync the resource name
watch(
	() => props.submissionName,
	(newName) => {
		if (newName && newName !== 'new') {
			submissionResource.name = newName
			submissionResource.reload()
		}
	}
)

// Clear stale state when switching between different discussions
watch(
	() => props.discussionID,
	() => {
		gradingComments.value = []
		studentNewComment.value = ''
		studentCommentEditor.value?.clear()
		editorValues.value = {}
		editorKey.value = {}
		// Reset submission resource to avoid stale doc (grade, status, editor lock)
		submissionResource.name = props.submissionName || 'new'
		submissionResource.doc = null
		original_post.value = ''
		isDirty.value = false
		submissionFile.value = null
	}
)

// Watch for when all required data becomes available
watch(discussionReady, async (hasData) => {
	if (hasData) {
		await reloadDiscussionLists()
	}
})

const reloadDiscussionLists = async () => {
	if (isReloading) return  // ← PREVENT INFINITE LOOP
	isReloading = true

	try {
		await all_discussions.reload({
			course_name: props.courseName,
			discussion_id: props.discussionID,
		})
		await savedsubmission.reload({
			course_name: props.courseName,
			discussion_id: props.discussionID,
			owner: owner.value,
		})
	} catch (error) {
		console.error("Error reloading discussion lists:", error)
	} finally {
		isReloading = false
	}
}



const filteredDiscussions = computed(() => {
	let filter_discussions = toRaw(all_discussions.data)
	if (!filter_discussions) return []

	if (isStudent.value) {
		if (discussion.doc?.use_studentgroup) {
			return filter_discussions.filter(item =>
				item.student_group === studentGroup.value
			)
		}
		return filter_discussions
	} else {
		if (selectedGroupFilter.value !== 'all') {
			return filter_discussions.filter(item =>
				item.student_group === selectedGroupFilter.value
			)
		}
		return filter_discussions
	}
})


const refreshDiscussionLists = () => {
	reloadDiscussionLists()
	dashboardResource.submit({
		course_name: props.courseName,
		discussion_id: props.discussionID,
	})
}



const newSubmission = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		let doc = {
			doctype: 'Discussion Submission',
			disc_activity: props.discussionID,
			disc_title: discussion.doc?.discussion_name,
			member: user.data?.name,
			coursesc: props.courseName,
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
})

watch(submissionResource, () => {
	if (submissionResource.doc) {
		if (submissionResource.doc.original_attachment) {
			imageResource.reload({
				image: submissionResource.doc.original_attachment,
			})
		}
		original_post.value = submissionResource.doc.original_post || ''
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

		if (submissionResource.doc.name) {
			fetchGradingComments(submissionResource.doc.name)
		}
	}
})

// Grading comments (student view, only for graded activities)
const gradingCommentsResource = createResource({
	url: 'seminary.seminary.api.get_grading_comments',
	auto: false,
	onSuccess(data) {
		gradingComments.value = data || []
	},
})

const fetchGradingComments = (name) => {
	gradingCommentsResource.submit({ submission_name: name })
}

const addStudentCommentResource = createResource({
	url: 'seminary.seminary.api.add_grading_comment',
})

const postStudentComment = () => {
	if (!studentNewComment.value || !submissionResource.doc?.name) return
	addStudentCommentResource.submit(
		{
			submission_name: submissionResource.doc.name,
			comment: studentNewComment.value,
		},
		{
			onSuccess() {
				studentNewComment.value = ''
				studentCommentEditor.value?.clear()
				fetchGradingComments(submissionResource.doc.name)
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

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
		{ label: __('Not Graded'), value: 'Not Graded' },
		{ label: __('Graded'), value: 'Graded' },
		{ label: __('Pass'), value: 'Pass' },
		{ label: __('Fail'), value: 'Fail' },
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
	if (!props.courseName) {
		console.warn('Cannot fetch student groups: Missing course name.');
		return;
	}

	call('seminary.seminary.api.get_student_groups_simple', {
		course_name: props.courseName,
	})
		.then((response) => {
			studentGroups.value = response || [];
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
		}
	}
);

watch(
	() => selectedGroupFilter.value,
	(newGroup) => {
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
