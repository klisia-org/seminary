<template>
	<div class="flex flex-col gap-4">
		<div>
			<p class="text-sm font-semibold text-ink-gray-7">{{ __('Career / Job Board') }}</p>
			<p class="text-xs text-ink-gray-5">
				{{ __('Used to prefill your job applications. Visible to organizations only when you apply.') }}
			</p>
		</div>

		<div v-if="!loaded" class="text-sm text-ink-gray-5">{{ __('Loading...') }}</div>

		<div
			v-else-if="!hasPerson"
			class="rounded-md bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3"
		>
			{{ __("Your profile isn't set up for the job board yet. Please contact the registrar.") }}
		</div>

		<template v-else>
			<!-- Skills -->
			<div>
				<label class="mb-1 block text-xs font-medium text-ink-gray-6">{{ __('Skills') }}</label>
				<div v-if="form.skills.length" class="mb-2 flex flex-wrap gap-1.5">
					<span
						v-for="tag in form.skills"
						:key="tag"
						class="inline-flex items-center gap-1 rounded-full bg-surface-gray-2 px-2.5 py-1 text-sm text-ink-gray-8"
					>
						{{ tag }}
						<button type="button" class="text-ink-gray-5 hover:text-ink-gray-8" @click="removeSkill(tag)">
							<X class="size-3.5" />
						</button>
					</span>
				</div>
				<select
					class="field-input"
					:value="''"
					@change="addSkill($event.target.value); $event.target.value = ''"
				>
					<option value="">{{ availableSkills.length ? __('Add a skill...') : __('No more skills to add') }}</option>
					<option v-for="opt in availableSkills" :key="opt.name" :value="opt.name">
						{{ opt.category ? `${opt.name} — ${opt.category}` : opt.name }}
					</option>
				</select>
			</div>

			<!-- Résumé -->
			<div>
				<label class="mb-1 block text-xs font-medium text-ink-gray-6">{{ __('Résumé') }}</label>
				<div class="flex flex-wrap items-center gap-2">
					<FileUploader
						:upload-args="{ folder: 'Home/Attachments', private: 1 }"
						:validate-file="validateResume"
						@success="onResumeUploaded"
					>
						<template #default="{ uploading, progress, openFileSelector }">
							<Button :loading="uploading" @click="openFileSelector">
								{{ uploading ? __('Uploading {0}%').format(progress) : (form.resume ? __('Replace résumé') : __('Upload résumé')) }}
							</Button>
						</template>
					</FileUploader>
					<span v-if="resumeLabel" class="text-sm text-ink-gray-6">{{ resumeLabel }}</span>
					<button v-if="form.resume" type="button" class="text-sm text-ink-red-4 hover:underline" @click="clearResume">
						{{ __('Remove') }}
					</button>
				</div>
				<p class="mt-1 text-xs text-ink-gray-5">{{ __('PDF or Word document.') }}</p>
			</div>

			<!-- Preferred application contact -->
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<div>
					<label class="mb-1 block text-xs font-medium text-ink-gray-6">{{ __('Preferred email for applications') }}</label>
					<input
						v-model="form.preferred_application_email"
						type="email"
						class="field-input"
						:placeholder="__('Leave blank to use your primary email')"
					/>
				</div>
				<div>
					<label class="mb-1 block text-xs font-medium text-ink-gray-6">{{ __('Preferred phone for applications') }}</label>
					<input
						v-model="form.preferred_application_phone"
						type="text"
						class="field-input"
						:placeholder="__('Leave blank to use your primary phone')"
					/>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { createResource, Button, FileUploader, toast } from 'frappe-ui'
import { X } from 'lucide-vue-next'
import { validateFileSize } from '@/utils'

const FIELDS = ['resume', 'preferred_application_email', 'preferred_application_phone']

const loaded = ref(false)
const hasPerson = ref(false)
const uploadedName = ref('')
const profileResumeName = ref('')
const skillOptions = ref([])

const form = reactive({
	skills: [],
	resume: '',
	preferred_application_email: '',
	preferred_application_phone: '',
})
let snapshot = serialize()

function serialize() {
	return JSON.stringify({ ...form, skills: [...form.skills] })
}

// Only "real" edits count: clean (or no-Person) forms contribute nothing to the
// parent's combined dirty/save, so the shared Save button stays accurate.
const dirty = computed(() => hasPerson.value && serialize() !== snapshot)

const availableSkills = computed(() =>
	skillOptions.value.filter((opt) => !form.skills.includes(opt.name))
)

const resumeLabel = computed(() => {
	if (uploadedName.value) return uploadedName.value
	if (!form.resume) return ''
	return profileResumeName.value || form.resume.split('/').pop()
})

createResource({
	url: 'seminary.partner.api.list_skill_tags',
	auto: true,
	onSuccess(data) {
		skillOptions.value = data || []
	},
})

createResource({
	url: 'seminary.partner.api.get_my_career_profile',
	auto: true,
	onSuccess(data) {
		hasPerson.value = data !== null
		if (data) applyData(data)
		loaded.value = true
	},
	onError() {
		loaded.value = true
	},
})

function applyData(data) {
	form.skills = [...(data.skills || [])]
	for (const key of FIELDS) form[key] = data[key] ?? ''
	profileResumeName.value = data.resume_name || ''
	uploadedName.value = ''
	snapshot = serialize()
}

const saveResource = createResource({
	url: 'seminary.partner.api.update_my_career_profile',
	onSuccess(data) {
		applyData(data)
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not save your career details.'))
	},
})

// Driven by the parent form's single Save button. Resolves immediately when
// there is nothing to save so it composes cleanly with Promise.all.
function save() {
	if (!dirty.value) return Promise.resolve()
	return saveResource.submit({
		skills: form.skills,
		resume: form.resume || '',
		preferred_application_email: form.preferred_application_email || '',
		preferred_application_phone: form.preferred_application_phone || '',
	})
}

defineExpose({ save, dirty })

function addSkill(name) {
	if (name && !form.skills.includes(name)) form.skills.push(name)
}

function removeSkill(name) {
	form.skills = form.skills.filter((s) => s !== name)
}

function onResumeUploaded(file) {
	form.resume = file.file_url
	uploadedName.value = file.file_name || file.name || ''
	profileResumeName.value = ''
}

function clearResume() {
	form.resume = ''
	uploadedName.value = ''
	profileResumeName.value = ''
}

function validateResume(file) {
	const ext = (file.name.split('.').pop() || '').toLowerCase()
	if (!['pdf', 'doc', 'docx'].includes(ext)) {
		return __('Please upload a PDF or Word document.')
	}
	return validateFileSize(file)
}
</script>

<style scoped>
.field-input {
	@apply block w-full rounded-md border border-outline-gray-2 bg-surface-white px-3 py-1.5 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none;
}
</style>
