<template>
	<!-- Summary: the next meeting or an open poll, one line (decisions/101 §4). -->
	<div v-if="summary || state.can_manage"
		class="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-outline-gray-2 bg-surface-white px-4 py-3">
		<CalendarDays class="h-5 w-5 shrink-0 text-ink-gray-6" />
		<div class="min-w-0 flex-1 text-sm">
			<template v-if="summary?.status === 'Polling'">
				<div class="font-medium text-ink-gray-9">{{ __('When can you meet? “{0}”').format(summary.title) }}</div>
				<div class="text-ink-gray-6">{{ __('Poll closes {0}').format(fmt(summary.poll_closes_utc)) }}</div>
			</template>
			<template v-else-if="summary">
				<div class="font-medium text-ink-gray-9">{{ __('Next meeting: {0}').format(summary.title) }}</div>
				<div class="text-ink-gray-6">
					{{ fmtRange(summary) }}
					<span v-if="summary.location"> · {{ summary.location }}</span>
				</div>
			</template>
			<div v-else class="text-ink-gray-6">{{ __('No meeting planned.') }}</div>
		</div>
		<a v-if="summary?.link" :href="summary.link" target="_blank" rel="noopener"
			class="rounded-md bg-surface-gray-7 px-3 py-1.5 text-sm text-ink-white hover:opacity-90">{{ __('Join') }}</a>
		<Button v-if="summary?.status === 'Polling'" variant="solid" :label="__('Vote')" @click="openList" />
		<Button :label="__('Meetings')" @click="openList" />
		<Button v-if="state.can_manage" :label="__('Schedule')" @click="openSchedule" />
	</div>

	<!-- All meetings -->
	<Dialog v-model="showList" :options="{ title: __('Meetings: {0}').format(cohortName), size: '2xl' }">
		<template #body-content>
			<div class="flex flex-col gap-4">
				<div v-if="state.calendar_feed" class="flex flex-wrap items-center gap-2 rounded-lg bg-surface-gray-1 px-3 py-2 text-sm">
					<CalendarPlus class="h-4 w-4 text-ink-gray-6" />
					<span class="flex-1 text-ink-gray-7">{{ __('See these meetings in your own calendar.') }}</span>
					<Button v-if="!feedUrl" :label="__('Subscribe')" :loading="feedRes.loading" @click="getFeed" />
					<template v-else>
						<a :href="webcal" class="text-ink-blue-3 hover:underline">{{ __('Open in calendar') }}</a>
						<Button :label="__('Copy link')" @click="copyFeed" />
					</template>
				</div>

				<div v-if="meetingsRes.loading && !meetings.length" class="py-6 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
				<div v-else-if="!meetings.length" class="py-6 text-center text-sm text-ink-gray-5">{{ __('No meetings yet.') }}</div>

				<section v-for="m in meetings" :key="m.name" class="rounded-lg border border-outline-gray-2 p-3"
					:class="{ 'opacity-60': m.status === 'Cancelled' }">
					<div class="flex flex-wrap items-start gap-2">
						<div class="min-w-0 flex-1">
							<div class="font-medium text-ink-gray-9">
								{{ m.title }}
								<span v-if="m.series" class="ml-1 rounded bg-surface-gray-2 px-1.5 text-xs font-normal text-ink-gray-6">{{ __('series') }}</span>
								<span v-if="m.status === 'Cancelled'" class="ml-1 rounded bg-surface-gray-2 px-1.5 text-xs font-normal text-ink-gray-6">{{ __('cancelled') }}</span>
							</div>
							<div v-if="m.status === 'Polling'" class="text-sm text-ink-gray-6">
								{{ __('Poll closes {0}').format(fmt(m.poll_closes_utc)) }}
							</div>
							<div v-else class="text-sm text-ink-gray-6">{{ fmtRange(m) }}</div>
							<div class="text-sm text-ink-gray-6">
								<template v-if="m.mode === 'In person'">{{ __('In person') }}<span v-if="m.location"> · {{ m.location }}</span></template>
								<template v-else>
									{{ m.school_meeting ? __('Online, school meeting account') : __('Online') }}
									<a v-if="m.link && m.status === 'Scheduled'" :href="m.link" target="_blank" rel="noopener" class="ml-1 text-ink-blue-3 hover:underline">{{ __('Join') }}</a>
								</template>
							</div>
							<div v-if="m.meeting_status === 'Failed'" class="text-xs text-ink-red-4">{{ m.meeting_error || __('The meeting link could not be created.') }}</div>
							<div v-if="m.host_key" class="text-xs text-ink-gray-5">{{ __('Host key: {0}').format(m.host_key) }}</div>
							<div v-if="m.my_attendance" class="text-xs text-ink-gray-5">{{ __('Your attendance: {0}').format(__(m.my_attendance)) }}</div>
						</div>
						<div v-if="state.can_manage && m.status === 'Scheduled'" class="flex flex-wrap gap-1.5">
							<Button v-if="m.started" size="sm" :label="__('Attendance')" @click="openAttendance(m)" />
							<template v-else>
								<Button size="sm" :label="__('Move')" @click="openMove(m)" />
								<Button size="sm" :label="__('Cancel')" @click="cancel(m, 0)" />
								<Button v-if="m.series" size="sm" :label="__('Cancel the rest')" @click="cancel(m, 1)" />
							</template>
						</div>
						<Button v-if="state.can_manage && m.status === 'Polling'" size="sm" :label="__('Cancel poll')" @click="cancel(m, 0)" />
					</div>

					<!-- poll options -->
					<div v-if="m.status === 'Polling'" class="mt-3 flex flex-col gap-2">
						<div v-for="o in m.options" :key="o.name" class="rounded-md bg-surface-gray-1 px-3 py-2">
							<div class="flex flex-wrap items-center gap-2">
								<div class="min-w-0 flex-1 text-sm">
									<div class="text-ink-gray-9">{{ fmtRange(o) }}</div>
									<div v-if="state.can_manage && zones.length" class="text-xs text-ink-gray-5">
										{{ zones.map((z) => `${z}: ${fmtIn(o.start_utc, z)}`).join(' · ') }}
									</div>
								</div>
								<div class="flex gap-1">
									<button v-for="a in answers" :key="a.value" type="button"
										class="rounded-md border px-2 py-1 text-xs"
										:class="o.mine === a.value ? a.on : 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:border-outline-gray-3'"
										:title="voterNames(o, a.value)"
										@click="answer(m, o, a.value)">
										{{ a.label }} <span class="text-ink-gray-5">{{ o.tally[a.value] || 0 }}</span>
									</button>
								</div>
								<Button v-if="state.can_manage" size="sm" variant="solid" :label="__('Pick')" @click="pickOption(m, o)" />
							</div>
							<div v-if="o.clashes?.length" class="mt-1 text-xs text-ink-amber-3">
								{{ __('Has a class then: {0}').format(o.clashes.join(', ')) }}
							</div>
						</div>
						<div v-if="m.non_voters?.length" class="text-xs text-ink-gray-5">
							{{ __('Not answered yet: {0}').format(m.non_voters.join(', ')) }}
						</div>
					</div>
				</section>
			</div>
		</template>
	</Dialog>

	<!-- Schedule: poll or set -->
	<Dialog v-model="showSchedule" :options="{ title: __('Schedule a meeting'), size: 'xl' }">
		<template #body-content>
			<div class="flex flex-col gap-4">
				<div class="flex gap-1 rounded-lg bg-surface-gray-2 p-1 text-sm">
					<button v-for="k in kinds" :key="k.value" type="button" class="flex-1 rounded-md px-3 py-1.5"
						:class="form.kind === k.value ? 'bg-surface-white font-medium text-ink-gray-9 shadow-sm' : 'text-ink-gray-6'"
						@click="form.kind = k.value">{{ k.label }}</button>
				</div>
				<FormControl v-model="form.title" :label="__('Title')" :placeholder="__('e.g. Monthly check-in')" />

				<template v-if="form.kind === 'poll'">
					<div>
						<div class="mb-1.5 text-xs text-ink-gray-5">{{ __('Times to offer') }}</div>
						<div v-for="(o, i) in form.options" :key="i" class="mb-2 flex flex-wrap items-center gap-2">
							<input v-model="o.date" type="date" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
							<input v-model="o.from" type="time" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
							<span class="text-ink-gray-5">–</span>
							<input v-model="o.to" type="time" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
							<button v-if="form.options.length > 1" type="button" class="text-ink-gray-5 hover:text-ink-red-4" :title="__('Remove')" @click="form.options.splice(i, 1)"><X class="h-4 w-4" /></button>
						</div>
						<Button size="sm" :label="__('Add a time')" @click="addOption" />
					</div>
					<div class="flex flex-wrap items-center gap-2 text-sm">
						<span class="text-ink-gray-6">{{ __('Poll closes') }}</span>
						<input v-model="form.closes_date" type="date" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
						<input v-model="form.closes_time" type="time" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
					</div>
				</template>

				<template v-else>
					<div class="flex flex-wrap items-center gap-2">
						<input v-model="form.date" type="date" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
						<input v-model="form.from" type="time" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
						<span class="text-ink-gray-5">–</span>
						<input v-model="form.to" type="time" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
					</div>
					<div class="flex flex-wrap items-center gap-2 text-sm">
						<span class="text-ink-gray-6">{{ __('Repeat') }}</span>
						<select v-model="form.repeat" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm">
							<option value="">{{ __('Does not repeat') }}</option>
							<option value="weekly">{{ __('Every week') }}</option>
							<option value="fortnightly">{{ __('Every two weeks') }}</option>
							<option value="monthly">{{ __('Every month') }}</option>
						</select>
						<template v-if="form.repeat">
							<span class="text-ink-gray-6">{{ __('until') }}</span>
							<input v-model="form.until" type="date" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
							<span class="text-ink-gray-6">{{ __('or') }}</span>
							<input v-model.number="form.count" type="number" min="2" max="52" class="w-20 rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
							<span class="text-ink-gray-6">{{ __('times') }}</span>
						</template>
					</div>
				</template>

				<div class="flex gap-4 text-sm">
					<label v-for="mode in modes" :key="mode.value" class="flex items-center gap-1.5">
						<input v-model="form.mode" type="radio" :value="mode.value" />{{ mode.label }}
					</label>
				</div>
				<template v-if="form.mode === 'Virtual'">
					<label v-if="state.school_meeting_allowed" class="flex items-center gap-2 text-sm text-ink-gray-7">
						<input v-model="form.school_meeting" type="checkbox" class="rounded" />
						{{ __('Use a school meeting account (the link is created for you)') }}
					</label>
					<FormControl v-if="!form.school_meeting" v-model="form.link" :label="__('Meeting link')" placeholder="https://" />
				</template>
				<FormControl v-else v-model="form.location" type="textarea" :label="__('Where')" :placeholder="__('Address or room')" />
				<p class="text-xs text-ink-gray-5">{{ __('Times are in your time zone; each member sees them in theirs.') }}</p>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="__('Cancel')" @click="showSchedule = false" />
				<Button variant="solid" :loading="saving" :label="form.kind === 'poll' ? __('Ask members') : __('Schedule')" @click="submitSchedule" />
			</div>
		</template>
	</Dialog>

	<!-- Move -->
	<Dialog v-model="showMove" :options="{ title: __('Move the meeting') }">
		<template #body-content>
			<div class="flex flex-wrap items-center gap-2">
				<input v-model="move.date" type="date" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
				<input v-model="move.from" type="time" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
				<span class="text-ink-gray-5">–</span>
				<input v-model="move.to" type="time" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm" />
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="__('Cancel')" @click="showMove = false" />
				<Button variant="solid" :loading="saving" :label="__('Move')" @click="submitMove" />
			</div>
		</template>
	</Dialog>

	<!-- Attendance -->
	<Dialog v-model="showAttendance" :options="{ title: __('Attendance'), size: 'lg' }">
		<template #body-content>
			<div class="flex flex-col divide-y divide-outline-gray-1">
				<div v-for="row in attendance" :key="row.person" class="flex items-center gap-2 py-2">
					<span class="flex-1 text-sm text-ink-gray-8">{{ row.name }}</span>
					<button v-for="s in statuses" :key="s.value" type="button"
						class="rounded-md border px-2 py-1 text-xs"
						:class="row.status === s.value ? 'border-outline-gray-4 bg-surface-gray-7 text-ink-white' : 'border-outline-gray-2 text-ink-gray-7 hover:border-outline-gray-3'"
						@click="row.status = row.status === s.value ? '' : s.value">{{ s.label }}</button>
				</div>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="__('Close')" @click="showAttendance = false" />
				<Button variant="solid" :loading="saving" :label="__('Save')" @click="submitAttendance" />
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, Dialog, FormControl, call } from 'frappe-ui'
import { CalendarDays, CalendarPlus, X } from 'lucide-vue-next'
import { createResource } from 'frappe-ui'
import { createToast } from '@/utils'

