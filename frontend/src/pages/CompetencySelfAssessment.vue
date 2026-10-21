<template>
	<div class="self-assessment">
		<PageHeader>
			<template #title>
				<Breadcrumbs class="h-7" :items="breadcrumbs" />
			</template>
		</PageHeader>

		<div v-if="context.loading" class="flex justify-center py-16">
			<LoadingIndicator class="h-8 w-8" />
		</div>

		<div v-else-if="context.data && !context.data.is_cbe" class="mx-5 my-8 max-w-xl">
			<h1 class="text-xl font-bold text-ink-gray-8">{{ __('Nothing to assess here') }}</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ __('This course is graded numerically and does not use self-assessment.') }}
			</p>
		</div>

		<div v-else-if="!selfEvalEnabled" class="mx-5 my-8 max-w-xl">
			<h1 class="text-xl font-bold text-ink-gray-8">{{ __('Self-assessment is off') }}</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ __('Your school has not enabled student self-assessment for this programme.') }}
			</p>
		</div>

		<!-- Pick a competency -->
		<div v-else-if="!props.competency" class="px-3 py-4 sm:px-5">
			<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('Assess Your Own Growth') }}</h1>
			<p class="mt-1 max-w-2xl text-sm text-ink-gray-6">
				{{ __('For each competency, say where you think you are and why. Your mentors do the same separately; comparing the two is the point.') }}
			</p>

			<div v-if="overview.loading" class="flex justify-center py-12">
				<LoadingIndicator class="h-6 w-6" />
			</div>
			<ul v-else class="mt-5 divide-y rounded-md border border-outline-gray-2">
				<li v-for="c in overview.data || []" :key="c.name"
					class="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
					<div class="min-w-0">
						<div class="font-medium text-ink-gray-8">{{ c.competency_name }}</div>
						<div class="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-gray-5">
							<span v-for="s in c.self_assessments" :key="s.name">
								{{ stageLabel(s.stage) }}:
								<span :class="s.status === 'Submitted' ? 'text-ink-green-3' : ''">
									{{ s.status === 'Submitted' ? __('submitted') : __('draft') }}
								</span>
							</span>
							<span v-if="!c.self_assessments?.length">{{ __('Not started') }}</span>
						</div>
					</div>
					<div class="flex items-center gap-2">
						<Badge v-if="c.result?.final_code" :label="c.result.final_code"
							:theme="c.result.status === 'Competent' ? 'green' : 'orange'" />
						<router-link :to="{
							name: 'CompetencySelfAssessment',
							params: { courseName: props.courseName, competency: c.name },
						}">
							<Button variant="subtle" size="sm">{{ __('Open') }}</Button>
						</router-link>
					</div>
				</li>
			</ul>
		</div>

		<!-- One competency -->
		<div v-else class="px-3 py-4 sm:px-5">
			<div class="max-w-3xl">
				<div v-if="stages.length > 1" class="mb-4 flex gap-2">
					<Button v-for="s in stages" :key="s" size="sm"
						:variant="s === stage ? 'solid' : 'subtle'" @click="stage = s">
						{{ stageLabel(s) }}
					</Button>
				</div>
				<SelfAssessmentPanel :course-name="props.courseName" :competency="props.competency"
					:stage="stage" />
			</div>
		</div>
	</div>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
import SelfAssessmentPanel from '@/components/SelfAssessmentPanel.vue'
import { Badge, Breadcrumbs, Button, LoadingIndicator, createResource } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
	courseName: { type: String, required: true },
	competency: { type: String, default: null },
})

const stage = ref('Final')

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{
		label: props.courseName,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{ label: __('Self-Assessment') },
])

const context = createResource({
	url: 'seminary.seminary.cbe_api.get_competency_context',
	makeParams: () => ({ course_schedule: props.courseName }),
	auto: true,
})

const overview = createResource({
	url: 'seminary.seminary.cbe_api.get_student_competency_overview',
	makeParams: () => ({ course_schedule: props.courseName }),
	onError: () => {},
})

const selfEvalEnabled = computed(() => !!context.data?.framework?.course_self_eval)

// Which self-assessments exist is a school setting, not a per-student choice,
// so the tabs are derived from the framework's timing rather than offered
// unconditionally.
const stages = computed(() => {
	const when = context.data?.framework?.course_self_eval_points || ''
	const out = []
	if (when.startsWith('Start')) out.push('Baseline')
	if (when.includes('End') || when.includes('end')) out.push('Final')
	return out.length ? out : ['Final']
})

const stageLabel = (s) => (s === 'Baseline' ? __('Starting point') : __('Where I am now'))

watch(
	() => [props.competency, context.data?.is_cbe],
	([competency, isCbe]) => {
		if (!isCbe) return
		if (competency) {
			if (!stages.value.includes(stage.value)) stage.value = stages.value[0]
		} else {
			overview.reload()
		}
	},
	{ immediate: true }
)
</script>
