<template>
	<div class="competency-gradebook">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
		</header>

		<div v-if="context.loading" class="flex justify-center py-16">
			<LoadingIndicator class="h-8 w-8" />
		</div>

		<div v-else-if="context.data && !context.data.is_cbe" class="mx-5 my-8 max-w-xl">
			<h1 class="text-xl font-bold text-ink-gray-8">{{ __('Not a competency-based course') }}</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ __('This section is graded numerically. Use the gradebook instead.') }}
			</p>
			<router-link :to="{ name: 'Gradebook', params: { courseName: props.courseName } }">
				<Button variant="solid" class="mt-4">{{ __('Open Gradebook') }}</Button>
			</router-link>
		</div>

		<template v-else-if="context.data">
			<div class="border-b px-3 py-3 sm:px-5">
				<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('Competency Assessment') }}</h1>
				<p class="mt-1 text-sm text-ink-gray-6">{{ props.courseName }}</p>

				<div v-if="isFinalized" class="mt-3 rounded-md bg-surface-blue-1 px-4 py-3 text-sm text-ink-blue-3">
					{{ __('Grades for this course have been sent. This view is read-only.') }}
				</div>

				<!-- Send Selected appears only for open-ended sections (ADR 065 7a);
				     everywhere else grades are sent for the whole class at once. -->
				<div v-if="canSendSelected" class="mt-3 flex flex-wrap items-center gap-2">
					<Button variant="solid" theme="blue" :disabled="!selected.length || sending"
						:loading="sending" @click="sendSelected">
						<template #prefix><Send class="h-4 w-4" /></template>
						{{ __('Send Grades for Selected') }}
						<span v-if="selected.length">&nbsp;({{ selected.length }})</span>
					</Button>
					<span class="text-sm text-ink-gray-6">
						{{ __('This section has no end date, so students can be finalized as they finish. Sending is final for those students.') }}
					</span>
				</div>
			</div>

			<div class="flex flex-col gap-4 px-3 py-4 sm:flex-row sm:px-5">
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
							<input v-if="canSendSelected" type="checkbox" class="shrink-0"
								:value="r.name" v-model="selected" :disabled="r.finalized"
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
						<div v-if="detail.data.missing_evaluators?.length"
							class="mb-4 rounded-md bg-surface-amber-1 px-4 py-3 text-sm text-ink-amber-3">
							<p class="font-medium">{{ __('Still outstanding') }}</p>
							<ul class="mt-1 list-inside list-disc">
								<li v-for="(m, i) in detail.data.missing_evaluators" :key="i">{{ m }}</li>
							</ul>
						</div>

						<article v-for="c in detail.data.competencies" :key="c.name"
							class="mb-5 rounded-md border border-outline-gray-2">
							<header class="flex flex-wrap items-start justify-between gap-2 border-b px-4 py-3">
								<div class="min-w-0">
									<h3 class="font-semibold text-ink-gray-8">{{ c.competency_name }}</h3>
									<div v-if="c.statement" class="prose-sm mt-1 text-ink-gray-6"
										v-html="c.statement" />
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
												<div v-else class="space-y-2">
													<div v-for="ev in gradingEvaluators" :key="ev.instructor"
														class="space-y-1">
														<div class="text-xs text-ink-gray-5">{{ ev.instructor }}</div>
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
												<Button v-if="!isFinalized && c.result" size="sm" variant="ghost"
													class="mt-1" @click="openOverride(c, d)">
													{{ __('Edit') }}
												</Button>
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</article>
					</template>
				</section>
			</div>
		</template>

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
import {
	Badge, Breadcrumbs, Button, Dialog, FormControl, LoadingIndicator, Tooltip,
	createResource, call, toast,
} from 'frappe-ui'
import { computed, inject, ref, watch } from 'vue'
import { Send } from 'lucide-vue-next'
import ProgressBar from '@/components/ProgressBar.vue'

const user = inject('$user')
const props = defineProps({
	courseName: { type: String, required: true },
})

const activeRoster = ref(null)
const selected = ref([])
const sending = ref(false)

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{
		label: props.courseName,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{ label: __('Competency Assessment') },
])

