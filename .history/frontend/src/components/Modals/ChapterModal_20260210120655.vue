<template>
	<Dialog
		v-model="show"
		:options="dialogOptions"
		:disableOutsideClickToClose="true"
	>
		<template #body-content>
			<div class="chapter-dialog space-y-4 text-base max-h-[70vh] overflow-y-auto">
				<FormControl label="Title" v-model="chapter.chapter_title" :required="true" />
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
							<div class="mb-4">
								<Button @click="openFileSelector" :loading="uploading">
									{{
										uploading ? `Uploading ${progress}%` : 'Upload an zip file'
									}}
								</Button>
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
import { getFileSize } from '@/utils/'
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
