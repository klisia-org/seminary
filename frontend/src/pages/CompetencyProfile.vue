<template>
	<div class="competency-profile">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<FormControl v-if="(profile.data?.enrollments || []).length > 1" type="select"
				:options="enrollmentOptions" v-model="enrollment" />
		</header>

		<div v-if="profile.loading" class="flex justify-center py-16">
			<LoadingIndicator class="h-8 w-8" />
		</div>

		<div v-else-if="!profile.data?.is_cbe" class="mx-5 my-8 max-w-xl">
			<h1 class="text-xl font-bold text-ink-gray-8">{{ __('No competency profile') }}</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ __('None of your programmes are assessed by competency.') }}
			</p>
		</div>

		<div v-else class="px-3 py-4 sm:px-5">
			<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('My Formation') }}</h1>
			<p class="mt-1 max-w-2xl text-sm text-ink-gray-6">
				{{ __('Where you said you were starting, where you say you are now, and what your mentors saw. The gaps between them are the conversation.') }}
			</p>

			<!-- Controls -->
			<div class="mt-5 flex flex-wrap items-end gap-3">
				<FormControl type="select" :label="__('Compare')" :options="comparisonOptions"
					v-model="comparison" class="min-w-[16rem]" />
				<FormControl type="select" :label="__('Axes')" :options="scopeOptions" v-model="scope"
					class="min-w-[12rem]" />
				<FormControl type="select" :label="__('Course')" :options="courseOptions" v-model="course"
					class="min-w-[16rem]" />
			</div>

			<div v-if="!courses.length" class="mt-8 max-w-xl text-sm text-ink-gray-6">
				{{ __('Nothing has been assessed yet in this programme.') }}
			</div>

			<template v-else>
				<div class="mt-5 rounded-md border border-outline-gray-2 bg-surface-white px-2 py-3">
					<RadarChart :indicators="indicators" :series="chartSeries"
						:levels="profile.data.levels || []" />
					<p v-if="missingSeries.length" class="px-4 pb-2 text-xs text-ink-gray-5">
						{{ __('Not plotted, because it has not been recorded yet: {0}.')
							.format(missingSeries.join(', ')) }}
					</p>
				</div>

				<!-- The numbers behind the shape -->
				<div class="mt-6 overflow-x-auto rounded-md border border-outline-gray-2">
					<table class="w-full min-w-[36rem] text-sm">
						<thead>
							<tr class="border-b bg-surface-gray-1 text-left text-ink-gray-6">
								<th class="px-4 py-2 font-medium">
									{{ scope === 'dimension' ? __('Dimension') : __('Competency') }}
								</th>
								<th v-for="s in activeSeries" :key="s.key" class="px-4 py-2 font-medium">
									{{ s.label }}
								</th>
								<th class="px-4 py-2 font-medium">{{ __('Change') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="(ind, i) in indicators" :key="ind.name" class="border-b">
								<td class="px-4 py-2 text-ink-gray-8">{{ ind.name }}</td>
								<td v-for="s in activeSeries" :key="s.key" class="px-4 py-2 text-ink-gray-7">
									{{ levelLabel(seriesValues(s.key)[i]) }}
								</td>
								<td class="px-4 py-2" :class="deltaClass(delta(i))">{{ deltaLabel(delta(i)) }}</td>
							</tr>
						</tbody>
					</table>
				</div>

				<!-- What people actually said -->
				<h2 class="mt-8 text-lg font-semibold text-ink-gray-8">{{ __('In their words') }}</h2>
				<p class="mt-1 text-sm text-ink-gray-6">
					{{ __('Every narrative written about these competencies, newest last.') }}
				</p>

				<div v-if="!narratives.length" class="mt-3 text-sm text-ink-gray-5">
					{{ __('No narratives yet.') }}
				</div>
				<div v-else class="mt-3 space-y-6">
					<section v-for="group in narratives" :key="group.key">
						<h3 class="font-semibold text-ink-gray-8">{{ group.competency_name }}</h3>
						<div class="text-xs text-ink-gray-5">{{ group.course_name }}</div>
						<div class="mt-2 overflow-x-auto rounded-md border border-outline-gray-2">
							<table class="w-full min-w-[40rem] text-sm">
								<thead>
									<tr class="border-b bg-surface-gray-1 text-left text-ink-gray-6">
										<th class="px-4 py-2 font-medium">{{ __('Who') }}</th>
										<th class="px-4 py-2 font-medium">{{ __('When') }}</th>
										<th class="px-4 py-2 font-medium">{{ __('About') }}</th>
										<th class="px-4 py-2 font-medium">{{ __('Level') }}</th>
										<th class="px-4 py-2 font-medium">{{ __('What they said') }}</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="(n, idx) in group.rows" :key="idx" class="border-b align-top">
										<td class="px-4 py-2 whitespace-nowrap">
											<div class="text-ink-gray-8">{{ n.evaluator }}</div>
											<div class="text-xs text-ink-gray-5">
												{{ n.evaluator_kind === 'Self' ? stageLabel(n.stage) : n.instructor_category }}
											</div>
										</td>
										<td class="px-4 py-2 whitespace-nowrap text-ink-gray-6">
											{{ n.submitted_on ? formatDate(n.submitted_on) : '—' }}
										</td>
										<td class="px-4 py-2 text-ink-gray-6">{{ n.dimension || __('Overall') }}</td>
										<td class="px-4 py-2">
											<Badge v-if="n.level_code" :label="n.level_code" theme="gray" />
											<span v-else class="text-ink-gray-4">—</span>
										</td>
										<td class="px-4 py-2 text-ink-gray-7">
											<span v-if="n.narrative">{{ stripHtml(n.narrative) }}</span>
											<span v-else class="text-ink-gray-4">—</span>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</section>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup>
import { Badge, Breadcrumbs, FormControl, LoadingIndicator, createResource } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import RadarChart from '@/components/RadarChart.vue'
import { formatDate } from '@/utils'

const enrollment = ref(null)
const comparison = ref('baseline_self')
const scope = ref('competency')
const course = ref('all')

const breadcrumbs = [
	{ label: __('Transcripts'), route: { name: 'Transcripts' } },
	{ label: __('My Formation') },
]

const profile = createResource({
	url: 'seminary.seminary.cbe_api.get_competency_profile',
	makeParams: () => ({ program_enrollment: enrollment.value || undefined }),
	auto: true,
	onSuccess(data) {
		if (data?.program_enrollment && !enrollment.value) {
			enrollment.value = data.program_enrollment
		}
	},
	onError: () => {},
})

watch(enrollment, (v, old) => {
	if (old && v !== old) {
		course.value = 'all'
		profile.reload()
	}
})

const enrollmentOptions = computed(() =>
	(profile.data?.enrollments || []).map((e) => ({ label: e.program, value: e.name }))
)

// Which comparisons are worth offering depends on whether the school runs a
// baseline at all, so they are derived from what came back rather than fixed.
const SERIES = {
	baseline: { key: 'baseline', label: __('Starting point') },
	self_final: { key: 'self_final', label: __('Where I am now') },
	mentor_final: { key: 'mentor_final', label: __('My mentors') },
	result: { key: 'result', label: __('Recorded result') },
}

const comparisonOptions = [
	{ label: __('Starting point vs. where I am now'), value: 'baseline_self' },
	{ label: __('Starting point vs. my mentors'), value: 'baseline_mentor' },
	{ label: __('Where I am now vs. my mentors'), value: 'self_mentor' },
	{ label: __('My mentors vs. recorded result'), value: 'mentor_result' },
]

const scopeOptions = [
	{ label: __('One axis per competency'), value: 'competency' },
	{ label: __('One axis per dimension'), value: 'dimension' },
]

const courses = computed(() => profile.data?.courses || [])

const courseOptions = computed(() => [
	{ label: __('All courses'), value: 'all' },
	...courses.value.map((c) => ({ label: c.course_name, value: c.course_schedule })),
])

const shownCourses = computed(() =>
	course.value === 'all'
		? courses.value
		: courses.value.filter((c) => c.course_schedule === course.value)
)

const activeSeries = computed(() => {
	const pair = {
		baseline_self: ['baseline', 'self_final'],
		baseline_mentor: ['baseline', 'mentor_final'],
		self_mentor: ['self_final', 'mentor_final'],
		mentor_result: ['mentor_final', 'result'],
	}[comparison.value]
	return pair.map((k) => SERIES[k])
})

const indicators = computed(() => {
	const max = profile.data?.max_value || 4
	if (scope.value === 'dimension') {
		return (profile.data?.dimensions || []).map((d) => ({ name: d.dimension, max }))
	}
	return shownCourses.value
		.flatMap((c) => c.competencies)
		.map((c) => ({ name: c.competency_name, max }))
})

const dimensionCodes = computed(() =>
	(profile.data?.dimensions || []).map((d) => d.dimension_code)
)

// One value per axis. On the dimension view a dimension is averaged across
// every competency that has a value for it; a dimension nobody rated stays
// null rather than becoming a zero, because a zero would draw as "not
// competent" and that is a different claim.
function seriesValues(key) {
	const shown = shownCourses.value
	if (scope.value === 'dimension') {
		return dimensionCodes.value.map((code) => {
			const vals = shown
				.flatMap((c) => c.competencies)
				.map((c) => c.series?.[key]?.[code])
				.filter((v) => v != null)
			return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null
		})
	}
	return shown.flatMap((c) => c.competencies).map((c) => {
		const v = c.overall?.[key]
		return v == null ? null : v
	})
}

const chartSeries = computed(() =>
	activeSeries.value.map((s) => ({ name: s.label, values: seriesValues(s.key) }))
)

const missingSeries = computed(() =>
	activeSeries.value
		.filter((s) => !seriesValues(s.key).some((v) => v != null))
		.map((s) => s.label)
)

function delta(i) {
	const [a, b] = activeSeries.value
	const from = seriesValues(a.key)[i]
	const to = seriesValues(b.key)[i]
	if (from == null || to == null) return null
	return to - from
}

const deltaLabel = (d) =>
	d == null ? '—' : `${d > 0 ? '+' : ''}${Math.round(d * 100) / 100}`

const deltaClass = (d) => {
	if (d == null) return 'text-ink-gray-4'
	if (d > 0) return 'text-ink-green-3'
	if (d < 0) return 'text-ink-amber-3'
	return 'text-ink-gray-6'
}

function levelLabel(value) {
	if (value == null) return '—'
	const rounded = Math.round(value * 100) / 100
	const level = (profile.data?.levels || []).find(
		(l) => Number(l.threshold) === Math.round(value)
	)
	return level ? `${rounded} (${level.grade_code})` : `${rounded}`
}

const stageLabel = (s) => (s === 'Baseline' ? __('Starting point') : __('Where I am now'))

// Narratives are stored as rich text; the table wants one readable line.
const stripHtml = (html) => {
	const el = document.createElement('div')
	el.innerHTML = html || ''
	return (el.textContent || '').trim()
}

const narratives = computed(() =>
	shownCourses.value.flatMap((c) =>
		c.competencies
			.filter((comp) => (comp.narratives || []).length)
			.map((comp) => ({
				key: `${c.course_schedule}:${comp.name}`,
				competency_name: comp.competency_name,
				course_name: c.course_name,
				rows: comp.narratives,
			}))
	)
)
</script>
