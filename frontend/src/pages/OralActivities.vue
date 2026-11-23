<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
		<template #actions>
			<router-link :to="{
				name: 'OralActivityForm',
				params: {
					activityID: 'new',
				},
			}">
				<Button variant="solid">
					<template #prefix>
						<Plus class="w-4 h-4" />
					</template>
					{{ __('New') }}
				</Button>
			</router-link>
		</template>
	</PageHeader>

	<div class="md:w-3/4 md:mx-auto py-5 mx-5">
		<div class="grid grid-cols-2 gap-5 mb-5">
			<FormControl
				ref="titleInput"
				v-model="titleFilter"
				:placeholder="__('Search by title')"
			/>
			<select :aria-label="__('Course')"
				v-model="courseFilter"
				class="form-select border border-outline-gray-2 bg-surface-white rounded-md text-sm text-ink-gray-9 placeholder-ink-gray-5 focus:border-outline-gray-3 focus:ring-0"
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
			v-if="activities.data?.length"
			:columns="activityColumns"
			:rows="activities.data"
			row-key="name"
			:options="{
				showTooltip: false,
				selectable: false,
				getRowRoute: (row) => ({
					name: 'OralActivityForm',
					params: {
						activityID: row.name,
					},
				}),
			}"
		/>
		<div v-else class="text-center p-5 text-ink-gray-5 mt-52 w-3/4 md:w-1/2 mx-auto space-y-2">
			<Pencil class="size-10 mx-auto stroke-1 text-ink-gray-4" />
			<div class="text-xl font-medium">
				{{ __('No oral activities found') }}
			</div>
			<div class="leading-5">
				{{
					__(
						'You have not created any oral activities yet. To create one, click on the "New" button above.'
					)
				}}
			</div>
		</div>
		<div v-if="activities.data && activities.hasNextPage" class="flex justify-center my-5">
			<Button @click="activities.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
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
		reloadActivities()
	}, 500)
})

// Immediate watch for course filter
watch(courseFilter, () => {
	reloadActivities()
})

const reloadActivities = () => {
	// Update URL without causing re-render issues
	const query = {}
	if (titleFilter.value) query.title = titleFilter.value
	if (courseFilter.value) query.course = courseFilter.value

	router.replace({ query })

	activities.update({
		filters: activityFilter.value,
	})
	activities.reload()
}

const activityFilter = computed(() => {
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

const activities = createListResource({
	doctype: 'Oral Activity',
	fields: ['name', 'title', 'course', 'mode', 'allow_upload', 'creation'],
	orderBy: 'modified desc',
	cache: ['oral-activities'],
	auto: true,
	transform(data) {
		return data.map((row) => {
			return {
				...row,
				mode: __(row.mode),
				allow_upload: row.allow_upload ? __('Yes') : __('No'),
				creation: dayjs(row.creation).fromNow(),
			}
		})
	},
})

const activityColumns = computed(() => {
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
			align: 'left',
		},
		{
			label: __('Mode'),
			key: 'mode',
			width: '100px',
			align: 'center',
		},
		{
			label: __('Upload'),
			key: 'allow_upload',
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
		label: __('Oral Activities'),
		route: { name: 'OralActivities' },
	},
])
</script>
