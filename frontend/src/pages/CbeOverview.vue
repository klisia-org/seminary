<template>
	<div>
		<PageHeader>
			<template #title>
				<Breadcrumbs class="h-7" :items="[{ label: __('CBE Overview') }]" />
			</template>
			<template v-if="overview.data?.school" #tabs>
				<PageTabs :tabs="tabs" v-model="tab" :label="__('Overview views')" />
			</template>
		</PageHeader>

		<div class="px-3 py-4 sm:px-5">
			<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('CBE Overview') }}</h1>
			<p class="mt-1 text-sm text-ink-gray-6">
				{{ overview.data && !overview.data.school
					? __('The students you teach or mentor in competency-based courses, and where each one stands.')
					: __('Competency progress across courses: who is stalled, and which evaluators are behind.') }}
			</p>

			<!-- Filters, one row above the data -->
			<div class="mt-4 flex flex-wrap items-end gap-3">
				<FormControl v-if="programOptions.length > 1" type="select" :label="__('Program')"
					:options="programOptions" v-model="filters.program" />
				<FormControl v-if="cohortOptions.length > 1" type="select" :label="__('Cohort')"
					:options="cohortOptions" v-model="filters.cohort" />
				<FormControl v-if="termOptions.length > 1" type="select" :label="__('Term')"
					:options="termOptions" v-model="filters.academic_term" />
				<FormControl type="select" :label="__('Course')" :options="sectionOptions"
					v-model="filters.course_schedule" />
				<label class="flex items-center gap-2 pb-1 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="onlyLagging" /> {{ __('Only lagging') }}
				</label>
				<label class="flex items-center gap-2 pb-1 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="filters.include_closed" /> {{ __('Include closed courses') }}
				</label>
			</div>

			<div v-if="overview.loading && !overview.data" class="flex justify-center py-12">
				<LoadingIndicator class="h-6 w-6" />
			</div>

			<!-- Students -->
			<template v-else-if="tab === 'students' || !overview.data?.school">
				<p v-if="!visibleSections.length" class="mt-6 text-sm text-ink-gray-5">
					{{ onlyLagging ? __('Nobody is lagging.') : __('No competency-based students match these filters.') }}
				</p>
				<section v-for="g in visibleSections" :key="g.course_schedule" class="mt-6">
					<div class="mb-2 flex flex-wrap items-baseline gap-2">
						<router-link class="font-semibold text-ink-gray-8 hover:underline"
							:to="{ name: 'CourseDetail', params: { courseName: g.course_schedule }, query: { tab: 'review' } }">
							{{ g.course }}
						</router-link>
						<span class="text-xs text-ink-gray-5">{{ g.course_schedule }}</span>
						<span v-if="g.academic_term" class="text-xs text-ink-gray-5">· {{ g.academic_term }}</span>
						<Badge v-if="g.open_ended" :label="__('Open-ended')" theme="gray" />
					</div>
					<div class="overflow-x-auto rounded-md border border-outline-gray-2">
						<table class="min-w-full text-sm">
							<thead>
								<tr class="bg-surface-gray-2 text-left text-ink-gray-7">
									<th class="px-3 py-2 font-medium">{{ __('Student') }}</th>
									<th v-for="c in g.competencies" :key="c.name" class="px-3 py-2 font-medium">
										<span :title="c.competency_name">{{ c.competency_code || c.competency_name }}</span>
									</th>
									<th class="px-3 py-2 font-medium">{{ __('Last activity') }}</th>
									<th class="px-3 py-2 font-medium">{{ __('Lagging') }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="r in rowsOf(g)" :key="r.roster" class="border-t align-top">
									<td class="px-3 py-2">
										<router-link class="text-ink-gray-8 hover:underline"
											:to="{ name: 'CourseDetail', params: { courseName: g.course_schedule }, query: { tab: 'review', roster: r.roster } }">
											{{ r.student_name }}
										</router-link>
										<div v-if="r.finalized" class="text-xs text-ink-gray-5">{{ __('Grades sent') }}</div>
									</td>
									<td v-for="cell in r.cells" :key="cell.competency" class="px-3 py-2">
										<router-link
											:to="{ name: 'CourseDetail', params: { courseName: g.course_schedule }, query: { tab: 'review', roster: r.roster } }">
											<Badge :label="stateLabel(cell)" :theme="stateTheme(cell.state)" />
										</router-link>
										<div v-if="cell.state === 'awaiting_mentor'" class="mt-0.5 max-w-[12rem] truncate text-xs text-ink-gray-5"
											:title="cell.label">{{ cell.label }}</div>
									</td>
									<td class="px-3 py-2 text-ink-gray-6">
										{{ r.last_activity ? formatDate(r.last_activity) : __('None yet') }}
									</td>
									<td class="px-3 py-2">
										<div v-for="l in r.lagging" :key="l.reason" class="flex items-center gap-1 text-xs text-ink-amber-3">
											<AlertTriangle class="h-3.5 w-3.5 shrink-0" /> {{ l.label }}
										</div>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</section>
			</template>

			<!-- Mentors -->
			<template v-else>
				<p v-if="!overview.data?.mentors?.length" class="mt-6 text-sm text-ink-gray-5">
					{{ __('No evaluators give verdicts in the courses that match these filters.') }}
				</p>
				<div v-else class="mt-6 overflow-x-auto rounded-md border border-outline-gray-2">
					<table class="min-w-full text-sm">
						<thead>
							<tr class="bg-surface-gray-2 text-left text-ink-gray-7">
								<th class="px-3 py-2 font-medium">{{ __('Evaluator') }}</th>
								<th class="px-3 py-2 font-medium">{{ __('Role') }}</th>
								<th class="px-3 py-2 text-right font-medium">{{ __('Students') }}</th>
								<th class="px-3 py-2 text-right font-medium">{{ __('Verdicts due') }}</th>
								<th class="px-3 py-2 text-right font-medium">{{ __('Oldest due') }}</th>
								<th class="px-3 py-2 text-right font-medium">{{ __('Plans to review') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="m in overview.data.mentors" :key="m.instructor" class="border-t">
								<td class="px-3 py-2 text-ink-gray-8">{{ m.instructor_name }}</td>
								<td class="px-3 py-2 text-ink-gray-6">{{ m.categories.join(', ') }}</td>
								<td class="px-3 py-2 text-right tabular-nums">{{ m.mentees }}</td>
								<td class="px-3 py-2 text-right tabular-nums">{{ m.due }}</td>
								<td class="px-3 py-2 text-right tabular-nums">
									{{ m.oldest_due_days != null ? __('{0} days').format(m.oldest_due_days) : '—' }}
								</td>
								<td class="px-3 py-2 text-right tabular-nums">{{ m.plans_to_review }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup>
// Competency progress across sections (privatedocs p012 decision 5). School
// roles see everyone, with a mentor lens; a mentor or instructor sees their own
// students, which makes this their caseload view. Every cell opens that student
// in the course's Competency Review tab.
import { Badge, Breadcrumbs, FormControl, LoadingIndicator, createResource } from 'frappe-ui'
import { computed, reactive, ref, watch } from 'vue'
import { AlertTriangle } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import PageTabs from '@/components/PageTabs.vue'
import { useTabParam } from '@/composables/useTabParam'
import { formatDate } from '@/utils'

const tabs = computed(() => [
	{ key: 'students', label: __('Students') },
	{ key: 'mentors', label: __('Mentors') },
])
const tab = useTabParam(['students', 'mentors'], 'students')

const filters = reactive({
	program: '',
	cohort: '',
	academic_term: '',
	course_schedule: '',
	include_closed: false,
})
const onlyLagging = ref(false)

const overview = createResource({
	url: 'seminary.seminary.cbe_overview.get_cbe_overview',
	makeParams: () => ({
		program: filters.program || undefined,
		cohort: filters.cohort || undefined,
		academic_term: filters.academic_term || undefined,
		course_schedule: filters.course_schedule || undefined,
		include_closed: filters.include_closed ? 1 : 0,
	}),
	auto: true,
})
watch(filters, () => overview.reload(), { deep: true })

const any = (label) => [{ label, value: '' }]
const opts = computed(() => overview.data?.filters || {})
const programOptions = computed(() => [
	...any(__('All programs')),
	...(opts.value.programs || []).map((p) => ({ label: p, value: p })),
])
const cohortOptions = computed(() => [...any(__('All cohorts')), ...(opts.value.cohorts || [])])
const termOptions = computed(() => [
	...any(__('All terms')),
	...(opts.value.terms || []).map((t) => ({ label: t, value: t })),
])
const sectionOptions = computed(() => [...any(__('All courses')), ...(opts.value.sections || [])])

const rowsOf = (g) => (onlyLagging.value ? g.rows.filter((r) => r.lagging.length) : g.rows)
const visibleSections = computed(() =>
	(overview.data?.sections || []).filter((g) => rowsOf(g).length)
)

// A state always shows as words; the colour only repeats it.
const stateLabel = (cell) =>
	({
		decided: cell.label || __('Decided'),
		awaiting_mentor: __('Awaiting evaluator'),
		awaiting_result: __('Awaiting result'),
		awaiting_self: __('Awaiting self-assessment'),
		working: __('Working'),
		not_started: __('Not started'),
	})[cell.state] || cell.state
const stateTheme = (state) =>
	({
		decided: 'green',
		awaiting_mentor: 'orange',
		awaiting_result: 'blue',
		awaiting_self: 'orange',
		working: 'blue',
	})[state] || 'gray'
</script>
