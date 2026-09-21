<!--
  The §2.12 mapping, in the SPA (privatedocs p009 S11).

  A SCORM score is a claim made by third-party code running in a browser the
  student controls, so it reaches the gradebook only where an instructor has
  said which criterion it answers. That link existed from S10 but only on Desk,
  which meant the one deliberate act the design depends on was the one act the
  people who teach could not perform.

  Staff-only, and it shows the default plainly: unmapped records completion and
  nothing else. The server gates on the lesson's own section and refuses a
  criterion from any other -- this picker only ever offers what that gate will
  accept.
-->
<template>
	<div v-if="mapping.data" class="scorm-mapping">
		<div class="flex items-baseline justify-between gap-3">
			<div class="text-sm font-medium text-ink-gray-7">
				{{ __('Grade passback') }}
			</div>
			<Badge v-if="mapping.data.current" theme="green" variant="subtle">
				{{ __('Reporting') }}
			</Badge>
			<Badge v-else theme="gray" variant="subtle">
				{{ __('Completion only') }}
			</Badge>
		</div>

		<p v-if="mapping.data.competency_section" class="mt-2 text-sm text-ink-gray-6">
			{{
				__(
					'This is a competency-based section: the gradebook cell holds a level, not a percentage, so a SCORM score is never written to it. The package still records completion.'
				)
			}}
		</p>

		<template v-else>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{
					mapping.data.current
						? __(
								'A passing score from this SCO is written to the criterion below. A grade you enter by hand replaces it and is never overwritten.'
						  )
						: __(
								'This SCO records completion only. Choose a criterion to have a passing score written to the gradebook.'
						  )
				}}
			</p>

			<div class="mt-3 flex items-center gap-2">
				<FormControl
					class="flex-1"
					type="select"
					:modelValue="selected"
					:options="options"
					:disabled="saving"
					@update:modelValue="onChange"
				/>
				<LoadingIndicator v-if="saving" class="w-4 h-4 text-ink-gray-5" />
			</div>

			<p v-if="!mapping.data.criteria.length" class="mt-2 text-sm text-ink-gray-5">
				{{ __('This section has no assessment criteria yet. Add them in the course assessment setup first.') }}
			</p>
		</template>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, FormControl, LoadingIndicator, createResource, toast } from 'frappe-ui'

const props = defineProps({
	lesson: { type: String, required: true },
})

const saving = ref(false)
const selected = ref('')

const mapping = createResource({
	url: 'seminary.scorm.grades.criteria_for_lesson',
	makeParams() {
		return { lesson: props.lesson }
	},
	auto: true,
	onSuccess(data) {
		selected.value = data?.current || ''
	},
})

const options = computed(() => {
	const rows = mapping.data?.criteria || []
	return [
		{ label: __('Completion only — no grade reported'), value: '' },
		...rows.map((row) => ({
			// The stored title where there is one, the criterion it came from
			// otherwise: a row with no title is common and its docname is a
			// generated string nobody would recognise.
			label: row.title || row.assesscriteria_scac || row.name,
			value: row.name,
		})),
	]
})

const save = createResource({
	url: 'seminary.scorm.grades.set_criteria',
})

async function onChange(value) {
	const previous = selected.value
	selected.value = value
	saving.value = true
	try {
		await save.submit({ lesson: props.lesson, criteria: value || '' })
		mapping.reload()
		toast.success(value ? __('Grade passback enabled') : __('Grade passback turned off'))
	} catch (e) {
		// Put the control back where it was: the server refused, so the stored
		// mapping is still the old one and a control showing the new value
		// would be lying about the gradebook.
		selected.value = previous
		toast.error(e?.messages?.[0] || __('Could not change the mapping'))
	} finally {
		saving.value = false
	}
}
</script>

<style scoped>
.scorm-mapping {
	border: 1px solid var(--surface-gray-3, #e5e7eb);
	border-radius: 0.5rem;
	padding: 0.75rem 1rem;
	background: var(--surface-gray-1, #fafafa);
}
</style>
