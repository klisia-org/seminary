<template>
	<header
		class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
		<Breadcrumbs class="h-7" :items="breadcrumbs" />
		<div v-if="report.data?.editable" class="flex items-center gap-2 mt-3 md:mt-0">
			<Button variant="subtle" :loading="saving" @click="save()">
				{{ __('Save') }}
			</Button>
			<Button variant="solid" :loading="submitting" @click="submit()">
				{{ __('Submit') }}
			</Button>
		</div>
	</header>

	<div v-if="report.loading" class="px-5 py-8 text-ink-gray-6">{{ __('Loading…') }}</div>

	<!--
		A report is only created once grades are sent and the evidence exists (decisions/034
		section 10). Before that there is genuinely nothing to answer, so say so plainly rather
		than offering a blank form.
	-->
	<div v-else-if="!report.data" class="px-5 py-8">
		<div class="text-lg font-semibold text-ink-gray-9">{{ __('No outcome report yet') }}</div>
		<div class="mt-2 text-ink-gray-6 max-w-2xl">
			{{ __('An outcome report is prepared automatically once grades are sent for this offering. It arrives already filled in with what your assessments showed.') }}
		</div>
	</div>

	<div v-else class="mt-5 mb-10 w-full px-5">
		<div class="flex flex-wrap items-center gap-2 mb-4">
			<div class="text-xl font-semibold text-ink-gray-9 mr-2">
				{{ report.data.course }}
				<span v-if="report.data.section" class="text-ink-gray-6">· {{ report.data.section }}</span>
			</div>
			<Badge :theme="statusTheme" size="lg">{{ __(report.data.status) }}</Badge>
			<Badge v-if="report.data.modality" theme="gray" size="lg">{{ __(report.data.modality) }}</Badge>
			<Badge v-if="report.data.due_date" theme="gray" size="lg">
				{{ __('Due') }} {{ report.data.due_date }}
			</Badge>
		</div>

		<div v-if="report.data.changes_requested_note"
			class="mb-4 rounded bg-surface-amber-1 px-3 py-2 text-sm text-ink-gray-8">
			<strong>{{ __('Changes requested') }}:</strong> {{ report.data.changes_requested_note }}
		</div>

		<!--
			Cited figures are frozen copies of the auditable snapshots (section 3). When one is
			regenerated afterwards we surface the drift rather than silently updating the number,
			so a report never disagrees with itself unnoticed.
		-->
		<div v-if="report.data.evidence_drift"
			class="mb-4 rounded bg-surface-amber-1 px-3 py-2 text-sm text-ink-gray-8">
			{{ __('Some evidence cited here has been recalculated since this report was prepared. The figures below are what was shown when it was written.') }}
		</div>

		<div class="mb-6 flex flex-wrap gap-4 text-sm text-ink-gray-7">
			<div><strong>{{ report.data.counts.measured }}</strong> {{ __('measured') }}</div>
			<div><strong>{{ report.data.counts.unmet }}</strong> {{ __('below target') }}</div>
			<div><strong>{{ report.data.counts.not_assessed }}</strong> {{ __('not assessed') }}</div>
		</div>

		<div class="text-lg font-semibold text-ink-gray-9 mb-3">{{ __('Outcomes') }}</div>
		<div class="space-y-3 mb-8">
			<div v-for="row in rows" :key="row.idx" class="rounded border border-outline-gray-2 px-3 py-3"
				:class="{ 'bg-surface-amber-1': row.needs_action, 'bg-surface-gray-1': row.data_state !== 'Measured' }">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div class="font-medium text-ink-gray-8">
						{{ row.shorthand || row.clo }}
					</div>
					<div class="flex items-center gap-1.5">
						<Badge v-if="row.repeat_concern" theme="red" size="sm">
							{{ __('Repeat concern') }}
						</Badge>
						<Badge v-if="row.data_state !== 'Measured'" theme="gray" size="sm">
							{{ __(row.data_state) }}
						</Badge>
						<template v-else>
							<Badge :theme="row.met ? 'green' : 'red'" size="sm">
								{{ row.attainment }} / {{ row.target }}
							</Badge>
						</template>
					</div>
				</div>

				<!--
					An unmeasured outcome is a mapping gap, not a teaching result. Saying so keeps
					the professor from writing an apology for something that is not theirs to fix.
				-->
				<div v-if="row.data_state === 'Not Assessed'" class="mt-1.5 text-xs text-ink-gray-6">
					{{ __('Nothing in this offering measured this outcome. A note on why is enough — the fix is mapping, not teaching.') }}
				</div>
				<div v-else-if="row.data_state === 'No Data'" class="mt-1.5 text-xs text-ink-gray-6">
					{{ __('Mapped, but nothing graded to compute from.') }}
				</div>

				<FormControl v-if="row.needs_analysis" type="textarea" class="mt-2" :rows="2"
					:disabled="!report.data.editable"
					:label="row.needs_action ? __('What happened, in your reading?') : __('Note')"
					v-model="row.analysis" />

				<div v-if="row.needs_action" class="mt-2">
					<div class="text-xs text-ink-gray-6 mb-1">
						{{ __('This outcome missed its target, so it needs at least one improvement action before you can submit.') }}
					</div>
					<div v-if="row.actions?.length" class="flex flex-wrap gap-1.5 mb-2">
						<Badge v-for="action in row.actions" :key="action.name" theme="blue" size="sm">
							{{ action.title }}
						</Badge>
					</div>
					<Button v-if="report.data.editable" variant="subtle" size="sm" @click="openAction(row)">
						{{ __('Add an action') }}
					</Button>
				</div>
			</div>
		</div>

		<!--
			Closing the loop: prior actions come back with the attainment change alongside them, so
			"did it work?" is answered with evidence rather than recollection (section 6).
		-->
		<div v-if="priorActions.length">
			<div class="text-lg font-semibold text-ink-gray-9 mb-3">{{ __('What you said last time') }}</div>
			<div class="space-y-3 mb-8">
				<div v-for="row in priorActions" :key="row.idx"
					class="rounded border border-outline-gray-2 px-3 py-3">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<div class="font-medium text-ink-gray-8">{{ row.title }}</div>
						<div class="flex items-center gap-1.5">
							<Badge v-if="row.scope !== 'Instructor'" theme="blue" size="sm">
								{{ __('Course-wide') }}
							</Badge>
							<Badge v-if="row.delta !== null && row.delta !== undefined"
								:theme="row.delta > 0 ? 'green' : row.delta < 0 ? 'red' : 'gray'" size="sm">
								{{ row.delta > 0 ? '+' : '' }}{{ row.delta }} {{ __('pp') }}
							</Badge>
						</div>
					</div>
					<div class="mt-2 grid gap-2 md:grid-cols-2">
						<FormControl type="select" :label="__('Did you do it?')" :disabled="!report.data.editable"
							v-model="row.implementation_status"
							:options="['', 'Implemented', 'Partially Implemented', 'Not Implemented']" />
						<FormControl type="select" :disabled="!report.data.editable"
							:label="__('Did it work?') + (row.proposed_effectiveness ? ` (${__('suggested')}: ${row.proposed_effectiveness})` : '')"
							v-model="row.effectiveness"
							:options="['', 'Effective', 'Not Effective', 'Inconclusive']" />
					</div>
					<FormControl v-if="needsImplementationNote(row)" type="textarea" class="mt-2" :rows="2"
						:disabled="!report.data.editable" :label="__('Why not?')"
						v-model="row.implementation_note" />
					<FormControl v-if="overridesProposal(row)" type="textarea" class="mt-2" :rows="2"
						:disabled="!report.data.editable" :label="__('Why do you read it differently?')"
						v-model="row.effectiveness_note" />
					<div v-if="!row.closable" class="mt-1.5 text-xs text-ink-gray-5">
						{{ __('This action applies to every section of the course, so it is closed on the course summary rather than here.') }}
					</div>
				</div>
			</div>
		</div>

		<div class="text-lg font-semibold text-ink-gray-9 mb-3">{{ __('Reflection') }}</div>
		<FormControl type="textarea" :rows="5" :disabled="!report.data.editable"
			:label="__('What worked, what the cohort was like, anything you already changed mid-term')"
			v-model="reflection" class="mb-8" />

		<Dialog v-model="showAction" :options="{ title: __('Add an improvement action') }">
			<template #body-content>
				<FormControl :label="__('What will you do?')" v-model="newAction.title" class="mb-3" />
				<FormControl type="textarea" :rows="3" :label="__('How, concretely?')"
					v-model="newAction.description" class="mb-3" />
				<FormControl type="select" :label="__('Applies to')" v-model="newAction.applies_to_modality"
					:options="['All', 'Presential', 'Virtual', 'Hybrid']" />
				<div class="mt-2 text-xs text-ink-gray-5">
					{{ __('This reaches your next offering of this course, not the one you have just finished.') }}
				</div>
			</template>
			<template #actions>
				<Button variant="solid" :loading="addingAction" @click="saveAction()">
					{{ __('Add') }}
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, ref, reactive, watch } from 'vue'
import { createResource, Breadcrumbs, Badge, Button, FormControl, Dialog, toast } from 'frappe-ui'
import { updateDocumentTitle } from '@/utils'

