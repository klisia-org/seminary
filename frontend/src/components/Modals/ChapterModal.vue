<template>
	<Dialog
		v-model="show"
		:options="dialogOptions"
		:disableOutsideClickToClose="true"
	>
		<template #body-content>
			<div class="chapter-dialog space-y-4 text-base max-h-[70vh] overflow-y-auto">
				<FormControl label="Title" v-model="chapter.chapter_title" :required="true" />

				<!-- Competency-based sections only (ADR 065). This mapping is not
				     decoration: it drives when the self-assessment is offered and,
				     under a gating mode, what the chapter unlocks. -->
				<div v-if="isCbe">
					<FormControl
						type="select"
						:label="__('Competency delivered by this chapter')"
						:options="competencyOptions"
						v-model="chapter.course_competency"
					/>
					<p class="mt-1 text-sm text-ink-gray-5">
						{{ competencyHint }}
					</p>
					<SafeHtml
						v-if="chapter.course_competency && selectedCompetency?.statement"
						class="prose-sm mt-2 rounded-md bg-surface-gray-1 p-2 text-ink-gray-6"
						:html="selectedCompetency.statement"
					/>
				</div>

				<!-- Release date and prerequisites (decisions/107). Students
				     see a locked chapter greyed out with the reason. -->
				<section class="space-y-3 border-t border-outline-gray-2 pt-4" aria-labelledby="chapter-release-heading">
					<h3 id="chapter-release-heading" class="text-sm font-semibold text-ink-gray-8">
						{{ __('Release') }}
					</h3>
					<FormControl
						type="select"
						:label="__('Opens')"
						:options="releaseTypeOptions"
						v-model="chapter.release_type"
					/>
					<FormControl
						v-if="chapter.release_type === 'On a date'"
						type="datetime-local"
						:label="__('Opens on')"
						v-model="chapter.release_on"
					/>
					<FormControl
						v-if="chapter.release_type === 'Days after start'"
						type="number"
						:label="__('Days after start')"
						v-model="chapter.release_offset_days"
					/>
					<p v-if="releaseHint" class="text-sm text-ink-gray-5">{{ releaseHint }}</p>

					<div>
						<div class="text-sm font-medium text-ink-gray-8">{{ __('Prerequisites') }}</div>
						<p class="mt-1 text-sm text-ink-gray-5">
							{{ __('Students must meet every one before this chapter opens.') }}
						</p>
						<div
							v-for="(row, i) in chapter.prerequisites"
							:key="i"
							class="mt-2 flex flex-wrap items-end gap-2"
						>
							<FormControl
								type="select"
								class="w-40"
								:label="__('Requires')"
								:options="prerequisiteKinds"
								v-model="row.kind"
							/>
							<FormControl
								v-if="row.kind === 'Complete chapter'"
								type="select"
								class="min-w-48 flex-1"
								:label="__('Chapter')"
								:options="chapterOptions"
								v-model="row.chapter"
							/>
							<template v-else>
								<FormControl
									type="select"
									class="min-w-48 flex-1"
									:label="__('Quiz')"
									:options="quizOptions"
									v-model="row.quiz"
								/>
								<FormControl
									type="number"
									class="w-28"
									:label="__('Minimum %')"
									:placeholder="quizPassMark(row.quiz)"
									v-model="row.min_percentage"
								/>
							</template>
							<Button
								variant="ghost"
								:aria-label="__('Remove prerequisite')"
								@click="chapter.prerequisites.splice(i, 1)"
							>
								<template #icon><X class="h-4 w-4" aria-hidden="true" /></template>
							</Button>
						</div>
						<Button size="sm" class="mt-2" @click="addPrerequisite">
							{{ __('Add prerequisite') }}
						</Button>
					</div>
				</section>

				<!-- One student's own opening (decisions/107 §6). Only for a
				     saved chapter: an exception needs something to point at. -->
				<section
					v-if="props.chapterDetail"
					class="space-y-2 border-t border-outline-gray-2 pt-4"
					aria-labelledby="chapter-exceptions-heading"
				>
					<h3 id="chapter-exceptions-heading" class="text-sm font-semibold text-ink-gray-8">
						{{ __('Student exceptions') }}
					</h3>
					<p class="text-sm text-ink-gray-5">
						{{ __('Open this chapter earlier or later for one student, or waive its prerequisites. Saved straight away.') }}
					</p>
					<ul v-if="overrides.data?.overrides?.length" class="space-y-1">
						<li
							v-for="o in overrides.data.overrides"
							:key="o.name"
							class="flex items-start justify-between gap-2 rounded bg-surface-gray-1 p-2 text-sm"
						>
							<div>
								<div class="font-medium text-ink-gray-8">{{ o.student_name || o.student }}</div>
								<div class="text-ink-gray-6">
									<span v-if="o.open_from">{{ __('Opens {0}').format(formatWhen(o.open_from)) }}</span>
									<span v-if="o.open_from && o.waive_prerequisites"> · </span>
									<span v-if="o.waive_prerequisites">{{ __('Prerequisites waived') }}</span>
								</div>
								<div class="text-ink-gray-5">{{ o.reason }}</div>
							</div>
							<Button
								variant="ghost"
								:aria-label="__('Remove exception for {0}', [o.student_name || o.student])"
								@click="removeOverride(o.name)"
							>
								<template #icon><Trash2 class="h-4 w-4" aria-hidden="true" /></template>
							</Button>
						</li>
					</ul>
					<div class="space-y-2 rounded border border-outline-gray-2 p-2">
						<FormControl
							type="select"
							:label="__('Student')"
							:options="rosterOptions"
							v-model="newOverride.student"
						/>
						<FormControl
							type="datetime-local"
							:label="__('Opens on (optional)')"
							v-model="newOverride.open_from"
						/>
						<FormControl
							type="checkbox"
							:label="__('Waive prerequisites')"
							v-model="newOverride.waive_prerequisites"
						/>
						<p v-if="isCbe && newOverride.waive_prerequisites" class="text-sm text-ink-amber-3">
							{{ __('This also lifts the self-assessment lock for this student.') }}
						</p>
						<FormControl type="textarea" :label="__('Reason')" v-model="newOverride.reason" />
						<Button size="sm" :loading="saveOverride.loading" @click="addOverride">
							{{ __('Add exception') }}
						</Button>
					</div>
				</section>

				<Switch
					size="sm"
					:label="__('SCORM Package')"
					:description="
						__(
							'Enable this only if you want to upload a SCORM package as a chapter.'
						)
					"
					v-model="chapter.is_scorm_package"
				/>
				<div v-if="chapter.is_scorm_package">
					<!-- SmartFileUploader, not FileUploader (p009 §2.11). A real
					     SCORM export is routinely larger than the worker upload
					     ceiling, so the plain uploader simply fails on exactly
					     the packages this feature exists to play. This one sends
					     them straight to object storage and falls back to
					     /api/method/upload_file when the server says a direct
					     upload does not apply -- same slot contract, same
					     @success payload. -->
					<SmartFileUploader
						v-if="!chapter.scorm_package"
						:fileTypes="['.zip']"
						:validateFile="validateFile"
						@success="(file) => (chapter.scorm_package = file)"
					>
						<template v-slot="{ file, progress, uploading, openFileSelector }">
							<div class="mb-4 flex items-center gap-2">
								<Button @click="openFileSelector" :loading="uploading">
									{{
										uploading ? `Uploading ${progress}%` : 'Upload an zip file'
									}}
								</Button>
								<span v-if="uploadLimits.data?.max_upload_mb" class="text-sm text-ink-gray-5">
									{{ __('Max {0} MB').format(uploadLimits.data.max_upload_mb) }}
								</span>
							</div>
						</template>
					</SmartFileUploader>
					<div v-else class="">
						<div class="flex items-center">
							<div class="border rounded-md p-2 mr-2">
								<FileText class="h-5 w-5 stroke-1.5 text-ink-gray-7" />
							</div>
							<div class="flex flex-col">
								<span>
									{{ chapter.scorm_package.file_name }}
								</span>
								<span class="text-sm text-ink-gray-4 mt-1">
									{{ getFileSize(chapter.scorm_package.file_size) }}
								</span>
								<!-- Acceptance is asynchronous now: the chapter
								     saves, then a job unpacks the package and
								     builds one lesson per SCO. -->
								<span class="text-xs text-ink-gray-5 mt-1">
									{{ __('Unpacked after you save; its lessons appear when that finishes.') }}
								</span>
							</div>
							<X
								@click="() => (chapter.scorm_package = null)"
								class="bg-surface-gray-3 rounded-md cursor-pointer stroke-1.5 w-5 h-5 p-1 ml-4"
							/>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	Button,
	createResource,
	Dialog,
	FormControl,
	Switch,
	toast
} from 'frappe-ui'
import { computed, reactive, watch } from 'vue'
import { getFileSize, uploadLimits, validateFileSize, refiledMessage } from '@/utils/'
import { capture } from '@/telemetry'
import { FileText, Trash2, X } from 'lucide-vue-next'
import SmartFileUploader from '@/components/SmartFileUploader.vue'
import { useSettings } from '@/stores/settings'
import {createDialog} from '@/utils/dialogs'

