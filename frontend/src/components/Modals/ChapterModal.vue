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
					<div
						v-if="chapter.course_competency && selectedCompetency?.statement"
						class="prose-sm mt-2 rounded-md bg-surface-gray-1 p-2 text-ink-gray-6"
						v-html="selectedCompetency.statement"
					/>
				</div>

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
					<FileUploader
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
					</FileUploader>
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
	FileUploader,
	FormControl,
	Switch,
	toast
} from 'frappe-ui'
import { computed, reactive, watch } from 'vue'
import { getFileSize, uploadLimits, validateFileSize } from '@/utils/'
import { capture } from '@/telemetry'
import { FileText, X } from 'lucide-vue-next'
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
})

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
			onSuccess() {
				show.value = false
				resetChapter()
				outline.value.reload()
				toast.success(__('Chapter updated successfully'))
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
