<!--
  The rubric as a student reads it (decisions/095 §6): before submitting, the
  full grid; once graded, the level reached on each criterion is highlighted
  with the grader's comment.
-->
<template>
	<div v-if="rubric" class="rounded-md border border-outline-gray-2 p-4">
		<h3 class="mb-3 font-semibold text-ink-gray-9">{{ __('Rubric') }}</h3>
		<div class="overflow-x-auto">
			<table class="w-full min-w-[36rem] border-collapse text-sm">
				<thead>
					<tr>
						<th class="w-1/4 border border-outline-gray-2 bg-surface-gray-2 p-2 text-left font-medium text-ink-gray-7">
							{{ __('Criterion') }}
						</th>
						<th v-for="lv in rubric.levels" :key="lv.label"
							class="border border-outline-gray-2 bg-surface-gray-2 p-2 text-left font-medium text-ink-gray-7">
							{{ lv.label }}
						</th>
					</tr>
				</thead>
				<tbody>
					<template v-for="c in rubric.criteria" :key="c.criterion_code">
						<tr>
							<td class="border border-outline-gray-2 p-2 align-top">
								<div class="font-medium text-ink-gray-8">{{ c.title }}</div>
								<div class="text-xs text-ink-gray-5">{{ c.share }}%</div>
								<div v-if="c.description" class="mt-1 text-xs text-ink-gray-6">{{ c.description }}</div>
								<div v-if="rubric.labels?.[c.criterion_code]?.length" class="mt-1 flex flex-wrap gap-1">
									<Badge v-for="l in rubric.labels[c.criterion_code]" :key="l" :label="l" theme="blue" />
								</div>
							</td>
							<td v-for="lv in rubric.levels" :key="lv.label"
								class="border border-outline-gray-2 p-2 align-top text-xs"
								:class="reached(c) === lv.label ? 'bg-surface-green-2 font-medium text-ink-gray-9' : 'text-ink-gray-6'">
								{{ cellText(c, lv) }}
							</td>
						</tr>
						<tr v-if="commentOf(c)">
							<td :colspan="rubric.levels.length + 1"
								class="border border-outline-gray-2 bg-surface-blue-1 p-2 text-xs text-ink-blue-2">
								{{ commentOf(c) }}
							</td>
						</tr>
					</template>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup>
import { Badge, createResource } from 'frappe-ui'
import { computed, watch } from 'vue'

const props = defineProps({
	activityDoctype: { type: String, required: true },
	activity: { type: String, required: true },
	submission: { type: String, default: null },
})

const view = createResource({
	url: 'seminary.seminary.rubrics.get_student_view',
	makeParams: () => ({
		activity_doctype: props.activityDoctype,
		activity: props.activity,
		submission: props.submission && props.submission !== 'new' ? props.submission : null,
	}),
	auto: true,
})

watch(() => [props.activity, props.submission], () => view.reload())

const rubric = computed(() => view.data?.rubric)
const scoreOf = (c) => view.data?.scores?.find((s) => s.criterion_code === c.criterion_code)
const reached = (c) => scoreOf(c)?.level
const commentOf = (c) => scoreOf(c)?.comment

const cellText = (c, lv) => {
	const cell = rubric.value.cells.find(
		(x) => x.criterion_code === c.criterion_code && x.level === lv.label
	)
	return cell?.descriptor || lv.description || ''
}
</script>
