<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<!-- Add header content if needed -->
	</header>
	<div class="p-5 pb-10">
    <div class="flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:items-center justify-between mb-5">
      
      <div v-if="tableData.rows.length > 0" class="px-5 py-4">
		<ListView :columns="tableData.columns" :rows="tableData.rows" :options="{
			selectable: false,
			showTooltip: false,
			onRowClick: () => { },
		}" row-key="id" v-if="tableData.rows.length > 0">
			<ListHeader>
				<ListHeaderItem v-for="column in tableData.columns" :key="column.key" :item="column" />
			</ListHeader>
			<ListRow v-for="row in tableData.rows" :key="row.id" :row="row" v-slot="{ column, item }">
				<ListRowItem :item="item" :align="column.align">
				
				</ListRowItem>
			</ListRow>
		</ListView>
    </div>
  </div>
    <div v-if="courses.data?.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-5">
      <router-link v-for="course in courses.data" :to="{ name: 'CourseDetail', params: { courseName: course.name } }" :key="course.name">
        <h3>{{ course.course }}</h3>
			<p>{{ course.academic_term }}</p>
      </router-link>
    </div>
    <div v-else class="flex flex-col items-center justify-center text-sm text-ink-gray-5 italic mt-48">
      <BookOpen class="size-10 mx-auto stroke-1 text-ink-gray-4" />
      <div class="text-lg font-medium mb-1">
        <span>No courses found</span>
      
     
    </div>
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
import { studentStore } from '@/stores/student'
import { createResource } from 'frappe-ui'
import { ListView, ListHeader, ListHeaderItem, ListRow, ListRowItem } from 'frappe-ui'
import { reactive } from 'vue'
//import CourseCard from '@/components/CourseCard.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const start = ref(0)


const { getStudentInfo } = studentStore()
let studentInfo = getStudentInfo().value
console.log(studentInfo.user)

const courses = createResource({
  url: "seminary.seminary.utils.get_courses",
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
