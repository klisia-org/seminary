<template>
	<div class="rounded-lg border p-5 space-y-4 text-left">
		<div class="flex items-center gap-2 text-base font-semibold text-ink-gray-9">
			<Mic class="h-5 w-5 shrink-0" />
			{{ activityDoc.data?.title || __('Oral Activity') }}
		</div>
		<SafeHtml v-if="activityDoc.data?.prompt" :html="activityDoc.data.prompt"
			class="ProseMirror prose prose-sm max-w-none !whitespace-normal text-ink-gray-8" />

		<!-- Staff: where to grade it -->
		<div v-if="isStaff" class="flex flex-wrap gap-2">
			<router-link v-if="gradeable.data" :to="{
				name: 'OralActivitySubmissionCS',
				params: { courseName, activityID: activity },
			}">
				<Button variant="solid">{{ __('Submissions') }}</Button>
			</router-link>
			<p v-else class="text-sm text-ink-gray-5">
				{{ __('Students cannot record this yet: add it to the section\'s Course Assessment as an Oral criterion.') }}
			</p>
			<router-link v-if="gradeable.data && activityDoc.data?.capture === 'Virtual meeting'"
				:to="{ name: 'OralActivityMeetingsConfigure', params: { courseName, activityID: activity } }">
				<Button>{{ __('Configure meetings') }}</Button>
			</router-link>
			<router-link :to="{ name: 'OralActivityForm', params: { activityID: activity } }">
				<Button>{{ __('Edit activity') }}</Button>
			</router-link>
			<router-link :to="{ name: 'CourseAssessment', params: { courseName } }">
				<Button :variant="gradeable.data ? 'outline' : 'solid'">{{ __('Configure Assessments') }}</Button>
			</router-link>
		</div>

		<!-- Student -->
		<p v-else-if="state.data && !state.data.gradeable" class="rounded-md bg-surface-amber-1 p-3 text-sm text-ink-amber-3">
			{{ __('This activity is not open for recording yet. Your instructor still needs to add it to the course\'s assessments.') }}
		</p>
		<template v-else-if="state.data">
			<div v-if="myDates.data?.due_date" class="text-sm text-ink-gray-6">
				{{ __('Due {0}.').format(formatWhen(myDates.data.due_date)) }}
				<span v-if="myDates.data.cutoff_date">
					{{ __('Nothing is accepted after {0}.').format(formatWhen(myDates.data.cutoff_date)) }}
				</span>
			</div>
			<RubricView activity-doctype="Oral Activity" :activity="activity"
				:submission="state.data.submission?.name || null" />

			<!-- Already submitted -->
			<div v-if="state.data.submission" class="space-y-3">
				<div class="text-sm text-ink-green-3">
					{{ __('Submitted {0}.').format(formatWhen(state.data.submission.submitted_on)) }}
				</div>
				<div v-if="state.data.submission.status === 'Graded'" class="rounded-md bg-surface-gray-2 p-3 text-sm">
					<div class="font-medium">{{ __('Grade: {0}').format(state.data.submission.grade) }}</div>
					<SafeHtml v-if="state.data.submission.comments" :html="state.data.submission.comments" class="prose-sm mt-1" />
				</div>
				<OralPlayer :recording="state.data.submission.recording" />
			</div>

			<!-- Recorded, not yet submitted -->
			<!-- Captured from class meetings (decisions/100d) -->
			<div v-else-if="state.data.capture === 'Virtual meeting'" class="space-y-2 text-sm">
				<p class="rounded-md bg-surface-amber-1 p-3 text-ink-amber-3">
					{{ __('This activity is recorded in your online class meetings, for assessment. A recorder named for it, or the meeting\'s own recording notice, shows in the call. Your instructor confirms who took part, and your submission then appears here.') }}
				</p>
				<!-- Only this student's own group meeting (decisions/100d-a §6) -->
				<div v-for="m in state.data.my_meetings || []" :key="m.name"
					class="rounded-md border p-3 text-ink-gray-8">
					<div class="font-medium">{{ __('Your group meeting') }}<template v-if="m.group"> · {{ m.group }}</template></div>
					<div>{{ whenLocal(m.start_utc) }}–{{ timeLocal(m.end_utc) }}</div>
					<a v-if="m.link" :href="m.link" target="_blank" rel="noopener noreferrer">
						<Button size="sm" variant="solid" class="mt-2">{{ __('Join the meeting') }}</Button>
					</a>
				</div>
				<ul v-if="state.data.meetings?.length" class="list-disc pl-5 text-ink-gray-7">
					<li v-for="m in state.data.meetings" :key="m.meeting_date + m.from_time">
						{{ formatDay(m.meeting_date) }} · {{ hhmm(m.from_time) }}–{{ hhmm(m.to_time) }}
					</li>
				</ul>
				<p v-else-if="!state.data.my_meetings?.length" class="text-ink-gray-5">{{ __('No meeting has been chosen yet.') }}</p>
			</div>

			<div v-else-if="state.data.recording" class="space-y-3">
				<OralPlayer :recording="state.data.recording" :key="state.data.recording" />
				<p class="text-sm text-ink-gray-6">
					{{ isConversation
						? __('Check the recording, link each speaker to a person if speakers are listed, then submit it for everyone on it.')
						: __('Check the recording, then submit it.') }}
				</p>
				<Button variant="solid" :loading="submitting" @click="submit">{{ __('Submit') }}</Button>
			</div>

			<!-- Record -->
			<div v-else-if="state.data.may_record" class="space-y-3">
				<div v-if="isConversation" class="space-y-2">
					<div class="text-sm font-medium">{{ __('Who is here?') }}</div>
					<p class="text-xs text-ink-gray-5">
						{{ __('Tick the classmates taking part. Only they are on the recording and get this submission.') }}
					</p>
					<div v-if="state.data.choosable.length" class="flex flex-wrap gap-y-2">
						<FormControl v-for="p in state.data.choosable" :key="p.student" type="checkbox" class="mr-6"
							:label="p.name" :modelValue="present.includes(p.student)"
							@update:modelValue="(v) => togglePresent(p.student, v)" />
					</div>
					<p v-else class="text-sm text-ink-gray-5">
						{{ __('Everyone else in your group has already recorded.') }}
					</p>
				</div>
				<OralRecorder reference-doctype="Scheduled Course Assess Criteria" :reference-name="state.data.scac"
					:max-s="state.data.max_seconds" :notice="state.data.notice" :participants="present"
					@finished="state.reload()" />
				<div v-if="state.data.allow_upload" class="space-y-1">
					<div class="text-sm text-ink-gray-6">{{ __('Or upload a recording made elsewhere:') }}</div>
					<input type="file" accept="audio/*" class="text-sm" :aria-label="__('Or upload a recording made elsewhere:')" :disabled="uploading" @change="upload" />
					<p class="text-xs text-ink-gray-5">
						{{ __('An uploaded file is marked with the time it was uploaded, not when it was recorded.') }}
					</p>
				</div>
			</div>

			<p v-else class="text-sm text-ink-gray-5">{{ __('This activity cannot be recorded now.') }}</p>
		</template>
		<p v-else-if="state.error" class="text-sm text-ink-gray-5">
			{{ state.error.messages?.[0] || __('This activity is not available.') }}
		</p>
	</div>
