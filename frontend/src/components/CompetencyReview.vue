<!--
  One student's competencies as a before-and-after (privatedocs p012 decision 3).

  Per competency, a grid: one lane per voice (the student, each instructor, each
  mentor, the recorded result) by one strip per dimension, the scale's levels
  along each strip. Lanes are direct-labelled, so nobody is averaged into
  anybody else and identity never rests on colour alone. Three hues only (self,
  instructor, mentor); several mentors are told apart by marker shape and by
  their lane label. A missing value leaves its cell empty and hides nothing.

  The course radar underneath answers the other question -- where across the
  course -- and draws only complete series, naming the ones it leaves out
  (echarts would close a gap through the centre, which reads as the lowest level).
-->
<template>
	<div class="competency-review" :data-viz-theme="theme">
		<div v-if="review.loading && !review.data" class="flex justify-center py-12">
			<LoadingIndicator class="h-6 w-6" />
		</div>
		<p v-else-if="review.data && review.data.enrolled === false" class="text-sm text-ink-gray-5">
			{{ __('Not on the roster of this course.') }}
		</p>

		<template v-else-if="review.data?.is_cbe">
			<div class="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-gray-6"
				:aria-label="__('Marker legend')">
				<span class="inline-flex items-center gap-1">
					<Marker kind="baseline" /> {{ __('Starting point') }}
				</span>
				<span class="inline-flex items-center gap-1">
					<Marker kind="self" /> {{ __('Final self-assessment') }}
				</span>
				<span class="inline-flex items-center gap-1">
					<Marker kind="instructor" /> {{ __('Instructor') }}
				</span>
				<span class="inline-flex items-center gap-1">
					<Marker kind="mentor" /> {{ __('Mentor') }}
				</span>
				<span class="inline-flex items-center gap-1">
					<Marker kind="result" /> {{ __('Recorded result') }}
				</span>
				<button class="ml-auto text-ink-gray-6 underline decoration-dotted"
					@click="asTable = !asTable">
					{{ asTable ? __('Show as chart') : __('Show as table') }}
				</button>
			</div>

			<article v-for="c in review.data.competencies" :key="c.name"
				class="mb-4 rounded-md border border-outline-gray-2">
				<header class="flex flex-wrap items-start justify-between gap-2 border-b px-4 py-3">
					<h3 class="font-semibold text-ink-gray-8">{{ c.competency_name }}</h3>
					<Badge :label="__(c.status)" :theme="statusTheme(c.status)" />
				</header>

				<div class="px-4 py-3">
					<p v-if="statusLine(c)" class="mb-3 text-sm text-ink-gray-6">{{ statusLine(c) }}</p>
					<p v-if="!lanes(c).length" class="text-sm text-ink-gray-5">
						{{ __('Nothing has been submitted for this competency yet.') }}
					</p>

					<!-- Chart: lanes x dimensions -->
					<div v-else-if="!asTable" class="overflow-x-auto">
						<div class="grid min-w-[32rem] items-center gap-x-3 gap-y-1"
							:style="{ gridTemplateColumns: `minmax(8rem, 12rem) repeat(${dims.length}, minmax(7rem, 1fr))` }">
							<div />
							<div v-for="d in dims" :key="d.dimension_code"
								class="truncate text-xs font-medium text-ink-gray-7">
								{{ d.dimension }}
							</div>

							<template v-for="lane in lanes(c)" :key="lane.key">
								<div class="min-w-0 py-1">
									<div class="truncate text-sm text-ink-gray-8">{{ lane.label }}</div>
									<div v-if="lane.sublabel" class="truncate text-xs text-ink-gray-5">
										{{ lane.sublabel }}
									</div>
								</div>
								<div v-for="d in dims" :key="d.dimension_code" class="strip">
									<span v-for="(lv, i) in levels" :key="lv.grade_code" class="tick"
										:style="{ left: pos(i) }" />
									<span v-if="lane.from?.[d.dimension_code] != null && lane.to?.[d.dimension_code] != null"
										class="change" :style="changeStyle(lane, d)" />
									<span v-for="m in lane.marks.filter((m) => m.values[d.dimension_code] != null)"
										:key="m.key" class="mark" :style="{ left: posOf(m.values[d.dimension_code]) }"
										:title="`${m.title} — ${d.dimension}: ${m.codes[d.dimension_code] || m.values[d.dimension_code]}`">
										<Marker :kind="m.kind" :shape="m.shape" />
									</span>
								</div>
							</template>

							<div />
							<div v-for="d in dims" :key="d.dimension_code" class="strip-axis">
								<span v-for="(lv, i) in levels" :key="lv.grade_code" class="tick-label"
									:style="{ left: pos(i) }">{{ lv.grade_code }}</span>
							</div>
						</div>
					</div>

					<!-- Table: the same values, for anyone the chart does not serve -->
					<table v-else class="w-full text-sm">
						<thead>
							<tr class="text-left text-ink-gray-6">
								<th class="py-1 pr-3 font-medium">{{ __('Who') }}</th>
								<th v-for="d in dims" :key="d.dimension_code" class="py-1 pr-3 font-medium">
									{{ d.dimension }}
								</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="s in c.series" :key="s.key" class="border-t">
								<td class="py-1 pr-3 text-ink-gray-8">
									{{ seriesTitle(s) }}
								</td>
								<td v-for="d in dims" :key="d.dimension_code" class="py-1 pr-3 text-ink-gray-7">
									{{ s.codes[d.dimension_code] || s.values[d.dimension_code] || '—' }}
								</td>
							</tr>
						</tbody>
					</table>

					<!-- In their words -->
					<div v-if="narratives(c).length" class="mt-4 space-y-3 border-t pt-3">
						<div v-for="s in narratives(c)" :key="s.key">
							<div class="text-xs font-medium text-ink-gray-6">{{ seriesTitle(s) }}</div>
							<SafeHtml class="prose-sm text-ink-gray-7" :html="s.narrative" />
						</div>
					</div>
				</div>
			</article>

			<!-- The course at a glance -->
			<section v-if="radarAxes.length >= 3" class="rounded-md border border-outline-gray-2 px-4 py-3">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<h3 class="font-semibold text-ink-gray-8">{{ __('Across the course') }}</h3>
					<div class="flex flex-wrap gap-1">
						<button v-for="s in radarCandidates" :key="s.id" type="button"
							class="rounded-full border px-2 py-0.5 text-xs"
							:class="hidden[s.id] ? 'border-outline-gray-2 text-ink-gray-5' : 'border-outline-gray-4 text-ink-gray-8'"
							:aria-pressed="!hidden[s.id]" @click="hidden[s.id] = !hidden[s.id]">
							{{ s.name }}
						</button>
					</div>
				</div>
				<RadarChart :indicators="radarAxes" :series="radarSeries" :levels="levels" height="340px" />
				<p v-if="radarIncomplete.length" class="mt-1 text-xs text-ink-gray-5">
					{{ __('Not drawn until every axis has a value: {0}.').format(radarIncomplete.join(', ')) }}
				</p>
			</section>
		</template>
	</div>
