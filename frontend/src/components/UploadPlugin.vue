<template>
	<div class="rounded-md border border-outline-gray-2 p-3">
		<SmartFileUploader
			:fileTypes="['image/*', 'video/*', 'audio/*', '.pdf']"
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
	let extension = file.name.split('.').pop().toLowerCase()
	if (!['jpg', 'jpeg', 'png', 'mp4', 'mov', 'mp3', 'pdf'].includes(extension)) {
		return 'Only image and video files are allowed.'
	}
	return validateFileSize(file)
}
</script>
