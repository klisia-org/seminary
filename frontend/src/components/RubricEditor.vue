<!--
  The rubric editor on an assignment's or discussion's page (decisions/095).

  The school's scale supplies the levels; the instructor writes criteria and,
  if they like, weights and their own wording for some cells. Criteria split
  100% evenly; a typed weight fixes that criterion's percent and the blank ones
  share what is left, so the boxes always show what the grade will use. A rubric
  someone was graded on is saved as a new version, never edited in place.
-->
<template>
	<div class="rounded-md border border-outline-gray-2 p-5">
		<div class="mb-3 flex items-center justify-between">
			<div>
				<div class="font-semibold text-ink-gray-9">{{ __('Rubric') }}</div>
				<div class="text-xs text-ink-gray-5">
					{{ __('Grade this activity by criteria on the school\'s rubric scale.') }}
				</div>
			</div>
			<div v-if="editing" class="flex gap-2">
				<Button v-if="editor.data?.rubric" variant="ghost" theme="red" @click="remove">
					{{ __('Remove rubric') }}
				</Button>
				<Button variant="solid" :loading="saving" @click="save">{{ __('Save rubric') }}</Button>
			</div>
		</div>

		<div v-if="editor.loading && !editor.data" class="py-4 text-sm text-ink-gray-5">{{ __('Loading…') }}</div>

		<div v-else-if="!editor.data?.scales?.length" class="rounded bg-surface-amber-1 p-3 text-sm text-ink-amber-3">
			<template v-if="editor.data?.can_manage_scales">
				{{ __('No rubric scale is set up yet.') }}
				<a href="/app/rubric-scale/new" target="_blank" class="underline">{{ __('Create the school\'s scale') }}</a>
			</template>
			<template v-else>
				{{ __('No rubric scale is set up yet. Ask your academic office to create one.') }}
			</template>
		</div>

		<div v-else-if="!editing">
			<Button @click="startNew">{{ __('Add a rubric') }}</Button>
		</div>

		<div v-else class="space-y-4">
			<div v-if="editor.data.locked" class="rounded bg-surface-blue-1 p-3 text-sm text-ink-blue-2">
				{{ __('Students have been graded on this rubric. Saving creates version {0}; grades already given keep this one.').format((editor.data.rubric?.version || 1) + 1) }}
			</div>

			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<FormControl v-model="form.scale" type="select" :label="__('Scale')" :options="scaleOptions" />
				<FormControl v-if="copyOptions.length" type="select" :label="__('Copy from…')" :options="copyOptions"
					:modelValue="''" @update:modelValue="copyFrom" />
			</div>
			<div class="flex flex-wrap gap-1">
				<Badge v-for="lv in levels" :key="lv.label" theme="gray"
					:label="`${lv.label} · ${lv.percent}%`" />
			</div>

			<div v-for="(c, i) in form.criteria" :key="c.key" class="space-y-2 border-t pt-3">
				<div class="flex items-end gap-2">
					<FormControl v-model="c.title" class="flex-1" :label="__('Criterion {0}').format(i + 1)" />
					<FormControl v-model="c.weight" type="number" class="w-28" :label="__('Weight %')"
						:placeholder="String(shares[i])" :title="__('Leave blank to share what is left evenly')" />
					<div class="w-16 pb-2 text-right text-xs text-ink-gray-5">
						{{ rescaled ? `→ ${shares[i]}%` : (c.weight > 0 ? __('fixed') : __('auto')) }}
					</div>
					<Button variant="ghost" :aria-label="__('Remove criterion')" @click="form.criteria.splice(i, 1)">
						<X class="h-4 w-4" />
					</Button>
				</div>
				<FormControl v-model="c.description" type="textarea" rows="2"
					:placeholder="__('What is judged (optional)')" />
				<Badge v-for="l in editor.data.rubric?.labels?.[c.criterion_code] || []" :key="l" :label="l" theme="blue" />
				<button type="button" class="text-xs text-ink-gray-6 underline" @click="c.open = !c.open">
					{{ c.open ? __('Hide wording per level') : __('Write wording per level (optional)') }}
				</button>
				<div v-if="c.open" class="space-y-2 pl-3">
					<FormControl v-for="lv in levels" :key="lv.label" v-model="c.cells[lv.label]" type="textarea"
						rows="2" :label="lv.label" :placeholder="lv.description || ''" />
				</div>
			</div>

			<Button @click="addCriterion">{{ __('Add criterion') }}</Button>

			<p class="text-xs text-ink-gray-5">
				{{ __('Criteria share 100% evenly. Type a weight to fix one; the blank ones share what is left. Clear it to go back to automatic.') }}
			</p>
			<p v-if="weightNote" class="text-sm" :class="weightBlocked ? 'text-ink-red-3' : 'text-ink-gray-6'">
				{{ weightNote }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { Badge, Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { X } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
	activityDoctype: { type: String, required: true },
	activity: { type: String, required: true },
})

const editing = ref(false)
const saving = ref(false)
const form = reactive({ scale: null, criteria: [] })
let nextKey = 0

const editor = createResource({
	url: 'seminary.seminary.rubrics.get_editor',
	makeParams: () => ({ activity_doctype: props.activityDoctype, activity: props.activity }),
	auto: true,
	onSuccess: (d) => load(d.rubric, d),
})

