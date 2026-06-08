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
				<router-link :to="{
					name: 'CourseStatus',
					params: {
						courseName: course.data.name,
					},
				}">
					<Button variant="subtle" class="w-full mt-2" size="md">
						<span>
							{{ __('My Status') }}
						</span>
					</Button>
				</router-link>

			</div>


			<Button v-else @click="enrollStudent()" variant="solid" class="w-full" size="md">
				<span>
					{{ __('Start Learning') }}
				</span>
			</Button>

			<Button
				v-if="canCheckin"
				variant="solid"
				class="w-full mt-2"
				size="md"
				:loading="submitting"
				@click="markAttendance"
			>
				<template #prefix><CalendarCheck class="w-4 h-4" /></template>
				<span>{{ __('Mark my attendance') }}</span>
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
						{{ __('Configure Student Groups') }}
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
						{{ __('Gradebook') }}
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
						{{ __('Attendance') }}
					</span>
				</Button>
			</router-link>
			<Button
				v-if="(user?.data?.is_moderator || is_instructor()) && portalDisciplinary"
				variant="subtle"
				class="w-full mt-2"
				size="md"
				@click="showReportModal = true"
			>
				<span>
					{{ __('Report Disciplinary Incident') }}
				</span>
			</Button>
			<ReportDisciplinaryIncidentModal
				v-if="portalDisciplinary"
				v-model="showReportModal"
				mode="course"
				:course="course.data.name"
			/>
			<div class="space-y-4">
				<div class="mt-8 font-medium text-ink-gray-9">
					{{ __('This course has:') }}
				</div>
				<div class="flex items-center text-ink-gray-9">
					<BookOpen class="h-4 w-4 stroke-1.5" />
					<span class="ml-2">
						{{ course.data.lessons }} {{ __('Lessons') }}
					</span>
				</div>
				<div class="flex items-center text-ink-gray-9">
					<Users class="h-4 w-4 stroke-1.5" />
					<span class="ml-2">
						{{ formatAmount(course.data.enrollments) }}
						{{ __('Enrolled Students') }}
					</span>
				</div>


			</div>
		</div>
	</div>

	<!-- Self check-in dialog -->
	<Dialog v-model="showCheckinDialog" :options="{ title: __('Mark my attendance') }">
		<template #body-content>
			<div class="space-y-3">
				<template v-if="checkinContext.data?.enforce">
					<p class="text-sm text-ink-gray-6">
						{{ checkinContext.data?.course_title }} — {{ selectedMeeting }}
					</p>
					<FormControl
						v-if="checkinContext.data?.requires_code"
						v-model="codeInput"
						type="text"
						:label="__('Check-in Code')"
						:description="__('The code shown on screen during class.')"
						@keyup.enter="submitCheckin()"
					/>
				</template>
				<template v-else>
					<FormControl
						v-model="selectedMeeting"
						type="select"
						:label="__('Meeting date')"
						:options="pendingOptions"
					/>
				</template>
				<p v-if="checkinError" class="text-sm text-ink-red-4">
					{{ checkinError }}
				</p>
			</div>
		</template>
		<template #actions>
			<Button variant="solid" class="w-full" :loading="submitting" @click="submitCheckin()">
				{{ __('Check in') }}
			</Button>
		</template>
	</Dialog>
</template>
<script setup>
import { BookOpen, Users, Star, GraduationCap, CalendarCheck } from 'lucide-vue-next'
import { computed, inject, ref, watch } from 'vue'
import { Button, Dialog, FormControl, createResource, call, toast, Tooltip } from 'frappe-ui'
import { formatAmount } from '@/utils/'
import { usePortalDisciplinary } from '@/composables/usePortalDisciplinary'
import ReportDisciplinaryIncidentModal from '@/components/Modals/ReportDisciplinaryIncidentModal.vue'

import { useRouter } from 'vue-router'


const router = useRouter()
const user = inject('$user')

const { portalDisciplinary } = usePortalDisciplinary()
const showReportModal = ref(false)

const props = defineProps({
	course: {
		type: Object,
		default: null,
	},
})

// --- Student self check-in ------------------------------------------------
const showCheckinDialog = ref(false)
const selectedMeeting = ref('')
const codeInput = ref('')
const submitting = ref(false)
const checkinError = ref('')

// Pull a human message out of a frappe-ui call error (server validation
// messages live in `messages`; `message` may carry a "…Error: " prefix).
function checkinErrorMsg(e) {
	if (Array.isArray(e?.messages) && e.messages.length) return e.messages.join('\n')
	const m = (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()
	return m || __('Could not check in. Please try again.')
}

const checkinContext = createResource({
	url: 'seminary.seminary.course_checkin.get_course_checkin_context',
	makeParams() {
		return { course_schedule: props.course.data?.name }
	},
})

watch(
	() => props.course.data?.name,
	(name) => name && checkinContext.reload(),
	{ immediate: true }
)

const canCheckin = computed(
	() => checkinContext.data?.eligible && !user?.data?.is_moderator && !is_instructor()
)

const pendingOptions = computed(() =>
	(checkinContext.data?.pending || []).map((p) => ({
		label: p.meeting_date,
		value: p.meeting_date,
	}))
)

function markAttendance() {
	const ctx = checkinContext.data
	if (!ctx?.eligible) return
	checkinError.value = ''
	if (ctx.enforce) {
		const m = ctx.open_meeting
		if (!m) {
			toast.error(__('No class is open for check-in right now.'))
			return
		}
		if (m.already_checked_in) {
			toast.success(__('You are already checked in for this class.'))
			return
		}
		selectedMeeting.value = m.meeting_date
		codeInput.value = ''
		if (ctx.requires_code) {
			showCheckinDialog.value = true
		} else {
			submitCheckin()
		}
	} else {
		if (!ctx.pending?.length) {
			toast.success(__('No meetings are awaiting your attendance.'))
			return
		}
		selectedMeeting.value = ctx.pending[0].meeting_date
		showCheckinDialog.value = true
	}
}

async function submitCheckin() {
	if (!selectedMeeting.value) {
		toast.error(__('Select a meeting date'))
		return
	}
	submitting.value = true
	checkinError.value = ''
	try {
		const res = await call('seminary.seminary.course_checkin.course_check_in', {
			course_schedule: props.course.data.name,
			meeting_date: selectedMeeting.value,
			code: codeInput.value || null,
		})
		toast.success(
			res?.status === 'Tardy' ? __('Checked in — marked Tardy') : __('Checked in'))
		showCheckinDialog.value = false
		checkinContext.reload()
	} catch (e) {
		const msg = checkinErrorMsg(e)
		checkinError.value = msg
		// Surface it even on the one-click path (no dialog open yet).
		showCheckinDialog.value = true
		toast.error(msg)
	} finally {
		submitting.value = false
	}
}

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
	return user_is_instructor
}




</script>