const $dialog = createDialog

const show = defineModel()
const outline = defineModel('outline')
const settingsStore = useSettings()

const props = defineProps({
	course: {
		type: String,
		required: true,
	},
	chapterDetail: {
		type: Object,
	},
})

const defaultChapterState = () => ({
	chapter_title: '',
	is_scorm_package: 0,
	scorm_package: null,
	course_competency: '',
	release_type: 'Always open',
	release_on: '',
	release_offset_days: 0,
	prerequisites: [],
})

// Datetime fields travel as "YYYY-MM-DD HH:mm:ss"; the input wants
// "YYYY-MM-DDTHH:mm".
const toInput = (value) => (value ? String(value).slice(0, 16).replace(' ', 'T') : '')
const fromInput = (value) => (value ? `${value.replace('T', ' ')}:00` : null)
const formatWhen = (value) => (value ? String(value).slice(0, 16).replace('T', ' ') : '')

const releaseTypeOptions = [
	{ label: __('Always open'), value: 'Always open' },
	{ label: __('On a date'), value: 'On a date' },
	{ label: __('Days after the section starts'), value: 'Days after start' },
]
const prerequisiteKinds = [
	{ label: __('Complete a chapter'), value: 'Complete chapter' },
	{ label: __('Pass a quiz'), value: 'Pass quiz' },
]

