<template>
	<header class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<router-link :to="{ name: 'PartnerInternshipPostings' }" class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
			<ArrowLeft class="size-4" />{{ __('Internships') }}
		</router-link>
	</header>

	<div v-if="posting.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>

	<div v-else class="mx-auto w-full max-w-2xl px-4 py-6 sm:px-6">
		<h1 class="text-xl font-bold text-ink-gray-9">{{ name ? __('Edit internship') : __('New internship') }}</h1>
		<div class="mt-1 rounded-md bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3">
			{{ __('Saved internships are reviewed by seminary staff before they go live.') }}
		</div>

		<div class="mt-4 flex flex-col gap-4">
			<FormControl type="text" :label="__('Title')" v-model="form.title" />

			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<FormControl type="select" :label="__('Internship type')" v-model="form.internship_type" :options="typeOptions" />
				<FormControl type="select" :label="__('Acceptance')" v-model="form.acceptance_mode" :options="acceptanceOptions" />
				<FormControl type="select" :label="__('Location')" v-model="form.location" :options="locationOptions" />
				<FormControl type="select" :label="__('Default supervisor')" v-model="form.default_site_supervisor" :options="supervisorOptions" />
				<FormControl type="number" :label="__('Number of placements')" v-model="form.planned_placements" />
				<FormControl type="number" :label="__('Minimum hours / week')" v-model="form.min_hours_per_week" />
				<FormControl type="select" :label="__('Status')" v-model="form.status" :options="statusOptions" />
			</div>

			<div class="flex flex-col gap-2 rounded-md border border-outline-gray-2 p-3">
				<label class="flex items-center gap-2 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="form.flexible_dates" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />{{ __('Flexible dates') }}
				</label>
				<div v-if="!form.flexible_dates" class="grid grid-cols-1 gap-3 sm:grid-cols-2">
					<FormControl type="date" :label="__('Preferred start')" v-model="form.preferred_start" />
					<FormControl type="date" :label="__('Preferred end')" v-model="form.preferred_end" />
				</div>
				<label class="flex items-center gap-2 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="form.flexible_schedule" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />{{ __('Flexible weekly schedule') }}
				</label>
				<div v-if="!form.flexible_schedule" class="flex flex-col gap-2">
					<div v-for="(slot, i) in form.weekly_schedule" :key="i" class="flex flex-wrap items-end gap-2">
						<FormControl type="select" :label="i === 0 ? __('Day') : ''" v-model="slot.day_of_week" :options="dayOptions" />
						<FormControl type="time" :label="i === 0 ? __('Start') : ''" v-model="slot.start_time" />
						<FormControl type="time" :label="i === 0 ? __('End') : ''" v-model="slot.end_time" />
						<Button variant="ghost" theme="red" @click="removeSlot(i)">{{ __('Remove') }}</Button>
					</div>
					<button type="button" class="self-start text-sm text-ink-blue-6 hover:underline" @click="addSlot">{{ __('+ Add time block') }}</button>
					<FormControl type="textarea" :label="__('Schedule notes')" v-model="form.schedule_notes" />
				</div>
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

			<label class="flex items-center gap-2 text-sm text-ink-gray-7">
				<input type="checkbox" v-model="form.open_students" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />{{ __('Open to students') }}
			</label>

			<div class="flex items-center gap-2 pt-1">
				<Button variant="solid" :loading="save.loading" @click="onSave">{{ __('Save internship') }}</Button>
				<router-link :to="{ name: 'PartnerInternshipPostings' }" class="text-sm text-ink-gray-6 hover:text-ink-gray-8">{{ __('Cancel') }}</router-link>
			</div>
		</div>
	</div>
</template>

<script setup>
import { reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { createResource, Button, FormControl, TextEditor, toast } from 'frappe-ui'
import { ArrowLeft } from 'lucide-vue-next'
import { usePartnerOrg } from '@/composables/usePartnerOrg'

const props = defineProps({ name: { type: String, default: null } })
const router = useRouter()
const { activeOrg } = usePartnerOrg()

const acceptanceOptions = ['Auto-Accept on Submission', 'Evaluate Applications'].map((v) => ({ label: __(v), value: v }))
const statusOptions = ['Open', 'Closed'].map((v) => ({ label: __(v), value: v }))
const dayOptions = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((v) => ({ label: __(v), value: v }))

const form = reactive({
	title: '', internship_type: '', description: '', qualifications: '',
	location: '', default_site_supervisor: '', acceptance_mode: 'Evaluate Applications',
	planned_placements: 1, min_hours_per_week: 0, status: 'Open',
	flexible_dates: 1, preferred_start: '', preferred_end: '',
	flexible_schedule: 1, schedule_notes: '', open_students: 1,
	weekly_schedule: [],
})

function addSlot() {
	form.weekly_schedule.push({ day_of_week: 'Monday', start_time: '', end_time: '' })
}
function removeSlot(i) {
	form.weekly_schedule.splice(i, 1)
}

const typeOptions = computed(() => [{ label: '—', value: '' }, ...((posting.data?.types || []).map((t) => ({ label: t.name, value: t.name })))])
const locationOptions = computed(() => [{ label: '—', value: '' }, ...((posting.data?.locations || []).map((l) => ({ label: l.location_name, value: l.name })))])
const supervisorOptions = computed(() => [{ label: '—', value: '' }, ...((posting.data?.supervisors || []).map((s) => ({ label: s.full_name || s.person, value: s.person })))])

const posting = createResource({
	url: 'seminary.partner.internship_portal.get_internship_posting',
	makeParams: () => ({ name: props.name || undefined, org: activeOrg.value }),
	auto: true,
	onSuccess(data) {
		for (const k of Object.keys(form)) {
			if (data?.[k] !== undefined && data?.[k] !== null) form[k] = data[k]
		}
	},
})

const save = createResource({
	url: 'seminary.partner.internship_portal.save_internship_posting',
	makeParams: () => ({ name: props.name || undefined, values: { ...form }, org: activeOrg.value }),
	onSuccess() {
		toast.success(__('Internship saved — pending staff review.'))
		router.push({ name: 'PartnerInternshipPostings' })
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not save the internship.'))
	},
})
function onSave() {
	if (!form.title) { toast.error(__('Title is required.')); return }
	if (!form.internship_type) { toast.error(__('Pick an internship type.')); return }
	if (!save.loading) save.submit()
}
</script>
