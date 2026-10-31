<!--
  Course outcomes on an assignment's or discussion's page (aretenic 077a,
  seminary p023). Rendered only with aretenic installed; every call goes to
  aretenic.

  A map belongs to one section's assessment row. Saving here applies to every
  section using the activity that is still in Draft or Open for Enrollment;
  sections further along are listed read-only, with a link to their own page.
-->
<template>
	<div class="rounded-md border border-outline-gray-2 p-5">
		<div class="mb-3 flex items-center justify-between">
			<div>
				<div class="font-semibold text-ink-gray-9">{{ __('Course outcomes') }}</div>
				<div class="text-xs text-ink-gray-5">
					{{ __('The course learning outcomes this activity measures, as a whole or by rubric criterion.') }}
				</div>
			</div>
			<Button v-if="openSections.length && cloList.length" variant="solid" :loading="saving" @click="save">
				{{ __('Save outcomes') }}
			</Button>
		</div>

		<div v-if="outcomes.loading && !outcomes.data" class="py-4 text-sm text-ink-gray-5">{{ __('Loading…') }}</div>

		<div v-else-if="!cloList.length" class="text-sm text-ink-gray-5">
			{{ __('No course learning outcomes are defined for this course yet.') }}
		</div>

		<div v-else class="space-y-4">
			<div v-if="!openSections.length" class="rounded bg-surface-amber-1 p-3 text-sm text-ink-amber-3">
				{{ __('No section using this activity is in Draft or Open for Enrollment. Map outcomes from the section\'s Course Assessment page.') }}
			</div>
			<div v-else-if="outcomes.data.differs" class="rounded bg-surface-blue-1 p-3 text-sm text-ink-blue-2">
				{{ __('The open sections are mapped differently. Saving gives them all this mapping.') }}
			</div>

			<ul class="space-y-3">
				<li v-for="clo in cloList" :key="clo.name" class="border-b border-outline-gray-1 pb-3 last:border-0">
					<label class="flex cursor-pointer items-start gap-2">
						<input v-model="selected" type="checkbox" :value="clo.name" :disabled="!openSections.length"
							class="mt-1 h-4 w-4 rounded border-outline-gray-2 text-ink-blue-2" />
						<span>
							<span class="text-sm font-medium text-ink-gray-8">
								{{ clo.outcome_code }}<template v-if="clo.shorthand"> — {{ clo.shorthand }}</template>
							</span>
							<SafeHtml class="clo-statement block text-sm text-ink-gray-6" :html="clo.statement" as="span" />
						</span>
					</label>
					<div v-if="criteria.length && selected.includes(clo.name)" class="ml-6 mt-2 space-y-1">
						<div class="text-xs text-ink-gray-5">
							{{ (criteriaByClo[clo.name] || []).length
								? __('Measured by these rubric criteria:')
								: __('Measured by the whole activity. Tick criteria to narrow it.') }}
						</div>
						<label v-for="c in criteria" :key="c.id" class="flex cursor-pointer items-center gap-2 text-xs text-ink-gray-7">
							<input v-model="criteriaByClo[clo.name]" type="checkbox" :value="c.id"
								:disabled="!openSections.length" class="h-3.5 w-3.5 rounded border-outline-gray-2 text-ink-blue-2" />
							{{ c.label }} <span class="text-ink-gray-5">({{ c.share }}%)</span>
						</label>
					</div>
				</li>
			</ul>

			<div class="space-y-1 text-xs text-ink-gray-5">
				<div v-if="openSections.length">
					{{ __('Saving applies to: {0}').format(openSections.map(sectionLabel).join(', ')) }}
				</div>
				<div v-if="closedSections.length">
					{{ __('Already under way, change from their own page:') }}
					<template v-for="(s, i) in closedSections" :key="s.scac">
						<router-link :to="{ name: 'CourseAssessment', params: { courseName: s.course_schedule } }"
							class="underline">{{ sectionLabel(s) }}</router-link>
						<span> ({{ __(s.state) }})</span><span v-if="i < closedSections.length - 1">, </span>
					</template>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Button, call, createResource, toast } from 'frappe-ui'
import { computed, reactive, ref, watch } from 'vue'
import SafeHtml from '@/components/SafeHtml.vue'

const props = defineProps({
	activityDoctype: { type: String, required: true },
	activity: { type: String, required: true },
})

const selected = ref([])
const criteriaByClo = reactive({})
const saving = ref(false)

const outcomes = createResource({
	url: 'aretenic.activity_outcomes.get_activity_outcomes',
	makeParams: () => ({ activity_doctype: props.activityDoctype, activity: props.activity }),
	auto: true,
	onSuccess: (d) => load(d),
})

watch(() => props.activity, () => outcomes.reload())

const cloList = computed(() => outcomes.data?.clos || [])
const criteria = computed(() => outcomes.data?.criteria || [])
const sections = computed(() => outcomes.data?.sections || [])
const openSections = computed(() => sections.value.filter((s) => s.editable))
const closedSections = computed(() => sections.value.filter((s) => !s.editable))
const sectionLabel = (s) => (s.academic_term ? `${s.course_schedule} · ${s.academic_term}` : s.course_schedule)

const load = (d) => {
	const maps = d.maps || {}
	selected.value = Object.keys(maps)
	Object.keys(criteriaByClo).forEach((k) => delete criteriaByClo[k])
	for (const [clo, m] of Object.entries(maps)) {
		criteriaByClo[clo] = m.map_by === 'Rubric criteria' ? [...m.items] : []
	}
}

watch(selected, (val) => val.forEach((clo) => {
	if (!Array.isArray(criteriaByClo[clo])) criteriaByClo[clo] = []
}), { deep: true })

const save = async () => {
	saving.value = true
	try {
		const d = await call('aretenic.activity_outcomes.save_activity_outcomes', {
			activity_doctype: props.activityDoctype,
			activity: props.activity,
			mappings: JSON.stringify(
				selected.value.map((clo) => ({ clo, criteria: criteria.value.length ? criteriaByClo[clo] || [] : [] }))
			),
		})
		outcomes.setData(d)
		load(d)
		toast.success(__('Outcomes saved'))
	} catch (e) {
		toast.error((Array.isArray(e?.messages) && e.messages.join('\n')) || __('Could not save the outcomes.'))
	} finally {
		saving.value = false
	}
}

defineExpose({ reload: () => outcomes.reload() })
</script>

<style scoped>
.clo-statement :deep(p) {
	margin: 0;
}
</style>