const releaseOptions = createResource({
	url: 'seminary.seminary.content_release.get_release_options',
	params: { course: props.course },
	auto: false,
	onError: () => {},
})

const chapterOptions = computed(() => [
	{ label: __('Choose a chapter'), value: '' },
	...(releaseOptions.data?.chapters || [])
		.filter((c) => c.name !== props.chapterDetail?.name)
		.map((c) => ({ label: c.chapter_title, value: c.name })),
])
const quizOptions = computed(() => [
	{ label: __('Choose a quiz'), value: '' },
	...(releaseOptions.data?.quizzes || []).map((q) => ({ label: q.title || q.name, value: q.name })),
])
const quizPassMark = (quiz) => {
	const q = (releaseOptions.data?.quizzes || []).find((x) => x.name === quiz)
	return q?.passing_percentage ? String(q.passing_percentage) : __('Pass mark')
}

const releaseHint = computed(() => {
	if (chapter.release_type === 'Days after start') {
		return __('Counted from the section start date, or from each student’s enrolment in an open-ended section.')
	}
	if (chapter.release_type === 'On a date') {
		return __('When the course is copied to a new term, this date moves with the start date.')
	}
	return ''
})

const addPrerequisite = () => {
	chapter.prerequisites.push({ kind: 'Complete chapter', chapter: '', quiz: '', min_percentage: '' })
}

// Student exceptions save on their own, so they never wait on the chapter.
const overrides = createResource({
	url: 'seminary.seminary.content_release.get_chapter_overrides',
	makeParams: () => ({ chapter: props.chapterDetail?.name }),
	auto: false,
	onError: () => {},
})
const rosterOptions = computed(() => [
	{ label: __('Choose a student'), value: '' },
	...(overrides.data?.roster || []).map((r) => ({ label: r.student_name || r.student, value: r.student })),
])
const emptyOverride = () => ({ student: '', open_from: '', waive_prerequisites: false, reason: '' })
const newOverride = reactive(emptyOverride())

