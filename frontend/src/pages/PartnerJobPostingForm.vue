<template>
	<header class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<router-link :to="{ name: 'PartnerJobPostings' }" class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
			<ArrowLeft class="size-4" />{{ __('Job Postings') }}
		</router-link>
	</header>

	<div v-if="posting.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>

	<div v-else class="mx-auto w-full max-w-2xl px-4 py-6 sm:px-6">
		<h1 class="text-xl font-bold text-ink-gray-9">{{ name ? __('Edit posting') : __('New posting') }}</h1>
		<div class="mt-1 rounded-md bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3">
			{{ __('Saved postings are reviewed by seminary staff before they go live.') }}
		</div>

		<div class="mt-4 flex flex-col gap-4">
			<FormControl type="text" :label="__('Job title')" v-model="form.job_title" />

			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<FormControl type="select" :label="__('Employment type')" v-model="form.employment_type" :options="employmentOptions" />
				<FormControl type="select" :label="__('Position type')" v-model="form.position_type" :options="positionOptions" />
				<FormControl type="select" :label="__('Location')" v-model="form.location" :options="locationOptions" />
				<FormControl type="number" :label="__('Number of positions')" v-model="form.planned_vacancies" />
				<FormControl type="date" :label="__('Closes on')" v-model="form.closes_on" />
				<FormControl type="select" :label="__('Status')" v-model="form.status" :options="statusOptions" />
			</div>

			<div>
				<div class="mb-1 text-sm text-ink-gray-7">{{ __('Description') }}</div>
				<TextEditor :content="form.description" @change="(v) => (form.description = v)" :editable="true" :fixedMenu="true" :bubbleMenu="false"
					editorClass="prose-sm max-w-none rounded-b-md border-x border-b border-outline-gray-2 bg-surface-white px-2 py-2 min-h-[8rem] max-h-[20rem] overflow-y-auto text-ink-gray-8" />
			</div>
			<div>
				<div class="mb-1 text-sm text-ink-gray-7">{{ __('Qualifications') }}</div>
				<TextEditor :content="form.qualifications" @change="(v) => (form.qualifications = v)" :editable="true" :fixedMenu="true" :bubbleMenu="false"
					editorClass="prose-sm max-w-none rounded-b-md border-x border-b border-outline-gray-2 bg-surface-white px-2 py-2 min-h-[6rem] max-h-[16rem] overflow-y-auto text-ink-gray-8" />
			</div>

			<div v-if="skillTags.data?.length">
				<div class="mb-1 text-sm text-ink-gray-7">{{ __('Skills') }}</div>
				<div class="flex flex-wrap gap-1.5">
					<button v-for="tag in skillTags.data" :key="tag" type="button" @click="toggleSkill(tag)"
						class="rounded-full border px-2.5 py-1 text-xs transition"
						:class="form.skills.includes(tag) ? 'border-outline-blue-1 bg-surface-blue-2 text-ink-blue-3' : 'border-outline-gray-2 text-ink-gray-6 hover:border-outline-gray-3'">
						{{ tag }}
					</button>
				</div>
			</div>

			<div class="flex flex-col gap-2">
				<label class="flex items-center gap-2 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="form.open_students" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />{{ __('Open to students') }}
				</label>
				<label class="flex items-center gap-2 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="form.open_alumni" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />{{ __('Open to alumni') }}
				</label>
				<label class="flex items-center gap-2 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="form.require_doctrinal_alignment" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />
					{{ __('Require doctrinal agreement (needs a doctrinal statement on your profile)') }}
				</label>
			</div>

			<div class="flex items-center gap-2 pt-1">
				<Button variant="solid" :loading="save.loading" @click="onSave">{{ __('Save posting') }}</Button>
				<router-link :to="{ name: 'PartnerJobPostings' }" class="text-sm text-ink-gray-6 hover:text-ink-gray-8">{{ __('Cancel') }}</router-link>
			</div>
		</div>
	</div>
</template>

<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { computed } from 'vue'
import { createResource, Button, FormControl, TextEditor, toast } from 'frappe-ui'
import { ArrowLeft } from 'lucide-vue-next'
import { usePartnerOrg } from '@/composables/usePartnerOrg'

const props = defineProps({ name: { type: String, default: null } })
const router = useRouter()
const { activeOrg } = usePartnerOrg()

const employmentOptions = ['', 'Full-time', 'Part-time', 'Contract', 'Salary with fundraising', 'Volunteer'].map((v) => ({ label: v ? __(v) : '—', value: v }))
const positionOptions = ['', 'Pastoral / Preaching', 'Teaching / Education', 'Worship / Music', 'Youth & Children', 'Counseling / Care', 'Missions / Outreach', 'Administration / Operations', 'Facilities / Support', 'Other'].map((v) => ({ label: v ? __(v) : '—', value: v }))
const statusOptions = ['Open', 'Closed'].map((v) => ({ label: __(v), value: v }))

const form = reactive({
	job_title: '', description: '', qualifications: '', employment_type: '', position_type: '',
	location: '', planned_vacancies: 1, closes_on: '', status: 'Open',
	open_students: 0, open_alumni: 0, require_doctrinal_alignment: 0, skills: [],
})
const locationOptions = computed(() => [{ label: '—', value: '' }, ...((posting.data?.locations || []).map((l) => ({ label: l.location_name, value: l.name })))])

const skillTags = createResource({
	url: 'seminary.partner.portal.get_skill_tags',
	makeParams: () => ({ org: activeOrg.value }),
	auto: true,
})

const posting = createResource({
	url: 'seminary.partner.portal.get_job_posting',
	makeParams: () => ({ name: props.name || undefined, org: activeOrg.value }),
	auto: true,
	onSuccess(data) {
		for (const k of Object.keys(form)) {
			if (k === 'skills') form.skills = [...(data?.skills || [])]
			else if (data?.[k] !== undefined && data?.[k] !== null) form[k] = data[k]
		}
	},
})

function toggleSkill(tag) {
	const i = form.skills.indexOf(tag)
	if (i === -1) form.skills.push(tag)
	else form.skills.splice(i, 1)
}

const save = createResource({
	url: 'seminary.partner.portal.save_job_posting',
	makeParams: () => ({ name: props.name || undefined, values: { ...form }, org: activeOrg.value }),
	onSuccess() {
		toast.success(__('Posting saved — pending staff review.'))
		router.push({ name: 'PartnerJobPostings' })
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not save the posting.'))
	},
})
function onSave() {
	if (!form.job_title) {
		toast.error(__('Job title is required.'))
		return
	}
	if (!save.loading) save.submit()
}
</script>
