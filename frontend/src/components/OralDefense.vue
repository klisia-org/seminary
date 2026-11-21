<template>
	<div v-if="state.data?.required" class="mb-4 rounded-lg border p-4 space-y-3 text-left">
		<div class="flex items-center justify-between gap-2">
			<div class="flex items-center gap-2 font-semibold text-ink-gray-9">
				<Mic class="h-5 w-5 shrink-0" />
				{{ __('Oral defense') }}
			</div>
			<Badge :theme="badgeTheme">{{ badgeLabel }}</Badge>
		</div>

		<!-- Not open yet -->
		<p v-if="['Waiting for Questions', 'Waiting for Release'].includes(state.data.status)"
			class="text-sm text-ink-gray-6">
			{{ __('Your paper is in. The questions for your oral defense are being prepared; this page will tell you when it opens. Until then the assignment is incomplete.') }}
		</p>

		<!-- Open, not started -->
		<template v-else-if="state.data.status === 'Open'">
			<p class="text-sm text-ink-gray-7">
				{{ __('Answer {0} questions about your paper, aloud, one at a time. You see each question only when it is asked, with {1} seconds to read it and {2} seconds to answer. There is one take per question.').format(state.data.count, state.data.prepare_s, state.data.answer_s) }}
				<template v-if="state.data.follow_up">
					{{ __('After an answer there may be one more question on what you said.') }}
				</template>
			</p>
			<p v-if="state.data.due" class="text-sm" :class="pastDue ? 'text-ink-red-3' : 'text-ink-gray-6'">
				{{ __('Due {0}.').format(formatWhen(state.data.due)) }}
				<template v-if="pastDue">{{ __('It is past due, so a late deduction may apply.') }}</template>
			</p>
			<p v-if="state.data.written" class="text-sm text-ink-gray-6">
				{{ __('You answer in writing instead of aloud.') }}
			</p>
			<p v-else class="text-xs text-ink-gray-5">{{ noticeText }}</p>
			<Button variant="solid" :loading="busy" @click="start">{{ __('Start the defense') }}</Button>
		</template>

		<!-- In progress -->
		<template v-else-if="state.data.status === 'In Progress'">
			<div class="text-xs text-ink-gray-5">
				{{ __('Answered {0}. Stay on this page until the defense is done.').format(state.data.answered) }}
			</div>
			<div v-if="waiting" class="text-sm text-ink-gray-6" role="status">
				{{ __('One moment: there may be a follow-up question on your answer.') }}
			</div>
			<template v-else-if="current">
				<template v-if="state.data.written">
					<div class="rounded-md bg-surface-gray-2 p-3 text-sm font-medium">
						<span v-if="current.follow_up" class="mr-1 text-ink-blue-3">{{ __('Follow-up:') }}</span>
						{{ current.question }}
					</div>
					<FormControl v-model="written" type="textarea" rows="6" :placeholder="__('Your answer')" />
					<Button variant="solid" :loading="busy" @click="sendWritten">{{ __('Next') }}</Button>
				</template>
				<OralRecorder v-else :key="current.name" reference-doctype="Oral Defense Question"
					:reference-name="current.name" :prepare-s="state.data.prepare_s" :max-s="state.data.answer_s"
					:notice="state.data.notice" @finished="next">
					<template #question>
						<div class="rounded-md bg-surface-gray-2 p-3 text-sm font-medium">
							<span v-if="current.follow_up" class="mr-1 text-ink-blue-3">{{ __('Follow-up:') }}</span>
							{{ current.question }}
						</div>
					</template>
				</OralRecorder>
			</template>
			<Button v-else-if="state.data.recording" variant="solid" :loading="busy" @click="next">
				{{ __('Continue') }}
			</Button>
		</template>

		<p v-else-if="state.data.status === 'Done'" class="text-sm text-ink-green-3">
			{{ __('Your oral defense is done. Thank you.') }}
		</p>
	</div>
</template>

<script setup>
// The student's oral defense of a submitted paper (decisions/100c): one
// question at a time, recorded under exam conditions, with an optional
// follow-up the page waits for at most 20 seconds.
import { Badge, Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { computed, onBeforeUnmount, ref } from 'vue'
import { Mic } from 'lucide-vue-next'
import OralRecorder from '@/components/OralRecorder.vue'

const props = defineProps({
	submission: { type: String, required: true },
})

const busy = ref(false)
const waiting = ref(false)
const current = ref(null)
const written = ref('')
let pollTimer = null
let retries = 0
let openTimer = null

const state = createResource({
	url: 'seminary.seminary.oral_defense.my_defense',
	makeParams: () => ({ submission: props.submission }),
	auto: true,
	onSuccess(data) {
		current.value = data.current && !data.recording ? data.current : null
		// Until it opens, look again now and then: questions take a minute or two.
		clearTimeout(openTimer)
		if (['Waiting for Questions', 'Waiting for Release'].includes(data.status)) {
			openTimer = setTimeout(() => state.reload(), 15000)
		}
	},
})

const formatWhen = (value) => (value ? new Date(value).toLocaleString(userLocale()) : '')
const pastDue = computed(() => state.data?.due && new Date(state.data.due) < new Date())

const badgeLabel = computed(() => {
	const s = state.data?.status
	if (s === 'Done') return __('Done')
	if (s === 'In Progress') return __('In progress')
	return __('Incomplete')
})
const badgeTheme = computed(() => (state.data?.status === 'Done' ? 'green' : 'orange'))

const noticeText = computed(() => {
	const parts = [__('Your answers are recorded. Your instructors and school staff can listen to them.')]
	const n = state.data?.notice
	if (n?.steps?.length) parts.push(__('They will be processed by: {0}.').format(n.steps.join(', ')))
	if (n?.retention_days) {
		parts.push(__('The audio is kept for {0} days after your grades are sent.').format(n.retention_days))
	}
	return parts.join(' ')
})

const show = (out) => {
	retries = 0
	waiting.value = false
	if (out.done) {
		current.value = null
		state.reload()
		return
	}
	written.value = ''
	current.value = out.current
	state.reload()
}

const start = async () => {
	busy.value = true
	try {
		show(await call('seminary.seminary.oral_defense.start', { submission: props.submission }))
	} catch (e) {
		toast.error(e.messages?.[0] || __('The defense could not start.'))
	} finally {
		busy.value = false
	}
}

const next = async () => {
	clearTimeout(pollTimer)
	busy.value = true
	try {
		const out = await call('seminary.seminary.oral_defense.next_question', { submission: props.submission })
		if (out.wait) {
			waiting.value = true
			current.value = null
			pollTimer = setTimeout(next, 2000)
			return
		}
		show(out)
	} catch (e) {
		// The answer may still be on its way: try again shortly, a few times.
		retries += 1
		if (retries <= 5) {
			pollTimer = setTimeout(next, 3000)
		} else {
			retries = 0
			toast.error(e.messages?.[0] || __('The defense could not move on. Reload the page.'))
		}
	} finally {
		busy.value = false
	}
}

const sendWritten = async () => {
	busy.value = true
	try {
		const out = await call('seminary.seminary.oral_defense.answer_in_writing', {
			submission: props.submission,
			question: current.value.name,
			answer: written.value,
		})
		if (out.wait) {
			waiting.value = true
			pollTimer = setTimeout(next, 2000)
			return
		}
		show(out)
	} catch (e) {
		toast.error(e.messages?.[0] || __('The answer could not be saved.'))
	} finally {
		busy.value = false
	}
}

onBeforeUnmount(() => {
	clearTimeout(pollTimer)
	clearTimeout(openTimer)
})
</script>
