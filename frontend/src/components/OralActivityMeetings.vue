<template>
	<div v-if="options.data?.capture === 'Virtual meeting'" class="rounded-lg border p-4 space-y-3">
		<div class="flex items-center justify-between gap-2">
			<div class="font-semibold text-ink-gray-9">{{ __('Captured meetings') }}</div>
			<Button size="sm" @click="openAdd">
				<template #prefix><Video class="h-4 w-4" /></template>
				{{ __('Capture a meeting') }}
			</Button>
		</div>
		<p class="text-sm text-ink-gray-5">
			{{ __('Choose the online class meetings in which students present. Each is recorded for this activity only; after it, confirm who took part and their submissions are created.') }}
		</p>
		<div v-if="captures.data?.length" class="divide-y rounded border text-sm">
			<div v-for="c in captures.data" :key="c.name" class="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
				<div class="min-w-0">
					<span class="font-medium">{{ formatDay(c.meeting_date) }}</span>
					<span class="text-ink-gray-5"> · {{ hhmm(c.from_time) }}–{{ hhmm(c.to_time) }} · {{ methodLabel(c.method) }}</span>
					<div v-if="c.error" class="text-xs" :class="c.status === 'Failed' ? 'text-ink-red-3' : 'text-ink-gray-5'">
						{{ c.error }}
					</div>
				</div>
				<div class="flex items-center gap-2">
					<Badge :theme="theme(c.status)">{{ statusLabel(c.status) }}</Badge>
					<Button v-if="['Captured', 'Confirmed'].includes(c.status)" size="sm" variant="subtle" @click="openReview(c.name)">
						{{ c.status === 'Captured' ? __('Confirm participants') : __('Participants') }}
					</Button>
					<Button v-if="['Scheduled', 'Armed', 'Failed'].includes(c.status)" size="sm" variant="ghost" theme="red"
						@click="cancel(c.name)">
						{{ __('Cancel') }}
					</Button>
				</div>
			</div>
		</div>
		<p v-else class="text-xs text-ink-gray-4">{{ __('No meeting is captured yet.') }}</p>

		<Dialog v-model="showAdd" :options="{ title: __('Capture a meeting') }">
			<template #body-content>
				<div class="space-y-3">
					<p v-if="!options.data.meetings.length" class="text-sm text-ink-gray-6">
						{{ __('The section has no online meeting still to come. Add one to its calendar first.') }}
					</p>
					<template v-else>
						<FormControl v-model="form.meeting" type="select" :label="__('Meeting')" :options="meetingOptions" />
						<FormControl v-model="form.method" type="select" :label="__('How it is recorded')" :options="methodOptions" />
						<p v-if="form.meeting && !methodOptions.length" class="text-sm text-ink-amber-3">
							{{ __('No capture method can record this meeting.') }}
						</p>
						<p class="text-xs text-ink-gray-5">
							{{ __('Students are told on the activity and the calendar that this meeting is recorded for assessment.') }}
						</p>
					</template>
				</div>
			</template>
			<template #actions>
				<Button @click="showAdd = false">{{ __('Cancel') }}</Button>
				<Button variant="solid" :loading="busy" :disabled="!form.meeting || !form.method" @click="add">
					{{ __('Capture') }}
				</Button>
			</template>
		</Dialog>

		<Dialog v-model="showReview" :options="{ title: __('Who took part'), size: '2xl' }">
			<template #body-content>
				<div v-if="review.data" class="space-y-3 text-sm">
					<p class="text-ink-gray-6">
						{{ __('Link each person in the meeting to a student, or leave them out. A name that matches the roster is suggested; nothing is final until you confirm.') }}
					</p>
					<div v-for="r in review.data.recordings" :key="r.name">
						<OralPlayer :recording="r.name" />
					</div>
					<div class="divide-y rounded border">
						<div v-for="p in review.data.participants" :key="p.name" class="grid grid-cols-1 gap-2 px-3 py-2 sm:grid-cols-2">
							<div>
								<div class="font-medium">{{ p.display_name || __('(no name)') }}</div>
								<div class="text-xs text-ink-gray-5">
									<span v-if="p.email">{{ p.email }} · </span>
									<span v-if="p.joined_at">{{ hm(p.joined_at) }}–{{ hm(p.left_at) }}</span>
									<span v-if="p.match"> · {{ p.match === 'Email' ? __('matched by email') : __('suggested by name') }}</span>
								</div>
							</div>
							<FormControl v-model="links[p.name]" type="select" :options="rosterOptions"
								:disabled="review.data.status === 'Confirmed'" />
						</div>
					</div>
				</div>
			</template>
			<template #actions>
				<Button @click="showReview = false">{{ __('Close') }}</Button>
				<Button v-if="review.data?.status === 'Captured'" variant="solid" :loading="busy" @click="confirm">
					{{ __('Confirm and create submissions') }}
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
// The class meetings an oral activity is captured from, on one section (decisions/100d).
import { Badge, Button, Dialog, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { computed, reactive, ref, watch } from 'vue'
import { Video } from 'lucide-vue-next'
import OralPlayer from '@/components/OralPlayer.vue'

const props = defineProps({
	course: { type: String, required: true },
	activity: { type: String, required: true },
})
const emit = defineEmits(['confirmed'])

const busy = ref(false)
const showAdd = ref(false)
const showReview = ref(false)
const form = reactive({ meeting: '', method: '' })
const links = reactive({})

const options = createResource({
	url: 'seminary.seminary.oral_meetings.capture_options',
	makeParams: () => ({ course: props.course, activity: props.activity }),
	auto: true,
	onError: () => {},
})
const captures = createResource({
	url: 'seminary.seminary.oral_meetings.list_captures',
	makeParams: () => ({ course: props.course, activity: props.activity }),
	auto: true,
	onError: () => {},
})
const review = createResource({
	url: 'seminary.seminary.oral_meetings.get_capture',
	makeParams: (v) => ({ name: v.name }),
	onSuccess(data) {
		Object.keys(links).forEach((k) => delete links[k])
		data.participants.forEach((p) => (links[p.name] = p.student || p.suggested_student || ''))
	},
})

const hhmm = (t) => (t ? String(t).split(':').slice(0, 2).join(':') : '')
const hm = (v) => (v ? new Date(v).toLocaleTimeString(userLocale(), { hour: '2-digit', minute: '2-digit' }) : '')
const formatDay = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString(userLocale()) : '')
const methodLabel = (m) => options.data?.methods.find((x) => x.method === m)?.label || m
const STATUS = {
	Scheduled: __('Waiting'),
	Armed: __('Ready to record'),
	Captured: __('Recorded: confirm who took part'),
	Confirmed: __('Confirmed'),
	Failed: __('Failed'),
	Cancelled: __('Cancelled'),
}
const statusLabel = (s) => STATUS[s] || s
const theme = (s) => ({ Armed: 'blue', Captured: 'orange', Confirmed: 'green', Failed: 'red' })[s] || 'gray'

