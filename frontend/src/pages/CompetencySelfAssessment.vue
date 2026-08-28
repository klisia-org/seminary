<template>
	<div class="self-assessment">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
		</header>

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
		<div v-else-if="form.data" class="px-3 py-4 sm:px-5">
			<div class="max-w-3xl">
				<div class="flex flex-wrap items-center gap-2">
					<h1 class="text-2xl font-bold text-ink-gray-9">{{ form.data.competency_name }}</h1>
					<Badge :label="stageLabel(stage)" theme="gray" />
					<Badge v-if="isSubmitted" :label="__('Submitted')" theme="green" />
				</div>
				<div v-if="form.data.statement" class="prose-sm mt-2 text-ink-gray-6"
					v-html="form.data.statement" />

				<div v-if="stages.length > 1" class="mt-4 flex gap-2">
					<Button v-for="s in stages" :key="s" size="sm"
						:variant="s === stage ? 'solid' : 'subtle'" @click="setStage(s)">
						{{ stageLabel(s) }}
					</Button>
				</div>

				<div v-if="isSubmitted" class="mt-4 rounded-md bg-surface-blue-1 px-4 py-3 text-sm text-ink-blue-3">
					{{ __('You submitted this on {0}. It can no longer be changed.').format(form.data.submitted_on) }}
				</div>

				<section v-for="d in rows" :key="d.dimension_code"
					class="mt-5 rounded-md border border-outline-gray-2 px-4 py-4">
					<h2 class="font-semibold text-ink-gray-8">{{ d.dimension }}</h2>
					<div v-if="d.demonstrated_by" class="prose-sm mt-1 text-ink-gray-6"
						v-html="d.demonstrated_by" />

					<div class="mt-3 flex flex-wrap gap-2">
						<button v-for="lv in form.data.levels" :key="lv.grade_code" type="button"
							class="rounded-md border px-3 py-1.5 text-sm"
							:class="d.level_code === lv.grade_code
								? 'border-outline-gray-4 bg-surface-gray-4 font-medium text-ink-gray-9'
								: 'border-outline-gray-2 text-ink-gray-6 hover:bg-surface-gray-2'"
							:disabled="isSubmitted" @click="d.level_code = lv.grade_code">
							{{ lv.grade_code }}
						</button>
					</div>

					<FormControl class="mt-3" type="textarea" :label="__('In your own words')"
						:disabled="isSubmitted" v-model="d.narrative" />
				</section>

				<FormControl class="mt-5" type="textarea" :disabled="isSubmitted"
					:label="__('Anything else about this competency')" v-model="narrative" />

				<div v-if="!isSubmitted" class="mt-5 flex flex-wrap items-center gap-2">
					<Button variant="subtle" :loading="saving === 'draft'" @click="save(false)">
						{{ __('Save Draft') }}
					</Button>
					<Button variant="solid" :loading="saving === 'submit'" :disabled="!allRated"
						@click="save(true)">
						{{ __('Submit') }}
					</Button>
					<span v-if="!allRated" class="text-sm text-ink-gray-6">
						{{ __('Choose a level for every dimension before submitting.') }}
					</span>
					<span v-else class="text-sm text-ink-gray-6">
						{{ __('Submitting is final.') }}
					</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import {
	Badge, Breadcrumbs, Button, FormControl, LoadingIndicator, createResource, call, toast,
} from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
	courseName: { type: String, required: true },
	competency: { type: String, default: null },
})

const stage = ref('Final')
const rows = ref([])
const narrative = ref('')
const saving = ref(null)

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

const form = createResource({
	url: 'seminary.seminary.cbe_api.get_self_assessment',
	makeParams: () => ({
		course_schedule: props.courseName,
		course_competency: props.competency,
		stage: stage.value,
	}),
	onSuccess(data) {
		rows.value = (data?.dimensions || []).map((d) => ({ ...d }))
		narrative.value = data?.narrative || ''
	},
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

const isSubmitted = computed(() => form.data?.status === 'Submitted')
const allRated = computed(() => rows.value.length && rows.value.every((r) => r.level_code))

const stageLabel = (s) => (s === 'Baseline' ? __('Starting point') : __('Where I am now'))

const setStage = (s) => {
	stage.value = s
	form.reload()
}

watch(
	() => [props.competency, context.data?.is_cbe],
	([competency, isCbe]) => {
		if (!isCbe) return
		if (competency) {
			if (!stages.value.includes(stage.value)) stage.value = stages.value[0]
			form.reload()
		} else {
			overview.reload()
		}
	},
	{ immediate: true }
)

const save = async (submit) => {
	if (submit && !window.confirm(__('Submit this assessment? It cannot be changed afterwards.'))) {
		return
	}
	saving.value = submit ? 'submit' : 'draft'
	try {
		await call('seminary.seminary.cbe_api.save_self_assessment', {
			course_schedule: props.courseName,
			course_competency: props.competency,
			stage: stage.value,
			ratings: JSON.stringify(
				rows.value.map((r) => ({
					dimension_code: r.dimension_code,
					level_code: r.level_code,
					narrative: r.narrative,
				}))
			),
			narrative: narrative.value,
			submit: submit ? 1 : 0,
		})
		toast.success(submit ? __('Assessment submitted') : __('Draft saved'))
		form.reload()
	} catch (e) {
		const msg = Array.isArray(e?.messages) && e.messages.length
			? e.messages.join('\n')
			: (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()
		toast.error(msg || __('Could not save your assessment.'))
	} finally {
		saving.value = null
	}
}
</script>
