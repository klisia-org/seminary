<template>
	<div class="rounded-md border border-outline-gray-2 p-3">
		<FileUploader
			:fileTypes="['image/*', 'video/*', 'audio/*', '.pdf']"
			:validateFile="validateFile"
			@success="(data) => addFile(data)"
		>
			<template #default="{ uploading, progress, openFileSelector }">
				<div class="flex items-center gap-2">
					<Button @click="openFileSelector" :loading="uploading">
						{{ uploading ? __('Uploading {0}%').format(progress) : __('Upload File') }}
					</Button>
					<span v-if="uploadLimits.data?.max_upload_mb" class="text-sm text-ink-gray-5">
						{{ __('Max {0} MB').format(uploadLimits.data.max_upload_mb) }}
					</span>
				</div>
			</template>
		</FileUploader>
	</div>
</template>
<script setup>
import { FileUploader, Button } from 'frappe-ui'
import { uploadLimits, validateFileSize } from '@/utils'

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
	let extension = file.name.split('.').pop().toLowerCase()
	if (!['jpg', 'jpeg', 'png', 'mp4', 'mov', 'mp3', 'pdf'].includes(extension)) {
		return 'Only image and video files are allowed.'
	}
	return validateFileSize(file)
}
</script>