</template>

<script setup>
import { Badge, LoadingIndicator, createResource } from 'frappe-ui'
import { computed, h, reactive, ref, watch } from 'vue'
import RadarChart from '@/components/RadarChart.vue'
import { useTheme } from '@/composables/useTheme'

const props = defineProps({
	courseName: { type: String, required: true },
	// Blank: the viewer's own review. A student's name: staff or their mentor.
	student: { type: String, default: null },
})

const { theme } = useTheme()
const asTable = ref(false)
const hidden = reactive({})

const review = createResource({
	url: 'seminary.seminary.cbe_api.get_competency_review',
	makeParams: () => ({
		course_schedule: props.courseName,
		student: props.student || undefined,
	}),
	auto: true,
	onError: () => {},
})
watch(() => [props.courseName, props.student], () => review.reload())
defineExpose({ reload: () => review.reload() })

const levels = computed(() => review.data?.levels || [])
const dims = computed(() => review.data?.dimensions || [])

// Positions: level i of n sits at the centre of the i-th band.
const pos = (i) => `${((i + 0.5) / Math.max(levels.value.length, 1)) * 100}%`
const posOf = (value) => {
	const list = levels.value
	if (!list.length) return '50%'
	// Values are thresholds; place between bands when a mean lands between.
	const t = list.map((l) => Number(l.threshold))
	if (value <= t[0]) return pos(0)
	if (value >= t[t.length - 1]) return pos(t.length - 1)
	for (let i = 0; i < t.length - 1; i++) {
		if (value >= t[i] && value <= t[i + 1]) {
			const f = (value - t[i]) / (t[i + 1] - t[i] || 1)
			return `${((i + 0.5 + f) / list.length) * 100}%`
		}
	}
	return pos(0)
}

