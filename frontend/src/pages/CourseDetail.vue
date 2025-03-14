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
						<div v-if="course.data.instructors.length = 1" class="text-lg font-semibold">Instructor</div>
						<div v-else="course.data.instructors.length > 1"class="text-lg font-semibold">Instructors</div>
					</div>
					<div v-for="instructor in course.data.instructors" class="flex items-center">
						<br>
						{{ instructor.instructor_name }}
					
							<span
								class="h-6 mr-1 p-2"
								:class="{
									'avatar-group overlap': course.data.instructors.length > 1,
								}"
							>
								<InstructorAvatar
									:instructor="instructor"
								/>
								<br>
							</span>
											
						</div>
					<div class="mt-10">
						<CourseOutline
							:title="('Course Outline')"
							:courseName="course.data.name"
							:showOutline="true"
						/>
					</div>
				</div>
				<div class="border-0 rounded-md min-w-80">
					<CourseCardOverlay :course="course" class="mb-4" />
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import { createResource, Breadcrumbs, Badge, Tooltip } from 'frappe-ui'
import { computed } from 'vue'
import CourseOutline from '@/components/CourseOutline.vue'
import { updateDocumentTitle } from '@/utils'
import InstructorAvatar from '@/components/InstructorAvatar.vue'
import CourseCardOverlay from '@/components/CourseCardOverlay.vue'

const props = defineProps({
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
})
console.log(course)

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