</template>

<script setup>
// An oral activity inside a lesson (decisions/100b): the student records alone
// or with the classmates present, checks the recording and submits it.
import { Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { computed, inject, ref } from 'vue'
import { Mic } from 'lucide-vue-next'
import SafeHtml from '@/components/SafeHtml.vue'
import OralPlayer from '@/components/OralPlayer.vue'
import OralRecorder from '@/components/OralRecorder.vue'
import RubricView from '@/components/RubricView.vue'
import { getCsrfToken } from '@/utils/csrf'

const user = inject('$user')
const props = defineProps({
	activity: { type: String, required: true },
	courseName: { type: String, required: true },
})

// Same rule as the discussion block: a staff role wins over Student.
const isStaff = computed(() => !!(user.data?.is_moderator || user.data?.is_evaluator || user.data?.is_instructor))
const present = ref([])
const submitting = ref(false)
const uploading = ref(false)

const activityDoc = createResource({
	url: 'frappe.client.get_value',
	makeParams: () => ({ doctype: 'Oral Activity', filters: { name: props.activity }, fieldname: ['title', 'prompt', 'mode', 'capture'] }),
	auto: true,
})
const whenLocal = (iso) => new Date(iso).toLocaleString(userLocale(), { dateStyle: 'full', timeStyle: 'short' })
const timeLocal = (iso) => new Date(iso).toLocaleTimeString(userLocale(), { hour: '2-digit', minute: '2-digit' })
const hhmm = (t) => (t ? String(t).split(':').slice(0, 2).join(':') : '')
const formatDay = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString(userLocale()) : '')
const isConversation = computed(() => (state.data?.mode || activityDoc.data?.mode) === 'Conversation')

const gradeable = createResource({
	url: 'seminary.seminary.oral_activities.gradeable',
	makeParams: () => ({ course: props.courseName, activity: props.activity }),
	auto: true,
})

const state = createResource({
	url: 'seminary.seminary.oral_activities.my_state',
	makeParams: () => ({ course: props.courseName, activity: props.activity }),
	auto: !isStaff.value,
})

const myDates = createResource({
	url: 'seminary.seminary.deadlines.get_my_dates',
	makeParams: () => ({ course: props.courseName, activity_type: 'oral', activity: props.activity }),
	auto: !isStaff.value,
	onError: () => {},
})
const formatWhen = (value) => (value ? new Date(value).toLocaleString(userLocale()) : '')

const togglePresent = (student, on) => {
	const set = new Set(present.value)
	on ? set.add(student) : set.delete(student)
	present.value = [...set]
}

const submit = async () => {
	submitting.value = true
	try {
		await call('seminary.seminary.oral_activities.submit', { recording: state.data.recording })
		toast.success(__('Submitted.'))
		state.reload()
	} catch (e) {
		toast.error(e.messages?.[0] || __('The recording could not be submitted.'))
	} finally {
		submitting.value = false
	}
}

const upload = async (event) => {
	const file = event.target.files?.[0]
	if (!file) return
	uploading.value = true
	try {
		const form = new FormData()
		form.append('reference_doctype', 'Scheduled Course Assess Criteria')
		form.append('reference_name', state.data.scac)
		form.append('participants', JSON.stringify(present.value))
		form.append('file', file, file.name)
		const headers = {}
		const token = getCsrfToken()
		if (token) headers['X-Frappe-CSRF-Token'] = token
		const response = await fetch('/api/method/seminary.seminary.oral.upload_recording', {
			method: 'POST',
			body: form,
			headers,
			credentials: 'same-origin',
		})
		if (!response.ok) {
			const body = await response.json().catch(() => ({}))
			let message = __('The file could not be uploaded.')
			try {
				message = JSON.parse(JSON.parse(body._server_messages)[0]).message || message
			} catch (e) {}
			throw new Error(message)
		}
		state.reload()
	} catch (e) {
		toast.error(e.message)
	} finally {
		uploading.value = false
		event.target.value = ''
	}
}
</script>
