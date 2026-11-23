<template>
	<FileUploader
		fileTypes=".zip,.xml"
		:uploadArgs="{ private: 1 }"
		@success="(file) => importFile(file)"
	>
		<template #default="{ uploading, progress, openFileSelector }">
			<Button
				@click="openFileSelector"
				:loading="uploading || importing"
				:title="__('Questions exported from Canvas, Blackboard or Brightspace (QTI 1.2 or 2.1, .zip or .xml)')"
			>
				<template #prefix>
					<Upload class="w-4 h-4" />
				</template>
				{{ uploading ? __('Uploading {0}%').format(progress) : __('Import Questions') }}
			</Button>
		</template>
	</FileUploader>
	<Dialog v-model="showReport" :options="{ title: __('Questions imported'), size: 'lg' }">
		<template #body-content>
			<div class="space-y-4 text-base text-ink-gray-8">
				<p>
					{{ __('{0} of {1} questions were added.').format(report.created, report.found) }}
				</p>
				<div v-if="report.skipped.length">
					<div class="font-semibold mb-2">
						{{ __('Not imported; add these by hand') }}
					</div>
					<ul class="list-disc pl-5 space-y-1 text-sm">
						<li v-for="(s, i) in report.skipped" :key="i">
							{{ s.title }}: {{ s.reason }}
						</li>
					</ul>
				</div>
				<div v-if="report.notes.length">
					<div class="font-semibold mb-2">{{ __('Check these') }}</div>
					<ul class="list-disc pl-5 space-y-1 text-sm">
						<li v-for="(n, i) in report.notes" :key="i">{{ n.title }}: {{ n.note }}</li>
					</ul>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Button, Dialog, FileUploader, call, toast } from 'frappe-ui'
import { reactive, ref } from 'vue'
import { Upload } from 'lucide-vue-next'

const props = defineProps({
	doctype: { type: String, required: true },
	name: { type: String, required: true },
})
const emit = defineEmits(['imported'])

const importing = ref(false)
const showReport = ref(false)
const report = reactive({ created: 0, found: 0, skipped: [], notes: [] })

const importFile = (file) => {
	importing.value = true
	call('seminary.seminary.qti.import_questions', {
		doctype: props.doctype,
		name: props.name,
		file_url: file.file_url,
	})
		.then((data) => {
			Object.assign(report, data)
			showReport.value = true
			emit('imported')
		})
		.catch((err) => {
			toast.error(err.messages?.[0] || err.message || err)
		})
		.finally(() => {
			importing.value = false
		})
}
</script>
