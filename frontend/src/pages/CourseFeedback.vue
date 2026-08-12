<template>
	<!--
		Optional Aretenic surface (ADR 030): renders an explanatory empty state when the app is
		absent or nothing is open, so the route is harmless either way.

		No token appears anywhere on this path. End-of-course feedback is portal-only precisely
		because a mailed token would persist in the communication ledger as a durable person-to-token
		map (decisions/035 §7); the invitation is resolved from the session instead.
	-->
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
		<h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Course feedback') }}</h1>
	</header>

	<div class="mx-auto max-w-2xl p-5">
		<div v-if="questionnaire.loading" class="text-ink-gray-5">{{ __('Loading…') }}</div>

		<div v-else-if="submitted" class="rounded border border-outline-gray-2 bg-surface-white p-6">
			<h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Thank you.') }}</h2>
			<p class="mt-1 text-sm text-ink-gray-6">
				{{ __('Your answers have been recorded.') }}
			</p>
			<Button class="mt-4" variant="subtle" :label="__('Back to my courses')"
				@click="router.push({ name: 'Courses' })" />
		</div>

		<div v-else-if="!isOpen" class="rounded border border-outline-gray-2 bg-surface-white p-6">
			<h2 class="text-lg font-semibold text-ink-gray-9">
				{{ answered ? __('You have already answered') : __('Nothing open') }}
			</h2>
			<p class="mt-1 text-sm text-ink-gray-6">
				{{
					answered
						? __('Thank you — your answers were recorded and cannot be changed.')
						: __('There is no feedback questionnaire open for this course right now.')
				}}
			</p>
		</div>

		<div v-else>
			<h2 class="text-lg font-semibold text-ink-gray-9">{{ data.title }}</h2>
			<p v-if="data.estimated_minutes" class="mt-0.5 text-sm text-ink-gray-5">
				{{ __('About {0} minutes.', [data.estimated_minutes]) }}
			</p>

			<!--
				Shown verbatim, before the first question. Where the cohort is small enough to be
				reported descriptively this is the sentence saying answers will be read individually
				— the price of that mode, and not something to soften (decisions/035 §8).
			-->
			<div v-if="data.notice"
				class="mt-4 rounded border px-3 py-2.5 text-sm"
				:class="data.small_cohort
					? 'border-amber-300 bg-amber-50 text-amber-900'
					: 'border-outline-gray-2 bg-surface-gray-1 text-ink-gray-7'">
				{{ data.notice }}
			</div>
			<div v-else-if="data.anonymity === 'Anonymous'"
				class="mt-4 rounded border border-outline-gray-2 bg-surface-gray-1 px-3 py-2.5 text-sm text-ink-gray-7">
				{{ __('Your answers are reported together with everyone else\'s and are not linked back to you. Your instructor sees them only after grades have been submitted.') }}
			</div>

			<div v-if="data.intro_text" class="mt-4 text-sm text-ink-gray-7" v-html="data.intro_text" />

			<div v-for="block in data.blocks" :key="block.block" class="mt-6">
				<h3 v-if="block.title" class="mb-3 text-base font-medium text-ink-gray-8">
					{{ block.title }}
				</h3>

				<div v-for="q in block.questions" :key="q.name" class="mb-5">
					<label class="block text-sm font-medium text-ink-gray-8">
						{{ q.prompt }}
						<span v-if="q.is_required" class="text-red-600">*</span>
					</label>
					<p v-if="q.help_text" class="mt-0.5 text-xs text-ink-gray-5">{{ q.help_text }}</p>

					<div v-if="['Likert', 'NPS'].includes(q.item_type)" class="mt-2 flex flex-wrap gap-x-4 gap-y-1">
						<label v-for="p in q.scale" :key="p.value"
							class="flex items-center gap-1.5 text-sm text-ink-gray-7">
							<input type="radio" :name="q.name" :value="p.value" v-model="answers[q.name]" />
							{{ p.label }}
						</label>
					</div>

					<div v-else-if="q.item_type === 'Yes-No'" class="mt-2 flex gap-4">
						<label class="flex items-center gap-1.5 text-sm text-ink-gray-7">
							<input type="radio" :name="q.name" value="1" v-model="answers[q.name]" />
							{{ __('Yes') }}
						</label>
						<label class="flex items-center gap-1.5 text-sm text-ink-gray-7">
							<input type="radio" :name="q.name" value="0" v-model="answers[q.name]" />
							{{ __('No') }}
						</label>
					</div>

					<div v-else-if="q.item_type === 'Single Choice'" class="mt-2 space-y-1">
						<label v-for="o in q.options" :key="o.option_code"
							class="flex items-center gap-1.5 text-sm text-ink-gray-7">
							<input type="radio" :name="q.name" :value="o.option_code" v-model="answers[q.name]" />
							{{ o.option_label }}
						</label>
					</div>

					<div v-else-if="q.item_type === 'Multi Choice'" class="mt-2 space-y-1">
						<label v-for="o in q.options" :key="o.option_code"
							class="flex items-center gap-1.5 text-sm text-ink-gray-7">
							<input type="checkbox" :value="o.option_code" v-model="multi[q.name]" />
							{{ o.option_label }}
						</label>
					</div>

					<input v-else-if="['Numeric', 'Rating'].includes(q.item_type)" type="number"
						class="mt-2 w-32 rounded border border-outline-gray-2 px-2 py-1 text-sm"
						:min="q.min_value" :max="q.max_value" v-model="answers[q.name]" />

					<textarea v-else rows="3" v-model="answers[q.name]"
						class="mt-2 w-full rounded border border-outline-gray-2 px-2 py-1 text-sm" />
				</div>
			</div>

			<div v-if="error" class="mt-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
				{{ error }}
			</div>

			<div class="mt-6 flex items-center gap-3">
				<Button variant="solid" :loading="submit.loading" :label="__('Submit')" @click="send" />
				<span class="text-xs text-ink-gray-5">
					{{ __('You can only submit once, and answers cannot be changed afterwards.') }}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, createResource } from 'frappe-ui'

