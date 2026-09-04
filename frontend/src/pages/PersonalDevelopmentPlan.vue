<template>
	<div class="development-plan">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<div class="flex items-center gap-2">
				<router-link v-if="plan.data?.is_cbe"
					:to="mentorMode
						? { name: 'SelfDevelopmentPlans', params: { student: plan.data.student } }
						: { name: 'SelfDevelopmentPlans' }">
					<Button variant="subtle" size="sm">{{ __('All plans') }}</Button>
				</router-link>
				<Badge v-if="plan.data?.status" :label="plan.data.status" :theme="statusThemeOf" />
			</div>
		</header>

		<div v-if="plan.loading" class="flex justify-center py-16">
			<LoadingIndicator class="h-8 w-8" />
		</div>

		<div v-else-if="!plan.data?.is_cbe" class="mx-5 my-8 max-w-xl">
			<h1 class="text-xl font-bold text-ink-gray-8">{{ __('No development plan here') }}</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ __('This course is graded numerically and does not ask for one.') }}
			</p>
		</div>

		<div v-else-if="!plan.data?.enrolled" class="mx-5 my-8 max-w-xl">
			<h1 class="text-xl font-bold text-ink-gray-8">{{ __('Not enrolled') }}</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ __('You are not on the roster for this course.') }}
			</p>
		</div>

		<div v-else class="px-3 py-4 sm:px-5">
			<div class="max-w-3xl">
				<h1 class="text-2xl font-bold text-ink-gray-9">
					{{ mentorMode ? plan.data.student_name || plan.data.student : __('My Development Plan') }}
				</h1>
				<p v-if="mentorMode" class="mt-1 text-sm text-ink-gray-6">
					{{ __('Their plan, as they wrote it. You respond to it; you do not edit it.') }}
				</p>
				<p v-else class="mt-1 text-sm text-ink-gray-6">
					{{ __('What you will work on next, in your own words. This plan belongs to this course — nothing is carried over from an earlier one, and nothing you leave unfinished here becomes a debt in the next.') }}
				</p>

				<div v-if="mentorMode && plan.data.status === 'Draft'"
					class="mt-4 rounded-md bg-surface-gray-2 px-4 py-3 text-sm text-ink-gray-6">
					{{ __('This plan is still a draft. There is nothing to respond to until the student submits it.') }}
				</div>

				<div v-if="submitted && !mentorMode"
					class="mt-4 rounded-md bg-surface-blue-1 px-4 py-3 text-sm text-ink-blue-3">
					{{ __('You submitted this on {0}. It can no longer be changed.')
						.format(formatDate(plan.data.submitted_on)) }}
				</div>
				<div v-else-if="plan.data.blocks_completion && !mentorMode"
					class="mt-4 rounded-md bg-surface-amber-1 px-4 py-3 text-sm text-ink-amber-3">
					{{ __('Your grades for this course cannot be finalised until this plan is submitted.') }}
				</div>

				<!-- Mentor's response, once there is one -->
				<section v-if="plan.data.mentor_feedback && !mentorMode"
					class="mt-5 rounded-md border border-outline-gray-2 px-4 py-4">
					<h2 class="font-semibold text-ink-gray-8">{{ __('From your mentor') }}</h2>
					<div class="prose-sm mt-1 text-ink-gray-6" v-html="plan.data.mentor_feedback" />
				</section>

				<!-- Mentor sign-off. Separate from the student's fields on purpose:
				     a mentor answers a plan, they do not rewrite it. -->
				<section v-if="mentorMode && plan.data.status !== 'Draft'"
					class="mt-5 rounded-md border border-outline-gray-2 px-4 py-4">
					<h2 class="font-semibold text-ink-gray-8">{{ __('Your response') }}</h2>
					<FormControl class="mt-2" type="textarea" :rows="4" v-model="feedback" />
					<div class="mt-3 flex flex-wrap items-center gap-2">
						<Button variant="subtle" :loading="saving === 'review'" @click="review(false)">
							{{ __('Save Response') }}
						</Button>
						<Button variant="solid" :loading="saving === 'accept'" @click="review(true)">
							{{ __('Accept Plan') }}
						</Button>
						<span class="text-sm text-ink-gray-6">
							{{ __('Accepting marks the plan settled. You can still add to your response afterwards.') }}
						</span>
					</div>
				</section>

				<section class="mt-5">
					<h2 class="font-semibold text-ink-gray-8">{{ __('Looking back on this course') }}</h2>
					<FormControl class="mt-2" type="textarea" :rows="4" :disabled="submitted"
						v-model="reflection" />
				</section>

				<!-- The school's own prompts -->
				<section v-if="unanswered.length && !submitted" class="mt-6">
					<h2 class="font-semibold text-ink-gray-8">{{ __('Questions to answer') }}</h2>
					<p class="mt-1 text-sm text-ink-gray-6">
						{{ __('Each answer becomes a goal. You can add goals of your own as well.') }}
					</p>
					<div class="mt-2 space-y-2">
						<div v-for="q in unanswered" :key="q.question_key"
							class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-dashed border-outline-gray-3 px-4 py-3">
							<div class="prose-sm min-w-0 text-ink-gray-7" v-html="q.question_text" />
							<Button size="sm" variant="subtle" @click="addGoal(q)">
								{{ __('Answer this') }}
							</Button>
						</div>
					</div>
				</section>

				<section class="mt-6">
					<div class="flex items-center justify-between">
						<h2 class="font-semibold text-ink-gray-8">{{ __('Goals') }}</h2>
						<Button v-if="!submitted" size="sm" variant="subtle" @click="addGoal()">
							{{ __('Add a goal of my own') }}
						</Button>
					</div>

					<p v-if="!goals.length" class="mt-2 text-sm text-ink-gray-5">
						{{ __('No goals yet.') }}
					</p>

					<div v-for="(g, i) in goals" :key="i"
						class="mt-3 rounded-md border border-outline-gray-2 px-4 py-4">
						<div class="flex items-start justify-between gap-3">
							<div class="min-w-0">
								<div v-if="g.question_text" class="prose-sm text-ink-gray-7"
									v-html="g.question_text" />
								<div v-else class="text-sm font-medium text-ink-gray-7">
									{{ __('My own goal') }}
								</div>
							</div>
							<Button v-if="!submitted" size="sm" variant="ghost" theme="red"
								@click="goals.splice(i, 1)">
								{{ __('Remove') }}
							</Button>
						</div>

						<FormControl class="mt-3" type="textarea" :rows="3" :disabled="submitted"
							:label="__('What I want to grow in')" v-model="g.goal" />

						<div class="mt-3 grid gap-3 sm:grid-cols-2">
							<FormControl type="select" :disabled="submitted"
								:label="__('Competency (optional)')" :options="competencyOptions"
								v-model="g.course_competency" />
							<FormControl type="select" :disabled="submitted"
								:label="__('Dimension (optional)')" :options="dimensionOptions"
								v-model="g.dimension_code" />
						</div>

						<FormControl class="mt-3" type="textarea" :rows="2" :disabled="submitted"
							:label="__('How I will go about it')" v-model="g.action_steps" />

						<div class="mt-3 grid gap-3 sm:grid-cols-2">
							<FormControl type="date" :disabled="submitted"
								:label="__('By when')" v-model="g.target_date" />
							<FormControl type="select" :disabled="submitted"
								:label="__('Where this stands')" :options="goalStatuses"
								v-model="g.status" />
						</div>

						<FormControl class="mt-3" type="textarea" :rows="2" :disabled="submitted"
							:label="__('Help I will need')" v-model="g.support_needed" />
					</div>
				</section>

				<div v-if="!submitted" class="mt-6 flex flex-wrap items-center gap-2">
					<Button variant="subtle" :loading="saving === 'draft'" @click="save(false)">
						{{ __('Save Draft') }}
					</Button>
					<Button variant="solid" :loading="saving === 'submit'" :disabled="!goals.length"
						@click="save(true)">
						{{ __('Submit') }}
					</Button>
					<span class="text-sm text-ink-gray-6">
						{{ goals.length
							? __('Submitting is final — your mentor reads it next.')
							: __('Add at least one goal before submitting.') }}
					</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import {
	Badge, Breadcrumbs, Button, FormControl, LoadingIndicator, call, createResource, toast,
} from 'frappe-ui'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { formatDate } from '@/utils'

