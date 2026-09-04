<!--
  One activity, one student, graded in levels (ADR 065 section 11c).

  The four submission pages differ in almost everything except this: each names
  the criteria row it was graded under and the student who sat it. So they share
  one panel rather than growing four near-copies that drift apart. The page asks
  the server what to render and hides its own numeric box when the answer is
  "competency", which is why this emits its mode rather than deciding alone.
-->
<template>
	<div v-if="panel.loading" class="flex justify-center py-6">
		<LoadingIndicator class="h-5 w-5" />
	</div>

	<div v-else-if="data?.is_cbe && data.unmapped"
		class="rounded-md bg-surface-amber-1 px-4 py-3 text-sm text-ink-amber-3">
		{{ __('This is a competency-based course, but this activity is not mapped to a competency yet. Set its competency in Configure Assessments before grading it.') }}
	</div>

	<div v-else-if="data?.is_cbe" class="space-y-4 rounded-md border border-outline-gray-2 p-5">
		<div>
			<h3 class="font-semibold text-ink-gray-9">{{ data.competency_name }}</h3>
			<div v-if="data.statement" class="prose-sm mt-1 text-ink-gray-6" v-html="data.statement" />
			<p class="mt-1 text-xs text-ink-gray-5">
				{{ __('Graded in levels, not points.') }}
				<span v-if="data.read_only">{{ __('Grades for this student have been sent; this is read-only.') }}</span>
			</p>
		</div>

		<p v-if="!data.rows.length" class="text-sm text-ink-gray-5">
			{{ __('Nobody is asked to grade this activity. Check who grades what in Configure Assessments.') }}
		</p>

		<div v-for="row in data.rows" :key="row.instructor" class="border-t pt-3">
			<div class="flex items-center gap-2">
				<span class="text-sm font-medium text-ink-gray-8">{{ row.instructor_name }}</span>
				<Badge :label="row.instructor_category" theme="gray" />
				<span v-if="!row.can_grade" class="text-xs text-ink-gray-5">
					{{ __('read-only') }}
				</span>
			</div>

			<div v-for="cell in row.cells" :key="cell.dimension_code || 'overall'" class="mt-3">
				<div class="text-sm text-ink-gray-7">{{ cell.dimension }}</div>
				<!-- The competency's own words for what this dimension looks like:
				     an evaluator picking a level should be reading the descriptor,
				     not remembering it. -->
				<div v-if="cell.demonstrated_by" class="prose-sm mt-0.5 text-xs text-ink-gray-5"
					v-html="cell.demonstrated_by" />
				<div class="mt-1 flex flex-wrap gap-1">
					<button v-for="lv in data.levels" :key="lv.grade_code" type="button"
						class="rounded border px-2 py-0.5 text-xs"
						:class="cell.grade?.level_code === lv.grade_code
							? 'border-outline-gray-4 bg-surface-gray-4 font-medium text-ink-gray-9'
							: 'border-outline-gray-2 text-ink-gray-6 hover:bg-surface-gray-2'"
						:disabled="data.read_only || !row.can_grade || saving"
						@click="setLevel(row, cell, lv)">
						{{ lv.grade_code }}
					</button>
				</div>
				<!-- A note belongs to a level, so it cannot be written before one
				     is chosen; there would be nothing to attach it to. -->
				<FormControl v-if="row.can_grade && !data.read_only && cell.grade?.level_code" type="textarea" rows="2"
					class="mt-2" :placeholder="__('Note (optional)')" :modelValue="cell.grade?.narrative || ''"
					@change="(v) => setNarrative(row, cell, v)" />
				<p v-else-if="cell.grade?.narrative" class="mt-1 text-xs text-ink-gray-6">
					{{ cell.grade.narrative }}
				</p>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Badge, FormControl, LoadingIndicator, createResource, call, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
	submissionDoctype: { type: String, required: true },
	submission: { type: String, required: true },
})

// 'loading' until the answer is known, so a page does not flash its numeric box
// at an evaluator who is not supposed to see one.
const emit = defineEmits(['mode'])

const saving = ref(false)

const panel = createResource({
	url: 'seminary.seminary.cbe_api.get_activity_grading_panel',
	makeParams: () => ({
		submission_doctype: props.submissionDoctype,
		submission: props.submission,
	}),
	auto: true,
	// An ordinary numeric section legitimately answers "not competency-based";
	// a failure here must not take the grading page down with it.
	onError: () => emit('mode', 'numeric'),
})

const data = computed(() => panel.data)

watch(
	() => panel.data,
	(d) => {
		if (!d) return
		emit('mode', d.is_cbe ? 'competency' : 'numeric')
	},
	{ immediate: true }
)

watch(() => props.submission, () => panel.reload())

const save = async (row, cell, levelCode, narrative) => {
	saving.value = true
	try {
		await call('seminary.seminary.cbe_api.save_activity_grade', {
			roster: data.value.roster,
			assess_criteria: data.value.assess_criteria,
			instructor: row.instructor,
			level_code: levelCode,
			dimension_code: cell.dimension_code || null,
			narrative: narrative ?? null,
		})
		panel.reload()
	} catch (e) {
		const messages = Array.isArray(e?.messages) ? e.messages : []
		toast.error(
			messages.join('\n') ||
			(e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim() ||
			__('Could not save that level.')
		)
	} finally {
		saving.value = false
	}
}

const setLevel = (row, cell, level) =>
	save(row, cell, level.grade_code, cell.grade?.narrative)

const setNarrative = (row, cell, value) =>
	save(row, cell, cell.grade.level_code, value)
</script>
