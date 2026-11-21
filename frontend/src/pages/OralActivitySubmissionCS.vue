<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
	</PageHeader>
	<div class="md:w-3/4 md:mx-auto py-5 mx-5 space-y-4">
		<div>
			<h2 class="text-xl font-semibold text-ink-gray-9">{{ summary.data?.title || __('Oral Activity') }}</h2>
			<div class="text-sm text-ink-gray-5">
				{{ summary.data?.mode === 'Conversation' ? __('Recorded in groups') : __('Recorded individually') }}
				<span v-if="dueDate.data"> · {{ __('Due') }}: {{ formatWhen(dueDate.data) }}</span>
			</div>
		</div>
		<div v-if="summary.data" class="overflow-x-auto rounded border">
			<table class="w-full text-sm">
				<thead class="bg-surface-gray-2 text-left text-ink-gray-7">
					<tr>
						<th class="p-2">{{ __('Student') }}</th>
						<th v-if="summary.data.mode === 'Conversation'" class="p-2">{{ __('Group') }}</th>
						<th class="p-2">{{ __('Submitted') }}</th>
						<th class="p-2">{{ __('Status') }}</th>
						<th class="p-2 text-right">{{ __('Grade') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in summary.data.students" :key="row.student" class="border-t"
						:class="row.submission ? 'cursor-pointer hover:bg-surface-gray-1' : ''" @click="open(row)">
						<td class="p-2">{{ row.student_name }}</td>
						<td v-if="summary.data.mode === 'Conversation'" class="p-2">{{ row.group || '' }}</td>
						<td class="p-2">
							<span v-if="row.submitted_on" :class="row.late ? 'text-ink-red-3' : ''">
								{{ formatWhen(row.submitted_on) }}<template v-if="row.late"> · {{ __('late') }}</template>
							</span>
							<Badge v-else theme="orange">{{ __('Not Submitted') }}</Badge>
						</td>
						<td class="p-2">
							<Badge v-if="row.status" :theme="row.status === 'Graded' ? 'green' : 'gray'">{{ __(row.status) }}</Badge>
						</td>
						<td class="p-2 text-right">{{ row.status === 'Graded' ? row.grade : '' }}</td>
					</tr>
				</tbody>
			</table>
		</div>
		<p v-else-if="summary.error" class="text-sm text-ink-gray-5">
			{{ summary.error.messages?.[0] || __('The submissions could not be loaded.') }}
		</p>
	</div>
</template>

<script setup>
// The section's submissions for one oral activity (decisions/100b).
import PageHeader from '@/components/PageHeader.vue'
import { Badge, Breadcrumbs, createResource } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const props = defineProps({
	courseName: { type: String, required: true },
	activityID: { type: String, required: true },
})

const summary = createResource({
	url: 'seminary.seminary.oral_activities.section_summary',
	makeParams: () => ({ course: props.courseName, activity: props.activityID }),
	auto: true,
})
const dueDate = createResource({
	url: 'seminary.seminary.utils.get_assessment_due_date',
	makeParams: () => ({ course: props.courseName, activity_type: 'oral', activity_id: props.activityID }),
	auto: true,
	onError: () => {},
})
const formatWhen = (value) => (value ? new Date(value).toLocaleString(userLocale()) : '')

const open = (row) => {
	if (!row.submission) return
	router.push({
		name: 'OralActivitySubmission',
		params: { courseName: props.courseName, activityID: props.activityID, submissionName: row.submission },
	})
}

const breadcrumbs = computed(() => [
	{ label: __('Gradebook'), route: { name: 'Gradebook', params: { courseName: props.courseName } } },
	{
		label: summary.data?.title || __('Oral Activity'),
		route: { name: 'OralActivitySubmissionCS', params: { courseName: props.courseName, activityID: props.activityID } },
	},
])
</script>