const MENTOR_SHAPES = ['triangle', 'diamond', 'square-rot']

const seriesTitle = (s) => (s.sublabel && s.kind !== 'result' ? `${s.label} · ${s.sublabel}` : s.label)

// One lane per voice. The student's Baseline and Final share a lane, joined by
// the change between them; everyone else has their own.
const lanes = (c) => {
	const out = []
	const base = c.series.find((s) => s.kind === 'baseline')
	const fin = c.series.find((s) => s.kind === 'self')
	if (base || fin) {
		out.push({
			key: 'self',
			label: review.data?.own ? __('You') : review.data?.student_name || __('Student'),
			sublabel: __('Self-assessment'),
			from: base?.values,
			to: fin?.values,
			marks: [base, fin].filter(Boolean).map((s) => ({
				key: s.key, kind: s.kind, values: s.values, codes: s.codes, title: s.label,
			})),
		})
	}
	let m = 0
	for (const s of c.series) {
		if (!['instructor', 'mentor', 'result'].includes(s.kind)) continue
		const shape = s.kind === 'mentor' ? MENTOR_SHAPES[m++ % MENTOR_SHAPES.length] : null
		out.push({
			key: s.key,
			label: s.label,
			sublabel: s.kind === 'result' ? s.sublabel : s.sublabel,
			marks: [{ key: s.key, kind: s.kind, shape, values: s.values, codes: s.codes, title: s.label }],
		})
	}
	return out
}

const changeStyle = (lane, d) => {
	const a = parseFloat(posOf(lane.from[d.dimension_code]))
	const b = parseFloat(posOf(lane.to[d.dimension_code]))
	return { left: `${Math.min(a, b)}%`, width: `${Math.abs(b - a)}%` }
}

const narratives = (c) => c.series.filter((s) => s.narrative)

const statusTheme = (status) =>
	({ Competent: 'green', 'Not Yet Competent': 'orange', 'In Progress': 'blue' })[status] || 'gray'

const statusLine = (c) => {
	const waiting = (c.waiting_on || []).map((w) => `${w.name} (${w.category})`)
	if (review.data?.own && !c.mentors_shown) {
		if (!c.self_final) return __('Submit your final self-assessment; your mentors’ views appear here once they have all submitted theirs.')
		return waiting.length
			? __('Your mentors’ views appear here once they have all submitted. Still to come: {0}.').format(waiting.join(', '))
			: ''
	}
	return waiting.length ? __('Still to submit: {0}.').format(waiting.join(', ')) : ''
}

// --- radar ------------------------------------------------------------------
const PALETTE = {
	light: { self: '#2a78d6', instructor: '#eb6834', mentor: '#1baf7a', result: '#0b0b0b', baseline: '#2a78d6' },
	dark: { self: '#3987e5', instructor: '#d95926', mentor: '#199e70', result: '#ffffff', baseline: '#3987e5' },
}
const colors = computed(() => PALETTE[theme.value === 'dark' ? 'dark' : 'light'])

const overall = (values) => {
	const v = Object.values(values || {}).filter((x) => x != null)
	return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
}

const maxLevel = computed(() => Math.max(...levels.value.map((l) => Number(l.threshold)), 1))

// Axes are the course's competencies; a course of one or two competencies has
// no shape to draw across them, so its dimensions stand in.
const byCompetency = computed(() => (review.data?.competencies || []).length >= 3)
const radarAxes = computed(() => {
	if (!review.data) return []
	const items = byCompetency.value
		? review.data.competencies.map((c) => c.competency_code || c.competency_name)
		: dims.value.map((d) => d.dimension)
	return items.map((name) => ({ name, max: maxLevel.value }))
})

