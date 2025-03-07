<template>
	<div class="course-card">
		<img :src="course.course_image" alt="Course Image" />
		<div class="course-details">
			<h3>{{ course.course_name }}</h3>
			<p>{{ course.academic_term }}</p>
			<p>{{ course.c_datestart }} - {{ course.c_dateend }}</p>
		</div>
	</div>
	<div
		v-if="course.course"
		class="flex flex-col h-full rounded-md border-2 overflow-auto"
		style="min-height: 350px"
	>
		<div
			class="course-image"
			:class="{ 'default-image': !course.image }"
			:style="{ backgroundImage: 'url(\'' + encodeURI(course.course_image) + '\')' }"
		>
			
			</div>
			<div v-if="!course.course_image" class="image-placeholder">
				<span class="text-ink-gray-7">No Image</span>
			</div>
		</div>
		<div class="flex flex-col flex-auto p-4">
			<div class="flex items-center justify-between mb-2">
				<div v-if="course.lessons">
					<Tooltip :text="__('Lessons')">
						<span class="flex items-center text-ink-gray-7">
							<BookOpen class="h-4 w-4 stroke-1.5 mr-1" />
							{{ course.lessons }}
						</span>
					</Tooltip>
				</div>

			

			<div class="text-xl font-semibold leading-6 text-ink-gray-9">
				{{ course.course }}
			</div>

			<div class="short-introduction text-ink-gray-7 text-sm">
				{{ course.course_description_for_lms }}
			</div>

			<ProgressBar
				v-if="user && course.membership"
				:progress="course.membership.progress"
			/>

			<div
				v-if="user && course.membership"
				class="text-sm text-ink-gray-7 mt-2 mb-4"
			>
				{{ Math.ceil(course.membership.progress) }}% completed
			</div>

			<div class="flex items-center justify-between mt-auto">
				<div class="flex avatar-group overlap">
					<div
						class="h-6 mr-1"
						:class="{ 'avatar-group overlap': course.instructors.length > 1 }"
					>
						<UserAvatar
							v-for="instructor in course.instructors"
							:user="instructor"
						/>
					</div>
					<CourseInstructors :instructors="course.instructors" />
				</div>

			</div>
		</div>
	</div>
	
</template>
<script setup>
import { BookOpen, Users, Star } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import { sessionStore } from '@/stores/session'
import { Badge, Tooltip } from 'frappe-ui'
import CourseInstructors from '@/components/CourseInstructors.vue'
import ProgressBar from '@/components/ProgressBar.vue'

const { user } = sessionStore()

const props = defineProps({
	course: {
		type: Object,
		default: null,
	},
})
</script>
<style>
.course-image {
	height: 168px;
	width: 100%;
	background-size: cover;
	background-position: center;
	background-repeat: no-repeat;
}

.course-card-pills {
	background: #ffffff;
	margin-left: 0;
	margin-right: 0.5rem;
	padding: 3.5px 8px;
	font-size: 11px;
	text-align: center;
	letter-spacing: 0.011em;
	text-transform: uppercase;
	font-weight: 600;
	width: fit-content;
}

.default-image {
	display: flex;
	flex-direction: column;
	align-items: center;
	background-color: theme('colors.green.100');
	color: theme('colors.green.600');
}

.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}
.image-placeholder {
	display: flex;
	align-items: center;
	flex: 1;
	font-size: 5rem;
	color: theme('colors.gray.700');
	font-weight: 600;
}
.avatar-group.overlap .avatar + .avatar {
	margin-left: calc(-8px);
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
.course-card {
  /* Add your styles here */
}
</style>
