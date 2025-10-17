<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<router-link
			:to="{
				name: 'DiscussionActivityForm',
				params: {
					discussionID: 'new',
				},
			}"
		>
			<Button variant="solid">
				<template #prefix>
					<Plus class="w-4 h-4" />
				</template>
				{{ __('New') }}
			</Button>
		</router-link>
	</header>

	<div class="md:w-3/4 md:mx-auto py-5 mx-5">
		<div class="grid grid-cols-3 gap-5 mb-5">
			<FormControl v-model="titleFilter" :placeholder="__('Search by title')" />
			<FormControl
				v-model="courseFilter"
				type="select"
				:options="coursesListed"
				:placeholder="__('Course')"
			/>
	
		</div>
		<ListView
			v-if="discussions.data?.length"
			:columns="discussionColumns"
			:rows="discussions.data"
			row-key="name"
			:options="{
				showTooltip: false,
				selectable: false,
				getRowRoute: (row) => ({
					name: 'DiscussionActivityForm',
					params: {
						discussionID: row.name,
					},
				}),
			}"
		>
		</ListView>
		<div
			v-else
			class="text-center p-5 text-ink-gray-5 mt-52 w-3/4 md:w-1/2 mx-auto space-y-2"
		>
			<Pencil class="size-10 mx-auto stroke-1 text-ink-gray-4" />
			<div class="text-xl font-medium">
				{{ __('No discussion activities found') }}
			</div>
			<div class="leading-5">
				{{
					__(
						'You have not created any discussion activities yet. To create a new discussion activity, click on the "New" button above.'
					)
				}}
			</div>
		</div>
		<div
			v-if="discussions.data && discussions.hasNextPage"
			class="flex justify-center my-5"
		>
			<Button @click="discussions.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	createListResource,
	FormControl,
	ListView,
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { Plus, Pencil } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const user = inject('$user')
const dayjs = inject('$dayjs')
const titleFilter = ref('')
const courseFilter = ref('')
const router = useRouter()

onMounted(() => {
	if (!user.data?.is_moderator && !user.data?.is_instructor) {
		router.push({ name: 'Courses' })
	}

	titleFilter.value = router.currentRoute.value.query.title
	courseFilter.value = router.currentRoute.value.query.course
})

watch([titleFilter, courseFilter], () => {
	router.push({
		query: {
			title: titleFilter.value,
			course: courseFilter.value,
		},
	})
	reloadDiscussions()
})

const reloadDiscussions = () => {
	discussions.update({
		filters: discussionFilter.value,
	})
	discussions.reload()
}

const discussionFilter = computed(() => {
	let filters = {}
	if (titleFilter.value) {
		filters.title = ['like', `%${titleFilter.value}%`]
	}
	if (courseFilter.value) {
		filters.course = courseFilter.value
	}
	if (!user.data?.is_moderator) {
		filters.owner = user.data?.email
	}
	return filters
})

const discussions = createListResource({
	doctype: 'Discussion Activity',
	fields: ['name', 'discussion_name', 'course', 'post_before', 'use_studentgroup', 'creation'],
	orderBy: 'modified desc',
	cache: ['discussions'],
	transform(data) {
		return data.map((row) => {
			return {
				...row,
				creation: dayjs(row.creation).fromNow(),
			}
		})
	},
})

const discussionColumns = computed(() => {
	return [
		{
			label: __('Title'),
			key: 'discussion_name',
			width: 2,
		},
		{
			label: __('Course'),
			key: 'course',
			width: 1,
			align: 'left',
		},
		{
			label: __('Post Before Reply is Mandatory'),
			key: 'post_before',
			width: 1,
			align: 'left',
		},
		{
			label: __('Use Student Group'),
			key: 'use_studentgroup',
			width: 1,
			align: 'left',
		},
		{
			label: __('Created'),
			key: 'creation',
			width: 1,
			align: 'center',
		},
	]
})



const coursesListed = computed(() => {
	if (!discussions.data) return []
	let courses = Array.from(
		new Set(discussions.data.map((discussion) => discussion.course))
	)
	return courses.map((course) => {
		return {
			label: course,
			value: course,
		}
	})
})

const breadcrumbs = computed(() => [
	{
		label: 'Discussion Activities',
		route: { name: 'DiscussionActivities' },
	},
])
</script>
