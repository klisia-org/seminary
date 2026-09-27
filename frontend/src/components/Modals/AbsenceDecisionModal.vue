<template>
	<Dialog v-model="open" :options="{ title: __('Students over the absence limit'), size: '2xl' }" @close="finish(false)">
		<template #body-content>
			<p class="mb-4 text-sm text-ink-gray-6">
				{{ __('Decide for each student before the grades are sent. If you leave it to the registrar, the grade is sent and the registrar decides.') }}
			</p>
			<div v-for="row in rows" :key="row.roster" class="mb-4 rounded-md border border-outline-gray-2 p-3">
				<div class="mb-2 flex items-center justify-between">
					<span class="font-medium text-ink-gray-9">{{ row.stuname_roster || row.student }}</span>
					<span class="text-sm font-semibold text-ink-red-4">
						{{ __('{0} / {1} absences', [row.effective_absences, row.absence_limit]) }}
					</span>
				</div>
				<FormControl type="select" :options="choices" v-model="row.decision" />
				<FormControl
					v-if="row.decision === 'Keep the grade'"
					type="textarea"
					class="mt-2"
					:label="__('Reason')"
					v-model="row.reason"
				/>
			</div>
		</template>
		<template #actions>
			<Button variant="solid" :loading="saving" :disabled="!complete" @click="confirm">
				{{ __('Save and Send Grades') }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
// Send Grades stops for a student over the absence limit until someone decides
// (ADR 081). `ask` resolves true when the send may go ahead.
import { computed, ref } from 'vue'
import { Button, Dialog, FormControl, call, toast } from 'frappe-ui'

const open = ref(false)
const saving = ref(false)
const rows = ref([])
let courseSchedule = null
let resolver = null

const choices = [
	{ label: __('Choose…'), value: '' },
	{ label: __('Fail for absence'), value: 'Fail for absence' },
	{ label: __('Keep the grade'), value: 'Keep the grade' },
	{ label: __('No recommendation (the registrar decides)'), value: 'No recommendation' },
]

const complete = computed(() =>
	rows.value.every(
		(r) => r.decision && (r.decision !== 'Keep the grade' || (r.reason || '').trim())
	)
)

const finish = (proceed) => {
	open.value = false
	if (resolver) resolver(proceed)
	resolver = null
}

const ask = async (course_schedule, rosters = null) => {
	courseSchedule = course_schedule
	const needed = await call('seminary.seminary.absence_decisions.absence_decisions_needed', {
		course_schedule,
		rosters: rosters ? JSON.stringify(rosters) : null,
	})
	if (!needed?.length) return true
	rows.value = needed.map((r) => ({ ...r, decision: '', reason: '' }))
	open.value = true
	return new Promise((resolve) => {
		resolver = resolve
	})
}

const confirm = async () => {
	saving.value = true
	try {
		await call('seminary.seminary.absence_decisions.record_absence_decisions', {
			course_schedule: courseSchedule,
			decisions: JSON.stringify(
				rows.value.map((r) => ({ roster: r.roster, decision: r.decision, reason: r.reason }))
			),
		})
		finish(true)
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || __('Could not save the decisions.'))
	} finally {
		saving.value = false
	}
}

defineExpose({ ask })
</script>