const props = defineProps({
	courseName: { type: String, required: true },
})

const saving = ref(false)
const submitting = ref(false)
const addingAction = ref(false)
const showAction = ref(false)
const activeRow = ref(null)
const rows = ref([])
const priorActions = ref([])
const reflection = ref('')
const newAction = reactive({ title: '', description: '', applies_to_modality: 'All' })

const report = createResource({
	url: 'aretenic.improvement_api.get_report',
	makeParams: () => ({ course_schedule: props.courseName }),
	auto: true,
	onSuccess: (data) => {
		// Local copies so edits survive a re-render; the server owns everything else on the page.
		rows.value = (data?.clo_results || []).map((r) => ({ ...r }))
		priorActions.value = (data?.prior_actions || []).map((r) => ({ ...r }))
		reflection.value = data?.overall_reflection || ''
	},
})

const statusTheme = computed(
	() =>
		({
			Draft: 'orange',
			Submitted: 'blue',
			'Changes Requested': 'orange',
			Accepted: 'green',
		}[report.data?.status] || 'gray')
)

function needsImplementationNote(row) {
	return ['Partially Implemented', 'Not Implemented'].includes(row.implementation_status)
}

function overridesProposal(row) {
	return (
		row.effectiveness &&
		row.proposed_effectiveness &&
		row.effectiveness !== row.proposed_effectiveness
	)
}