const meetingOptions = computed(() =>
	(options.data?.meetings || []).map((m) => ({
		label: `${formatDay(m.date)} · ${hhmm(m.from_time)}–${hhmm(m.to_time)}`,
		value: m.name,
	}))
)
const methodOptions = computed(() => {
	const m = (options.data?.meetings || []).find((x) => x.name === form.meeting)
	return (m?.methods || []).map((name) => ({ label: methodLabel(name), value: name }))
})
watch(methodOptions, (opts) => {
	if (!opts.find((o) => o.value === form.method)) form.method = opts[0]?.value || ''
})
const rosterOptions = computed(() => [
	{ label: __('Not a student / leave out'), value: '' },
	...(review.data?.roster || []).map((r) => ({ label: r.name, value: r.student })),
])

const openAdd = () => {
	options.reload()
	form.meeting = options.data?.meetings?.[0]?.name || ''
	showAdd.value = true
}

const add = async () => {
	busy.value = true
	try {
		await call('seminary.seminary.oral_meetings.schedule_capture', {
			course: props.course,
			activity: props.activity,
			meeting: form.meeting,
			capture_method: form.method,
		})
		toast.success(__('The meeting will be captured'))
		showAdd.value = false
		captures.reload()
		setTimeout(() => captures.reload(), 4000)
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The meeting could not be captured'))
	} finally {
		busy.value = false
	}
}

const cancel = async (name) => {
	try {
		await call('seminary.seminary.oral_meetings.cancel_capture', { name })
		captures.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not cancel'))
	}
}

const openReview = (name) => {
	review.submit({ name })
	showReview.value = true
}

const confirm = async () => {
	busy.value = true
	try {
		const out = await call('seminary.seminary.oral_meetings.confirm_capture', {
			name: review.data.name,
			links: JSON.stringify(links),
		})
		toast.success(__('{0} submissions created').format(out.submissions.length))
		showReview.value = false
		captures.reload()
		emit('confirmed')
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not confirm'))
	} finally {
		busy.value = false
	}
}
</script>
