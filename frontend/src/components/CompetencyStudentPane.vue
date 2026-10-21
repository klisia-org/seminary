<template>
<div class="competency-student-pane">
	<div class="flex flex-col gap-4 sm:flex-row" :class="padded ? 'px-3 py-4 sm:px-5' : ''">
		<!-- Roster -->
		<aside class="w-full shrink-0 sm:w-72">
			<div class="mb-2 flex items-center justify-between">
				<h2 class="text-sm font-semibold uppercase tracking-wide text-ink-gray-6">
					{{ __('Students') }}
				</h2>
				<Badge v-if="roster.data" :label="String(roster.data.length)" theme="gray" />
			</div>
			<p v-if="roster.data && !roster.data.length" class="text-sm text-ink-gray-5">
				{{ __('There are no students enrolled in this course.') }}
			</p>
			<ul v-else class="divide-y rounded-md border border-outline-gray-2">
				<li v-for="r in roster.data || []" :key="r.name"
					class="flex items-center gap-2 px-2 py-2"
					:class="r.name === activeRoster ? 'bg-surface-gray-2' : ''">
					<input v-if="selectable" type="checkbox" class="shrink-0"
						:value="r.name" v-model="selectedModel" :disabled="r.finalized"
						:aria-label="__('Select {0}').format(r.stuname_roster)" />
					<button class="min-w-0 flex-1 text-left" @click="select(r.name)">
						<div class="flex items-center justify-between gap-2">
							<span class="truncate text-sm font-medium text-ink-gray-8">
								{{ r.stuname_roster }}
							</span>
							<span class="shrink-0 text-xs text-ink-gray-5">{{ r.progress }}%</span>
						</div>
						<ProgressBar :progress="r.progress" class="mt-1" />
						<span v-if="r.finalized" class="text-xs text-ink-gray-5">
							{{ __('Grades sent') }}
						</span>
					</button>
				</li>
			</ul>
		</aside>

		<!-- Selected student -->
		<section class="min-w-0 flex-1">
			<div v-if="detail.loading" class="flex justify-center py-12">
				<LoadingIndicator class="h-6 w-6" />
			</div>
			<p v-else-if="!activeRoster" class="text-sm text-ink-gray-5">
				{{ __('Select a student to record their assessment.') }}
			</p>

			<template v-else-if="detail.data">
					<!-- The before-and-after, every evaluator apart (p012 decision 3). -->
					<CompetencyReview v-if="showReview" ref="reviewRef" class="mb-5"
						:courseName="courseName" :student="detail.data.student" />
				<!-- The plan is the student's word on what comes next; a
				     mentor reads and responds to it here (ADR 065 §8). -->
				<div v-if="requiresPdp" class="mb-4 flex justify-end">
					<router-link :to="{
						name: 'PersonalDevelopmentPlan',
						params: { courseName: props.courseName },
						query: { student: detail.data.student },
					}">
						<Button variant="subtle" size="sm">
							{{ __('Development Plan') }}
						</Button>
					</router-link>
				</div>

				<div v-if="detail.data.missing_evaluators?.length"
					class="mb-4 rounded-md bg-surface-amber-1 px-4 py-3 text-sm text-ink-amber-3">
					<p class="font-medium">{{ __('Still outstanding') }}</p>
					<ul class="mt-1 list-inside list-disc">
						<li v-for="m in detail.data.missing_evaluators" :key="`${m.instructor}-${m.assess_criteria}`">{{ m.message }}</li>
					</ul>
				</div>

				<article v-for="c in detail.data.competencies" :key="c.name"
					class="mb-5 rounded-md border border-outline-gray-2">
					<header class="flex flex-wrap items-start justify-between gap-2 border-b px-4 py-3">
						<div class="min-w-0">
							<h3 class="font-semibold text-ink-gray-8">{{ c.competency_name }}</h3>
							<SafeHtml v-if="c.statement" class="prose-sm mt-1 text-ink-gray-6"
								:html="c.statement" />
						</div>
						<Badge v-if="c.result?.final_code" :label="c.result.final_code"
							:theme="c.result.status === 'Competent' ? 'green' : 'orange'" />
					</header>

					<div class="overflow-x-auto">
						<table class="min-w-full border-collapse text-sm">
							<thead>
								<tr class="bg-surface-gray-2 text-left">
									<th class="px-3 py-2 font-medium">{{ __('Dimension') }}</th>
									<th v-for="a in c.assessments" :key="a.name" class="px-3 py-2 font-medium">
										{{ a.title }}
									</th>
									<th class="px-3 py-2 font-medium">{{ __('Result') }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="d in c.dimensions" :key="d.dimension_code" class="border-t align-top">
									<th class="px-3 py-3 text-left font-medium text-ink-gray-7">
										<div>{{ d.dimension }}</div>
										<Tooltip v-if="d.demonstrated_by" :text="stripHtml(d.demonstrated_by)">
											<span class="text-xs font-normal text-ink-gray-5 underline decoration-dotted">
												{{ __('How this is demonstrated') }}
											</span>
										</Tooltip>
									</th>
									<td v-for="a in c.assessments" :key="a.name" class="px-3 py-3">
										<p v-if="!weightOf(a, d)" class="text-xs text-ink-gray-4">
											{{ __('Not measured here') }}
										</p>
										<div v-else-if="!evaluatorsFor(a, d).length" class="text-xs text-ink-gray-4">
											{{ __('Nobody grades this here') }}
										</div>
										<div v-else class="space-y-2">
											<div v-for="ev in evaluatorsFor(a, d)" :key="`${ev.instructor}-${ev.instructor_category}`"
												class="space-y-1">
												<div class="text-xs text-ink-gray-5">{{ ev.instructor_name }}</div>
												<div class="flex flex-wrap gap-1">
													<button v-for="lv in levels" :key="lv.grade_code"
														type="button"
														class="rounded border px-2 py-0.5 text-xs"
														:class="chipClass(a, ev, d, lv)"
														:disabled="isFinalized || !canGradeAs(ev)"
														@click="setLevel(a, ev, d, lv)">
														{{ lv.grade_code }}
													</button>
												</div>
											</div>
										</div>
									</td>
									<td class="px-3 py-3">
										<div class="font-medium text-ink-gray-8">
											{{ resultDim(c, d)?.final_code || '—' }}
										</div>
										<div v-if="resultDim(c, d)?.computed_value != null"
											class="text-xs text-ink-gray-5">
											{{ __('Computed') }}: {{ resultDim(c, d).computed_value }}
										</div>
										<div v-if="resultDim(c, d)?.override_value"
											class="text-xs text-ink-amber-3">
											{{ __('Overridden') }}: {{ resultDim(c, d).override_value }}
										</div>
										<Button v-if="!isFinalized && c.result && canOverride" size="sm" variant="ghost"
											class="mt-1" @click="openOverride(c, d)">
											{{ __('Edit') }}
										</Button>
									</td>
								</tr>
							</tbody>
						</table>
					</div>

					<!-- The mentor's own view of the competency, beside the
					     student's (ADR 079 decision 6). -->
					<div v-if="givesVerdict" class="border-t px-4 py-4">
						<div class="mb-3 flex flex-wrap items-center gap-2">
							<h4 class="font-semibold text-ink-gray-8">{{ __('Your assessment') }}</h4>
							<Badge v-if="myAssessment(c)?.status === 'Submitted'"
								:label="__('Submitted')" theme="green" />
							<Badge v-else-if="c.mentor_due" :label="__('Due')" theme="orange" />
							<span v-else class="text-xs text-ink-gray-5">
								{{ __('Not due yet: the student still has work to submit for this competency.') }}
							</span>
						</div>
						<CompetencyRatingForm :dimensions="mentorDimensions(c)" :levels="levels"
							:narrative="myAssessment(c)?.narrative || ''"
							:locked="isFinalized || myAssessment(c)?.status === 'Submitted'"
							:saving="mentorSaving[c.name] || null"
							:comparisons="studentView(c)"
							:comparison-title="__('The student has assessed this competency.')"
							:dimension-narrative-label="__('What you observed')"
							:overall-label="__('Overall, for this competency')"
							@save="(payload) => saveMentor(c, payload)" />
					</div>
				</article>
			</template>
		</section>
	</div>

	<Dialog v-model="overrideDialog" :options="{ title: __('Replace the computed value') }">
		<template #body-content>
			<p class="mb-3 text-sm text-ink-gray-6">
				{{ __('The computed value is kept alongside your replacement, together with your name and this reason.') }}
			</p>
			<FormControl type="number" step="0.01" :label="__('Value')" v-model="overrideValue" class="mb-3" />
			<FormControl type="textarea" :label="__('Reason')" v-model="overrideReason" />
		</template>
		<template #actions>
			<Button variant="solid" :loading="savingOverride"
				:disabled="!overrideReason || overrideValue === '' || overrideValue === null"
				@click="saveOverride">
				{{ __('Save') }}
			</Button>
		</template>
	</Dialog>
</div>
</template>

<script setup>
// One student's competency work in a section: the roster on the left, the
// selected student's review, activity levels, mentor verdict and result on the
// right. Shared by the gradebook's "By student" view and the course page's
// Competency Review tab (privatedocs p012 decision 3); the server scopes the
// roster to the viewer, so a mentor sees only their own students.
import {
	Badge, Button, Dialog, FormControl, LoadingIndicator, Tooltip,
	createResource, call, toast,
} from 'frappe-ui'
import { htmlToText } from '@/utils'
import { computed, inject, ref, watch } from 'vue'
import ProgressBar from '@/components/ProgressBar.vue'
import CompetencyRatingForm from '@/components/CompetencyRatingForm.vue'
import CompetencyReview from '@/components/CompetencyReview.vue'

const user = inject('$user')
const props = defineProps({
	courseName: { type: String, required: true },
	// get_competency_context's payload, already loaded by the host page.
	context: { type: Object, default: null },
	selectable: { type: Boolean, default: false },
	selected: { type: Array, default: () => [] },
	initialRoster: { type: String, default: null },
	showReview: { type: Boolean, default: false },
	padded: { type: Boolean, default: false },
})
const emit = defineEmits(['update:selected', 'graded'])

const selectedModel = computed({
	get: () => props.selected,
	set: (v) => emit('update:selected', v),
})

const activeRoster = ref(props.initialRoster)
const reviewRef = ref(null)

const roster = createResource({
	url: 'seminary.seminary.cbe_api.get_competency_roster',
	makeParams: () => ({ course_schedule: props.courseName }),
	onSuccess(data) {
		if (activeRoster.value) detail.reload()
		else if (data?.length) select(data[0].name)
	},
	// Silent: an ordinary section legitimately returns nothing here.
	onError: () => {},
})

const detail = createResource({
	url: 'seminary.seminary.cbe_api.get_student_competency_detail',
	makeParams: () => ({ roster: activeRoster.value }),
	onError: () => {},
})

watch(
	() => props.context?.is_cbe,
	(isCbe) => {
		if (isCbe) roster.reload()
	},
	{ immediate: true }
)

const select = (name) => {
	activeRoster.value = name
	detail.reload()
}

const refresh = () => {
	detail.reload()
	roster.reload()
	reviewRef.value?.reload()
	emit('graded')
}

defineExpose({ select, roster, reload: refresh })

// --- the mentor's assessment ---------------------------------------------------
const viewerInstructor = computed(() => props.context?.viewer?.instructor)
const givesVerdict = computed(() =>
	(detail.data?.evaluators || []).some(
		(e) => e.instructor === viewerInstructor.value && e.gives_competency_verdict
	)
)
const myAssessment = (c) =>
	(c.assessments_by_mentor || []).find(
		(r) => r.evaluator_kind === 'Mentor' && r.instructor === viewerInstructor.value
	)
const byDimension = (ratings) =>
	Object.fromEntries((ratings || []).map((r) => [r.dimension_code, r]))
const mentorDimensions = (c) => {
	const saved = byDimension(myAssessment(c)?.ratings)
	return (c.dimensions || []).map((d) => ({
		...d,
		level_code: saved[d.dimension_code]?.level_code || null,
		narrative: saved[d.dimension_code]?.narrative || '',
	}))
}
// The student's own Final view, unless the framework withholds it from a
// mentor who has not yet formed theirs (`mentor_sees_self_eval`).
const studentView = (c) =>
	(c.assessments_by_mentor || [])
		.filter((r) => r.evaluator_kind === 'Self' && r.stage === 'Final' && !r.withheld
			&& r.status === 'Submitted')
		.map((r) => ({
			key: r.name,
			label: detail.data?.student_name || __('Student'),
			sublabel: __('Self-assessment'),
			tone: 'self',
			narrative: r.narrative,
			ratings: byDimension(r.ratings),
		}))

const mentorSaving = ref({})
const saveMentor = async (c, { submit, ratings, narrative }) => {
	if (submit && !window.confirm(__('Submit your assessment of {0}? It cannot be changed afterwards.').format(c.competency_name))) {
		return
	}
	mentorSaving.value = { ...mentorSaving.value, [c.name]: submit ? 'submit' : 'draft' }
	try {
		await call('seminary.seminary.cbe_api.save_mentor_assessment', {
			roster: activeRoster.value,
			course_competency: c.name,
			ratings: JSON.stringify(ratings),
			narrative,
			submit: submit ? 1 : 0,
		})
		toast.success(submit ? __('Assessment submitted') : __('Draft saved'))
		refresh()
	} catch (e) {
		toast.error(e?.messages?.[0] || e?.message || __('Could not save your assessment.'))
	} finally {
		mentorSaving.value = { ...mentorSaving.value, [c.name]: null }
	}
}

const levels = computed(() => props.context?.levels || [])
const requiresPdp = computed(() => !!props.context?.framework?.require_pdp)
const isFinalized = computed(() =>
	['Closed', 'Cancelled'].includes(props.context?.workflow_state)
)

// Only evaluators the framework says grade activities get chips; a mentor who
// only gives a final verdict should not be offered per-activity levels.
const gradingEvaluators = computed(
	() => (detail.data?.evaluators || []).filter((e) => e.grades_activities)
)

// An opted-out cell is not applicable, so it gets no picker at all — offering
// one would invite a grade that nothing reads (ADR 065 section 11b).
const evaluatorsFor = (assessment, dimension) =>
	gradingEvaluators.value.filter(
		(e) => assessment.graded_cells?.[`${e.instructor_category}|${dimension.dimension_code}`]
	)

const canGradeAs = (ev) =>
	user?.data?.is_moderator || ev.instructor === props.context?.viewer?.instructor

const weightOf = (assessment, dimension) =>
	Number(assessment.weights?.[dimension.dimension_code] || 0)

const perDimension = () =>
	props.context?.framework?.activity_grading_mode === 'One grade per evaluator per dimension'

const gradeFor = (assessment, ev, dimension) => {
	const key = perDimension() ? dimension.dimension_code : ''
	return assessment.grades?.[ev.instructor]?.[key]
}

const chipClass = (assessment, ev, dimension, level) => {
	const current = gradeFor(assessment, ev, dimension)
	return current?.level_code === level.grade_code
		? 'border-outline-gray-4 bg-surface-gray-4 font-medium text-ink-gray-9'
		: 'border-outline-gray-2 text-ink-gray-6 hover:bg-surface-gray-2'
}

const setLevel = async (assessment, ev, dimension, level) => {
	try {
		await call('seminary.seminary.cbe_api.save_activity_grade', {
			roster: activeRoster.value,
			assess_criteria: assessment.name,
			instructor: ev.instructor,
			level_code: level.grade_code,
			dimension_code: perDimension() ? dimension.dimension_code : null,
		})
		refresh()
	} catch (e) {
		toast.error(errorMessage(e, __('Could not save that level.')))
	}
}

const resultDim = (competency, dimension) =>
	(competency.result_dimensions || []).find(
		(r) => r.dimension_code === dimension.dimension_code
	)

// The recorded result is the section's: only its staff replace a value.
const canOverride = computed(() => props.context?.viewer?.access === 'instructor')

// --- override -------------------------------------------------------------
const overrideDialog = ref(false)
const overrideValue = ref('')
const overrideReason = ref('')
const overrideTarget = ref(null)
const savingOverride = ref(false)

const openOverride = (competency, dimension) => {
	const row = resultDim(competency, dimension)
	overrideTarget.value = { result: competency.result.name, dimension }
	overrideValue.value = row?.override_value ?? row?.computed_value ?? ''
	overrideReason.value = row?.override_reason || ''
	overrideDialog.value = true
}

const saveOverride = async () => {
	savingOverride.value = true
	try {
		await call('seminary.seminary.cbe_api.set_result_override', {
			result: overrideTarget.value.result,
			dimension_code: overrideTarget.value.dimension.dimension_code,
			override_value: overrideValue.value,
			override_reason: overrideReason.value,
		})
		overrideDialog.value = false
		refresh()
	} catch (e) {
		toast.error(errorMessage(e, __('Could not save the override.')))
	} finally {
		savingOverride.value = false
	}
}

function errorMessage(e, fallback) {
	if (Array.isArray(e?.messages) && e.messages.length) return e.messages.join('\n')
	const m = (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()
	return m || fallback
}

function stripHtml(html) {
	return htmlToText(html)
}
</script>