const props = defineProps({
	courseName: { type: String, required: true },
})

const route = useRoute()
const goals = ref([])
const reflection = ref('')
const feedback = ref('')
const saving = ref(null)

// A mentor reaches the same page with ?student=, which the server honours only
// for staff; everything the student can edit is read-only in that mode.
const mentorMode = computed(
	() => !!route.query.student && !!plan.data?.viewer_is_staff
)

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{
		label: props.courseName,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{ label: __('Development Plan') },
])

const plan = createResource({
	url: 'seminary.seminary.cbe_api.get_development_plan',
	makeParams: () => ({
		course_schedule: props.courseName,
		student: route.query.student || undefined,
	}),
	auto: true,
	onSuccess(data) {
		goals.value = (data?.goals || []).map((g) => ({ ...g }))
		reflection.value = data?.reflection || ''
		feedback.value = data?.mentor_feedback || ''
	},
	onError: () => {},
})

const submitted = computed(
	() => mentorMode.value || (plan.data?.status && plan.data.status !== 'Draft')
)

const statusThemeOf = computed(
	() => ({ Draft: 'gray', Submitted: 'blue', Reviewed: 'orange', Accepted: 'green' }[
		plan.data?.status
	] || 'gray')
)

// Prompts still without a goal. Recomputed from the working list rather than
// taken from the server, so answering one removes it immediately.
const unanswered = computed(() => {
	const answered = new Set(goals.value.map((g) => g.standard_question).filter(Boolean))
	return (plan.data?.questions || []).filter((q) => !answered.has(q.question_key))
})