function payload() {
	return {
		report: report.data.name,
		clo_results: rows.value.map((r) => ({ idx: r.idx, analysis: r.analysis })),
		prior_actions: priorActions.value.map((r) => ({
			idx: r.idx,
			implementation_status: r.implementation_status,
			implementation_note: r.implementation_note,
			effectiveness: r.effectiveness,
			effectiveness_note: r.effectiveness_note,
			disposition: r.disposition,
		})),
		overall_reflection: reflection.value,
	}
}

const saveResource = createResource({ url: 'aretenic.improvement_api.save_report' })
const submitResource = createResource({ url: 'aretenic.improvement_api.submit_report' })
const addResource = createResource({ url: 'aretenic.improvement_api.add_action' })

async function save(quiet = false) {
	saving.value = true
	try {
		await saveResource.submit(payload())
		if (!quiet) toast.success(__('Saved'))
		return true
	} catch (e) {
		toast.error(e.messages?.[0] || __('Could not save'))
		return false
	} finally {
		saving.value = false
	}
}

async function submit() {
	// Save first: the completeness gate runs server-side against stored values, so submitting
	// unsaved edits would fail on text the professor can plainly see on screen.
	if (!(await save(true))) return
	submitting.value = true
	try {
		await submitResource.submit({ report: report.data.name })
		toast.success(__('Submitted'))
		report.reload()
	} catch (e) {
		toast.error(e.messages?.[0] || __('Could not submit'))
	} finally {
		submitting.value = false
	}
}

function openAction(row) {
	activeRow.value = row
	newAction.title = ''
	newAction.description = ''
	newAction.applies_to_modality = report.data?.modality || 'All'
	showAction.value = true
}

async function saveAction() {
	if (!newAction.title?.trim()) {
		toast.error(__('Give the action a title'))
		return
	}
	addingAction.value = true
	try {
		await save(true)
		await addResource.submit({
			report: report.data.name,
			clo: activeRow.value.clo,
			title: newAction.title,
			description: newAction.description,
			applies_to_modality: newAction.applies_to_modality,
		})
		showAction.value = false
		report.reload()
		toast.success(__('Action added'))
	} catch (e) {
		toast.error(e.messages?.[0] || __('Could not add the action'))
	} finally {
		addingAction.value = false
	}
}

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{
		label: report.data?.course || props.courseName,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{ label: __('Outcome Report') },
])

watch(
	() => props.courseName,
	() => report.reload()
)

updateDocumentTitle(computed(() => ({ title: __('Outcome Report') })))
</script>
