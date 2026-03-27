<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
		<Breadcrumbs :items="breadcrumbs" />
		<router-link :to="{
			name: 'DiscussionActivityForm',
			params: {
				discussionID: 'new',
			},
		}">
			<Button variant="solid">
				<template #prefix>
					<Plus class="w-4 h-4" />
				</template>
				{{ __('New') }}
			</Button>
		</router-link>
	</header>

	<div class="md:w-3/4 md:mx-auto py-5 mx-5">
		<div class="grid grid-cols-2 gap-5 mb-5">
			<FormControl
				ref="titleInput"
				v-model="titleFilter"
				:placeholder="__('Search by title')"
			/>
			<select
				v-model="courseFilter"
				class="form-select border-gray-300 rounded-md text-sm text-gray-800 placeholder-gray-500 focus:border-gray-500 focus:ring-0"
			>
				<option value="">{{ __('All Courses') }}</option>
				<option
					v-for="course in coursesList.data || []"
					:key="course.name"
					:value="course.name"
				>
					{{ course.name }}
				</option>
			</select>
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
		/>
		<div v-else class="text-center p-5 text-ink-gray-5 mt-52 w-3/4 md:w-1/2 mx-auto space-y-2">
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
		<div v-if="discussions.data && discussions.hasNextPage" class="flex justify-center my-5">
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
	createResource,
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
let debounceTimer = null

onMounted(() => {
	if (!user.data?.is_moderator && !user.data?.is_instructor) {
		router.push({ name: 'Courses' })
	}

	titleFilter.value = router.currentRoute.value.query.title || ''
	courseFilter.value = router.currentRoute.value.query.course || ''
})

// Debounced watch for title filter
watch(titleFilter, () => {
	clearTimeout(debounceTimer)
	debounceTimer = setTimeout(() => {
		reloadDiscussions()
	}, 500)
})

// Immediate watch for course filter
watch(courseFilter, () => {
	reloadDiscussions()
})

const reloadDiscussions = () => {
	// Update URL without causing re-render issues
	const query = {}
	if (titleFilter.value) query.title = titleFilter.value
	if (courseFilter.value) query.course = courseFilter.value

	router.replace({ query })

	discussions.update({
		filters: discussionFilter.value,
	})
	discussions.reload()
}

const discussionFilter = computed(() => {
	let filters = {}
	if (titleFilter.value) {
		filters.discussion_name = ['like', `%${titleFilter.value}%`]
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
	auto: true,
	transform(data) {
		return data.map((row) => {
			return {
				...row,
				post_before: row.post_before ? __('Yes') : __('No'),
				use_studentgroup: row.use_studentgroup ? __('Yes') : __('No'),
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
			label: __('Post Before'),
			key: 'post_before',
			width: '100px',
			align: 'center',
		},
		{
			label: __('Groups'),
			key: 'use_studentgroup',
			width: '100px',
			align: 'center',
		},
		{
			label: __('Created'),
			key: 'creation',
			width: 1,
			align: 'center',
		},
	]
})

// Separate resource to get ALL courses for the dropdown (not filtered)
const coursesList = createResource({
	url: 'frappe.client.get_list',
	params: {
		doctype: 'Course',
		fields: ['name'],
		order_by: 'name asc',
		limit_page_length: 0,
	},
	auto: true,
})

const coursesListed = computed(() => {
	let options = [{ label: __('All Courses'), value: '' }]
	if (coursesList.data) {
		coursesList.data.forEach((course) => {
			options.push({
				label: course.name,
				value: course.name,
			})
		})
	}
	return options
})

const breadcrumbs = computed(() => [
	{
		label: __('Discussion Activities'),
		route: { name: 'DiscussionActivities' },
	},
])
</script>
