<template>
	<!-- not-prose: the lesson page styles its content as prose, which would
	     restyle every heading and list inside the form. -->
	<div class="not-prose my-4 rounded-lg border border-outline-gray-2 bg-surface-white p-4">
		<div v-if="ctx.loading && !ctx.data" class="flex justify-center py-6">
			<LoadingIndicator class="h-6 w-6" />
		</div>

		<p v-else-if="ctx.error" class="text-sm text-ink-gray-6">
			{{ __('This reflection could not be loaded.') }}
		</p>

		<template v-else-if="ctx.data">
			<div class="mb-3 flex flex-wrap items-center gap-2">
				<component :is="ctx.data.kind === 'developmentPlan' ? Compass : Sprout"
					class="h-4 w-4 text-ink-gray-6" />
				<span class="text-sm font-medium text-ink-gray-7">{{ heading }}</span>
				<Badge v-if="ctx.data.done" :label="__('Done')" theme="green" />
				<Badge v-if="ctx.data.required" :label="__('Required to finish the course')" theme="orange" />
				<Badge v-if="ctx.data.mentor_feedback" :label="__('Mentor feedback')" theme="blue" />
			</div>

			<!-- Staff see where the reflection sits and what it covers; the
			     form is the student's. -->
			<div v-if="ctx.data.preview" class="rounded-md bg-surface-gray-1 px-4 py-3 text-sm text-ink-gray-6">
				<p>{{ previewText }}</p>
				<ul v-if="ctx.data.competencies.length" class="mt-2 list-inside list-disc">
					<li v-for="c in ctx.data.competencies" :key="c.name">{{ c.competency_name }}</li>
				</ul>
			</div>

			<DevelopmentPlanPanel v-else-if="ctx.data.kind === 'developmentPlan'"
				:course-name="ctx.data.course_schedule" embedded @submitted="onSubmitted" />

			<SelfAssessmentPanel v-else-if="ctx.data.competencies.length === 1"
				:course-name="ctx.data.course_schedule" :competency="ctx.data.competencies[0].name"
				:stage="ctx.data.stage" heading-tag="h2" @submitted="onSubmitted" />

			<!-- Several competencies: one at a time, the next open one first. -->
			<div v-else class="space-y-2">
				<div v-for="c in ctx.data.competencies" :key="c.name"
					class="rounded-md border border-outline-gray-2">
					<button type="button" class="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
						:aria-expanded="open === c.name" @click="open = open === c.name ? null : c.name">
						<span class="font-medium text-ink-gray-8">{{ c.competency_name }}</span>
						<Badge :label="c.submitted ? __('Submitted') : __('To do')"
							:theme="c.submitted ? 'green' : 'gray'" />
					</button>
					<div v-if="open === c.name" class="border-t px-4 py-4">
						<SelfAssessmentPanel :course-name="ctx.data.course_schedule" :competency="c.name"
							:stage="ctx.data.stage" heading-tag="h3" @submitted="onSubmitted" />
					</div>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { Badge, LoadingIndicator, call, createResource } from 'frappe-ui'
import { computed, ref } from 'vue'
import { Compass, Sprout } from 'lucide-vue-next'
import SelfAssessmentPanel from '@/components/SelfAssessmentPanel.vue'
import DevelopmentPlanPanel from '@/components/DevelopmentPlanPanel.vue'

// A reflection placed in a lesson by the course's Competency Framework
// (ADR 079 decision 1). What it covers comes from the server, read off the
// stored lesson and its chapter, never from the block's own data.
const props = defineProps({
	lesson: { type: String, required: true },
})

const open = ref(null)

const ctx = createResource({
	url: 'seminary.seminary.cbe_api.get_reflection_block',
	makeParams: () => ({ lesson: props.lesson }),
	auto: true,
	onSuccess(data) {
		if (open.value) return
		const next = (data?.competencies || []).find((c) => !c.submitted)
		open.value = next?.name || null
	},
})

const heading = computed(() => {
	const d = ctx.data
	if (!d) return ''
	if (d.kind === 'developmentPlan') return __('Development plan')
	if (d.stage === 'Baseline') return __('Self-assessment: where I am starting')
	return d.scope === 'chapter'
		? __('Self-assessment: this competency')
		: __('Self-assessment: every competency in this course')
})

const previewText = computed(() => {
	const d = ctx.data
	if (d.kind === 'developmentPlan') {
		return __('Students write their development plan here.')
	}
	return d.stage === 'Baseline'
		? __('Students record where they are starting on each competency here.')
		: __('Students assess their growth here, and see their mentors’ views once the framework allows.')
})

// Submitting completes the lesson: the server decides whether it is complete,
// and the lesson page is told so it can update its own progress.
const onSubmitted = async () => {
	await ctx.reload()
	if (!ctx.data?.done) return
	try {
		const progress = await call('seminary.seminary.doctype.course_lesson.course_lesson.save_progress', {
			lesson: props.lesson,
			chapter: ctx.data.chapter,
			course: ctx.data.course_schedule,
		})
		window.dispatchEvent(new CustomEvent('seminary:lesson-progress', { detail: progress }))
	} catch {
		/* progress is recomputed on the next visit */
	}
}
</script>