const context = createResource({
	url: 'seminary.seminary.cbe_api.get_competency_context',
	makeParams: () => ({ course_schedule: props.courseName }),
	auto: true,
})

const roster = createResource({
	url: 'seminary.seminary.cbe_api.get_competency_roster',
	makeParams: () => ({ course_schedule: props.courseName }),
	onSuccess(data) {
		if (!activeRoster.value && data?.length) select(data[0].name)
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
	() => context.data?.is_cbe,
	(isCbe) => { if (isCbe) roster.reload() },
	{ immediate: true }
)

const levels = computed(() => context.data?.levels || [])
const isFinalized = computed(() =>
	['Closed', 'Cancelled'].includes(context.data?.workflow_state)
)

const canSendSelected = computed(
	() =>
		context.data?.open_ended &&
		context.data?.workflow_state === 'Grading' &&
		(user?.data?.is_moderator || user?.data?.is_instructor || user?.data?.is_evaluator)
)

// Only evaluators the framework says grade activities get chips; a mentor who
// only gives a final verdict should not be offered per-activity levels.
const gradingEvaluators = computed(
	() => (detail.data?.evaluators || []).filter((e) => e.grades_activities)
)

const canGradeAs = (ev) =>
	user?.data?.is_moderator || ev.instructor === context.data?.viewer?.instructor

const select = (name) => {
	activeRoster.value = name
	detail.reload()
}

const weightOf = (assessment, dimension) =>
	Number(assessment.weights?.[dimension.dimension_code] || 0)

const gradeFor = (assessment, ev, dimension) => {
	const perDimension = context.data?.framework?.activity_grading_mode ===
		'One grade per evaluator per dimension'
	const key = perDimension ? dimension.dimension_code : ''
	return assessment.grades?.[ev.instructor]?.[key]
}

const chipClass = (assessment, ev, dimension, level) => {
	const current = gradeFor(assessment, ev, dimension)
	return current?.level_code === level.grade_code
		? 'border-outline-gray-4 bg-surface-gray-4 font-medium text-ink-gray-9'
		: 'border-outline-gray-2 text-ink-gray-6 hover:bg-surface-gray-2'
}

const setLevel = async (assessment, ev, dimension, level) => {
	const perDimension = context.data?.framework?.activity_grading_mode ===
		'One grade per evaluator per dimension'
	try {
		await call('seminary.seminary.cbe_api.save_activity_grade', {
			roster: activeRoster.value,
			assess_criteria: assessment.name,
			instructor: ev.instructor,
			level_code: level.grade_code,
			dimension_code: perDimension ? dimension.dimension_code : null,
		})
		detail.reload()
		roster.reload()
	} catch (e) {
		toast.error(errorMessage(e, __('Could not save that level.')))
	}
}

const resultDim = (competency, dimension) =>
	(competency.result_dimensions || []).find(
		(r) => r.dimension_code === dimension.dimension_code
	)

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
		detail.reload()
	} catch (e) {
		toast.error(errorMessage(e, __('Could not save the override.')))
	} finally {
		savingOverride.value = false
	}
}

// --- send selected --------------------------------------------------------
const sendSelected = async () => {
	const names = (roster.data || [])
		.filter((r) => selected.value.includes(r.name))
		.map((r) => r.stuname_roster)
	const message = __(
		'Send grades for {0}? This writes their transcript and cannot be undone. The section stays open for everyone else.'
	).format(names.join(', '))
	if (!window.confirm(message)) return

	sending.value = true
	try {
		const res = await call('seminary.seminary.api.send_selected_grades', {
			course_schedule: props.courseName,
			rosters: JSON.stringify(selected.value),
		})
		toast.success(__('Grades sent for {0} student(s)').format(res.finalized))
		selected.value = []
		roster.reload()
		detail.reload()
	} catch (e) {
		toast.error(errorMessage(e, __('Could not send grades.')))
	} finally {
		sending.value = false
	}
}

function errorMessage(e, fallback) {
	if (Array.isArray(e?.messages) && e.messages.length) return e.messages.join('\n')
	const m = (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()
	return m || fallback
}

function stripHtml(html) {
	const el = document.createElement('div')
	el.innerHTML = html || ''
	return el.textContent || ''
}
</script>
