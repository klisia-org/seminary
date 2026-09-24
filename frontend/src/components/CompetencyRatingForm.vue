<template>
	<div class="space-y-4">
		<div v-if="comparisons.length"
			class="rounded-md border border-outline-blue-1 bg-surface-blue-1 px-4 py-3 text-sm text-ink-blue-3">
			<p class="font-medium">{{ comparisonTitle }}</p>
			<p class="mt-0.5">{{ __('Their levels are marked on each dimension below.') }}</p>
		</div>

		<section v-for="d in rows" :key="d.dimension_code"
			class="rounded-md border border-outline-gray-2 px-4 py-4">
			<h3 class="font-semibold text-ink-gray-8">{{ d.dimension }}</h3>
			<SafeHtml v-if="d.demonstrated_by" class="prose-sm mt-1 text-ink-gray-6"
				:html="d.demonstrated_by" />

			<CompetencyLevelPicker class="mt-3" :levels="levels" v-model="d.level_code"
				:label="d.dimension" :disabled="locked" :marks="marksFor(d)" />

			<FormControl class="mt-3" type="textarea" :label="dimensionNarrativeLabel"
				:disabled="locked" v-model="d.narrative" />

			<ul v-if="commentsFor(d).length" class="mt-3 space-y-2">
				<li v-for="c in commentsFor(d)" :key="c.key"
					class="rounded-md bg-surface-gray-1 px-3 py-2 text-sm">
					<div class="flex flex-wrap items-center gap-2">
						<span class="font-medium text-ink-gray-8">{{ c.label }}</span>
						<span v-if="c.sublabel" class="text-xs text-ink-gray-5">{{ c.sublabel }}</span>
						<Badge v-if="c.level_code" :label="c.level_code"
							:theme="c.tone === 'self' ? 'orange' : 'blue'" />
					</div>
					<p v-if="c.narrative" class="mt-1 whitespace-pre-line text-ink-gray-7">{{ c.narrative }}</p>
				</li>
			</ul>
		</section>

		<FormControl type="textarea" :disabled="locked" :label="overallLabel" v-model="overall" />

		<div v-for="c in overallComments" :key="c.key"
			class="rounded-md bg-surface-gray-1 px-3 py-2 text-sm">
			<span class="font-medium text-ink-gray-8">{{ c.label }}</span>
			<p class="mt-1 whitespace-pre-line text-ink-gray-7">{{ c.narrative }}</p>
		</div>

		<div v-if="!locked" class="flex flex-wrap items-center gap-2">
			<Button variant="subtle" :loading="saving === 'draft'" @click="save(false)">
				{{ __('Save Draft') }}
			</Button>
			<Button variant="solid" :loading="saving === 'submit'" :disabled="!allRated"
				@click="save(true)">
				{{ __('Submit') }}
			</Button>
			<span class="text-sm text-ink-gray-6">
				{{ allRated
					? __('Submitting is final.')
					: __('Choose a level for every dimension before submitting.') }}
			</span>
		</div>
	</div>
</template>

<script setup>
import { Badge, Button, FormControl } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import CompetencyLevelPicker from '@/components/CompetencyLevelPicker.vue'

// One competency's rating form -- a level and a narrative per dimension, plus
// an overall narrative -- shared by the student's self-assessment (page and
// lesson block) and the mentor's assessment in the gradebook (ADR 079
// decisions 1 and 6). The host loads and saves; this only edits.
//
// `comparisons` are other people's submitted views of the same competency:
// [{ key, label, sublabel, tone: 'mentor' | 'self', narrative,
//    ratings: { [dimension_code]: { level_code, narrative } } }]
const props = defineProps({
	dimensions: { type: Array, default: () => [] },
	levels: { type: Array, default: () => [] },
	narrative: { type: String, default: '' },
	locked: { type: Boolean, default: false },
	saving: { type: String, default: null },
	comparisons: { type: Array, default: () => [] },
	comparisonTitle: { type: String, default: '' },
	dimensionNarrativeLabel: { type: String, default: () => __('In your own words') },
	overallLabel: { type: String, default: () => __('Anything else about this competency') },
})
const emit = defineEmits(['save'])

const rows = ref([])
const overall = ref('')

watch(
	() => [props.dimensions, props.narrative],
	() => {
		rows.value = props.dimensions.map((d) => ({ ...d }))
		overall.value = props.narrative || ''
	},
	{ immediate: true }
)

const allRated = computed(() => rows.value.length && rows.value.every((r) => r.level_code))

const marksFor = (d) =>
	props.comparisons
		.filter((c) => c.ratings?.[d.dimension_code]?.level_code)
		.map((c) => ({
			key: c.key,
			label: c.label,
			tone: c.tone,
			level_code: c.ratings[d.dimension_code].level_code,
		}))

const commentsFor = (d) =>
	props.comparisons
		.filter((c) => c.ratings?.[d.dimension_code])
		.map((c) => ({
			key: c.key,
			label: c.label,
			sublabel: c.sublabel,
			tone: c.tone,
			level_code: c.ratings[d.dimension_code].level_code,
			narrative: c.ratings[d.dimension_code].narrative,
		}))

const overallComments = computed(() => props.comparisons.filter((c) => c.narrative))

const save = (submit) => {
	emit('save', {
		submit,
		narrative: overall.value,
		ratings: rows.value.map((r) => ({
			dimension_code: r.dimension_code,
			level_code: r.level_code,
			narrative: r.narrative,
		})),
	})
}
</script>
