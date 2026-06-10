<template>
	<div v-if="assignment.data">

		<!-- Instructor View -->
		<div v-if="isInstructorView && !showTitle" class="space-y-6 p-5">
			<!-- Assignment Dashboard -->
			<div v-if="courseName">
					<h3 class="text-lg font-semibold mb-4 text-ink-gray-9">
						{{ __('Assignment') }}:
					</h3>
					<div v-html="assignment.data.question"
						class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal">
					</div>
				<h3 class="text-lg font-semibold mb-4 text-ink-gray-9">{{ __('Assignment Dashboard') }}</h3>
				<div v-if="assignmentDashboard.student_count > 0">
					<div class="border rounded-lg p-4 text-center">
						<div class="text-2xl font-bold text-ink-gray-9">{{ assignmentDashboard.student_count }}</div>
						<div class="text-xs text-ink-gray-5 mt-1">{{ __('Students Who Submitted') }}</div>
					</div>
					<router-link
						:to="{ name: 'AssignmentSubmissionCS', params: { courseName: courseName, assignmentID: props.assignmentID } }">
						<Button variant="solid" class="w-full mt-3">{{ __('Grade this Assignment') }}</Button>
					</router-link>
	
				</div>
				<div v-else class="text-sm text-ink-gray-5">
					{{ __('No students have submitted this assignment yet.') }}
					<!-- Edit Assignment only when no student has submitted -->
					<router-link :to="{ name: 'AssignmentForm', params: { assignmentID: props.assignmentID } }">
						<Button variant="solid" class="w-full mt-3">{{ __('Edit Assignment') }}</Button>
					</router-link>
				</div>
			</div>

			<!-- Grading criteria info + link -->
			<div v-if="courseName">
				<div v-if="!isGradedAssignment"
					class="bg-surface-blue-1 border border-outline-blue-1 rounded-md p-3 mb-3 text-sm text-ink-blue-2">
					{{ __('This assignment is currently not associated with a grading criteria.') }}
				</div>
				<router-link :to="{ name: 'CourseAssessment', params: { courseName: courseName } }">
					<Button variant="outline" class="w-full">{{ __('Edit Course Assessments') }}</Button>
				</router-link>
			</div>
		</div>

		<!-- Grading view: submission on the left, prof comments/grading on the right.
		     The AssignmentSubmission route is locked to instructors, so `showTitle`
		     alone implies the prof grading screen — no need to also check role flags. -->
		<div v-if="showTitle" class="grid grid-cols-[65%,35%] h-full">
			<!-- LEFT: student submission -->
			<div class="border-r p-5 overflow-y-auto h-[calc(100vh-3.2rem)]">
				<div class="text-lg font-semibold mb-3 text-ink-gray-9">
					<div v-if="submissionName === 'new'">
						{{ __('Submission by') }} {{ user.data?.full_name }}
					</div>
					<div v-else>
						{{ __('Submission by') }} {{ submissionResource.doc?.member_name }}
					</div>
				</div>
				<details class="mb-4">
					<summary class="cursor-pointer text-sm text-ink-gray-7 font-medium select-none">
						{{ __('Assignment Question') }}
					</summary>
					<div v-html="assignment.data.question"
						class="ProseMirror prose prose-sm max-w-none mt-2 prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 !whitespace-normal">
					</div>
				</details>
				<SubmissionViewer
					:submission="submissionResource.doc"
					:type="assignment.data?.type"
				/>
			</div>
			<!-- RIGHT: prof comments / grading panel -->
			<div class="p-5 overflow-y-auto h-[calc(100vh-3.2rem)]">
				<div class="flex items-center justify-between mb-4">
					<div class="font-semibold text-ink-gray-9">
						{{ __('Grading') }}
					</div>
					<div class="flex items-center space-x-2">
						<Badge v-if="isDirty" theme="orange">
							{{ __('Not Saved') }}
						</Badge>
						<Badge v-else-if="submissionResource.doc?.status" :theme="statusTheme" size="lg">
							{{ submissionResource.doc?.status }}
						</Badge>
						<Button variant="solid" @click="submitAssignment()">
							{{ __('Save') }}
						</Button>
					</div>
				</div>
				<div v-if="canGradeSubmission" class="space-y-4">
					<FormControl v-if="submissionResource.doc" v-model="submissionResource.doc.status"
						:label="__('Grading Status')" type="select" :options="submissionStatusOptions" />
					<FormControl v-if="submissionResource.doc" v-model="submissionResource.doc.grade"
						:label="__('Score')" type="number" />
					<div>
						<div class="text-sm text-ink-gray-5 mb-1">
							{{ __('Comments') }}
						</div>
						<RichTextEditor
							:id="'assignment-comments-' + (submissionName || 'new')"
							:content="comments || ''"
							:placeholder="__('Comments for the student…')"
							@change="(val) => { comments = val; isDirty = true }"
						/>
					</div>
					<div>
						<div class="text-sm text-ink-gray-5 mb-1">
							{{ __('Feedback file (optional)') }}
						</div>
						<FileUploader
							v-if="!commentAttachFile"
							@success="(file) => saveCommentAttach(file)"
						>
							<template #default="{ uploading, progress, openFileSelector }">
								<Button @click="openFileSelector" :loading="uploading" variant="outline">
									{{
										uploading
											? __('Uploading {0}%').format(progress)
											: __('Attach feedback file')
									}}
								</Button>
							</template>
						</FileUploader>
						<div v-else class="flex items-center text-ink-gray-7">
							<div class="border self-start rounded-md p-2 mr-2">
								<FileText class="h-5 w-5 stroke-1.5" />
							</div>
							<a :href="commentAttachFile.file_url" target="_blank"
								class="flex-1 min-w-0 !no-underline text-sm leading-5 break-all">
								{{ commentAttachFile.file_name || filenameFromUrl(commentAttachFile.file_url) }}
							</a>
							<X @click="removeCommentAttach()"
								class="bg-surface-gray-3 rounded-md cursor-pointer stroke-1.5 w-5 h-5 p-1 ml-3 shrink-0" />
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Student-side review: rendered submission + read-only comments thread,
		     mirroring the prof view. Mutually-exclusive `v-if` (not `v-else-if`)
		     so that an instructor in the lesson context can never accidentally
		     land here when the chain is interpreted oddly. -->
		<div
			v-if="!showTitle && !isInstructorView && hasSubmission && !editMode"
			class="p-5 h-full overflow-y-auto border rounded-lg"
		>
			<div class="flex items-center justify-between mb-4">
				<div class="text-lg font-semibold text-ink-gray-9">
					{{ __('Your Submission') }}
				</div>
				<div class="flex items-center space-x-2">
					<Badge
						v-if="submissionResource.doc?.grade != null && submissionResource.doc?.grade !== ''"
						theme="green"
						size="lg"
					>
						{{ __('Score') }}: {{ submissionResource.doc.grade }}
					</Badge>
					<Badge v-if="submissionResource.doc?.status" :theme="statusTheme" size="lg">
						{{ submissionResource.doc?.status }}
					</Badge>
					<Button v-if="canModifyAssignment" variant="outline" @click="editMode = true">
						{{ __('Edit submission') }}
					</Button>
				</div>
			</div>
			<!-- Prof's overall feedback (the legacy single `comments` field — distinct
			     from the anchored thread in the sidebar, which lives in
			     `comments_thread`). Shown when the prof has written something. -->
			<div
				v-if="submissionResource.doc?.comments"
				class="mb-4 p-3 bg-surface-blue-2 text-ink-blue-2 rounded-md"
			>
				<div class="text-sm text-ink-gray-5 font-medium mb-2">
					{{ __('Feedback from') }}: {{ submissionResource.doc?.evaluator || __('Evaluator') }}
				</div>
				<div class="leading-5 prose prose-sm max-w-none" v-html="submissionResource.doc.comments"></div>
			</div>
			<!-- Prof's attached feedback file (e.g. marked-up .docx with track changes). -->
			<a
				v-if="submissionResource.doc?.comment_attach"
				:href="submissionResource.doc.comment_attach"
				target="_blank"
				class="mb-4 border rounded-md p-3 bg-surface-white flex items-center text-ink-gray-7 !no-underline hover:bg-surface-gray-2 transition-colors"
			>
				<div class="border self-start rounded-md p-2 mr-3 shrink-0">
					<FileText class="h-5 w-5 stroke-1.5" />
				</div>
				<div class="flex-1 min-w-0">
					<div class="text-xs text-ink-gray-5 font-medium">
						{{ __('Feedback file') }}
					</div>
					<div class="text-sm text-ink-blue-2 underline break-all">
						{{ filenameFromUrl(submissionResource.doc.comment_attach) }}
					</div>
				</div>
			</a>
			<details class="mb-4">
				<summary class="cursor-pointer text-sm text-ink-gray-7 font-medium select-none">
					{{ __('Assignment Question') }}
				</summary>
				<div v-html="assignment.data.question"
					class="ProseMirror prose prose-sm max-w-none mt-2 prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 !whitespace-normal">
				</div>
			</details>
			<SubmissionViewer
				:submission="submissionResource.doc"
				:type="assignment.data?.type"
				:can-comment="false"
			/>
		</div>

		<!-- Student input view: question on the left, input form on the right.
		     Shown when the student has no submission yet OR clicked "Edit submission". -->
		<div
			v-if="!showTitle && !isInstructorView && (!hasSubmission || editMode)"
			class="grid grid-cols-[65%,35%] h-full border rounded-lg"
		>
			<div class="border-r p-5 overflow-y-auto h-[calc(100vh-3.2rem)]">
				<div class="text-sm text-ink-gray-7 font-medium mb-2">
					{{ __('Assignment') }}:
				</div>
				<div v-html="assignment.data.question"
					class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal">
				</div>
			</div>

			<div class="flex flex-col">
				<div class="p-5">
					<div class="flex items-center justify-between mb-4">
						<div class="font-semibold text-ink-gray-9">
							{{ __('Submission') }}
						</div>
						<div class="flex items-center space-x-2">
							<Badge v-if="isDirty" theme="orange">
								{{ __('Not Saved') }}
							</Badge>
							<Badge v-else-if="submissionResource.doc?.status" :theme="statusTheme" size="lg">
								{{ submissionResource.doc?.status }}
							</Badge>
							<Button v-if="editMode && hasSubmission" variant="subtle" @click="editMode = false">
								{{ __('Cancel') }}
							</Button>
							<Button variant="solid" @click="submitAssignment()">
								{{ __('Save') }}
							</Button>
						</div>
					</div>
					<div v-if="canGradeSubmission && portalDisciplinary && submissionResource.doc" class="mb-2">
						<Button variant="outline" theme="red" @click="showReportModal = true">
							{{ __('Report Disciplinary Incident for this Submission') }}
						</Button>
						<ReportDisciplinaryIncidentModal
							v-model="showReportModal"
							mode="assessment"
							:course="submissionResource.doc.course || courseName"
							:student="submissionResource.doc.student"
							:student-name="submissionResource.doc.member_name"
							:assessment="submissionResource.doc.course_assess"
							:assessment-name="assignment.data?.title"
						/>
					</div>
					<div v-if="
						submissionName != 'new' &&
						!['Pass', 'Fail', 'Graded'].includes(submissionResource.doc?.status) &&
						submissionResource.doc?.owner == user.data?.name
					" class="bg-surface-blue-2 text-ink-blue-2 p-3 rounded-md leading-5 text-sm mb-4">
						{{ __("You've successfully submitted the assignment.") }}
						{{
							__(
								"Once the moderator grades your submission, you'll find the details here."
							)
						}}
						{{ __('Feel free to make edits to your submission if needed, until it is graded.') }}
					</div>
					<div v-if="showUploader()">
						<div class="text-xs text-ink-gray-5 mt-1 mb-2">
							{{ __('Add your assignment as {0}').format(assignment.data.type) }}
						</div>
						<FileUploader v-if="!submissionFile" :fileTypes="getType()" :validateFile="validateFile"
							@success="(file) => saveSubmission(file)">
							<template #default="{ uploading, progress, openFileSelector }">
								<div class="flex items-center gap-2">
									<Button @click="openFileSelector" :loading="uploading">
										{{
											uploading
												? __('Uploading {0}%').format(progress)
												: __('Upload File')
										}}
									</Button>
									<span v-if="uploadLimits.data?.max_upload_mb" class="text-sm text-ink-gray-5">
										{{ __('Max {0} MB').format(uploadLimits.data.max_upload_mb) }}
									</span>
								</div>
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
								<X v-if="canModifyAssignment" @click="removeSubmission()"
									class="bg-surface-gray-3 rounded-md cursor-pointer stroke-1.5 w-5 h-5 p-1 ml-4" />
							</div>
						</div>
					</div>
					<div v-else-if="['URL', 'YouTube'].includes(assignment.data.type)">
						<div class="text-xs text-ink-gray-5 mb-1">
							{{ assignment.data.type === 'YouTube' ? __('Enter a YouTube link') : __('Enter a URL') }}
						</div>
						<FormControl v-model="answer" type="text" :readonly="!canModifyAssignment" />
					</div>
					<div v-else>
						<div class="text-sm mb-4">
							{{ __('Write your answer here') }}
						</div>
						<RichTextEditor
							:id="'assignment-answer-' + (submissionName || 'new')"
							:content="answer || ''"
							:placeholder="__('Write your answer here')"
							@change="(val) => (answer = val)"
						/>
					</div>

					<div v-if="
						user.data?.name == submissionResource.doc?.owner &&
						submissionResource.doc?.comments
					" class="mt-8 p-3 bg-surface-blue-2 text-ink-blue-2 rounded-md">
						<div class="text-sm text-ink-gray-5 font-medium mb-2">
							{{ __('Comments by') }}: {{ submissionResource.doc?.evaluator || __('Evaluator') }}
						</div>
						<div class="leading-5">
							<div v-html="submissionResource.doc.comments"></div>
						</div>
					</div>
				</div>
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
import { computed, inject, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { FileText, X } from 'lucide-vue-next'
import { getFileSize, uploadLimits, validateFileSize } from '@/utils'
import { useRouter } from 'vue-router'
import SubmissionViewer from '@/components/AssignmentViewers/SubmissionViewer.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import ReportDisciplinaryIncidentModal from '@/components/Modals/ReportDisciplinaryIncidentModal.vue'
import { usePortalDisciplinary } from '@/composables/usePortalDisciplinary'

const { portalDisciplinary } = usePortalDisciplinary()
const showReportModal = ref(false)
const submissionFile = ref(null)
const commentAttachFile = ref(null)
const answer = ref(null)
const comments = ref(null)
const router = useRouter()
const user = inject('$user')
const showTitle = router.currentRoute.value.name == 'AssignmentSubmission'
const isDirty = ref(false)
const editMode = ref(false)

const props = defineProps({
	assignmentID: {
		type: String,
		required: true,
	},
	submissionName: {
		type: String,
		default: 'new',
	},
})

onMounted(() => {
	window.addEventListener('keydown', keyboardShortcut)
	console.log('User: ', user.data)
})

const keyboardShortcut = (e) => {
	if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
		submitAssignment()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})

