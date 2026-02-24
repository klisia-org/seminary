<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
		<Breadcrumbs :items="breadcrumbs" />
	</header>
	<div class="md:w-7/12 md:mx-auto mx-4 py-10">
		<div class="mb-4">
			<label for="courseFilter" class="block text-sm font-medium text-gray-700">{{ __('Filter by Course') }}</label>
			<select id="courseFilter" v-model="selectedCourse" class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md">
				<option value="all">{{ __('All Courses') }}</option>
				<option v-for="course in courses" :key="course.id" :value="course.id">{{ course.name }}</option>
			</select>
		</div>
		<Exam v-for="exam in filteredExams" :key="exam.id" :examName="exam.id" />
	</div>
	<!-- Right Section (1/3 width) -->
	<div class="col-span-1 space-y-4">
		<div class="space-y-4 border p-5 rounded-md">
			<Discussions v-if="(user.data?.is_student && submisisonDetails.data?.name) || user.data?.is_instructor"
				:title="__('Exam Comments')" :doctype="'Exam Submission'" :docname="submisisonDetails.doc.name"
				:key="submisisonDetails.doc.name" type="single" />
		</div>
	</div>
</template>
<script setup>
import Exam from '@/components/Exam.vue'
import { createResource, Breadcrumbs } from 'frappe-ui'
import { computed, inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { updateDocumentTitle } from '@/utils'
import Discussions from '@/components/Discussions.vue'

const user = inject('$user')
const router = useRouter()
const selectedCourse = ref('all')
const courses = ref([])

onMounted(() => {
	if (!user.data) {
		router.push({ name: 'Courses' })
	}
})

const props = defineProps({
	examID: {
		type: String,
		required: true,
	},
})

const title = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'Exam Activity',
		fieldname: 'title',
		filters: {
			name: props.examID,
		},
	},
	auto: true,
})

const submissionDetails = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'Exam Submission',
		fieldname: 'name',
		filters: {
			exam: props.examID,
			member: user.data.name,
		},
	},
	auto: true,
	cache: ['exam-submission', props.examID],
})

console.log('User in Exam Page:', user.data)
const breadcrumbs = computed(() => {
	return [{ label: __('Exam Submission') }, { label: title.data?.title }]
})

const pageMeta = computed(() => {
	return {
		title: title.data?.title,
		description: __('Exam Submission'),
	}
})

updateDocumentTitle(pageMeta)

const filteredExams = computed(() => {
	if (selectedCourse.value === 'all') {
		return courses.value; // Show all courses
	}
	return courses.value.filter(course => course.id === selectedCourse.value);
})
</script>