const saveOverride = createResource({
	url: 'seminary.seminary.content_release.save_chapter_override',
})
const deleteOverride = createResource({
	url: 'seminary.seminary.content_release.delete_chapter_override',
})

const addOverride = () => {
	saveOverride.submit(
		{
			data: {
				chapter: props.chapterDetail.name,
				student: newOverride.student,
				open_from: fromInput(newOverride.open_from),
				waive_prerequisites: newOverride.waive_prerequisites ? 1 : 0,
				reason: newOverride.reason,
			},
		},
		{
			onSuccess() {
				Object.assign(newOverride, emptyOverride())
				overrides.reload()
				toast.success(__('Exception added'))
			},
			onError(err) {
				toast.error(err.messages?.[0] || err.message || __('Could not add the exception'))
			},
		}
	)
}
const removeOverride = (name) => {
	deleteOverride.submit(
		{ name },
		{
			onSuccess() {
				overrides.reload()
				toast.success(__('Exception removed'))
			},
			onError(err) {
				toast.error(err.messages?.[0] || err.message || __('Could not remove the exception'))
			},
		}
	)
}

// Optional feature, gated the way the other competency surfaces are: an
// ordinary section never sees this resolve and the dialog is unchanged.
const competencyContext = createResource({
	url: 'seminary.seminary.cbe_api.get_competency_context',
	params: { course_schedule: props.course },
	auto: true,
	onError: () => {},
})

const isCbe = computed(() => !!competencyContext.data?.is_cbe)

// A competency belongs to one chapter, so the ones already spoken for by
// another chapter are not offered -- the server refuses them anyway, and a
// picker that lets you choose a value it will reject is worse than one that
// does not show it.
const competencyOptions = computed(() => {
	const mine = props.chapterDetail?.name
	const available = (competencyContext.data?.competencies || []).filter(
		(c) => !c.chapter || c.chapter === mine
	)
	return [
		{ label: __('None'), value: '' },
		...available.map((c) => ({ label: c.competency_name, value: c.name })),
	]
})

const selectedCompetency = computed(() =>
	(competencyContext.data?.competencies || []).find(
		(c) => c.name === chapter.course_competency
	)
)

const competencyHint = computed(() => {
	// The mode in force here, not the framework's default: a section may have
	// been given its own, and the dialog must describe what will actually happen.
	const mode = competencyContext.data?.effective_content_release
	if (mode === 'Chapter unlocks after previous competency self-assessed') {
		return __(
			'Students read this competency here, and the next mapped chapter opens once they have self-assessed it.'
		)
	}
	if (
		mode === 'Content open, activities locked until previous competency self-assessed'
	) {
		return __(
			'Students read this competency here, and the next mapped chapter’s graded work opens once they have self-assessed it.'
		)
	}
	return __(
		'Students read the competency and its descriptors here, and are prompted to assess their own growth in it.'
	)
})

const chapter = reactive(defaultChapterState())

const resetChapter = () => {
	Object.assign(chapter, defaultChapterState())
}

const chapterResource = createResource({
	url: 'seminary.seminary.api.upsert_chapter',
	makeParams(values) {
		return {
			chapter_title: chapter.chapter_title,
			course: props.course,
			is_scorm_package: chapter.is_scorm_package,
			scorm_package: chapter.scorm_package,
			name: props.chapterDetail?.name,
			// Only sent for a competency section, so a page that does not show
			// the field can never clear a mapping it knows nothing about.
			...(isCbe.value
				? { course_competency: chapter.course_competency || '' }
				: {}),
			release: {
				release_type: chapter.release_type || 'Always open',
				release_on: chapter.release_type === 'On a date' ? fromInput(chapter.release_on) : null,
				release_offset_days:
					chapter.release_type === 'Days after start' ? Number(chapter.release_offset_days) || 0 : 0,
				prerequisites: chapter.prerequisites
					.filter((r) => (r.kind === 'Complete chapter' ? r.chapter : r.quiz))
					.map((r) => ({
						kind: r.kind,
						chapter: r.kind === 'Complete chapter' ? r.chapter : null,
						quiz: r.kind === 'Pass quiz' ? r.quiz : null,
						min_percentage:
							r.kind === 'Pass quiz' && r.min_percentage !== '' ? Number(r.min_percentage) : null,
					})),
			},
		}
	},
})