const props = defineProps({
	courseName: { type: String, required: true },
})

const router = useRouter()
const user = inject('$user')
const hasAretenic = computed(() => !!user?.data?.has_aretenic)

const answers = reactive({})
const multi = reactive({})
const submitted = ref(false)
const error = ref('')

const questionnaire = createResource({
	url: 'aretenic.feedback_api.get_course_questionnaire',
	makeParams: () => ({ course_schedule: props.courseName }),
	onError: () => {},
})

const data = computed(() => questionnaire.data || {})
const isOpen = computed(() => !!data.value.open)
const answered = computed(() => !!data.value.answered)

const submit = createResource({
	url: 'aretenic.feedback_api.submit_questionnaire',
	onSuccess: () => {
		submitted.value = true
	},
	onError: (e) => {
		error.value = e?.messages?.[0] || __('Sorry — that could not be submitted.')
	},
})

function collect() {
	const out = []
	for (const block of data.value.blocks || []) {
		for (const q of block.questions) {
			let value =
				q.item_type === 'Multi Choice' ? multi[q.name] || [] : answers[q.name]
			if (value === '' || value === undefined || (Array.isArray(value) && !value.length)) {
				value = null
			}
			out.push({ question: q.name, value, required: q.is_required, prompt: q.prompt })
		}
	}
	return out
}

function send() {
	error.value = ''
	const collected = collect()
	const missing = collected.filter((a) => a.required && a.value === null)
	if (missing.length) {
		error.value = __('Please answer every required question ({0} remaining).', [missing.length])
		return
	}
	submit.submit({
		campaign: data.value.campaign,
		answers: JSON.stringify(collected.map((a) => ({ question: a.question, value: a.value }))),
	})
}

watch(
	() => [hasAretenic.value, props.courseName],
	([enabled, schedule]) => {
		if (enabled && schedule) questionnaire.reload()
	},
	{ immediate: true }
)
</script>
