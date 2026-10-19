<template>
	<section class="px-3 py-4 sm:px-5">
		<div v-if="review.loading && !review.data" class="flex justify-center py-12">
			<LoadingIndicator class="h-6 w-6" />
		</div>
		<template v-else-if="review.data?.is_cbe">
			<p v-if="!review.data.rows.length" class="text-sm text-ink-gray-5">
				{{ __('No students, or no assessment is mapped to a competency yet.') }}
			</p>
			<template v-else>
				<div class="mb-3 flex flex-wrap items-center gap-3">
					<TabButtons :buttons="groupButtons" v-model="groupBy" />
					<TabButtons :buttons="filterButtons" v-model="filter" />
					<span v-if="review.data.turnaround_days" class="text-xs text-ink-gray-5">
						{{ __('Red: waiting longer than the {0}-day feedback turnaround.').format(review.data.turnaround_days) }}
					</span>
				</div>

				<p v-if="!groups.length" class="text-sm text-ink-gray-5">{{ __('Nothing matches this filter.') }}</p>
				<div v-else class="overflow-x-auto">
					<table class="min-w-full border-collapse text-sm">
						<thead>
							<tr>
								<th class="border border-outline-gray-2 bg-surface-gray-2 px-3 py-2 text-left">
									{{ groupBy === 'assessment' ? __('Student') : __('Assessment') }}
								</th>
								<th class="border border-outline-gray-2 bg-surface-gray-2 px-3 py-2 text-left">
									{{ __('Submitted') }}
								</th>
								<th v-for="cat in categories" :key="cat"
									class="border border-outline-gray-2 bg-surface-gray-2 px-3 py-2">
									{{ cat }}
								</th>
							</tr>
						</thead>
						<tbody v-for="g in groups" :key="g.key">
							<tr>
								<th :colspan="2 + categories.length"
									class="border border-outline-gray-2 bg-surface-gray-1 px-3 py-1.5 text-left font-semibold text-ink-gray-8">
									<button v-if="groupBy === 'student'" class="hover:underline"
										@click="emit('open-student', g.rows[0].roster)">
										{{ g.label }}
									</button>
									<template v-else>{{ g.label }}</template>
								</th>
							</tr>
							<tr v-for="row in g.rows" :key="row.roster + row.assess_criteria" class="hover:bg-surface-gray-1">
								<td class="border border-outline-gray-2 px-3 py-2">
									<button v-if="groupBy === 'assessment'" class="text-left hover:underline"
										@click="emit('open-student', row.roster)">
										{{ row.student_name }}
									</button>
									<template v-else>{{ row.title }}</template>
								</td>
								<td class="border border-outline-gray-2 px-3 py-2 whitespace-nowrap">
									<router-link v-if="row.submission" :to="submissionRoute(row.submission)"
										class="text-ink-blue-3 hover:underline">
										{{ formatDate(row.submission.submitted_on) }}
									</router-link>
									<span v-else class="text-ink-gray-4">{{ __('Not submitted') }}</span>
								</td>
								<!-- One grade for the whole activity has no evaluator axis. -->
								<td v-if="row.activity_cell" :colspan="categories.length || 1"
									class="border border-outline-gray-2 px-3 py-2 text-center">
									<Tooltip v-if="row.activity_cell.state === 'graded'" :text="row.activity_cell.instructor">
										<span class="text-ink-gray-9">{{ row.activity_cell.level_code }}</span>
									</Tooltip>
									<span v-else :class="waitingClass(row)">{{ __('Not graded') }}</span>
								</td>
								<template v-else>
									<td v-for="cat in categories" :key="cat"
										class="border border-outline-gray-2 px-3 py-2 text-center">
										<template v-for="cell in [row.cells[cat]]" :key="cat">
											<Tooltip v-if="!cell || cell.state === 'na'" :text="__('Not applicable')">
												<span class="text-ink-gray-4">—</span>
											</Tooltip>
											<span v-else-if="cell.state === 'not_graded'" :class="waitingClass(row)">
												{{ __('Not graded') }}
											</span>
											<Tooltip v-else :text="cellDetail(cell)">
												<span :class="cell.state === 'graded' ? 'text-ink-gray-9' : waitingClass(row)">
													{{ cell.level_code || __('{0}/{1} dimensions').format(cell.graded, cell.asked) }}
												</span>
											</Tooltip>
										</template>
									</td>
								</template>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
		</template>
	</section>
</template>

<script setup>
import { LoadingIndicator, TabButtons, Tooltip, createResource } from 'frappe-ui'
import { computed, ref } from 'vue'

const props = defineProps({
	courseName: { type: String, required: true },
})
const emit = defineEmits(['open-student'])

const review = createResource({
	url: 'seminary.seminary.cbe_api.get_assessment_review',
	makeParams: () => ({ course_schedule: props.courseName }),
	auto: true,
})

defineExpose({ reload: () => review.reload() })

const categories = computed(() => review.data?.categories || [])

const groupBy = ref('assessment')
const groupButtons = [
	{ label: __('By assessment'), value: 'assessment' },
	{ label: __('By student'), value: 'student' },
]

const filter = ref('all')
const filterButtons = computed(() => [
	{ label: __('All'), value: 'all' },
	{ label: __('Not graded'), value: 'waiting' },
	{ label: __('Not submitted'), value: 'missing' },
	...(review.data?.turnaround_days ? [{ label: __('Overdue'), value: 'overdue' }] : []),
])

const keep = (row) => {
	if (filter.value === 'waiting') return row.submission && !row.complete
	if (filter.value === 'missing') return !row.submission
	if (filter.value === 'overdue') return row.overdue
	return true
}

// Rows arrive student by student, each in outline order; grouping by
// assessment keeps that order for the groups and the students within them.
const groups = computed(() => {
	const byAssessment = groupBy.value === 'assessment'
	const out = new Map()
	for (const row of review.data?.rows || []) {
		if (!keep(row)) continue
		const key = byAssessment ? row.assess_criteria : row.roster
		if (!out.has(key)) {
			out.set(key, { key, label: byAssessment ? row.title : row.student_name, rows: [] })
		}
		out.get(key).rows.push(row)
	}
	return [...out.values()]
})

const waitingClass = (row) => (row.overdue ? 'font-medium text-ink-red-3' : 'text-ink-gray-5')

const cellDetail = (cell) =>
	cell.detail
		.map((d) => `${d.dimension}: ${d.level_code || __('Not graded')}${d.instructor ? ` (${d.instructor})` : ''}`)
		.join('\n')

const submissionRoute = (s) => {
	const courseName = props.courseName
	switch (s.doctype) {
		case 'Assignment Submission':
			return { name: 'AssignmentSubmission', params: { courseName, assignmentID: s.activity, submissionName: s.name } }
		case 'Exam Submission':
			return { name: 'ExamSubmission', params: { courseName, examID: s.activity, submission: s.name } }
		case 'Discussion Submission':
			return { name: 'DiscussionActivitySubmission', params: { courseName, discussionID: s.activity, submissionName: s.name } }
		default:
			return { name: 'QuizSubmission', params: { submission: s.name } }
	}
}

// Frappe sends "YYYY-MM-DD HH:mm:ss", which Safari will not parse without the T.
const formatDate = (value) =>
	new Date(String(value).replace(' ', 'T')).toLocaleString(undefined, {
		month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
	})
</script>