const chapterReference = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Course Schedule Chapter Reference',
				chapter: values.name,
				parent: props.course,
				parenttype: 'Course Schedule',
				parentfield: 'chapters',
			},
		}
	},
})

const addChapter = async (close) => {
	chapterResource.submit(
		{},
		{
			validate() {
				return validateChapter()
			},
			onSuccess: (data) => {
				capture('chapter_created')
				chapterReference.submit(
					{ name: data.name },
					{
						onSuccess() {
							resetChapter()
							/* if (!settingsStore.onboardingDetails.data?.is_onboarded) {
							settingsStore.onboardingDetails.reload()
						} */
							outline.value.reload()
							toast.success(__('Chapter added successfully'))
							show.value = false
							close()
						},
						onError(err) {
							toast.error(err.messages?.[0] || err)
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

const validateChapter = () => {
	if (!chapter.chapter_title) {
		return __('Chapter Title is required')
	}
	if (chapter.is_scorm_package && !chapter.scorm_package) {
		return __('Please upload a SCORM package or uncheck the SCORM package option')
	}
}

const editChapter = (close) => {
	chapterResource.submit(
		{},
		{
			validate() {
				if (!chapter.chapter_title) {
					return __('Chapter Title is required')
				}
			},
			onSuccess(data) {
				show.value = false
				resetChapter()
				outline.value.reload()
				toast.success(__('Chapter updated successfully'))
				const refiled = refiledMessage(data?.__onload?.refiled)
				if (refiled) toast.info(refiled, { duration: 10 })
				close()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const populateChapter = (detail) => {
	if (!detail) {
		resetChapter()
		return
	}
	chapter.chapter_title = detail.chapter_title || ''
	chapter.is_scorm_package = detail.is_scorm_package || 0
	chapter.scorm_package = detail.scorm_package || null
	chapter.course_competency = detail.course_competency || ''
	const release = detail.release || {}
	chapter.release_type = release.release_type || 'Always open'
	chapter.release_on = toInput(release.release_on)
	chapter.release_offset_days = release.release_offset_days || 0
	chapter.prerequisites = (release.prerequisites || []).map((r) => ({
		kind: r.kind,
		chapter: r.chapter || '',
		quiz: r.quiz || '',
		min_percentage: r.min_percentage ?? '',
	}))
}

const initializeState = () => {
	if (props.chapterDetail) {
		populateChapter(props.chapterDetail)
	} else {
		resetChapter()
	}
}

const handleCancel = (close) => {
	show.value = false
	resetChapter()
	close?.()
}

watch(show, (value) => {
	if (value) {
		releaseOptions.reload()
		if (props.chapterDetail?.name) overrides.reload()
		Object.assign(newOverride, emptyOverride())
		initializeState()
	} else {
		resetChapter()
	}
})

watch(
	() => props.chapterDetail,
	(newChapter) => {
		if (show.value) {
			populateChapter(newChapter)
		}
	}
)

const validateFile = (file) => {
	let extension = file.name.split('.').pop().toLowerCase()
	if (extension !== 'zip') {
		return __('Only zip files are allowed')
	}
	return validateFileSize(file)
}

const dialogOptions = computed(() => ({
	title: props.chapterDetail ? __('Edit Chapter') : __('Add Chapter'),
	size: 'lg',
	actions: [
		{
			label: props.chapterDetail ? __('Edit') : __('Create'),
			variant: 'solid',
			onClick: (close) =>
				props.chapterDetail ? editChapter(close) : addChapter(close),
		},
		{
			label: __('Cancel'),
			variant: 'text',
			onClick: (close) => handleCancel(close),
		},
	],
}))
</script>