const props = defineProps({
	cohort: { type: String, required: true },
	cohortName: { type: String, default: '' },
})

const API = 'seminary.seminary.discipleship.meetings.'
const meetingsRes = createResource({
	url: API + 'cohort_meetings',
	makeParams: () => ({ cohort: props.cohort }),
	auto: true,
})
const feedRes = createResource({ url: API + 'calendar_feed_url' })

const state = computed(() => meetingsRes.data || {})
const meetings = computed(() => state.value.meetings || [])
const zones = computed(() => [...new Set((state.value.members || []).map((m) => m.time_zone).filter(Boolean))])
// The one thing to show in the feed: an open poll, else the next meeting.
const summary = computed(() => {
	const now = Date.now()
	const poll = meetings.value.find((m) => m.status === 'Polling')
	if (poll) return poll
	return meetings.value.find((m) => m.status === 'Scheduled' && new Date(m.end_utc).getTime() > now) || null
})

const answers = [
	{ value: 'Yes', label: __('Yes'), on: 'border-outline-green-2 bg-surface-green-2 text-ink-green-3' },
	{ value: 'If need be', label: __('If need be'), on: 'border-outline-amber-2 bg-surface-amber-2 text-ink-amber-3' },
	{ value: 'No', label: __('No'), on: 'border-outline-gray-4 bg-surface-gray-3 text-ink-gray-9' },
]
const statuses = [
	{ value: 'Present', label: __('Present') },
	{ value: 'Absent', label: __('Absent') },
	{ value: 'Excused', label: __('Excused') },
]
const kinds = [
	{ value: 'poll', label: __('Ask members') },
	{ value: 'direct', label: __('Set the time') },
]
const modes = [
	{ value: 'Virtual', label: __('Online') },
	{ value: 'In person', label: __('In person') },
]

