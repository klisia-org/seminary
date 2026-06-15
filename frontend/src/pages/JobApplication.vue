<template>
	<header
		class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<router-link :to="{ name: 'JobOpening', params: { jobName } }"
			class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
			<ArrowLeft class="size-4" />
			{{ __('Back to opening') }}
		</router-link>
	</header>

	<div v-if="context.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>

	<div v-else-if="context.error" class="p-5 text-ink-red-4">
		{{ context.error.messages?.[0] || __('This job opening is not available.') }}
	</div>

	<div v-else-if="context.data" class="mx-auto w-full max-w-2xl px-4 py-6 text-ink-gray-8 sm:px-6">
		<h1 class="text-xl font-bold text-ink-gray-9">
			{{ __('Apply: {0}').format(opening.job_title) }}
		</h1>
		<div class="mt-1 text-sm text-ink-gray-6">{{ opening.organization?.organization_name }}</div>

		<!-- Can't apply: explain and offer to go back -->
		<div v-if="!opening.can_apply" class="mt-5">
			<div v-if="opening.already_applied"
				class="rounded-md bg-surface-green-2 px-3 py-2 text-sm text-ink-green-3">
				{{ __('You have already applied to this opening.') }}
			</div>
			<div v-else-if="!context.data.has_person"
				class="rounded-md bg-surface-amber-2 px-3 py-2 text-sm text-ink-amber-3">
				{{ __("Your profile isn't set up to apply yet. Please contact the registrar.") }}
			</div>
			<div v-else-if="opening.status !== 'Open'"
				class="rounded-md bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-6">
				{{ __('This opening is closed and no longer accepting applications.') }}
			</div>
			<div v-else class="rounded-md bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-6">
				{{ __('This opening is open to a specific audience and is not available to you.') }}
			</div>
		</div>

		<!-- Apply form -->
		<form v-else class="mt-5 flex flex-col gap-4" @submit.prevent="onSubmitClick">
			<!-- Saved-but-not-submitted banner -->
			<div v-if="savedAsDraft"
				class="flex flex-col gap-2 rounded-lg border border-outline-amber-1 bg-surface-amber-1 p-3 sm:flex-row sm:items-center sm:justify-between">
				<div class="text-sm text-ink-amber-3">
					{{ __('Your application is saved but not submitted.') }}
				</div>
				<Button variant="solid" :loading="submit.loading" @click="submitNow">
					{{ __('Submit now') }}
				</Button>
			</div>

			<!-- Who it goes to + how they'll reach you (updates live) -->
			<div class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-3">
				<div class="mb-1 text-xs font-medium uppercase tracking-wide text-ink-gray-5">
					{{ __('Applying as') }}
				</div>
				<div class="font-medium text-ink-gray-8">{{ applicant.full_name }}</div>
				<div class="mt-2 flex items-start gap-2 text-sm text-ink-gray-6">
					<Mail class="mt-0.5 size-4 shrink-0 text-ink-gray-5" />
					<div>
						<div>
							{{ __('{0} will receive your application and reach you at:').format(opening.organization?.organization_name || __('The organization')) }}
						</div>
						<div class="mt-0.5 font-medium text-ink-gray-8">
							{{ effectiveEmail }}<span v-if="effectivePhone"> &middot; {{ effectivePhone }}</span>
						</div>
					</div>
				</div>
			</div>

			<!-- Optional: use a different contact for applications (saved to profile) -->
			<details class="rounded-lg border border-outline-gray-2 bg-surface-white p-3">
				<summary class="cursor-pointer text-sm text-ink-gray-7">
					{{ __('Use a different email or phone for job applications') }}
				</summary>
				<div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
					<FormControl type="email" :label="__('Preferred email')" v-model="preferredEmail"
						:placeholder="applicant.primary_email || __('Leave blank to use your primary email')" />
					<FormControl type="text" :label="__('Preferred phone')" v-model="preferredPhone"
						:placeholder="applicant.primary_mobile || __('Leave blank to use your primary phone')" />
				</div>
				<div class="mt-1 text-xs text-ink-gray-5">{{ __('Saved to your profile and reused next time.') }}</div>
			</details>

			<!-- Cover letter -->
			<div>
				<div class="mb-1 text-sm text-ink-gray-7">
					{{ __('Cover Letter') }} <span class="text-ink-red-3">*</span>
				</div>
				<TextEditor :content="coverLetter" @change="(val) => (coverLetter = val)" :editable="true"
					:fixedMenu="true" :bubbleMenu="false"
					editorClass="prose-sm max-w-none rounded-b-md border-x border-b border-outline-gray-2 bg-surface-white px-2 py-2 min-h-[10rem] max-h-[24rem] overflow-y-auto text-ink-gray-8"
					:placeholder="__('Share how the Lord has prepared you and why you sense a fit for this role.')" />
			</div>

			<!-- Doctrinal alignment (only when the opening requires it) -->
			<div v-if="opening.require_doctrinal_alignment">
				<div class="mb-1 text-sm text-ink-gray-7">
					{{ __('Doctrinal alignment') }} <span class="text-ink-red-3">*</span>
				</div>
				<div v-if="opening.doctrinal_statement"
					class="rounded-md border border-outline-gray-2 bg-surface-gray-1 p-3">
					<div class="mb-1 text-xs font-medium uppercase tracking-wide text-ink-gray-5">
						{{ __("The organization's doctrinal statement") }}
					</div>
					<div class="prose-sm max-h-64 max-w-none overflow-y-auto text-ink-gray-7"
						v-html="opening.doctrinal_statement" />
				</div>
				<FormControl class="mt-2" type="select" :label="__('Your response')" v-model="doctrinalAlignment"
					:options="alignmentOptions" />
				<FormControl v-if="doctrinalAlignment && doctrinalAlignment !== FULL_AGREEMENT" class="mt-2"
					type="textarea" :label="__('Explain your points of disagreement or reservation')"
					v-model="alignmentExplanation" :rows="4" />
			</div>

			<!-- Résumé -->
			<div>
				<div class="mb-1 text-sm text-ink-gray-7">{{ __('Résumé') }}</div>
				<div class="flex flex-wrap items-center gap-2">
					<FileUploader :upload-args="{ folder: 'Home/Attachments', private: 1 }"
						:validate-file="validateResume" @success="onResumeUploaded">
						<template #default="{ uploading, progress, openFileSelector }">
							<Button :loading="uploading" @click="openFileSelector">
								{{ uploading ? __('Uploading {0}%').format(progress) : (resumeUrl ? __('Replace résumé')
									: __('Upload résumé')) }}
							</Button>
						</template>
					</FileUploader>
					<span v-if="resumeLabel" class="text-sm text-ink-gray-6">{{ resumeLabel }}</span>
				</div>
				<div class="mt-1 text-xs text-ink-gray-5">{{ __('PDF or Word document. Optional if a résumé is on your profile.') }}
				</div>
			</div>

			<div class="flex flex-wrap items-center gap-2 pt-1">
				<Button variant="solid" :loading="submit.loading" @click="onSubmitClick">
					{{ __('Submit application') }}
				</Button>
				<Button :loading="submit.loading" @click="saveDraft">
					{{ __('Save without submitting') }}
				</Button>
				<router-link :to="{ name: 'JobOpening', params: { jobName } }"
					class="text-sm text-ink-gray-6 hover:text-ink-gray-8">
					{{ __('Cancel') }}
				</router-link>
			</div>
		</form>
	</div>

	<!-- Prayerful confirmation before submitting -->
	<Dialog v-model="showPrayer" :options="{ title: __('Before you submit') }">
		<template #body-content>
			<p class="text-base text-ink-gray-7">
				{{ __('Have you prayed and felt God leading you this way?') }}
			</p>
			<div class="mt-4 flex flex-col gap-2">
				<Button variant="solid" :loading="submit.loading" @click="confirmSubmit">
					{{ __('Yes, submit.') }}
				</Button>
				<Button :loading="submit.loading" @click="saveDraftFromDialog">
					{{ __('No, save it as I seek guidance') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createResource, Button, Dialog, FormControl, TextEditor, FileUploader, toast } from 'frappe-ui'
import { ArrowLeft, Mail } from 'lucide-vue-next'
import { validateFileSize } from '@/utils'

const FULL_AGREEMENT = 'I agree completely, without reservations'
const ALIGNMENT_VALUES = [
	'I agree completely, without reservations',
	'I agree completely, with reservations',
	'I agree partially',
	'I disagree',
]

const props = defineProps({
	jobName: { type: String, required: true },
})

const router = useRouter()

const coverLetter = ref('')
const resumeUrl = ref('')
const uploadedName = ref('')
const preferredEmail = ref('')
const preferredPhone = ref('')
const doctrinalAlignment = ref('')
const alignmentExplanation = ref('')
const savedAsDraft = ref(false)
const doSubmit = ref(false)
const showPrayer = ref(false)

const context = createResource({
	url: 'seminary.partner.api.get_apply_context',
	makeParams: () => ({ name: props.jobName }),
	auto: true,
	onSuccess(data) {
		const a = data?.applicant || {}
		const d = data?.draft || null
		resumeUrl.value = d?.resume || a.resume || ''
		preferredEmail.value = a.preferred_application_email || ''
		preferredPhone.value = a.preferred_application_phone || ''
		if (d) {
			coverLetter.value = d.cover_letter || ''
			doctrinalAlignment.value = d.doctrinal_alignment || ''
			alignmentExplanation.value = d.alignment_explanation || ''
			savedAsDraft.value = true
		}
	},
})

const opening = computed(() => context.data?.opening || {})
const applicant = computed(() => context.data?.applicant || {})

const effectiveEmail = computed(() => (preferredEmail.value || '').trim() || applicant.value.primary_email || '')
const effectivePhone = computed(() => (preferredPhone.value || '').trim() || applicant.value.primary_mobile || '')

const alignmentOptions = computed(() => [
	{ label: __('Select your response'), value: '' },
	...ALIGNMENT_VALUES.map((v) => ({ label: __(v), value: v })),
])

const resumeLabel = computed(() => {
	if (uploadedName.value) return uploadedName.value
	if (!resumeUrl.value) return ''
	if (resumeUrl.value === applicant.value?.resume && applicant.value?.resume_name) {
		return __('On your profile: {0}').format(applicant.value.resume_name)
	}
	return resumeUrl.value.split('/').pop()
})

const submit = createResource({
	url: 'seminary.partner.api.apply_to_job',
	makeParams: () => ({
		job_opening: props.jobName,
		cover_letter: coverLetter.value,
		resume: resumeUrl.value || '',
		preferred_email: preferredEmail.value || '',
		preferred_phone: preferredPhone.value || '',
		doctrinal_alignment: doctrinalAlignment.value || '',
		alignment_explanation: alignmentExplanation.value || '',
		submit: doSubmit.value ? '1' : '0',
	}),
	onSuccess(data) {
		showPrayer.value = false
		if (data?.submitted) {
			toast.success(__('Your application has been submitted.'))
			router.push({ name: 'JobOpening', params: { jobName: props.jobName } })
		} else {
			savedAsDraft.value = true
			toast.success(__('Saved. Submit when you are ready.'))
		}
	},
	onError(err) {
		showPrayer.value = false
		toast.error(err.messages?.[0] || __('Could not save your application.'))
	},
})

function stripHtml(html) {
	return (html || '').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()
}

function validateForSubmit() {
	if (!stripHtml(coverLetter.value)) {
		toast.error(__('Please write a cover letter before submitting.'))
		return false
	}
	if (opening.value.require_doctrinal_alignment) {
		if (!doctrinalAlignment.value) {
			toast.error(__("Please share your response to the organization's doctrinal statement."))
			return false
		}
		if (doctrinalAlignment.value !== FULL_AGREEMENT && !alignmentExplanation.value.trim()) {
			toast.error(__('Please explain your points of disagreement or reservation.'))
			return false
		}
	}
	return true
}

function onSubmitClick() {
	if (submit.loading) return
	showPrayer.value = true
}

function confirmSubmit() {
	if (!validateForSubmit()) {
		showPrayer.value = false
		return
	}
	doSubmit.value = true
	submit.submit()
}

function saveDraftFromDialog() {
	doSubmit.value = false
	submit.submit()
}

function saveDraft() {
	if (submit.loading) return
	doSubmit.value = false
	submit.submit()
}

function submitNow() {
	if (submit.loading) return
	if (!validateForSubmit()) return
	doSubmit.value = true
	submit.submit()
}

function onResumeUploaded(file) {
	resumeUrl.value = file.file_url
	uploadedName.value = file.file_name || file.name || ''
}

function validateResume(file) {
	const ext = (file.name.split('.').pop() || '').toLowerCase()
	if (!['pdf', 'doc', 'docx'].includes(ext)) {
		return __('Please upload a PDF or Word document.')
	}
	return validateFileSize(file)
}
</script>
