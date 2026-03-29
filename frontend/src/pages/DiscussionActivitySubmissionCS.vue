<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
		<Breadcrumbs :items="breadcrumbs" />
	</header>
	<div class="md:w-3/4 md:mx-auto py-5 mx-5">
		<!-- Discussion heading -->
		<div class="mb-5">
			<div class="flex items-baseline gap-3 mb-1">
				<h2 class="text-xl font-semibold text-ink-gray-9">
					{{ discussionDoc?.discussion_name || __('Select a Discussion') }}
				</h2>
				<Button variant="subtle" size="sm" @click="showDiscussionPicker = !showDiscussionPicker">
					{{ showDiscussionPicker ? __('Cancel') : __('Change') }}
				</Button>
			</div>
			<div v-if="dueDate" class="text-sm text-ink-gray-5">
				{{ __('Due') }}: {{ dayjs(dueDate).format('MMM D, YYYY') }}
			</div>
			<div class="text-sm text-ink-gray-4 mt-1">
				{{ __('Click on a student entry to start grading.') }}
			</div>
			<div v-if="showDiscussionPicker" class="mt-2 w-1/2">
				<Link doctype="Discussion Activity" v-model="discussionID"
					:filters="{ course: courseCourse }"
					:placeholder="__('Select Discussion Activity')"
					@change="onDiscussionChange" />
			</div>
		</div>

		<!-- Filters -->
		<div class="flex gap-4 mb-5 flex-wrap">
			<div class="w-48">
				<FormControl v-model="memberFilter" type="autocomplete"
					:options="studentOptions" :placeholder="__('All Students')" />
			</div>
			<div v-if="discussionDoc?.use_studentgroup && groupOptions.length > 1" class="w-48">
				<FormControl v-model="groupFilter" type="select"
					:options="groupOptions" :placeholder="__('All Groups')" />
			</div>
			<div class="w-40">
				<FormControl v-model="statusFilter" type="select"
					:options="statusOptions" />
			</div>
		</div>

		<!-- Table -->
		<ListView v-if="filteredRows.length" :columns="columns" :rows="filteredRows" rowKey="member" :options="{ selectable: false }">
			<ListHeader class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2">
				<ListHeaderItem :item="item" v-for="item in columns" />
			</ListHeader>
			<ListRows>
				<router-link v-for="row in filteredRows" :key="row.member" :to="row.submission_name ? {
					name: 'DiscussionActivitySubmission',
					params: {
						discussionID: discussionID,
						submissionName: row.submission_name,
						courseName: props.courseName,
					},
				} : ''" :class="{ 'pointer-events-none': !row.submission_name }">
					<ListRow :row="row">
						<template #default="{ column }">
							<ListRowItem :item="row[column.key]" :align="column.align">
								<div v-if="column.key === 'original_post_date'">
									<span v-if="row.original_post_date"
										:class="{ 'text-ink-red-3': dueDate && dayjs(row.original_post_date).isAfter(dayjs(dueDate)) }">
										{{ dayjs(row.original_post_date).format('MMM D, YYYY h:mm A') }}
									</span>
									<Badge v-else theme="orange">{{ __('Not Submitted') }}</Badge>
								</div>
								<div v-else-if="column.key === 'status'">
									<Badge :theme="getStatusTheme(row.status)">{{ row.status }}</Badge>
								</div>
								<div v-else>
									{{ row[column.key] ?? '' }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</router-link>
			</ListRows>
		</ListView>
		<div v-else-if="!summaryResource.loading" class="text-center p-5 text-ink-gray-5 mt-52 w-3/4 md:w-1/2 mx-auto space-y-2">
			<Pencil class="size-8 mx-auto stroke-1 text-ink-gray-4" />
			<div class="text-xl font-medium">{{ __('No submissions') }}</div>
			<div class="leading-5">{{ __('There are no submissions for this discussion.') }}</div>
		</div>
	</div>
</template>

<script setup>
import {
	Badge, Breadcrumbs, Button,
	createResource, FormControl,
	ListView, ListHeader, ListHeaderItem, ListRows, ListRow, ListRowItem,
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Pencil } from 'lucide-vue-next'
import Link from '@/components/Controls/Link.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const router = useRouter()

const props = defineProps({
	discussionID: { type: String, required: false },
	courseName: { type: String, required: true },
})

const discussionID = ref('')
const memberFilter = ref('')
const groupFilter = ref('')
const statusFilter = ref('')
const showDiscussionPicker = ref(false)

onMounted(() => {
	if (!user.data?.is_instructor && !user.data?.is_moderator) {
		router.push({ name: 'Courses' })
	}
	discussionID.value = props.discussionID || router.currentRoute.value.query.discussionID || ''
	memberFilter.value = router.currentRoute.value.query.member || ''
	statusFilter.value = router.currentRoute.value.query.status || ''
})

// Course details (for breadcrumbs + course field)
const course = createResource({
	url: 'seminary.seminary.utils.get_course_details',
	cache: ['course', props.courseName],
	params: { course: props.courseName },
	auto: true,
})

const courseCourse = computed(() => course.data?.course || '')

// Discussion Activity doc (for name, use_studentgroup)
const discussionDoc = ref(null)
const discussionDocResource = createResource({
	url: 'frappe.client.get',
	onSuccess(data) { discussionDoc.value = data },
})

// Due date from Scheduled Course Assess Criteria
const dueDate = ref(null)
const dueDateResource = createResource({
	url: 'frappe.client.get_value',
	onSuccess(data) { dueDate.value = data?.due_date || null },
})

// Roster with groups (for student filter + group filter)
const rosterResource = createResource({
	url: 'seminary.seminary.api.get_student_groups',
	cache: ['student_groups', props.courseName],
	params: { course_name: props.courseName },
	auto: true,
})

const studentOptions = computed(() => {
	const opts = [{ label: __('All Students'), value: '' }]
	if (rosterResource.data) {
		const seen = new Set()
		for (const s of rosterResource.data) {
			const email = s.student_name ? `${s.student_name}` : s.student
			if (!seen.has(s.student)) {
				seen.add(s.student)
				// get user email from roster
				opts.push({ label: email, value: s.student })
			}
		}
	}
	return opts
})

const groupOptions = computed(() => {
	const opts = [{ label: __('All Groups'), value: 'All' }]
	if (rosterResource.data) {
		const seen = new Set()
		for (const s of rosterResource.data) {
			if (s.student_group && !seen.has(s.student_group)) {
				seen.add(s.student_group)
				opts.push({ label: s.student_group, value: s.student_group })
			}
		}
	}
	return opts
})

// Main data: submission summary
const summaryResource = createResource({
	url: 'seminary.seminary.api.get_discussion_submission_summary',
})

function fetchDiscussionData(id) {
	if (!id) return
	discussionDocResource.submit({
		doctype: 'Discussion Activity',
		name: id,
	})
	dueDateResource.submit({
		doctype: 'Scheduled Course Assess Criteria',
		filters: { discussion: id, parent: props.courseName },
		fieldname: 'due_date',
	})
	summaryResource.submit({
		course_name: props.courseName,
		discussion_id: id,
	})
}

function onDiscussionChange(val) {
	showDiscussionPicker.value = false
	const id = typeof val === 'object' ? val?.value || val?.name : val
	if (id && id !== discussionID.value) {
		discussionID.value = id
	}
	fetchDiscussionData(discussionID.value)
	router.replace({
		query: {
			discussionID: discussionID.value,
			member: memberFilter.value || undefined,
			status: statusFilter.value || undefined,
		},
	})
}

// When discussionID changes (from Link v-model or initial load)
watch(discussionID, (newVal, oldVal) => {
	if (newVal && newVal !== oldVal) {
		showDiscussionPicker.value = false
		fetchDiscussionData(newVal)
	}
}, { immediate: true })

// Client-side filtering
const filteredRows = computed(() => {
	if (!summaryResource.data) return []
	let rows = summaryResource.data
	if (memberFilter.value) {
		rows = rows.filter(r => r.student_name === memberFilter.value || r.member === memberFilter.value)
	}
	if (groupFilter.value && groupFilter.value !== 'All') {
		rows = rows.filter(r => r.student_group === groupFilter.value)
	}
	if (statusFilter.value && statusFilter.value !== 'All') {
		rows = rows.filter(r => r.status === statusFilter.value)
	}
	return rows
})

// Columns
const columns = computed(() => [
	{ label: __('Student'), key: 'student_name', width: 2 },
	{ label: __('Original Post'), key: 'original_post_date', width: 2, align: 'left' },
	{ label: __('Replies'), key: 'reply_count', width: 1, align: 'center' },
	{ label: __('Score'), key: 'grade', width: 1, align: 'center' },
	{ label: __('Status'), key: 'status', width: 1, align: 'center' },
])

const statusOptions = computed(() => [
	{ label: __('All'), value: 'All' },
	{ label: __('Not Submitted'), value: 'Not Submitted' },
	{ label: __('Not Graded'), value: 'Not Graded' },
	{ label: __('Graded'), value: 'Graded' },
])

const getStatusTheme = (status) => {
	if (status === 'Graded') return 'green'
	if (status === 'Not Graded') return 'blue'
	if (status === 'Not Submitted') return 'orange'
	return 'red'
}

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{ label: course?.data?.course, route: { name: 'CourseDetail', params: { courseName: props.courseName } } },
	{ label: __('Gradebook'), route: { name: 'Gradebook', params: { courseName: props.courseName } } },
	{ label: __('Discussion Submissions') },
])
</script>