const radarCandidates = computed(() => {
	const comps = review.data?.competencies || []
	const voices = new Map()
	comps.forEach((c, ci) => {
		for (const s of c.series) {
			const id = s.kind === 'baseline' || s.kind === 'self' || s.kind === 'result'
				? s.kind
				: `${s.kind}:${s.label}:${s.sublabel}`
			if (!voices.has(id)) {
				voices.set(id, {
					id,
					kind: s.kind,
					name: s.kind === 'baseline' ? __('Starting point')
						: s.kind === 'self' ? __('Final self-assessment')
						: s.kind === 'result' ? __('Recorded result') : seriesTitle(s),
					perComp: {},
					perDim: {},
				})
			}
			const v = voices.get(id)
			v.perComp[ci] = overall(s.values)
			for (const [d, x] of Object.entries(s.values || {})) {
				;(v.perDim[d] ||= []).push(x)
			}
		}
	})
	return [...voices.values()].map((v) => ({
		...v,
		values: byCompetency.value
			? comps.map((_, ci) => v.perComp[ci] ?? null)
			: dims.value.map((d) => {
				const xs = v.perDim[d.dimension_code]
				return xs?.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null
			}),
	}))
})

const radarSeries = computed(() =>
	radarCandidates.value
		.filter((s) => !hidden[s.id] && s.values.every((x) => x != null))
		.map((s) => ({ name: s.name, values: s.values, color: colors.value[s.kind] }))
)
const radarIncomplete = computed(() =>
	radarCandidates.value.filter((s) => !s.values.every((x) => x != null)).map((s) => s.name)
)

// --- marker ------------------------------------------------------------------
// Each mark is ≥ 8px with a 2px surface ring so overlapping marks stay apart.
const Marker = (p) => {
	const c = colors.value[p.kind] || colors.value.self
	const ring = 'var(--surface-white, #fff)'
	const common = { width: 14, height: 14, viewBox: '0 0 14 14', 'aria-hidden': 'true', class: 'inline-block align-middle' }
	if (p.kind === 'baseline') {
		return h('svg', common, [h('circle', { cx: 7, cy: 7, r: 4.5, fill: ring, stroke: c, 'stroke-width': 2 })])
	}
	if (p.kind === 'self') {
		return h('svg', common, [h('circle', { cx: 7, cy: 7, r: 5, fill: c, stroke: ring, 'stroke-width': 2 })])
	}
	if (p.kind === 'instructor') {
		return h('svg', common, [h('rect', { x: 2, y: 2, width: 10, height: 10, rx: 2, fill: c, stroke: ring, 'stroke-width': 2 })])
	}
	if (p.kind === 'result') {
		return h('svg', common, [h('path', { d: 'M7 1 L13 7 L7 13 L1 7 Z', fill: 'none', stroke: c, 'stroke-width': 2 })])
	}
	const shape = p.shape || 'triangle'
	const d = shape === 'diamond' ? 'M7 1.5 L12.5 7 L7 12.5 L1.5 7 Z'
		: shape === 'square-rot' ? 'M3 3 H11 V11 H3 Z'
		: 'M7 1.5 L12.5 12 H1.5 Z'
	return h('svg', common, [h('path', { d, fill: c, stroke: ring, 'stroke-width': 1.5 })])
}
Marker.props = ['kind', 'shape']
</script>

<style scoped>
.strip {
	position: relative;
	height: 26px;
	border-radius: 4px;
	background: var(--surface-gray-1, #f8f8f8);
}
.strip-axis {
	position: relative;
	height: 16px;
}
.tick {
	position: absolute;
	top: 4px;
	bottom: 4px;
	width: 1px;
	background: var(--outline-gray-2, #e2e2e2);
}
.tick-label {
	position: absolute;
	transform: translateX(-50%);
	font-size: 11px;
	color: var(--ink-gray-5, #7c7c7c);
}
.mark {
	position: absolute;
	top: 50%;
	transform: translate(-50%, -50%);
	line-height: 0;
	cursor: default;
}
.change {
	position: absolute;
	top: 50%;
	height: 2px;
	transform: translateY(-50%);
	background: var(--ink-gray-4, #a0a0a0);
}
</style>
