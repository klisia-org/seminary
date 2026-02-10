<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
	</header>
	<div v-if="submissions.data?.length" class="md:w-3/4 md:mx-auto py-5 mx-5">
		<div class="text-xl font-semibold mb-5">
			{{ submissions.data[0].quiz_title }}
		</div>
		<ListView
			:columns="quizColumns"
			:rows="submissions.data"
			row-key="name"
			:options="{ showTooltip: false, selectable: false }"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in quizColumns">
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<router-link
					v-for="row in submissions.data"
					:to="{
						name: 'QuizSubmission',
						params: {
							submission: row.name,
						},
					}"
				>
					<ListRow :row="row" />
				</router-link>
			</ListRows>
		</ListView>
		<div class="flex justify-center my-5">
			<Button v-if="submissions.hasNextPage" @click="submissions.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
</template>
<script setup>
import {
	createListResource,
    createResource,
	Breadcrumbs,
	Button,
	ListView,
	ListRow,
	ListRows,
	ListHeader,
	ListHeaderItem,
} from 'frappe-ui'
import { computed, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const user = inject('$user')


onMounted(() => {
	if (!user.data?.is_instructor && !user.data?.is_moderator)
		router.push({ name: 'Courses' })
})

const props = defineProps({
	quizID: {
		type: String,
		required: true,
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
}) //Neded for the breadcrumbs

const submissions = createListResource({
	doctype: 'Quiz Submission',
	filters: {
		quiz: props.quizID,
        course: props.courseName
	},
	fields: ['name', 'member_name', 'score', 'percentage', 'quiz_title'],
	orderBy: 'creation desc',
	auto: true,
})

const quizColumns = computed(() => {
	return [
		{
			label: __('Student'),
			key: 'member_name',
			width: 1,
		},
		{
			label: __('Score'),
			key: 'score',
			width: 1,
			align: 'center',
		},
		{
			label: __('Percentage'),
			key: 'percentage',
			width: 1,
			align: 'center',
		},
	]
})

const breadcrumbs = computed(() => {
	let items = [{ label: __('Courses'), route: { name: 'Courses' } }]
	items.push({
		label: course?.data?.course,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	})
    items.push({
        label: 'Gradebook',
        route: { name: 'Gradebook', params: { courseName: props.courseName} },
    })
    items.push({
        label: 'Quiz Submissions',
    })
	return items
})
</script>
