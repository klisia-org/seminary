<template>
	<div class="rounded-md border border-outline-gray-2 p-4">
		<div class="mb-3 flex items-center justify-between">
			<h3 class="font-semibold text-ink-gray-8">{{ __('Placement') }} <span class="text-ink-gray-5">{{ placement.name }}</span></h3>
			<Badge :theme="statusTheme(currentStatus)" variant="subtle">{{ __(currentStatus) }}</Badge>
		</div>

		<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
			<FormControl type="select" :label="__('Site supervisor')" v-model="form.site_supervisor" :options="supervisorOptions" />
			<FormControl type="number" :label="__('Hours allocated')" v-model="form.hours_allocated" />
			<FormControl type="date" :label="__('Actual start')" v-model="form.actual_start" />
			<FormControl type="date" :label="__('Actual end')" v-model="form.actual_end" />
		</div>
		<p class="mt-1.5 text-xs text-ink-gray-5">
			{{ __('Status is set automatically: Active when the start date arrives, Completed when hours are met and your evaluation is submitted.') }}
		</p>
		<div class="mt-2 flex items-center gap-2">
			<Button variant="subtle" :loading="save.loading" @click="onSave">{{ __('Save placement') }}</Button>
			<Button v-if="canTerminate" variant="ghost" theme="red" :loading="term.loading" @click="onTerminate">{{ __('Terminate internship early') }}</Button>
		</div>

		<!-- Hours -->
		<div class="mt-5 border-t border-outline-gray-1 pt-4">
			<div class="mb-2 text-sm font-medium text-ink-gray-7">
				{{ __('Hours') }} <span class="text-ink-gray-5">({{ placement.hours_logged || 0 }} / {{ form.hours_allocated || 0 }} {{ __('counted') }})</span>
			</div>
			<div class="flex flex-wrap items-end gap-2">
				<FormControl type="date" :label="__('Date')" v-model="hoursForm.log_date" />
				<FormControl type="number" :label="__('Hours')" v-model="hoursForm.hours" class="w-24" />
				<FormControl type="text" :label="__('Description')" v-model="hoursForm.description" class="flex-1" />
				<Button variant="outline" :loading="addHours.loading" @click="onAddHours">{{ __('Add') }}</Button>
			</div>
			<ul v-if="hours.data?.length" class="mt-3 divide-y divide-outline-gray-1 text-sm">
				<li v-for="h in hours.data" :key="h.name" class="flex items-center justify-between py-1.5">
					<span class="text-ink-gray-7">{{ h.log_date }} &middot; {{ h.hours }}h <span class="text-ink-gray-5">{{ h.description }}</span></span>
					<label class="flex items-center gap-1.5 text-xs text-ink-gray-6">
						<input type="checkbox" :checked="h.supervisor_verified" @change="toggleVerify(h)" class="rounded border-outline-gray-3" />
						{{ __('Verified') }}
					</label>
				</li>
			</ul>
		</div>

		<!-- Supervisor evaluation: only once the placement is finished -->
		<div v-if="canEvaluate" class="mt-5 border-t border-outline-gray-1 pt-4">
			<div class="mb-2 text-sm font-medium text-ink-gray-7">{{ __('Supervisor evaluation') }}</div>
			<div v-if="evalSubmitted" class="rounded-md bg-surface-green-1 px-3 py-2 text-sm text-ink-green-3">{{ __('Evaluation submitted.') }}</div>
			<div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<FormControl type="select" :label="__('Overall readiness')" v-model="evalForm.overall_readiness" :options="scaleOptions" />
				<FormControl type="select" :label="__('Theological integration')" v-model="evalForm.theological_integration" :options="scaleOptions" />
				<FormControl type="select" :label="__('Relational skills')" v-model="evalForm.relational_skills" :options="scaleOptions" />
				<FormControl type="select" :label="__('Initiative')" v-model="evalForm.initiative" :options="scaleOptions" />
				<FormControl type="textarea" :label="__('Comments')" v-model="evalForm.comments" class="sm:col-span-2" />
				<label class="flex items-center gap-2 text-sm text-ink-gray-7 sm:col-span-2">
					<input type="checkbox" v-model="evalForm.endorses_ministry" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />{{ __('Endorse this student for ministry') }}
				</label>
				<div class="flex items-center gap-2 sm:col-span-2">
					<Button variant="subtle" :loading="saveEval.loading" @click="onSaveEval(0)">{{ __('Save draft') }}</Button>
					<Button variant="solid" :loading="saveEval.loading" @click="onSaveEval(1)">{{ __('Submit evaluation') }}</Button>
				</div>
			</div>
		</div>
		<div v-else class="mt-5 border-t border-outline-gray-1 pt-4 text-sm text-ink-gray-5">
			{{ __('The supervisor evaluation opens when the allocated hours are met or the internship is ended early.') }}
		</div>
	</div>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { createResource, Button, Badge, FormControl, toast } from 'frappe-ui'