const competencyOptions = computed(() => [
	{ label: '—', value: '' },
	...(plan.data?.competencies || []).map((c) => ({
		label: c.competency_name,
		value: c.name,
	})),
])

const dimensionOptions = computed(() => [
	{ label: '—', value: '' },
	...(plan.data?.dimensions || []).map((d) => ({
		label: d.dimension,
		value: d.dimension_code,
	})),
])

const goalStatuses = [
	{ label: __('Planned'), value: 'Planned' },
	{ label: __('In Progress'), value: 'In Progress' },
	// Some formation goals are never finished. The status stays available for
	// the ones that are, and nothing pushes a student towards claiming it.
	{ label: __('Achieved'), value: 'Achieved' },
]

const addGoal = (question = null) => {
	goals.value.push({
		standard_question: question?.question_key || null,
		question_text: question?.question_text || null,
		course_competency: '',
		dimension_code: '',
		goal: '',
		action_steps: '',
		target_date: null,
		support_needed: '',
		status: 'Planned',
	})
}

const review = async (accept) => {
	saving.value = accept ? 'accept' : 'review'
	try {
		await call('seminary.seminary.cbe_api.review_development_plan', {
			plan: plan.data.name,
			mentor_feedback: feedback.value,
			accept: accept ? 1 : 0,
		})
		toast.success(accept ? __('Plan accepted') : __('Response saved'))
		plan.reload()
	} catch (e) {
		toast.error(errorText(e) || __('Could not save your response.'))
	} finally {
		saving.value = null
	}
}

const errorText = (e) =>
	Array.isArray(e?.messages) && e.messages.length
		? e.messages.join('\n')
		: (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()

const save = async (submit) => {
	if (submit && !window.confirm(__('Submit this plan? It cannot be changed afterwards.'))) {
		return
	}
	saving.value = submit ? 'submit' : 'draft'
	try {
		await call('seminary.seminary.cbe_api.save_development_plan', {
			course_schedule: props.courseName,
			reflection: reflection.value,
			goals: JSON.stringify(goals.value),
			submit: submit ? 1 : 0,
		})
		toast.success(submit ? __('Plan submitted') : __('Draft saved'))
		plan.reload()
	} catch (e) {
		toast.error(errorText(e) || __('Could not save your plan.'))
	} finally {
		saving.value = null
	}
}
</script>