// --- times: inputs are the viewer's own time; the server speaks UTC ---
const dtf = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const tf = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })
function fmt(utc) { return utc ? dtf.format(new Date(utc)) : '' }
function fmtRange(x) { return x.start_utc ? `${fmt(x.start_utc)} – ${tf.format(new Date(x.end_utc))}` : '' }
function fmtIn(utc, tz) {
	try {
		return new Intl.DateTimeFormat(undefined, { timeZone: tz, weekday: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(utc))
	} catch { return '' }
}
function toUtc(date, time) {
	if (!date || !time) return null
	const d = new Date(`${date}T${time}`)
	return isNaN(d) ? null : d.toISOString()
}
function pad(n) { return String(n).padStart(2, '0') }
function localParts(utc) {
	const d = new Date(utc)
	return { date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, time: `${pad(d.getHours())}:${pad(d.getMinutes())}` }
}

function fail(e, fallback) {
	createToast({ title: e?.messages?.[0] || fallback, icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
}
function voterNames(o, value) {
	return (o.voters?.[value] || []).join(', ')
}

// --- list ---
const showList = ref(false)
function openList() { showList.value = true; meetingsRes.reload() }

async function answer(m, o, value) {
	try {
		await call(API + 'vote', { meeting: m.name, answers: JSON.stringify({ [o.name]: o.mine === value ? '' : value }) })
		meetingsRes.reload()
	} catch (e) { fail(e, __('Could not save your answer.')) }
}
async function pickOption(m, o) {
	if (!window.confirm(__('Schedule “{0}” for {1}? Members are told.').format(m.title, fmtRange(o)))) return
	try {
		await call(API + 'choose_option', { meeting: m.name, option: o.name })
		createToast({ title: __('Meeting scheduled.'), icon: 'check' })
		meetingsRes.reload()
	} catch (e) { fail(e, __('Could not schedule the meeting.')) }
}
async function cancel(m, rest) {
	const q = rest ? __('Cancel this meeting and the rest of the series? Members are told.') : __('Cancel “{0}”? Members are told.').format(m.title)
	if (!window.confirm(q)) return
	try {
		await call(API + 'cancel_meeting', { meeting: m.name, rest_of_series: rest })
		meetingsRes.reload()
	} catch (e) { fail(e, __('Could not cancel.')) }
}

// --- schedule ---
const showSchedule = ref(false)
const saving = ref(false)
const form = reactive({})
function blankOption() { return { date: '', from: '', to: '' } }
function openSchedule() {
	Object.assign(form, {
		kind: 'poll', title: '', mode: 'Virtual', link: '', location: '', school_meeting: false,
		options: [blankOption(), blankOption()], closes_date: '', closes_time: '18:00',
		date: '', from: '', to: '', repeat: '', until: '', count: null,
	})
	showSchedule.value = true
}
function addOption() {
	const last = form.options[form.options.length - 1]
	form.options.push({ ...blankOption(), from: last?.from || '', to: last?.to || '' })
}
function place() {
	return {
		mode: form.mode,
		link: form.mode === 'Virtual' && !form.school_meeting ? form.link || null : null,
		location: form.mode === 'In person' ? form.location || null : null,
		school_meeting: form.mode === 'Virtual' && form.school_meeting ? 1 : 0,
	}
}
async function submitSchedule() {
	saving.value = true
	try {
		if (form.kind === 'poll') {
			const options = form.options
				.map((o) => ({ start_utc: toUtc(o.date, o.from), end_utc: toUtc(o.date, o.to) }))
				.filter((o) => o.start_utc && o.end_utc)
			if (!options.length) throw { messages: [__('Offer at least one time.')] }
			await call(API + 'create_poll', {
				cohort: props.cohort, title: form.title, options: JSON.stringify(options),
				poll_closes_utc: toUtc(form.closes_date, form.closes_time), ...place(),
			})
			createToast({ title: __('Members were asked.'), icon: 'check' })
		} else {
			const out = await call(API + 'schedule', {
				cohort: props.cohort, title: form.title,
				start_utc: toUtc(form.date, form.from), end_utc: toUtc(form.date, form.to),
				repeat: form.repeat || null, until: form.repeat ? form.until || null : null,
				count: form.repeat && !form.until ? form.count || null : null, ...place(),
			})
			const made = out?.created?.length || 0
			createToast({ title: made === 1 ? __('Meeting scheduled.') : __('{0} meetings scheduled.').format(made), icon: 'check' })
			if (out?.skipped?.length) {
				createToast({ title: __('{0} not scheduled: {1}').format(out.skipped.length, out.skipped[0].reason), icon: 'alert-circle', iconClasses: 'text-ink-amber-3' })
			}
		}
		showSchedule.value = false
		meetingsRes.reload()
	} catch (e) { fail(e, __('Could not schedule.')) } finally { saving.value = false }
}

// --- move ---
const showMove = ref(false)
const move = reactive({ name: '', date: '', from: '', to: '' })
function openMove(m) {
	const s = localParts(m.start_utc), e = localParts(m.end_utc)
	Object.assign(move, { name: m.name, date: s.date, from: s.time, to: e.time })
	showMove.value = true
}
async function submitMove() {
	saving.value = true
	try {
		await call(API + 'move_meeting', { meeting: move.name, start_utc: toUtc(move.date, move.from), end_utc: toUtc(move.date, move.to) })
		showMove.value = false
		meetingsRes.reload()
	} catch (e) { fail(e, __('Could not move the meeting.')) } finally { saving.value = false }
}

// --- attendance ---
const showAttendance = ref(false)
const attendance = ref([])
const attendanceFor = ref('')
function openAttendance(m) {
	attendanceFor.value = m.name
	attendance.value = (m.attendance || []).map((r) => ({ ...r }))
	showAttendance.value = true
}
async function submitAttendance() {
	saving.value = true
	try {
		await call(API + 'mark_attendance', { meeting: attendanceFor.value, rows: JSON.stringify(attendance.value) })
		showAttendance.value = false
		meetingsRes.reload()
	} catch (e) { fail(e, __('Could not save attendance.')) } finally { saving.value = false }
}

// --- calendar feed ---
const feedUrl = ref('')
const webcal = computed(() => feedUrl.value.replace(/^https?:/, 'webcal:'))
async function getFeed() {
	try { feedUrl.value = await feedRes.submit({ cohort: props.cohort }) } catch (e) { fail(e, __('Could not get the calendar link.')) }
}
function copyFeed() {
	navigator.clipboard?.writeText(feedUrl.value).then(() => createToast({ title: __('Calendar link copied.'), icon: 'check' }))
}

watch(() => props.cohort, () => { feedUrl.value = ''; meetingsRes.reload() })
defineExpose({ openList, openSchedule })
</script>
