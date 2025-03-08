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
        {{ ('New') }}
      </Button>
    </router-link>
  </header>

  <div v-if="courses.data?.length" class="p-5 pb-10 flex flex-wrap justify-center gap-4">
    <div v-for="course in courses.data" :key="course.name" class="course_card" style="max-width: 640px; flex: 1 1 calc(100% - 1rem);">
      <router-link :to="{ name: 'CourseDetail', params: { courseName: course.name } }" class="w-full h-full">
        <div class="course-image" :style="{ backgroundImage: `url(${course.course_image})` }"></div>
        <div class="p-4">
          <h3 class="text-lg font-semibold">{{ course.course }}</h3>
          <div class="short-introduction text-ink-gray-7 text-sm">
            {{ course.short_introduction }}
            {{ course.academic_term }}
          </div>
        </div>
      </router-link>
    </div>
  </div>
    <div v-else class="flex flex-col items-center justify-center text-sm text-ink-gray-5 italic mt-48">
      <BookOpen class="size-10 mx-auto stroke-1 text-ink-gray-4" />
      <div class="text-lg font-medium mb-1">
        <span>No courses found</span>
      </div>
    </div>
  

</template>

<script setup>

import { computed, inject, onMounted, ref, watch } from 'vue'
import { BookOpen, Plus } from 'lucide-vue-next'
import { studentStore } from '@/stores/student'
import { createResource } from 'frappe-ui'
import { ListView, ListHeader, ListHeaderItem, ListRow, ListRowItem } from 'frappe-ui'
import { reactive } from 'vue'
import { usersStore} from '../stores/user'
import Breadcrumbs from '@/components/Breadcrumbs.vue' // Import Breadcrumbs component


const user = inject('$user')
const dayjs = inject('$dayjs')
const start = ref(0)

const breadcrumbs = computed(() => [
	{
		label: ('Courses'),
		route: { name: 'Courses' },
	},
])

const { getStudentInfo } = studentStore()
let studentInfo = getStudentInfo().value
console.log(studentInfo)

let userResource = usersStore()

console.log(user.data)

const courses = createResource({
  url: "seminary.seminary.utils.get_courses",
  cache: ['courses', user.data?.name],
  onSuccess: (response) => {
    tableData.rows = response.sort((a, b) => {
      if (a.academic_term < b.academic_term) return -1;
      if (a.academic_term > b.academic_term) return 1;
      if (a.course_name < b.course_name) return -1;
      if (a.course_name > b.course_name) return 1;
      return 0;
    });
  },
  auto: true
});

const tableData = reactive({
  rows: [],
  columns: [
    {
      label: 'Name',
      key: 'name',
      width: 1,
    },
    {
      label: 'Course',
      key: 'course',
      width: 1,
    },
    {
      label: 'Academic Term',
      key: 'academic_term',
      width: 1,
    },
    {
      label: 'Start Date',
      key: 'c_datestart',
      width: 1,
    },
    {
      label: 'End Date',
      key: 'c_dateend',
      width: 1,
    },
    {
      label: 'Image',
      key: 'course_image',
      width: 1,
    }
  ]
})

const setQueryParams = () => {
  let queries = new URLSearchParams(location.search)
  let filterKeys = {
    name: course?.name || '',
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
</script>
<style>
.course_card {
  display: flex;
  height: 350px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  border-radius: 0.5rem;
  box-shadow: 0 0 1rem rgba(0, 0, 0, 0.1);
  background-color: #fff;
  transition: all 0.3s;
}
.course-image {
	height: 168px;
	width: 100%;
	background-size: cover;
	background-position: center;
	background-repeat: no-repeat;
}


.image-placeholder {
	display: flex;
	align-items: center;
	flex: 1;
	font-size: 5rem;
	color: theme('colors.gray.700');
	font-weight: 600;
}

.short-introduction {
	display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
	-webkit-box-orient: vertical;
	text-overflow: ellipsis;
	width: 100%;
	overflow: hidden;
	margin: 0.25rem 0 1.25rem;
	line-height: 1.5;
}
</style>