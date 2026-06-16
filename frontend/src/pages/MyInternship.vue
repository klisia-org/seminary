<template>
	<header class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<router-link :to="{ name: 'MyInternships' }" class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
			<ArrowLeft class="size-4" />{{ __('My Internships') }}
		</router-link>
	</header>

	<div v-if="info.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="info.error" class="p-5 text-ink-red-4">{{ info.error.messages?.[0] || __('Not authorized.') }}</div>

	<div v-else-if="info.data" class="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
		<div class="flex flex-wrap items-center gap-2">
			<h1 class="text-xl font-bold text-ink-gray-9">{{ info.data.title }}</h1>
			<Badge :theme="statusTheme(info.data.status)" variant="subtle">{{ __(info.data.status) }}</Badge>
		</div>
		<div class="mt-1 text-sm text-ink-gray-5">
			{{ info.data.organization_name }} &middot; {{ __('{0} / {1} hours logged').format(info.data.total_hours_logged || 0, info.data.hours_target || 0) }}
		</div>

		<!-- Requirements -->
		<section v-if="info.data.requirements?.length" class="mt-6">
			<h2 class="mb-3 text-lg font-semibold text-ink-gray-8">{{ __('Your requirements') }}</h2>
			<div class="flex flex-col gap-3">
				<div v-for="req in info.data.requirements" :key="req.name" class="rounded-md border border-outline-gray-2 p-3">
					<div class="flex items-center justify-between gap-2">
						<span class="font-medium text-ink-gray-8">{{ req.title }}</span>
						<Badge :theme="reqTheme(req.status)" variant="subtle">{{ __(req.status) }}</Badge>
					</div>
					<div v-if="req.due_date" class="text-xs text-ink-gray-5">{{ __('Due {0}').format(req.due_date) }}</div>
					<div v-if="req.student_instructions" class="prose prose-sm mt-1 max-w-none text-ink-gray-7" v-html="req.student_instructions" />
					<a v-if="req.submit_template" :href="req.submit_template" target="_blank" class="mt-1 inline-block text-sm text-ink-blue-6 hover:underline">{{ __('Download form') }}</a>

					<div v-if="!['Completed', 'Waived'].includes(req.status)" class="mt-2">
						<FormControl v-if="req.student_submission_type === 'Text'" type="textarea" :label="req.student_label" v-model="req.student_submission_value" />
						<FormControl v-else-if="req.student_submission_type === 'Link'" type="text" :label="req.student_label || __('Link')" v-model="req.student_submission_value" />
						<label v-else-if="req.student_submission_type === 'Acknowledgement'" class="flex items-center gap-2 text-sm text-ink-gray-7">
							<input type="checkbox" v-model="req.student_acknowledged" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />{{ req.student_label || __('I acknowledge') }}
						</label>
						<div v-else-if="req.student_submission_type === 'Attachment'" class="flex items-center gap-2">
							<a v-if="req.student_attachment" :href="req.student_attachment" target="_blank" class="text-sm text-ink-blue-6 hover:underline">{{ __('Current file') }}</a>
							<FileUploader @success="(file) => onUpload(req, file)">
								<template #default="{ openFileSelector, uploading }">
									<Button variant="outline" :loading="uploading" @click="openFileSelector">{{ req.student_attachment ? __('Replace') : __('Upload') }}</Button>
								</template>
							</FileUploader>
						</div>
						<div class="mt-2">
							<Button variant="subtle" :loading="savingReq === req.name" @click="saveReq(req)">{{ __('Save') }}</Button>
						</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Placements -->
		<section class="mt-6">
			<h2 class="mb-3 text-lg font-semibold text-ink-gray-8">{{ __('Placements') }}</h2>
			<div v-if="!info.data.placements?.length" class="text-sm text-ink-gray-5">{{ __('A placement is set up once you are accepted.') }}</div>
			<div v-else class="flex flex-col gap-4">
				<StudentPlacementCard v-for="p in info.data.placements" :key="p.name" :placement="p" :hours-tracking="info.data.hours_tracking" />
			</div>
		</section>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import { createResource, Badge, Button, FormControl, FileUploader, toast } from 'frappe-ui'
import { ArrowLeft } from 'lucide-vue-next'
import StudentPlacementCard from '@/components/StudentPlacementCard.vue'

const props = defineProps({ name: { type: String, required: true } })

const info = createResource({
	url: 'seminary.partner.internship_api.get_my_internship',
	makeParams: () => ({ name: props.name }),
	auto: true,
})

const savingReq = ref(null)
const saveRes = createResource({ url: 'seminary.partner.internship_api.save_requirement_student' })
function saveReq(req) {
	savingReq.value = req.name
	saveRes.submit(
		{ name: req.name, values: { student_submission_value: req.student_submission_value, student_attachment: req.student_attachment, student_acknowledged: req.student_acknowledged } },
		{
			onSuccess: () => { savingReq.value = null; toast.success(__('Saved.')); info.reload() },
			onError: (e) => { savingReq.value = null; toast.error(e.messages?.[0] || __('Could not save.')) },
		},
	)
}
function onUpload(req, file) {
	req.student_attachment = file.file_url
	saveReq(req)
}

function statusTheme(s) {
	if (['Accepted', 'Active', 'Completed'].includes(s)) return 'green'
	if (['Rejected', 'Withdrawn'].includes(s)) return 'red'
	if (s === 'Under Review' || s === 'Submitted') return 'blue'
	return 'gray'
}
function reqTheme(s) {
	if (s === 'Completed') return 'green'
	if (s === 'Waived') return 'gray'
	if (s === 'Submitted' || s === 'In Progress') return 'blue'
	return 'gray'
}
</script>
