<template>
	<div class="border-2 rounded-md min-w-80">
		<iframe v-if="course.data.video_link" :src="video_link" class="rounded-t-md min-h-56 w-full" />
		<div class="p-5">
			<div v-if="course.data.membership" class="space-y-2">
				<router-link :to="{
					name: 'Lesson',
					params: {
						courseName: course.name,
						chapterNumber: course.data.current_lesson
							? course.data.current_lesson.split('-')[0]
							: 1,
						lessonNumber: course.data.current_lesson
							? course.data.current_lesson.split('-')[1]
							: 1,
					},
				}">
					<Button variant="solid" size="md" class="w-full">
						<span>
							{{ __('Continue Learning') }}
						</span>
					</Button>
				</router-link>

			</div>


			<Button v-else @click="enrollStudent()" variant="solid" class="w-full" size="md">
				<span>
					{{ __('Start Learning') }}
				</span>
			</Button>

			<router-link v-if="user?.data?.is_moderator || is_instructor()" :to="{
				name: 'CourseForm',
				params: {
					courseName: course.data.name,
				},
			}">
				<Button variant="subtle" class="w-full mt-2" size="md">
					<span>
						{{ __('Edit') }}
					</span>
				</Button>
			</router-link>

			<router-link :to="{
				name: 'CourseCalendar',
				params: {
					courseName: course.data.name,
				},
			}">
				<Button variant="subtle" class="w-full mt-2" size="md">
					<span>
						{{ __('Subscribe to the course calendar') }}
					</span>
				</Button>
			</router-link>
			<router-link v-if="user?.data?.is_moderator || is_instructor()" :to="{
				name: 'CourseAssessment',
				params: {
					courseName: course.data.name,
				},
			}">
				<Button variant="subtle" class="w-full mt-2" size="md">
					<span>
						{{ __('Configure Assessments') }}
					</span>
				</Button>
			</router-link>
			<router-link v-if="user?.data?.is_moderator || is_instructor()" :to="{
				name: 'StudentGroup',
				params: {
					courseName: course.data.name,
				},
			}">
				<Button variant="subtle" class="w-full mt-2" size="md">
					<span>
						{{ ('Configure Student Groups') }}
					</span>
				</Button>
			</router-link>
			<router-link v-if="user?.data?.is_moderator || is_instructor()" :to="{
				name: 'Gradebook',
				params: {
					courseName: course.data.name,
				},
			}">
				<Button variant="subtle" class="w-full mt-2" size="md">
					<span>
						{{ ('Gradebook') }}
					</span>
				</Button>
			</router-link>
			<router-link v-if="user?.data?.is_moderator || is_instructor()" :to="{
				name: 'StudentAttendanceCS',
				params: {
					courseName: course.data.name,
				},
			}">
				<Button variant="subtle" class="w-full mt-2" size="md">
					<span>
						{{ ('Attendance') }}
					</span>
				</Button>
			</router-link>
			<div class="space-y-4">
				<div class="mt-8 font-medium text-ink-gray-9">
					{{ ('This course has:') }}
				</div>
				<div class="flex items-center text-ink-gray-9">
					<BookOpen class="h-4 w-4 stroke-1.5" />
					<span class="ml-2">
						{{ course.data.lessons }} {{ ('Lessons') }}
					</span>
				</div>
				<div class="flex items-center text-ink-gray-9">
					<Users class="h-4 w-4 stroke-1.5" />
					<span class="ml-2">
						{{ formatAmount(course.data.enrollments) }}
						{{ ('Enrolled Students') }}
					</span>
				</div>


			</div>
		</div>
	</div>
</template>
<script setup>
import { BookOpen, Users, Star, GraduationCap } from 'lucide-vue-next'
import { computed, inject } from 'vue'
import { Button, createResource, Tooltip } from 'frappe-ui'
import { formatAmount } from '@/utils/'

import { useRouter } from 'vue-router'


const router = useRouter()
const user = inject('$user')

const props = defineProps({
	course: {
		type: Object,
		default: null,
	},
})

const video_link = computed(() => {
	if (props.course.data.video_link) {
		return 'https://www.youtube.com/embed/' + props.course.data.video_link
	}
	return null
})

function enrollStudent() {
	if (!user.data) {
		toast.success(__('You need to login to access this course'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 2000)
	} else {

		setTimeout(() => {
			router.push({
				name: 'Lesson',
				params: {
					courseName: props.course.data.name,
					chapterNumber: 1,
					lessonNumber: 1,
				},
			})
		}, 2000)

	}
}

const is_instructor = () => {
	let user_is_instructor = false
	props.course.data.instructors.forEach((instructor) => {
		if (!user_is_instructor && instructor.user == user.data?.name) {
			user_is_instructor = true
		}
	})
	console.log(user_is_instructor)
	return user_is_instructor
}




</script>