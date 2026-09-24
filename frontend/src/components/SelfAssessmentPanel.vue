<template>
	<div>
		<div v-if="form.loading && !form.data" class="flex justify-center py-8">
			<LoadingIndicator class="h-6 w-6" />
		</div>
		<template v-else-if="form.data">
			<div class="flex flex-wrap items-center gap-2">
				<component :is="headingTag" class="font-bold text-ink-gray-9"
					:class="headingTag === 'h1' ? 'text-2xl' : 'text-lg'">
					{{ form.data.competency_name }}
				</component>
				<Badge :label="stageLabel(stage)" theme="gray" />
				<Badge v-if="isSubmitted" :label="__('Submitted')" theme="green" />
				<Badge v-if="mentorViews.length" :label="__('Mentor feedback')" theme="blue" />
			</div>
			<SafeHtml v-if="form.data.statement" class="prose-sm mt-2 text-ink-gray-6"
				:html="form.data.statement" />

			<div v-if="isSubmitted" class="mt-4 rounded-md bg-surface-gray-2 px-4 py-3 text-sm text-ink-gray-7">
				{{ __('You submitted this on {0}. It can no longer be changed.').format(formatDate(form.data.submitted_on)) }}
			</div>

			<CompetencyRatingForm class="mt-4" :dimensions="form.data.dimensions"
				:levels="form.data.levels" :narrative="form.data.narrative || ''"
				:locked="isSubmitted" :saving="saving" :comparisons="mentorViews"
				:comparison-title="__('Your mentors have assessed this competency.')"
				@save="save" />
		</template>
	</div>
</template>

<script setup>
import { Badge, LoadingIndicator, createResource, call, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import CompetencyRatingForm from '@/components/CompetencyRatingForm.vue'
import { formatDate } from '@/utils'

// One competency's self-assessment at one stage: loaded, shown beside the
// mentors' views once the framework lets the student see them, and saved.
// Served both by the self-assessment page and by the lesson block (ADR 079
// decision 1).
const props = defineProps({
	courseName: { type: String, required: true },
	competency: { type: String, required: true },
	stage: { type: String, default: 'Final' },
	headingTag: { type: String, default: 'h1' },
})
const emit = defineEmits(['submitted'])

const saving = ref(null)

const form = createResource({
	url: 'seminary.seminary.cbe_api.get_self_assessment',
	makeParams: () => ({
		course_schedule: props.courseName,
		course_competency: props.competency,
		stage: props.stage,
	}),
	onError: () => {},
})

watch(() => [props.competency, props.stage], () => form.reload(), { immediate: true })

const isSubmitted = computed(() => form.data?.status === 'Submitted')

const mentorViews = computed(() =>
	(form.data?.mentors || []).map((m) => ({
		key: m.name,
		label: m.instructor_name,
		sublabel: m.instructor_category,
		tone: 'mentor',
		narrative: m.narrative,
		ratings: m.ratings,
	}))
)

const stageLabel = (s) => (s === 'Baseline' ? __('Starting point') : __('Where I am now'))

const save = async ({ submit, ratings, narrative }) => {
	if (submit && !window.confirm(__('Submit this assessment? It cannot be changed afterwards.'))) {
		return
	}
	saving.value = submit ? 'submit' : 'draft'
	try {
		await call('seminary.seminary.cbe_api.save_self_assessment', {
			course_schedule: props.courseName,
			course_competency: props.competency,
			stage: props.stage,
			ratings: JSON.stringify(ratings),
			narrative,
			submit: submit ? 1 : 0,
		})
		toast.success(submit ? __('Assessment submitted') : __('Draft saved'))
		await form.reload()
		if (submit) emit('submitted')
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
