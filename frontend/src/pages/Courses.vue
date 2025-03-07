<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<router-link
			v-if="user.data?.is_moderator"
			:to="{
				name: 'CourseForm',
				params: { courseName: 'new' },
			}"
		>
			<Button variant="solid">
				<template #prefix>
					<Plus class="h-4 w-4 stroke-1.5" />
				</template>
				{{ __('New') }}
			</Button>
		</router-link>
	</header>
	<div class="p-5 pb-10">
    <div class="flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:items-center justify-between mb-5">
      <div class="text-lg font-semibold">
        {{ __('All Courses') }}
      </div>
      <div class="flex flex-col space-y-2 lg:space-y-0 lg:flex-row lg:items-center lg:space-x-4">
        <div class="grid grid-cols-2 gap-2">
          <FormControl
            v-model="title"
            :placeholder="__('Search by Title')"
            type="text"
            class="min-w-40 lg:min-w-0 lg:w-32 xl:w-40"
            @input="updateCourses"
          />
        </div>
      </div>
    </div>
    <div v-if="courses.data?.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-5">
      <router-link v-for="course in courses.data" :to="{ name: 'CourseDetail', params: { courseName: course.name } }" :key="course.name">
        <CourseCard :course="course" />
      </router-link>
    </div>
    <div v-else-if="!courses.list.loading" class="flex flex-col items-center justify-center text-sm text-ink-gray-5 italic mt-48">
      <BookOpen class="size-10 mx-auto stroke-1 text-ink-gray-4" />
      <div class="text-lg font-medium mb-1">
        {{ __('No courses found') }}
      </div>
      <div class="leading-5 w-2/5 text-center">
        {{ __('There are no courses matching the criteria. Keep an eye out, fresh learning experiences are on the way soon!') }}
      </div>
    </div>
    <div v-if="!courses.list.loading && courses.hasNextPage" class="flex justify-center mt-5">
      <Button @click="courses.next()">
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
	Select,
	TabButtons,
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { BookOpen, Plus } from 'lucide-vue-next'
import { updateDocumentTitle } from '@/utils'
import CourseCard from '@/components/CourseCard.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const start = ref(0)
const pageLength = ref(30)
const categories = ref([])
const currentCategory = ref(null)
const title = ref('')
const certification = ref(false)
const filters = ref({})
const currentTab = ref('Live')

onMounted(() => {
	setFiltersFromQuery()
	updateCourses()
	})

const setFiltersFromQuery = () => {
	let queries = new URLSearchParams(location.search)
	title.value = queries.get('title') || ''
	
}

const courses = createListResource({
	doctype: 'Course Schedule',
	url: 'seminary.seminary.utils.get_courses',
	cache: ['courses', user.data?.name],
	pageLength: pageLength.value,
	start: start.value,
	onSuccess(data) {
		if (data.length < pageLength.value) {
			courses.setHasNextPage(false)
		}
	},
})

const updateCourses = () => {
	updateFilters()
	courses.update({
		filters: filters.value,
	})
	courses.reload()
}

const updateFilters = () => {
	updateTitleFilter()
	updateStudentFilter()
	setQueryParams()
}



const updateTitleFilter = () => {
	if (title.value) {
		filters.value['title'] = ['like', `%${title.value}%`]
	} else {
		delete filters.value['title']
	}
}




const updateStudentFilter = () => {
	if (!user.data || (user.data?.is_student && currentTab.value != 'Enrolled')) {
		filters.value['published'] = 1
	}
}

const setQueryParams = () => {
	let queries = new URLSearchParams(location.search)
	let filterKeys = {
		title: title.value,
		
	}

	Object.keys(filterKeys).forEach((key) => {
		if (filterKeys[key]) {
			queries.set(key, filterKeys[key])
		} else {
			queries.delete(key)
		}
	})

	history.replaceState({}, '', `${location.pathname}?${queries.toString()}`)
}



watch(currentTab, () => {
	updateCourses()
})

const courseType = computed(() => {
	let types = [
		{ label: __(''), value: null },
		{ label: __('New'), value: 'New' },
		{ label: __('Upcoming'), value: 'Upcoming' },
	]
	if (user.data?.is_student) {
		types.push({ label: __('Enrolled'), value: 'Enrolled' })
	} else {
		types.push({ label: __('Created'), value: 'Created' })
	}
	return types
})



const breadcrumbs = computed(() => [
	{
		label: __('Courses'),
		route: { name: 'Courses' },
	},
])

const pageMeta = computed(() => {
	return {
		title: 'Courses',
		description: 'Your courses.',
	}
})

updateDocumentTitle(pageMeta)
</script>
