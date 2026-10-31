<!--
  Rubric grading for one assignment or discussion submission (decisions/095).

  Shaped like CompetencyActivityGrading: the page hands over the submission and
  hides its own score box while this panel says it is active. Each level click
  saves at once, and the server answers with the derived grade, which the page
  copies into its own copy of the submission so a later whole-document save
  agrees with it.
-->
<template>
	<div v-if="data?.active" class="space-y-4 rounded-md border border-outline-gray-2 p-4">
		<div class="flex items-baseline justify-between">
			<h3 class="font-semibold text-ink-gray-9">{{ __('Rubric') }}</h3>
			<span class="text-sm text-ink-gray-7">
				<template v-if="data.grade != null">
					{{ __('Grade') }}: <strong>{{ data.grade }}</strong> / {{ data.max_grade }}
				</template>
				<template v-else>
					{{ __('{0} of {1} criteria graded').format(gradedCount, data.rubric.criteria.length) }}
				</template>
			</span>
		</div>

		<div v-for="c in data.rubric.criteria" :key="c.criterion_code" class="border-t pt-3">
			<div class="flex items-center gap-2">
				<span class="text-sm font-medium text-ink-gray-8">{{ c.title }}</span>
				<span class="text-xs text-ink-gray-5">{{ c.share }}%</span>
				<Badge v-for="l in data.rubric.labels?.[c.criterion_code] || []" :key="l" :label="l" theme="blue" />
			</div>
			<p v-if="c.description" class="mt-0.5 text-xs text-ink-gray-5">{{ c.description }}</p>
			<div class="mt-2 flex flex-wrap gap-1">
				<button v-for="lv in data.rubric.levels" :key="lv.label" type="button"
					class="rounded border px-2 py-0.5 text-xs"
					:class="scoreOf(c)?.level === lv.label
						? 'border-outline-gray-4 bg-surface-gray-4 font-medium text-ink-gray-9'
						: 'border-outline-gray-2 text-ink-gray-6 hover:bg-surface-gray-2'"
					:title="cellText(c, lv)" :disabled="saving" @click="save(c, lv.label, scoreOf(c)?.comment)">
					{{ lv.label }}
				</button>
			</div>
			<p v-if="scoreOf(c)" class="mt-1 text-xs text-ink-gray-6">
				{{ cellText(c, levelOf(scoreOf(c).level)) }}
			</p>
			<FormControl v-if="scoreOf(c)" type="textarea" rows="2" class="mt-2"
				:placeholder="__('Comment on this criterion (optional)')" :modelValue="scoreOf(c).comment || ''"
				@change="(e) => save(c, scoreOf(c).level, e?.target ? e.target.value : e)" />
		</div>
	</div>
</template>

<script setup>
import { Badge, FormControl, createResource, call, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
	submissionDoctype: { type: String, required: true },
	submission: { type: String, required: true },
})

const emit = defineEmits(['active', 'graded'])
const saving = ref(false)

const panel = createResource({
	url: 'seminary.seminary.rubrics.get_grading',
	makeParams: () => ({
		submission_doctype: props.submissionDoctype,
		submission: props.submission,
	}),
	auto: true,
	onError: () => emit('active', false),
})

const data = computed(() => panel.data)

watch(
	() => panel.data,
	(d) => {
		if (d) emit('active', !!d.active)
	},
	{ immediate: true }
)

watch(() => props.submission, () => panel.reload())

const scoreOf = (c) => data.value?.scores?.find((s) => s.criterion_code === c.criterion_code)
const levelOf = (label) => data.value?.rubric.levels.find((l) => l.label === label)
const gradedCount = computed(() => data.value?.scores?.length || 0)

// The instructor's own wording for this cell if they wrote one, else the
// school's description of the level.
const cellText = (c, lv) => {
	if (!lv) return ''
	const cell = data.value.rubric.cells.find(
		(x) => x.criterion_code === c.criterion_code && x.level === lv.label
	)
	return cell?.descriptor || lv.description || ''
}

const save = async (c, level, comment) => {
	saving.value = true
	try {
		const res = await call('seminary.seminary.rubrics.save_scores', {
			submission_doctype: props.submissionDoctype,
			submission: props.submission,
			scores: [{ criterion_code: c.criterion_code, level, comment: comment ?? null }],
		})
		await panel.reload()
		if (res?.grade != null) emit('graded', res)
	} catch (e) {
		const messages = Array.isArray(e?.messages) ? e.messages : []
		toast.error(messages.join('\n') || __('Could not save that level.'))
	} finally {
		saving.value = false
	}
}
</script>
