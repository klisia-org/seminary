<template>
	<Dialog v-model="open" :options="{ title: title, size: 'xl' }">
		<template #body-content>
			<div v-if="loading" class="text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
			<template v-else-if="dates">
				<!-- This student's dates on this assessment (decisions/082 section 2). -->
				<h4 class="font-semibold text-ink-gray-8 mb-1">{{ __('Dates for this student') }}</h4>
				<p class="mb-2 text-sm text-ink-gray-6">
					{{ dates.override ? __('This student has their own dates. Blank fields follow the assessment.') : __('This student follows the assessment\'s dates.') }}
				</p>
				<p class="mb-3 text-xs text-ink-gray-5">
					{{ __('Assessment: due {0}, cut-off {1}.').format(fmt(assessment?.due_date), fmt(assessment?.cutoff_date)) }}
				</p>
				<div class="grid gap-3 sm:grid-cols-2">
					<div>
						<label class="text-xs text-ink-gray-5">{{ __('Due date') }}</label>
						<DateTimePicker v-model="form.due_date" variant="subtle" />
					</div>
					<div>
						<label class="text-xs text-ink-gray-5">{{ __('Cut-off') }}</label>
						<DateTimePicker v-model="form.cutoff_date" variant="subtle" />
					</div>
					<div v-if="dates.replies_due_date !== null && dates.replies_due_date !== undefined">
						<label class="text-xs text-ink-gray-5">{{ __('Replies due') }}</label>
						<DateTimePicker v-model="form.replies_due_date" variant="subtle" />
					</div>
					<FormControl v-if="['Quiz', 'Exam'].includes(assessment?.type)" type="number"
						v-model="form.extra_minutes" :label="__('Extra minutes')" />
					<FormControl v-if="assessment?.type === 'Quiz'" type="number"
						v-model="form.extra_attempts" :label="__('Extra attempts')" />
					<FormControl class="sm:col-span-2" v-model="form.reason" :label="__('Reason')" />
				</div>
				<div class="mt-3 flex gap-2">
					<Button variant="solid" size="sm" :loading="saving" @click="saveDates">
						{{ dates.override ? __('Save dates') : __('Give this student different dates') }}
					</Button>
					<Button v-if="dates.override" size="sm" theme="red" @click="removeDates">
						{{ __('Back to the assessment\'s dates') }}
					</Button>
				</div>

				<!-- The late deduction on this grade (decisions/082 section 4). -->
				<template v-if="cell && cell.late_base_card">
					<h4 class="mt-6 font-semibold text-ink-gray-8 mb-1">{{ __('Late deduction') }}</h4>
					<p class="mb-2 text-sm text-ink-gray-6">
						{{ __('Submitted score {0}, less {1} for lateness = {2}.').format(cell.late_base_card, cell.late_deduction_card || 0, cell.rawscore_card) }}
						<span v-if="cell.late_adjusted_card">{{ __('You changed it: {0}').format(cell.late_adjusted_reason) }}</span>
					</p>
					<div v-if="!finalized" class="grid gap-3 sm:grid-cols-3">
						<FormControl type="number" v-model="adjust.deduction" :label="__('Deduction (%)')" />
						<FormControl class="sm:col-span-2" v-model="adjust.reason" :label="__('Reason')" />
					</div>
					<div v-if="!finalized" class="mt-3 flex gap-2">
						<Button size="sm" :loading="saving" @click="saveAdjustment(0)">{{ __('Waive it') }}</Button>
						<Button size="sm" :loading="saving" @click="saveAdjustment(adjust.deduction)">{{ __('Set this deduction') }}</Button>
						<Button v-if="cell.late_adjusted_card" size="sm" :loading="saving" @click="saveAdjustment(null)">
							{{ __('Back to the late policy') }}
						</Button>
					</div>
					<p v-else class="text-sm text-ink-gray-5">{{ __('Grades were sent, so this can no longer change.') }}</p>
				</template>
			</template>
		</template>
	</Dialog>
</template>

<script setup>
// The gradebook cell menu: one student's dates on one assessment, and the late
// deduction on their grade (decisions/082 section 7).
import { computed, reactive, ref } from 'vue'
import { Button, DateTimePicker, Dialog, FormControl, call, toast } from 'frappe-ui'

const emit = defineEmits(['changed'])

const open = ref(false)
const loading = ref(false)
const saving = ref(false)
const dates = ref(null)
const cell = ref(null)
const assessment = ref(null)
const student = ref(null)
const finalized = ref(false)
let courseSchedule = null

const form = reactive({})
const adjust = reactive({ deduction: '', reason: '' })

const title = computed(() =>
	student.value ? `${student.value.stuname_roster} · ${assessment.value?.title || ''}` : ''
)

const fmt = (value) => (value ? new Date(value).toLocaleString() : __('none'))

const errorText = (e, fallback) =>
	(Array.isArray(e?.messages) && e.messages.length ? e.messages.join('\n') : e?.message) || fallback

async function show(course, studentRow, assessmentRow, cellRow) {
	courseSchedule = course
	student.value = studentRow
	assessment.value = assessmentRow
	cell.value = cellRow
	finalized.value = !studentRow.active
	adjust.deduction = cellRow?.late_deduction_card || 0
	adjust.reason = cellRow?.late_adjusted_reason || ''
	open.value = true
	await load()
}

async function load() {
	loading.value = true
	try {
		const all = await call('seminary.seminary.deadlines.get_student_dates', {
			course: courseSchedule,
			student: student.value.student,
		})
		dates.value = all.find((d) => d.course_assess === assessment.value.assessment_criteria) || null
		let ov = {}
		if (dates.value?.override) {
			const list = await call('seminary.seminary.deadlines.get_deadline_settings', { course: courseSchedule })
			ov = (list.overrides || []).find((o) => o.name === dates.value.override) || {}
		}
		Object.assign(form, {
			name: ov.name || '',
			// Only what the override sets: a copied assessment date would stop
			// following the assessment when the instructor later moves it.
			due_date: ov.due_date || '',
			cutoff_date: ov.cutoff_date || '',
			replies_due_date: ov.replies_due_date || '',
			extra_minutes: ov.extra_minutes || '',
			extra_attempts: ov.extra_attempts || '',
			reason: ov.reason || '',
		})
	} catch (e) {
		toast.error(errorText(e, __('Could not load the dates.')))
	} finally {
		loading.value = false
	}
}

async function saveDates() {
	saving.value = true
	try {
		await call('seminary.seminary.deadlines.save_override', {
			data: JSON.stringify({
				...form,
				course_assess: assessment.value.assessment_criteria,
				student: student.value.student,
			}),
		})
		toast.success(__('Saved'))
		emit('changed')
		await load()
	} catch (e) {
		toast.error(errorText(e, __('Could not save.')))
	} finally {
		saving.value = false
	}
}

async function removeDates() {
	saving.value = true
	try {
		await call('seminary.seminary.deadlines.delete_override', { name: dates.value.override })
		emit('changed')
		await load()
	} catch (e) {
		toast.error(errorText(e, __('Could not remove.')))
	} finally {
		saving.value = false
	}
}

async function saveAdjustment(deduction) {
	saving.value = true
	try {
		const out = await call('seminary.seminary.deadlines.set_late_adjustment', {
			card: cell.value.name,
			deduction: deduction === null ? '' : deduction,
			reason: adjust.reason,
		})
		Object.assign(cell.value, out)
		toast.success(__('Saved'))
		emit('changed')
	} catch (e) {
		toast.error(errorText(e, __('Could not save.')))
	} finally {
		saving.value = false
	}
}

defineExpose({ show })
</script>
