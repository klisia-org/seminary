<!--
  Theme-aware radar chart (ADR 065 section 9).

  Built straight on echarts rather than on frappe-ui's ECharts wrapper for two
  reasons: the wrapper calls init(el, 'light') and never re-initialises, so it
  fights dark mode (ADR 003) with no way in; and it imports the whole echarts
  bundle, where registering only the radar chart costs a fraction of that.

  Colours are read from the app's own CSS custom properties at draw time, so the
  chart follows the palette instead of carrying a second one.
-->
<template>
	<div>
		<div ref="el" :style="{ height: height }" />
		<p v-if="!hasData" class="px-4 py-2 text-center text-sm text-ink-gray-5">
			{{ __('Nothing to plot yet.') }}
		</p>
	</div>
</template>

<script setup>
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useTheme } from '@/composables/useTheme'

echarts.use([RadarChart, LegendComponent, TooltipComponent, SVGRenderer])

const props = defineProps({
	// [{ name, max }] — one per axis.
	indicators: { type: Array, default: () => [] },
	// [{ name, values: [n|null], color }] — values align with indicators.
	series: { type: Array, default: () => [] },
	height: { type: String, default: '380px' },
	// Level codes to print instead of raw numbers, low to high.
	levels: { type: Array, default: () => [] },
})

const el = ref(null)
const { theme } = useTheme()
let chart = null
let observer = null

const hasData = computed(() =>
	props.indicators.length > 0 &&
	props.series.some((s) => (s.values || []).some((v) => v != null))
)

// Reading the tokens rather than hardcoding hexes is what keeps the chart in
// step with the palette; the fallbacks cover the case where a var is missing
// (an older shell, or the chart mounted before the stylesheet applied).
const token = (name, fallback) => {
	const value = getComputedStyle(document.documentElement)
		.getPropertyValue(name)
		.trim()
	return value || fallback
}

const palette = () => [
	token('--ink-blue-3', '#2c7ae0'),
	token('--ink-green-3', '#17864f'),
	token('--ink-amber-3', '#a35200'),
	token('--ink-purple-3', '#7b3ec4'),
]

const labelFor = (value) => {
	if (value == null) return '—'
	const rounded = Math.round(value * 100) / 100
	const level = props.levels.find((l) => Number(l.threshold) === Math.round(value))
	return level ? `${rounded} (${level.grade_code})` : `${rounded}`
}

const options = () => {
	const ink = token('--ink-gray-7', '#383838')
	const muted = token('--ink-gray-5', '#7c7c7c')
	const line = token('--outline-gray-2', '#e0e0e0')
	const split = token('--surface-gray-1', '#f8f8f8')
	const colors = palette()

	return {
		color: colors,
		textStyle: { color: ink, fontFamily: 'Inter, sans-serif' },
		tooltip: {
			trigger: 'item',
			backgroundColor: token('--surface-white', '#ffffff'),
			borderColor: line,
			textStyle: { color: ink },
			formatter: (params) => {
				const rows = props.indicators
					.map((ind, i) => `${ind.name}: <b>${labelFor(params.value[i])}</b>`)
					.join('<br/>')
				return `<b>${params.name}</b><br/>${rows}`
			},
		},
		legend: {
			bottom: 0,
			textStyle: { color: muted },
			icon: 'roundRect',
		},
		radar: {
			indicator: props.indicators.map((i) => ({ ...i })),
			shape: 'polygon',
			splitNumber: 4,
			axisName: { color: muted },
			axisLine: { lineStyle: { color: line } },
			splitLine: { lineStyle: { color: line } },
			splitArea: { areaStyle: { color: [split, 'transparent'] } },
		},
		series: [
			{
				type: 'radar',
				symbolSize: 6,
				emphasis: { focus: 'series' },
				data: props.series.map((s, i) => ({
					name: s.name,
					// echarts draws a gap for null, which is the honest rendering
					// of "nobody rated this dimension".
					value: s.values,
					itemStyle: { color: s.color || colors[i % colors.length] },
					lineStyle: { width: 2 },
					areaStyle: { opacity: 0.12 },
				})),
			},
		],
	}
}

const draw = () => {
	if (!el.value) return
	if (!chart) chart = echarts.init(el.value, null, { renderer: 'svg' })
	chart.setOption(options(), true)
}

onMounted(() => {
	draw()
	if (window.ResizeObserver) {
		observer = new ResizeObserver(() => chart?.resize())
		observer.observe(el.value)
	}
})

onBeforeUnmount(() => {
	observer?.disconnect()
	chart?.dispose()
	chart = null
})

// The tokens change value under the same selector when the theme flips, so the
// only way to pick up the new palette is to re-read them and redraw.
watch(theme, () => draw())
watch(() => [props.indicators, props.series], () => draw(), { deep: true })
</script>