const props = defineProps({
	placement: { type: Object, required: true },
	supervisors: { type: Array, default: () => [] },
	org: { type: String, required: true },
})
const emit = defineEmits(['changed'])

const scaleOptions = ['', 'Exceeds Expectations', 'Meets Expectations', 'Developing', 'Below Expectations', 'Not Observed'].map((v) => ({ label: v ? __(v) : '—', value: v }))
const supervisorOptions = computed(() => [{ label: '—', value: '' }, ...props.supervisors.map((s) => ({ label: s.full_name || s.person, value: s.person }))])

const form = reactive({
	site_supervisor: props.placement.site_supervisor || '',
	actual_start: props.placement.actual_start || '',
	actual_end: props.placement.actual_end || '',
	hours_allocated: props.placement.hours_allocated || 0,
})
// Re-sync allocation when the parent reloads.
watch(() => props.placement.hours_allocated, (v) => { form.hours_allocated = v || 0 })

// Status is system-driven and read-only for partners.
const currentStatus = computed(() => props.placement.placement_status || 'Proposed')
const hoursMet = computed(() => (props.placement.hours_allocated || 0) > 0 && (props.placement.hours_logged || 0) >= (props.placement.hours_allocated || 0))
const canEvaluate = computed(() => hoursMet.value || ['Completed', 'Terminated'].includes(currentStatus.value))
const canTerminate = computed(() => ['Proposed', 'Active'].includes(currentStatus.value))

const save = createResource({
	url: 'seminary.partner.internship_portal.save_placement',
	makeParams: () => ({ name: props.placement.name, values: { ...form }, org: props.org }),
	onSuccess() { toast.success(__('Placement saved.')); emit('changed') },
	onError(err) { toast.error(err.messages?.[0] || __('Could not save placement.')) },
})
function onSave() { if (!save.loading) save.submit() }

const term = createResource({
	url: 'seminary.partner.internship_portal.terminate_placement',
	makeParams: () => ({ name: props.placement.name, org: props.org }),
	onSuccess() { toast.success(__('Internship ended.')); emit('changed') },
	onError(err) { toast.error(err.messages?.[0] || __('Could not end the internship.')) },
})
function onTerminate() { if (!term.loading) term.submit() }

// Hours
const hoursForm = reactive({ log_date: '', hours: null, description: '' })
const hours = createResource({
	url: 'seminary.partner.internship_portal.list_hours',
	makeParams: () => ({ placement: props.placement.name, org: props.org }),
	auto: true,
})
const addHours = createResource({
	url: 'seminary.partner.internship_portal.add_hours',
	makeParams: () => ({ placement: props.placement.name, log_date: hoursForm.log_date, hours: hoursForm.hours, description: hoursForm.description, org: props.org }),
	onSuccess() { hoursForm.hours = null; hoursForm.description = ''; toast.success(__('Hours added.')); hours.reload(); emit('changed') },
	onError(err) { toast.error(err.messages?.[0] || __('Could not add hours.')) },
})
function onAddHours() {
	if (!hoursForm.log_date || !hoursForm.hours) { toast.error(__('Date and hours are required.')); return }
	if (!addHours.loading) addHours.submit()
}
const verify = createResource({ url: 'seminary.partner.internship_portal.verify_hours' })
function toggleVerify(h) {
	verify.submit({ name: h.name, verified: h.supervisor_verified ? 0 : 1, org: props.org }, { onSuccess() { hours.reload(); emit('changed') } })
}

// Evaluation
const evalForm = reactive({ overall_readiness: '', theological_integration: '', relational_skills: '', initiative: '', comments: '', endorses_ministry: 0 })
const evalName = ref(null)
const evalSubmitted = ref(false)
createResource({
	url: 'seminary.partner.internship_portal.get_supervisor_evaluation',
	makeParams: () => ({ placement: props.placement.name, org: props.org }),
	auto: true,
	onSuccess(data) {
		if (data?.name) {
			evalName.value = data.name
			evalSubmitted.value = data.docstatus === 1
			for (const k of Object.keys(evalForm)) if (data[k] !== undefined && data[k] !== null) evalForm[k] = data[k]
		}
	},
})
const saveEval = createResource({ url: 'seminary.partner.internship_portal.save_supervisor_evaluation' })
function onSaveEval(submit) {
	saveEval.submit(
		{ placement: props.placement.name, values: { ...evalForm }, submit, name: evalName.value || undefined, org: props.org },
		{
			onSuccess(data) {
				evalName.value = data.name
				evalSubmitted.value = data.docstatus === 1
				toast.success(submit ? __('Evaluation submitted.') : __('Draft saved.'))
			},
			onError(err) { toast.error(err.messages?.[0] || __('Could not save evaluation.')) },
		},
	)
}

function statusTheme(s) {
	if (s === 'Active' || s === 'Completed') return 'green'
	if (s === 'Terminated') return 'red'
	return 'gray'
}
</script>
