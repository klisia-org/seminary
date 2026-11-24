<template>
	<div class="rounded-md border border-outline-gray-2 p-3">
		<SmartFileUploader
			:fileTypes="LESSON_UPLOAD_ACCEPT"
			:validateFile="validateFile"
			@success="(data) => addFile(data)"
		>
			<template #default="{ uploading, progress, openFileSelector }">
				<div class="flex items-center gap-2">
					<Button @click="openFileSelector" :loading="uploading">
						{{ uploading ? __('Uploading {0}%').format(progress) : __('Upload File') }}
					</Button>
					<span v-if="maxUploadMb" class="text-sm text-ink-gray-5">
						{{ __('Max {0} MB').format(maxUploadMb) }}
					</span>
				</div>
			</template>
		</SmartFileUploader>
	</div>
</template>
<script setup>
import { computed } from 'vue'
import { Button } from 'frappe-ui'
import SmartFileUploader from '@/components/SmartFileUploader.vue'
import { effectiveUploadMb, uploadLimits, validateFileSize } from '@/utils'
import { LESSON_UPLOAD_ACCEPT, fileType } from '@/utils/mediaTypes'

// With object storage the browser uploads straight to it, so the ceiling here is
// the (much larger) direct one rather than Frappe's worker limit.
const maxUploadMb = computed(() => effectiveUploadMb())

const emit = defineEmits(['fileUploaded'])

const props = defineProps({
	onFileUploaded: {
		type: Function,
		required: true,
	},
})

const addFile = (file) => {
	props.onFileUploaded({
		file_url: file.file_url,
		file_type: file.file_type,
	})
}

const validateFile = (file) => {
	// The types the lesson plays or shows (decision 109 §2).
	if (!LESSON_UPLOAD_ACCEPT.includes(`.${fileType(file.name)}`)) {
		return __('This file type can\'t be played in a lesson. Upload a video (MP4, M4V, WebM, MOV, OGV), audio (MP3, M4A, AAC, WAV, OGG, Opus, FLAC), an image or a PDF.')
	}
	// The only call site on the direct path: `SmartFileUploader` sends qualifying
	// files straight to object storage, so they are bound by the direct ceiling
	// rather than the much smaller worker one.
	return validateFileSize(file, { allowDirect: true })
}
</script>
