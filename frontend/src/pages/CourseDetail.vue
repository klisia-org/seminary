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
						{{ course.data.name }}
					</div>
					<div class="my-3 leading-6 text-ink-gray-7">
						{{ course.data.course_description_for_lms }}
					</div>
					<div class="flex items-center">
						
						<span
							class="h-6 mr-1"
							:class="{
								'avatar-group overlap': course.data.instructors.length > 1,
							}"
						
							>
								<UserAvatar
									v-for="instructor in course.data.instructors"
									:user="instructor"
								/>
							</span>
							<CourseInstructors :instructors="course.data.instructors" />
						</div>
					</div>
					<div class="flex mt-3 mb-4 w-fit">
						
					</div>
					<CourseCardOverlay :course="course" class="md:hidden mb-4" />
					<div
						v-html="course.data.course_description_for_lms"
						class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"
					></div>
					<div class="mt-10">
						<CourseOutline
							:title="__('Course Outline')"
							:courseName="course.data.name"
							:showOutline="true"
						/>
					</div>
					
				</div>
				<div class="hidden md:block">
					<CourseCardOverlay :course="course" />
				</div>
			</div>
		</div>
	
</template>
<script setup>
import { createResource, Breadcrumbs, Badge, Tooltip } from 'frappe-ui'
import { computed } from 'vue'
import { Users, Star } from 'lucide-vue-next'
import CourseCardOverlay from '@/components/CourseCardOverlay.vue'
import CourseOutline from '@/components/CourseOutline.vue'
import CourseReviews from '@/components/CourseReviews.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import { updateDocumentTitle } from '@/utils'
import CourseInstructors from '@/components/CourseInstructors.vue'

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
		title: course?.data?.course,
		description: course?.data?.course_description_for_lms,
	}
})

updateDocumentTitle(pageMeta)
</script>
<style>
.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}
</style>
