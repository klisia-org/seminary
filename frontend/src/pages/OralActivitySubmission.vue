<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
	</PageHeader>
	<div v-if="sub.data" class="md:w-11/12 md:mx-auto py-5 mx-5 grid gap-5 md:grid-cols-[1fr,22rem]">
		<div class="space-y-4">
			<div>
				<h2 class="text-xl font-semibold text-ink-gray-9">{{ sub.data.member_name }}</h2>
				<div class="text-sm text-ink-gray-5">
					{{ sub.data.title }} · {{ __('Submitted {0}').format(formatWhen(sub.data.submitted_on)) }}
					<span v-if="sub.data.late" class="text-ink-red-3"> · {{ __('late') }}</span>
				</div>
				<div v-if="sub.data.group_submissions.length" class="text-sm text-ink-gray-6 mt-1">
					{{ __('Recorded with:') }}
					<template v-for="(o, i) in sub.data.group_submissions" :key="o.name">
						<router-link class="underline" :to="{
							name: 'OralActivitySubmission',
							params: { courseName, activityID, submissionName: o.name },
						}">{{ o.member_name }}</router-link><template v-if="i < sub.data.group_submissions.length - 1">, </template>
					</template>
				</div>
			</div>
			<SafeHtml v-if="sub.data.prompt" :html="sub.data.prompt"
				class="rounded-lg border border-outline-blue-1 bg-surface-blue-1 p-4 prose prose-sm max-w-none !whitespace-normal" />
			<OralPlayer v-if="sub.data.recording" :recording="sub.data.recording" />
			<p class="text-xs text-ink-gray-5">
				{{ __('Talk time helps you see who took part; it is never part of the grade.') }}
			</p>
		</div>

		<div class="space-y-4">
			<div class="border rounded-lg p-5 space-y-3">
				<h3 class="text-lg font-semibold text-ink-gray-9">{{ __('Grade') }}</h3>
				<CompetencyActivityGrading submission-doctype="Oral Activity Submission" :submission="submissionName"
					@mode="(m) => (gradeMode = m)" />
				<RubricGrading submission-doctype="Oral Activity Submission" :submission="submissionName"
					@active="(a) => (rubricActive = a)" @graded="sub.reload()" />
				<template v-if="gradeMode !== 'competency' && !rubricActive">
					<FormControl v-model="grade" type="number" min="0" :label="__('Grade (percentage)')" />
				</template>
				<div>
					<label for="oral-submission-comments" class="block text-sm font-medium text-ink-gray-7 mb-1">{{ __('Comments') }}</label>
					<textarea id="oral-submission-comments" v-model="comments" rows="5"
						class="block w-full rounded-md border border-outline-gray-2 bg-surface-white text-sm" />
				</div>
				<Button variant="solid" class="w-full" :loading="saving" @click="save">{{ __('Save') }}</Button>
				<GroupGradingPanel submission-doctype="Oral Activity Submission" :submission="submissionName"
					:course="courseName" @changed="sub.reload()" />
				<div v-if="sub.data.status === 'Graded'" class="text-xs text-ink-green-3">{{ __('Graded') }}</div>
			</div>
		</div>
	</div>
	<p v-else-if="sub.error" class="p-5 text-sm text-ink-gray-5">
		{{ sub.error.messages?.[0] || __('The submission could not be loaded.') }}
	</p>
</template>

<script setup>
// Grade one student's oral activity submission (decisions/100b).
import GroupGradingPanel from '@/components/GroupGradingPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { Breadcrumbs, Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { computed, ref } from 'vue'
import SafeHtml from '@/components/SafeHtml.vue'
import { htmlToText } from '@/utils'
import OralPlayer from '@/components/OralPlayer.vue'
import RubricGrading from '@/components/RubricGrading.vue'
import CompetencyActivityGrading from '@/components/CompetencyActivityGrading.vue'

const props = defineProps({
	courseName: { type: String, required: true },
	activityID: { type: String, required: true },
	submissionName: { type: String, required: true },
})

const grade = ref(null)
const comments = ref('')
const gradeMode = ref(null)
const rubricActive = ref(false)
const saving = ref(false)

const sub = createResource({
	url: 'seminary.seminary.oral_activities.get_submission',
	makeParams: () => ({ submission: props.submissionName }),
	auto: true,
	onSuccess(data) {
		grade.value = data.status === 'Graded' ? data.grade : null
		comments.value = htmlToText(data.comments)
	},
})
const formatWhen = (value) => (value ? new Date(value).toLocaleString(userLocale()) : '')

const save = async () => {
	saving.value = true
	try {
		const useBox = gradeMode.value !== 'competency' && !rubricActive.value
		if (useBox && (grade.value === null || grade.value === '')) {
			toast.error(__('Enter a grade first.'))
			return
		}
		await call('seminary.seminary.oral_activities.save_grade', {
			submission: props.submissionName,
			grade: useBox ? grade.value : sub.data.grade || 0,
			comments: comments.value,
		})
		toast.success(__('Saved.'))
		sub.reload()
	} catch (e) {
		toast.error(e.messages?.[0] || __('The grade could not be saved.'))
	} finally {
		saving.value = false
	}
}

const breadcrumbs = computed(() => [
	{ label: __('Gradebook'), route: { name: 'Gradebook', params: { courseName: props.courseName } } },
	{
		label: sub.data?.title || __('Oral Activity'),
		route: { name: 'OralActivitySubmissionCS', params: { courseName: props.courseName, activityID: props.activityID } },
	},
	{
		label: sub.data?.member_name || props.submissionName,
		route: {
			name: 'OralActivitySubmission',
			params: { courseName: props.courseName, activityID: props.activityID, submissionName: props.submissionName },
		},
	},
])
</script>
