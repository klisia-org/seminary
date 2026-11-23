<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
	</PageHeader>
	<div class="md:w-3/4 md:mx-auto py-5 mx-5 space-y-6">
		<div>
			<h2 class="text-xl font-semibold text-ink-gray-9">{{ state.data?.title || __('Oral Activity') }}</h2>
			<p class="text-sm text-ink-gray-5">{{ __('Captured from online meetings') }}</p>
		</div>

		<div class="flex flex-wrap gap-2">
			<Button :variant="mode === 'group' ? 'solid' : 'outline'" @click="mode = 'group'">{{ __('Group meetings') }}</Button>
			<Button :variant="mode === 'whole' ? 'solid' : 'outline'" @click="mode = 'whole'">{{ __('In a whole class meeting') }}</Button>
		</div>

		<OralActivityMeetings v-if="mode === 'whole'" :course="courseName" :activity="activityID" />

		<template v-else-if="state.data">
			<!-- 1. Groups -->
			<section class="rounded-lg border p-4 space-y-3">
				<div class="font-semibold">{{ __('1. Groups') }}</div>
				<p class="text-sm text-ink-gray-5">
					{{ __('Each group gets its own meeting, which only its members see. Students are shown with their time zone and the time it is for them now.') }}
				</p>
				<div class="flex flex-wrap items-end gap-3">
					<Button v-if="state.data.section_groups.length" @click="useSectionGroups">
						{{ __('Use the section\'s student groups') }}
					</Button>
					<FormControl v-model.number="size" type="number" min="1" :label="__('Group size')" class="w-28" />
					<FormControl v-model="keepZones" type="checkbox" :label="__('Keep nearby time zones together')" />
					<Button :loading="proposing" @click="bySize">{{ __('Make groups by size') }}</Button>
					<Button variant="ghost" @click="addGroup">{{ __('Add a group') }}</Button>
				</div>
				<div class="overflow-x-auto rounded border">
					<table class="w-full text-sm">
						<thead class="bg-surface-gray-2 text-left text-ink-gray-7">
							<tr>
								<th class="p-2">{{ __('Student') }}</th>
								<th class="p-2">{{ __('Time zone') }}</th>
								<th class="p-2">{{ __('Their time now') }}</th>
								<th class="p-2">{{ __('Group') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="s in sortedStudents" :key="s.student" class="border-t">
								<td class="p-2">{{ s.name }}</td>
								<td class="p-2" :class="s.time_zone ? '' : 'text-ink-gray-4'">{{ s.time_zone || __('unknown') }}</td>
								<td class="p-2">{{ s.time_zone ? localNow(s.time_zone) : '' }}</td>
								<td class="p-2">
									<select :aria-label="__('Group for {0}').format(s.name)" v-model="assign[s.student]"
										class="rounded-md border-outline-gray-2 bg-surface-white text-sm">
										<option value="">{{ __('No group') }}</option>
										<option v-for="g in labels" :key="g" :value="g">{{ g }}</option>
									</select>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<!-- 2. Times -->
			<section class="rounded-lg border p-4 space-y-3">
				<div class="font-semibold">{{ __('2. When') }}</div>
				<div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
					<FormControl v-model="c.date_from" type="date" :label="__('From')" />
					<FormControl v-model="c.date_to" type="date" :label="__('To')" />
					<FormControl v-model.number="c.length" type="number" min="5" :label="__('Each meeting (minutes)')" />
					<FormControl v-model="c.hours_from" type="time" :label="__('Day starts')" />
					<FormControl v-model="c.hours_to" type="time" :label="__('Day ends')" />
					<FormControl v-model.number="c.gap" type="number" min="0" :label="__('Break between meetings (minutes)')" />
				</div>
				<div class="flex flex-wrap gap-y-2">
					<FormControl v-for="(d, i) in weekdayNames" :key="i" type="checkbox" :label="d" class="mr-6"
						:modelValue="c.weekdays.includes(i)" @update:modelValue="(v) => toggleDay(i, v)" />
				</div>
				<FormControl v-model="c.attend" type="checkbox" :label="__('I attend each meeting')" />
				<p class="text-xs text-ink-gray-5">
					{{ c.attend
						? __('Meetings follow one another in your hours ({0}) and avoid your other classes.').format(state.data.my_time_zone)
						: __('Groups may meet at the same time, and the day\'s hours are read in each student\'s own time zone. When no time fits a whole group, the closest one is taken and explained.') }}
				</p>
				<FormControl v-if="state.data.school_accounts" v-model="c.use_accounts" type="checkbox"
					:label="__('Create the meetings on the school\'s meeting accounts')" />
				<Button variant="solid" :loading="suggesting" @click="suggest">{{ __('Suggest times') }}</Button>
			</section>

			<!-- 3. Review and create -->
			<section v-if="slots.length" class="rounded-lg border p-4 space-y-3">
				<div class="font-semibold">{{ __('3. Review and create') }}</div>
				<div class="divide-y rounded border text-sm">
					<div v-for="(s, i) in slots" :key="i" class="space-y-1 px-3 py-2">
						<div class="flex flex-wrap items-center justify-between gap-2">
							<span class="font-medium">{{ s.label }}</span>
							<span v-if="!s.start_utc" class="text-ink-red-3">{{ s.reason }}</span>
							<div v-else class="flex items-center gap-2">
								<input type="datetime-local" class="rounded border-outline-gray-2 text-sm"
									:value="toInput(s.start_utc)" @change="(e) => moveSlot(s, e.target.value)" />
								<span class="text-ink-gray-5">{{ __('{0} min').format(c.length) }}</span>
							</div>
						</div>
						<div class="text-xs text-ink-gray-6">
							<span v-for="m in s.local || []" :key="m.student" class="mr-3">
								{{ m.name }}: {{ m.time_zone ? zoneTime(s.start_utc, m.time_zone) + ' (' + m.time_zone + ')' : __('time zone unknown') }}
							</span>
						</div>
						<div v-if="s.note" class="rounded bg-surface-amber-1 p-2 text-xs text-ink-amber-3">{{ s.note }}</div>
					</div>
				</div>
				<div class="flex flex-wrap items-end gap-3">
					<FormControl v-model="method" type="select" :label="__('How it is recorded')" :options="methodOptions" />
					<FormControl v-if="!useAccounts" v-model="link" type="url" class="min-w-72"
						:label="__('Meeting link (for every group)')" :placeholder="__('https://zoom.us/j/...')" />
					<Button variant="solid" :loading="creating" :disabled="!method" @click="create">
						{{ __('Create {0} meetings').format(slots.filter((s) => s.start_utc).length) }}
					</Button>
				</div>
			</section>

			<!-- Existing -->
			<section class="rounded-lg border p-4 space-y-3">
				<div class="flex items-center justify-between">
					<div class="font-semibold">{{ __('Group meetings') }}</div>
					<router-link :to="{ name: 'OralActivitySubmissionCS', params: { courseName, activityID } }">
						<Button size="sm" variant="subtle">{{ __('Confirm participants and grade') }}</Button>
					</router-link>
				</div>
				<p v-if="!state.data.meetings.length" class="text-xs text-ink-gray-4">{{ __('None yet.') }}</p>
				<div v-else class="divide-y rounded border text-sm">
					<div v-for="m in state.data.meetings" :key="m.name" class="space-y-1 px-3 py-2">
						<div class="flex flex-wrap items-center justify-between gap-2">
							<div>
								<span class="font-medium">{{ m.group_label }}</span>
								<span class="text-ink-gray-5"> · {{ when(m.start_utc) }}</span>
								<a v-if="m.link" :href="m.link" target="_blank" rel="noopener noreferrer"
									class="ml-2 text-ink-blue-3 hover:underline">{{ __('Join') }}</a>
							</div>
							<div class="flex items-center gap-2">
								<Badge :theme="theme(m.status)">{{ __(m.status) }}</Badge>
								<template v-if="['Scheduled', 'Armed', 'Failed'].includes(m.status)">
									<Button size="sm" variant="ghost" @click="openMove(m)">{{ __('Move') }}</Button>
									<Button size="sm" variant="ghost" theme="red" @click="cancel(m)">{{ __('Cancel') }}</Button>
								</template>
							</div>
						</div>
						<div class="text-xs text-ink-gray-6">
							<span v-for="p in m.members" :key="p.student" class="mr-3">
								{{ p.student_name }}<template v-if="p.time_zone"> ({{ zoneTime(m.start_utc, p.time_zone) }} {{ p.time_zone }})</template>
								<button v-if="['Scheduled', 'Armed'].includes(m.status) && otherMeetings(m).length"
									class="ml-1 text-ink-blue-3 hover:underline" @click="openSwap(m, p)">{{ __('move') }}</button>
							</span>
						</div>
						<div v-if="m.meeting_status === 'Failed'" class="text-xs text-ink-red-3">{{ m.meeting_error }}</div>
						<div v-if="m.error" class="text-xs text-ink-gray-5">{{ m.error }}</div>
						<div v-if="m.schedule_note" class="text-xs text-ink-amber-3">{{ m.schedule_note }}</div>
						<div v-if="m.host_key" class="text-xs text-ink-gray-5">{{ __('Host key: {0}').format(m.host_key) }}</div>
					</div>
				</div>
			</section>
		</template>

		<Dialog v-model="showMove" :options="{ title: __('Move the meeting') }">
			<template #body-content>
				<div class="space-y-2">
					<input v-model="moveForm.start" type="datetime-local" class="w-full rounded border-outline-gray-2 text-sm" />
					<FormControl v-model.number="moveForm.length" type="number" min="5" :label="__('Minutes')" />
					<p class="text-xs text-ink-gray-5">{{ __('Its members are told the new time.') }}</p>
				</div>
			</template>
			<template #actions>
				<Button @click="showMove = false">{{ __('Cancel') }}</Button>
				<Button variant="solid" :loading="busy" @click="move">{{ __('Move') }}</Button>
			</template>
		</Dialog>

		<Dialog v-model="showSwap" :options="{ title: __('Move a student to another meeting') }">
			<template #body-content>
				<FormControl v-model="swapForm.to" type="select" :label="swapForm.name"
					:options="(swapForm.options || []).map((o) => ({ label: `${o.group_label} · ${when(o.start_utc)}`, value: o.name }))" />
			</template>
			<template #actions>
				<Button @click="showSwap = false">{{ __('Cancel') }}</Button>
				<Button variant="solid" :loading="busy" @click="swap">{{ __('Move') }}</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
// Group meetings for an oral activity on one section (decisions/100d-a).
import PageHeader from '@/components/PageHeader.vue'
import OralActivityMeetings from '@/components/OralActivityMeetings.vue'
import { Badge, Breadcrumbs, Button, Dialog, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { computed, reactive, ref } from 'vue'

const props = defineProps({
	courseName: { type: String, required: true },
	activityID: { type: String, required: true },
})

const mode = ref('group')
const size = ref(3)
const keepZones = ref(true)
const assign = reactive({})
const extraLabels = ref([])
const slots = ref([])
const method = ref('')
const link = ref('')
const proposing = ref(false)
const suggesting = ref(false)
const creating = ref(false)
const busy = ref(false)
const showMove = ref(false)
const showSwap = ref(false)
const moveForm = reactive({ name: '', start: '', length: 30 })
const swapForm = reactive({ student: '', name: '', from: '', to: '', options: [] })

const isoDay = (d) => d.toISOString().slice(0, 10)
const c = reactive({
	date_from: isoDay(new Date(Date.now() + 86400000)),
	date_to: isoDay(new Date(Date.now() + 8 * 86400000)),
	weekdays: [0, 1, 2, 3, 4],
	hours_from: '09:00',
	hours_to: '17:00',
	length: 30,
	gap: 10,
	attend: true,
	use_accounts: true,
})
// Monday first, as the server counts them.
const weekdayNames = [1, 2, 3, 4, 5, 6, 0].map((d) =>
	new Date(2026, 10, 1 + d).toLocaleDateString(userLocale(), { weekday: 'short' })
)

const state = createResource({
	url: 'seminary.seminary.oral_groups.configure_state',
	makeParams: () => ({ course: props.courseName, activity: props.activityID }),
	auto: true,
	onSuccess(data) {
		if (data.meetings.length === 0 && !Object.keys(assign).length && data.section_groups.length) useSectionGroups()
		if (!method.value) method.value = methodOptions.value[0]?.value || ''
	},
})

const useAccounts = computed(() => !!(state.data?.school_accounts && c.use_accounts))
const labels = computed(() => {
	const set = new Set([...Object.values(assign).filter(Boolean), ...extraLabels.value])
	return [...set].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
})
const sortedStudents = computed(() => state.data?.students || [])
const methodOptions = computed(() =>
	(state.data?.methods || [])
		.filter((m) => !m.needs_managed || useAccounts.value)
		.map((m) => ({ label: m.label, value: m.method }))
)

const setGroups = (groups) => {
	Object.keys(assign).forEach((k) => (assign[k] = ''))
	extraLabels.value = []
	groups.forEach((g) => g.students.forEach((s) => (assign[s] = g.label)))
	slots.value = []
}
const useSectionGroups = () => setGroups(state.data.section_groups)
const bySize = async () => {
	proposing.value = true
	try {
		setGroups(await call('seminary.seminary.oral_groups.propose_groups', {
			course: props.courseName, activity: props.activityID, size: size.value, keep_zones: keepZones.value ? 1 : 0,
		}))
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not make groups'))
	} finally {
		proposing.value = false
	}
}
const addGroup = () => {
	extraLabels.value.push(__('Group {0}').format(labels.value.length + 1))
}
const groupsPayload = () =>
	labels.value
		.map((label) => ({ label, students: Object.keys(assign).filter((s) => assign[s] === label) }))
		.filter((g) => g.students.length)

const toggleDay = (d, on) => {
	c.weekdays = on ? [...new Set([...c.weekdays, d])] : c.weekdays.filter((x) => x !== d)
}

const suggest = async () => {
	suggesting.value = true
	try {
		slots.value = await call('seminary.seminary.oral_groups.suggest', {
			course: props.courseName,
			activity: props.activityID,
			groups: JSON.stringify(groupsPayload()),
			constraints: JSON.stringify({ ...c, attend: c.attend ? 1 : 0, use_accounts: useAccounts.value ? 1 : 0 }),
		})
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not suggest times'))
	} finally {
		suggesting.value = false
	}
}

const pad = (n) => String(n).padStart(2, '0')
const toInput = (iso) => {
	const d = new Date(iso)
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
const moveSlot = (s, value) => {
	const start = new Date(value)
	const len = (new Date(s.end_utc) - new Date(s.start_utc)) || c.length * 60000
	s.start_utc = start.toISOString()
	s.end_utc = new Date(start.getTime() + len).toISOString()
	s.note = __('Moved by you.')
}
const when = (iso) => (iso ? new Date(iso).toLocaleString(userLocale(), { dateStyle: 'medium', timeStyle: 'short' }) : '')
const zoneTime = (iso, tz) => {
	try {
		return new Date(iso).toLocaleTimeString(userLocale(), { timeZone: tz, hour: '2-digit', minute: '2-digit', weekday: 'short' })
	} catch (e) {
		return ''
	}
}
const localNow = (tz) => zoneTime(new Date().toISOString(), tz)
const theme = (s) => ({ Armed: 'blue', Captured: 'orange', Confirmed: 'green', Failed: 'red' })[s] || 'gray'

const create = async () => {
	creating.value = true
	try {
		const out = await call('seminary.seminary.oral_groups.create_meetings', {
			course: props.courseName,
			activity: props.activityID,
			slots: JSON.stringify(slots.value.filter((s) => s.start_utc)),
			capture_method: method.value,
			link: useAccounts.value ? null : link.value || null,
		})
		toast.success(__('{0} meetings created').format(out.created.length))
		if (out.skipped.length) {
			toast.error(out.skipped.map((s) => `${s.label}: ${s.reason}`).join(' · '))
		}
		slots.value = []
		state.reload()
		setTimeout(() => state.reload(), 5000)
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The meetings could not be created'))
	} finally {
		creating.value = false
	}
}

const openMove = (m) => {
	moveForm.name = m.name
	moveForm.start = toInput(m.start_utc)
	moveForm.length = Math.round((new Date(m.end_utc) - new Date(m.start_utc)) / 60000) || 30
	showMove.value = true
}
const move = async () => {
	busy.value = true
	try {
		const start = new Date(moveForm.start)
		await call('seminary.seminary.oral_groups.move_meeting', {
			name: moveForm.name,
			start_utc: start.toISOString(),
			end_utc: new Date(start.getTime() + moveForm.length * 60000).toISOString(),
		})
		showMove.value = false
		state.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The meeting could not be moved'))
	} finally {
		busy.value = false
	}
}
const cancel = async (m) => {
	if (!window.confirm(__('Cancel the meeting for {0}? Its members are told.').format(m.group_label))) return
	try {
		await call('seminary.seminary.oral_groups.cancel_meeting', { name: m.name })
		state.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not cancel'))
	}
}
const otherMeetings = (m) =>
	(state.data?.meetings || []).filter((x) => x.name !== m.name && ['Scheduled', 'Armed'].includes(x.status))
const openSwap = (m, p) => {
	Object.assign(swapForm, { student: p.student, name: p.student_name, from: m.name, options: otherMeetings(m) })
	swapForm.to = swapForm.options[0]?.name || ''
	showSwap.value = true
}
const swap = async () => {
	busy.value = true
	try {
		await call('seminary.seminary.oral_groups.move_student', {
			student: swapForm.student, from_meeting: swapForm.from, to_meeting: swapForm.to,
		})
		showSwap.value = false
		state.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not move the student'))
	} finally {
		busy.value = false
	}
}

const breadcrumbs = computed(() => [
	{ label: state.data?.title || __('Oral Activity'), route: { name: 'OralActivitySubmissionCS', params: { courseName: props.courseName, activityID: props.activityID } } },
	{ label: __('Configure meetings'), route: { name: 'OralActivityMeetingsConfigure', params: { courseName: props.courseName, activityID: props.activityID } } },
])
</script>
