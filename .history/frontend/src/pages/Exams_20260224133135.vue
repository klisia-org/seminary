<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
		<Breadcrumbs :items="breadcrumbs" />
		<div class="flex items-center space-x-3">
			<router-link :to="{
				name: 'ExamForm',
				params: {
					examID: 'new',
				},
			}">
				<Button variant="solid">
					<template #prefix>
						<Plus class="w-4 h-4" />
					</template>
					{{ __('New Exam') }}
				</Button>
			</router-link>
		</div>
	</header>
	<div class="md:w-7/12 md:mx-auto mx-4 py-10">
		<FormControl v-model="selectedCourse" type="select" :options="courseOptions"
			:placeholder="__('Filter by Course')" class="w-64" />
	</div>
	<div v-if="exams.data?.length" class="md:w-3/4 md:mx-auto py-5 mx-5">
		<ListView :columns="examColumns" :rows="exams.data" row-key="name"
			:options="{ showTooltip: false, selectable: false }">
			<ListHeader class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2">
				<ListHeaderItem :item="item" v-for="item in examColumns">
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<router-link v-for="row in exams.data" :to="{
					name: 'ExamForm',
					params: {
						examID: row.name,
					},
				}">
					<ListRow :row="row" />
				</router-link>
			</ListRows>
		</ListView>
		<div class="flex justify-center my-5">
			<Button v-if="exams.hasNextPage" @click="exams.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<div v-else class="text-center p-5 text-ink-gray-5 mt-52 w-3/4 md:w-1/2 mx-auto space-y-2">
		<BookOpen class="size-10 mx-auto stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">
			{{ __('No exams found') }}
		</div>
		<div class="leading-5">
			{{
				__(
					'You have not created any exams yet. To create a new exam, click on the "New Exam" button above.'
				)
			}}
		</div>
	</div>
</template>

<script setup>
import {
	Autocomplete,
	Breadcrumbs,
	Button,
	FormControl,
	createListResource,
	createResource,
	ListView,
	ListRows,
	ListRow,
	ListHeader,
	ListHeaderItem,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { BookOpen, Plus } from 'lucide-vue-next'
import { updateDocumentTitle } from '@/utils'

const user = inject('$user')
const router = useRouter()
const selectedCourse = ref('')

onMounted(() => {
	if (!user.data?.is_moderator && !user.data?.is_instructor) {
		router.push({ name: 'Courses' })
	}
})

// Fetch courses for the dropdown
const courses = createResource({
	url: 'frappe.client.get_list',
	params: {
		doctype: 'Course',
		fields: ['name', 'course_name'],
		order_by: 'course_name asc',
		limit_page_length: 0,
	},
	auto: true,
})

const courseOptions = computed(() => {
	const options = [{ label: __('All Courses'), value: '' }]
	if (courses.data) {
		courses.data.forEach((course) => {
			options.push({
				label: course.course_name,
				value: course.name,
			})
		})
	}
	return options
})

const examFilter = computed(() => {
	const filters = {}

	if (!user.data?.is_moderator) {
		filters.owner = user.data?.name
	}

	if (selectedCourse.value) {
		filters.course = selectedCourse.value
	}

	return filters
})

// Reload exams when filter changes
watch(selectedCourse, () => {
	exams.reload()
})

const exams = createListResource({
	doctype: 'Exam Activity',
	filters: examFilter,
	fields: ['name', 'title', 'total_points', 'course'],
	auto: true,
	cache: ['exams', user.data?.name],
	orderBy: 'modified desc',
})

const examColumns = computed(() => {
	return [
		{
			label: __('Title'),
			key: 'title',
			width: 2,
		},
		{
			label: __('Course'),
			key: 'course',
			width: 1,
		},
		{
			label: __('Total Points'),
			key: 'total_points',
			width: 1,
			align: 'center',
		},
	]
})

const breadcrumbs = computed(() => {
	return [
		{
			label: __('Exams'),
			route: {
				name: 'Exams',
			},
		},
	]
})

const pageMeta = computed(() => {
	return {
		title: __('Exams'),
		description: __('List of exams'),
	}
})

updateDocumentTitle(pageMeta)
</script>
