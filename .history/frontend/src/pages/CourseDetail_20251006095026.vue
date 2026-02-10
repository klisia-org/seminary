<template>
	<div v-if="course.data">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
		</header>
		<div class="m-5">
			<div class="flex justify-between w-full">
				<div class="md:w-2/3">
					<div class="text-3xl font-semibold text-ink-gray-9">
						{{ course.data.course }}
					</div>
					<div class="my-3 leading-6 text-ink-gray-7">
						{{ course.data.short_introduction }}
					</div>

					<div
						v-html="course.data.course_description_for_lms"
						class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"
					></div>
					<div class="mt-10">
						<div v-if="course.data.instructors.length === 1" class="text-lg font-semibold">Instructor</div>
						<div v-else class="text-lg font-semibold">Instructors</div>
						<br />
					<div class="flex flex-wrap gap-4">
						<div
							v-for="instructor in course.data.instructors"
							:key="instructor.instructor_name"
							class="flex flex-col items-center"
						>
							<InstructorAvatar :instructor="instructor" size="xl" class="mb-2 w-20 h-20" />
							<div class="text-center text-sm font-medium">
								{{ instructor.instructor_name }}
							</div>
						</div>
					</div>
					</div>
					<div class="mt-10">
						<CourseOutline
							:title="('Course Outline')"
							:courseName="course.data.name"
							:showOutline="true"
							:allowEdit="canEditOutline"
						/>
					</div>
				</div>

				<div class="border-0 rounded-md min-w-80">
					<CourseCardOverlay :course="course" class="mb-4" />
					<div class="mt-5">
						<CourseCardToDo :course="props.courseName" />
					</div>
					<div class="mt-5">
						<Announcements :cs="props.courseName" />
					</div>
					<div v-if="user.data?.is_moderator || user.data?.is_instructor" class="mt-5 flex justify-center">
						<Button @click="openAnnouncementModal()">
							<span>
								{{ __('Make an Announcement') }}
							</span>
							<template #suffix>
								<Send class="h-4 stroke-1.5" />
							</template>
						</Button>
					</div>
					<div class="mt-5">
						<AnnouncementModal
						v-model="showAnnouncementModal"
						:cs="props.courseName"
						:students="studentEmails" />
					</div>

				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import { createResource, Breadcrumbs, Badge, Tooltip, Button } from 'frappe-ui'
import { computed, ref, inject } from 'vue'
import CourseOutline from '@/components/CourseOutline.vue'
import { updateDocumentTitle } from '@/utils'
import InstructorAvatar from '@/components/InstructorAvatar.vue'
import CourseCardOverlay from '@/components/CourseCardOverlay.vue'
import CourseCardToDo from '@/components/CourseCardToDo.vue'
import AnnouncementModal from '../components/Modals/AnnouncementModal.vue'
import { Send } from 'lucide-vue-next'
import Announcements from '../components/Announcements.vue'

const user = inject('$user')
const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})
const showAnnouncementModal = ref(false)

console.log("CourseName prop:", props.courseName)

const course = createResource({
	url: 'seminary.seminary.utils.get_course_details',
	cache: ['course', props.courseName],
	params: {
		course: props.courseName,
	},
	auto: true,
})
console.log(course)
console.log("Course props:", props.courseName)

const students = createResource({
	url: 'seminary.seminary.utils.get_roster',
	cache: ['roster', props.courseName],
	params: {
		course: props.courseName,
	},
	auto: true,
})
const studentEmails = computed(() =>
  (students.data || []).map(s => s.stuemail_rc)
);
console.log("Student Emails:", studentEmails.value)


const openAnnouncementModal = () => {
	showAnnouncementModal.value = true
}

const canEditOutline = computed(() => {
	const roles = user?.data || {}
	return Boolean(
		roles.is_moderator ||
		roles.is_instructor ||
		roles.is_evaluator
	)
})

const breadcrumbs = computed(() => {
	let items = [{ label: 'Courses', route: { name: 'Courses' } }]
	items.push({
		label: course?.data?.course,
		route: { name: 'CourseDetail', params: { courseName: course?.data?.name } },
	})
	return items
})

const pageMeta = computed(() => {
	return {
		title: course?.data?.title,
		description: course?.data?.short_introduction,
	}
})

updateDocumentTitle(pageMeta)
</script>
<style>

</style>