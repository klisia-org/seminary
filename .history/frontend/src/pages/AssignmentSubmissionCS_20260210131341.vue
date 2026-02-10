<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
	</header>
	<div class="md:w-3/4 md:mx-auto py-5 mx-5">
		<div class="grid grid-cols-3 gap-5 mb-5">
			<Link
				doctype="Assignment Activity"
				v-model="assignmentID"
				:placeholder="__('Assignment')"
			/>
			<Link doctype="User" v-model="member" :placeholder="__('Student')" />
			<FormControl
				v-model="status"
				type="select"
				:options="statusOptions"
				:placeholder="__('Status')"
			/>
		</div>
		<ListView
			v-if="submissions.loading || submissions.data?.length"
			:columns="submissionColumns"
			:rows="submissions.data"
			rowKey="name"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in submissionColumns" />
			</ListHeader>
			<ListRows>
				<router-link
					v-for="row in submissions.data"
					:to="{
						name: 'AssignmentSubmission',
						params: {
							assignmentID: row.assignment,
							submissionName: row.name,
						},
					}"
				>
					<ListRow :row="row">
						<template #default="{ column, item }">
							<ListRowItem :item="row[column.key]" :align="column.align">
								<div v-if="column.key == 'status'">
									<Badge :theme="getStatusTheme(row[column.key])">
										{{ row[column.key] }}
									</Badge>
								</div>
								<div v-else>
									{{ row[column.key] }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</router-link>
			</ListRows>
		</ListView>
		<div
			v-else
			class="text-center p-5 text-ink-gray-5 mt-52 w-3/4 md:w-1/2 mx-auto space-y-2"
		>
			<Pencil class="size-8 mx-auto stroke-1 text-ink-gray-4" />
			<div class="text-xl font-medium">
				{{ __('No submissions') }}
			</div>
			<div class="leading-5">
				{{ __('There are no submissions for this course.') }}
			</div>
		</div>
	</div>
</template>
<script setup>
import {
	Badge,
	Breadcrumbs,
	createListResource,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
    createResource
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Pencil } from 'lucide-vue-next'
import Link from '@/components/Controls/Link.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const router = useRouter()
const assignmentID = ref('')
const member = ref('')
const status = ref('')

onMounted(() => {
	if (!user.data?.is_instructor && !user.data?.is_moderator) {
		router.push({ name: 'Courses' })
	}
	assignmentID.value = props.assignmentID || router.currentRoute.value.query.assignmentID
	member.value = router.currentRoute.value.query.member
	status.value = router.currentRoute.value.query.status
	reloadSubmissions()
})

const props = defineProps({
	assignmentID: {
		type: String,
		required: false,
	},
    courseName: {
        type: String,
        required: true,
    },
})

const course = createResource({
	url: 'seminary.seminary.utils.get_course_details',
	cache: ['course', props.courseName],
	params: {
		course: props.courseName,
	},
	auto: true,
}) //Needed for the breadcrumbs

const getAssignmentFilters = () => {
	let filters = {
    course: props.courseName, // Add filter for course_schedule
  };
	if (assignmentID.value) {
		filters.assignment = assignmentID.value
	}
	if (member.value) {
		filters.member = member.value
	}
	if (status.value) {
		filters.status = status.value
	}
	return filters
}

const submissions = createListResource({
	doctype: 'Assignment Submission',
	fields: [
		'name',
		'assignment',
		'assignment_title',
		'member_name',
		'creation',
		'status',
		'grade',
	],
    filters: getAssignmentFilters(),
	orderBy: 'creation desc',
	transform(data) {
		return data.map((row) => {
			return {
				...row,
				creation: dayjs(row.creation).fromNow(),
			}
		})
	},
})

// watch changes in assignmentID, member, and status and if changes in any then reload submissions. Also update the url query params for the same
watch([assignmentID, member, status], () => {
	router.push({
		query: {
			assignmentID: assignmentID.value,
			member: member.value,
			status: status.value,
		},
	})
	reloadSubmissions()
})

const reloadSubmissions = () => {
	submissions.update({
		filters: getAssignmentFilters(),
	})
	submissions.reload()
}

const submissionColumns = computed(() => {
	return [
		{
			label: __('Student'),
			key: 'member_name',
			width: 1,
		},
		{
			label: __('Assignment'),
			key: 'assignment_title',
			width: 2,
		},
		{
			label: 'Submitted',
			key: 'creation',
			width: 1,
			align: 'left',
		},
		{
			label: 'Grade',
			key: 'grade',
			width: 1,
			align: 'center',
		},
		{
			label: 'Status',
			key: 'status',
			width: 1,
			align: 'center',
		},
	]
})

const statusOptions = computed(() => {
	return [
		{ label: '', value: '' },
		{ label: 'Pass', value: 'Pass' },
		{ label: 'Fail', value: 'Fail' },
		{ label: 'Not Graded', value: 'Not Graded' },
		{ label: 'Graded', value: 'Graded' },
	]
})

const getStatusTheme = (status) => {
	if (status === 'Pass' || status === 'Graded') {
		return 'green'
	} else if (status === 'Not Graded') {
		return 'blue'
	} else {
		return 'red'
	}
}

const breadcrumbs = computed(() => {
	let items = [{ label: 'Courses', route: { name: 'Courses' } }]
	items.push({
		label: course?.data?.course,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	})
    items.push({
        label: 'Gradebook',
        route: { name: 'Gradebook', params: { courseName: props.courseName} },
    })
    items.push({
        label: 'Assignment Submissions',
    })
	return items
})
</script>