const candidates = createResource({
	url: 'seminary.seminary.rubrics.copy_candidates',
	makeParams: () => ({ activity_doctype: props.activityDoctype, activity: props.activity }),
	auto: true,
})

watch(() => props.activity, () => {
	editor.reload()
	candidates.reload()
})

const criterionRow = (c = {}, cells = []) => ({
	key: nextKey++,
	criterion_code: c.criterion_code || null,
	title: c.title || '',
	description: c.description || '',
	weight: c.weight || null,
	open: cells.some((x) => x.criterion_code === c.criterion_code),
	cells: Object.fromEntries(
		cells.filter((x) => x.criterion_code === c.criterion_code).map((x) => [x.level, x.descriptor])
	),
})

const defaultScale = (d) => (d.scales.find((s) => s.is_default) || d.scales[0])?.name

const load = (rubric, d = editor.data, keepScale = false) => {
	if (!rubric) {
		editing.value = false
		form.scale = defaultScale(d)
		form.criteria = []
		return
	}
	editing.value = true
	const known = d.scales.some((s) => s.name === rubric.scale)
	if (!keepScale || !form.scale) form.scale = known ? rubric.scale : defaultScale(d)
	form.criteria = rubric.criteria.map((c) => criterionRow(c, rubric.cells))
}

const startNew = () => {
	editing.value = true
	form.scale = defaultScale(editor.data)
	form.criteria = [criterionRow()]
}

const addCriterion = () => form.criteria.push(criterionRow())

const scaleOptions = computed(() =>
	(editor.data?.scales || []).map((s) => ({ label: s.name, value: s.name }))
)
const levels = computed(
	() => editor.data?.scales.find((s) => s.name === form.scale)?.levels || []
)
const copyOptions = computed(() =>
	(candidates.data || []).length
		? [{ label: '', value: '' }, ...candidates.data.map((r) => ({
			label: r.course ? `${r.title} (${r.course})` : r.title,
			value: r.rubric,
		}))]
		: []
)

// The server's rule, mirrored so the boxes move as the instructor types: a
// typed weight is a fixed percent, the blank ones share what is left evenly,
// and only an all-fixed rubric that misses 100 is rescaled.
const weightParts = computed(() => {
	const w = form.criteria.map((c) => (Number(c.weight) > 0 ? Number(c.weight) : 0))
	const fixed = w.reduce((a, b) => a + b, 0)
	const auto = w.filter((x) => !x).length
	return { w, fixed: Math.round(fixed * 100) / 100, auto }
})

const shares = computed(() => {
	const { w, fixed, auto } = weightParts.value
	const fill = auto && fixed < 100 ? (100 - fixed) / auto : 0
	const all = w.map((x) => x || fill)
	const total = all.reduce((a, b) => a + b, 0)
	return all.map((x) => (total ? Math.round((x / total) * 1000) / 10 : 0))
})

const weightBlocked = computed(() => weightParts.value.auto > 0 && weightParts.value.fixed >= 100)
const rescaled = computed(() =>
	form.criteria.length > 0 && !weightParts.value.auto && weightParts.value.fixed !== 100
)

const weightNote = computed(() => {
	const { fixed } = weightParts.value
	if (weightBlocked.value)
		return __('The fixed weights add up to {0}%, which leaves nothing for the criteria left blank. Lower one of them or clear it.').format(fixed)
	if (rescaled.value)
		return __('Every weight is fixed and they add up to {0}%. We rescale them to a total of 100%, as shown beside each one.').format(fixed)
	return ''
})

const copyFrom = async (rubric) => {
	if (!rubric) return
	const r = await call('seminary.seminary.rubrics.get_rubric', { rubric })
	load(r, editor.data, true)
	// Copied criteria are new to this activity: the server codes them afresh,
	// so nothing keyed on the other rubric's codes follows them here.
	form.criteria.forEach((c) => (c.criterion_code = null))
}

const errorText = (e, fallback) => {
	const messages = Array.isArray(e?.messages) ? e.messages : []
	return messages.join('\n') || fallback
}

const save = async () => {
	const criteria = form.criteria.filter((c) => c.title.trim())
	if (!criteria.length) {
		toast.error(__('Add at least one criterion.'))
		return
	}
	if (weightBlocked.value) {
		toast.error(weightNote.value)
		return
	}
	saving.value = true
	try {
		const d = await call('seminary.seminary.rubrics.save_rubric', {
			activity_doctype: props.activityDoctype,
			activity: props.activity,
			scale: form.scale,
			criteria: criteria.map((c) => ({
				criterion_code: c.criterion_code,
				title: c.title,
				description: c.description,
				weight: c.weight,
				cells: c.cells,
			})),
		})
		editor.setData(d)
		load(d.rubric, d)
		toast.success(__('Rubric saved'))
	} catch (e) {
		toast.error(errorText(e, __('Could not save the rubric.')))
	} finally {
		saving.value = false
	}
}

const remove = async () => {
	if (!confirm(__('Remove the rubric from this activity? Grades already given keep theirs.'))) return
	try {
		await call('seminary.seminary.rubrics.remove_rubric', {
			activity_doctype: props.activityDoctype,
			activity: props.activity,
		})
		editor.reload()
	} catch (e) {
		toast.error(errorText(e, __('Could not remove the rubric.')))
	}
}
</script>