const assignment = createResource({
	url: 'frappe.client.get',
	params: {
		doctype: 'Assignment Activity',
		name: props.assignmentID,
	},
	auto: true,
	onSuccess(data) {
		if (props.submissionName != 'new') {
			submissionResource.reload()
		}
		if (isInstructorView.value && courseName.value && !showTitle) {
			assignmentDashboardResource.reload()
			gradingCriteriaResource.reload()
		}
	},
})

const newSubmission = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		let doc = {
			doctype: 'Assignment Submission',
			assignment: props.assignmentID,
			member: user.data?.name,
			course: router.currentRoute.value.params.courseName
		}
		if (showUploader()) {
			doc.assignment_attachment = submissionFile.value.file_url
		} else {
			doc.answer = answer.value
		}
		return {
			doc: doc,
		}
	},
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
	doctype: 'Assignment Submission',
	name: props.submissionName,
	onError(err) {
		toast.error(err.messages?.[0] || err)
	},
	auto: false,
	cache: [user.data?.name, props.assignmentID],
})

watch(submissionResource, () => {
	if (submissionResource.doc) {
		if (submissionResource.doc.assignment_attachment) {
			imageResource.reload({
				image: submissionResource.doc.assignment_attachment,
			})
		}
		if (submissionResource.doc.comment_attach) {
			call('seminary.seminary.api.get_file_info', {
				file_url: submissionResource.doc.comment_attach,
			}).then((info) => {
				commentAttachFile.value = info
			}).catch(() => {
				// fall back to a minimal stub so the UI can still render a download link
				commentAttachFile.value = {
					file_url: submissionResource.doc.comment_attach,
					file_name: filenameFromUrl(submissionResource.doc.comment_attach),
				}
			})
		} else {
			commentAttachFile.value = null
		}
		if (submissionResource.doc.answer) {
			answer.value = submissionResource.doc.answer
		}
		if (submissionResource.doc.comments) {
			comments.value = submissionResource.doc.comments
		}
		if (submissionResource.isDirty) {
			isDirty.value = true
		} else if (showUploader() && !submissionFile.value) {
			isDirty.value = true
		} else if (!showUploader() && !answer.value) {
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

// Auto-flip status to "Graded" when the instructor enters a grade — but
// NOT on initial load (oldGrade === undefined → newGrade = stored value
// would otherwise flip every student re-save to Graded), and only when the
// grading UI is actually visible (students never legitimately change grade).
watch(
	() => submissionResource.doc?.grade,
	(newGrade, oldGrade) => {
		if (
			canGradeSubmission.value &&
			oldGrade !== undefined &&
			newGrade !== oldGrade &&
			submissionResource.doc
		) {
			submissionResource.doc.status = 'Graded';
			isDirty.value = true;
		}
	}
);

const submitAssignment = () => {
	if (props.submissionName != 'new') {
		let evaluator =
			submissionResource.doc && submissionResource.doc.owner != user.data?.name
				? user.data?.name
				: null

		submissionResource.setValue.submit(
			{
				...submissionResource.doc,
				assignment_attachment: submissionFile.value?.file_url,
				evaluator: evaluator,
				comments: comments.value,
				answer: answer.value,

			},
			{
				onSuccess(data) {
					toast.success(__('Changed successfully'))
					isDirty.value = false;
					// Drop back to the read-only review of the saved submission.
					editMode.value = false;
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
				toast.success(__('Assignment submitted successfully'))
				if (router.currentRoute.value.name == 'AssignmentSubmission') {
					router.push({
						name: 'AssignmentSubmission',
						params: {
							assignmentID: props.assignmentID,
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

const saveCommentAttach = (file) => {
	isDirty.value = true
	commentAttachFile.value = file
	if (submissionResource.doc) {
		submissionResource.doc.comment_attach = file.file_url
	}
}

const removeCommentAttach = () => {
	isDirty.value = true
	commentAttachFile.value = null
	if (submissionResource.doc) {
		submissionResource.doc.comment_attach = null
	}
}

const filenameFromUrl = (url) =>
	(url || '').split('/').pop() || __('feedback file')

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
	const type = assignment.data?.type
	if (type == 'Image') {
		return ['image/*']
	} else if (type == 'Document') {
		return [
			'.doc',
			'.docx',
			'.xml',
			'application/msword',
			'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
		]
	} else if (type == 'PDF') {
		return ['.pdf']
	}
}

const validateFile = (file) => {
	let type = assignment.data?.type
	let extension = file.name.split('.').pop().toLowerCase()
	if (type == 'Image' && !['jpg', 'jpeg', 'png'].includes(extension)) {
		return __('Only image file is allowed.')
	} else if (
		type == 'Document' &&
		!['doc', 'docx', 'xml'].includes(extension)
	) {
		return __('Only document file is allowed.')
	} else if (type == 'PDF' && !['pdf'].includes(extension)) {
		return __('Only PDF file is allowed.')
	}
	return validateFileSize(file)
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
		router.currentRoute.value.name == 'AssignmentSubmission'
	)
})

// `hasSubmission` is true once the student has saved at least one submission.
// On first open AssignmentBlock passes 'new' until the resource finds an
// existing row; once it does, `props.submissionName` carries the real name.
const hasSubmission = computed(
	() =>
		!!props.submissionName &&
		props.submissionName !== 'new' &&
		!!submissionResource.doc?.name
)

const canModifyAssignment = computed(() => {
	if (!submissionResource.doc) return true
	if (submissionResource.doc.owner !== user.data?.name) return false
	if (submissionResource.doc.status !== 'Not Graded') return false
	// Any prof feedback that refers to the *current* submission state locks
	// further edits — otherwise the feedback would dangle on a stale version.
	// Lock applies on next page load (resource's fetched state is the truth).
	if (submissionResource.doc.comments) return false
	if (submissionResource.doc.comment_attach) return false
	if ((submissionResource.doc.comments_thread || []).length > 0) return false
	return true
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

const showUploader = () => {
	return ['PDF', 'Image', 'Document'].includes(assignment.data?.type)
}

// --- Instructor view: dashboard and grading shortcuts ---
const isInstructorView = computed(
	() => user.data?.is_moderator || user.data?.is_evaluator || user.data?.is_instructor
)
const courseName = computed(() => router.currentRoute.value.params.courseName)

const assignmentDashboard = ref({ student_count: 0 })

const assignmentDashboardResource = createResource({
	url: 'seminary.seminary.api.get_assignment_dashboard',
	makeParams() {
		return { course_name: courseName.value, assignment_id: props.assignmentID }
	},
	onSuccess(data) {
		assignmentDashboard.value = data || { student_count: 0 }
	},
})

const gradingCriteriaResource = createResource({
	url: 'seminary.seminary.api.GradeableAssignment',
	makeParams() {
		return { courseName: courseName.value, assignmentID: props.assignmentID }
	},
})
const isGradedAssignment = computed(() => !!gradingCriteriaResource.data)
</script>
