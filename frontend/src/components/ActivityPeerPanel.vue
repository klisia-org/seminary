<template>
	<!-- A student's group, topic, reviews and ratings on one activity
	     (decisions/120). Hidden when the activity uses none of them. -->
	<div v-if="p && shown" class="space-y-4 rounded-lg border p-4 text-left text-sm">
		<!-- Group -->
		<section v-if="p.is_group_work">
			<h3 class="mb-2 font-semibold text-ink-gray-9">{{ __('Your group') }}</h3>
			<div v-if="p.group">
				<div class="font-medium text-ink-gray-8">{{ p.group.group_name }}</div>
				<div class="text-ink-gray-6">{{ p.group.members.map((m) => m.name).join(', ') }}</div>
				<p class="mt-1 text-xs text-ink-gray-5">
					{{ __('Any member hands in the work for the whole group, and everyone sees what was handed in.') }}
				</p>
				<Button v-if="p.may_sign_up" size="sm" variant="ghost" class="mt-1" @click="leave">
					{{ __('Leave this group') }}
				</Button>
			</div>
			<p v-else-if="!p.may_sign_up" class="text-ink-gray-6">
				{{ __('You are not in a group yet. Your instructor will place you.') }}
			</p>
			<div v-if="p.may_sign_up && !p.group" class="space-y-2">
				<p class="text-ink-gray-6">
					{{ p.signup_closes_on
						? __('Join a group or start one by {0}.').format(formatWhen(p.signup_closes_on))
						: __('Join a group or start one.') }}
				</p>
				<div v-for="g in p.groups" :key="g.name" class="flex items-center justify-between gap-2 rounded border p-2">
					<div>
						<div class="font-medium">{{ g.group_name }}</div>
						<div class="text-xs text-ink-gray-5">{{ g.members.join(', ') || __('No one yet') }}</div>
					</div>
					<Button size="sm" :disabled="g.full" @click="join(g.name)">
						{{ g.full ? __('Full') : __('Join') }}
					</Button>
				</div>
				<Button size="sm" variant="solid" @click="start">{{ __('Start a new group') }}</Button>
			</div>
		</section>

		<!-- Topic -->
		<section v-if="p.topic_mode">
			<h3 class="mb-2 font-semibold text-ink-gray-9">{{ p.is_group_work ? __('Your group\'s topic') : __('Your topic') }}</h3>
			<div v-if="p.topic">
				<div class="font-medium text-ink-gray-8">{{ p.topic.title }}</div>
				<div v-if="p.topic.description" class="whitespace-pre-line text-ink-gray-6">{{ p.topic.description }}</div>
			</div>
			<p v-else-if="!p.topics.length" class="text-ink-gray-6">
				{{ p.is_group_work && !p.group && p.topic_mode === 'Students choose'
					? __('Join or start a group, then choose your group\'s topic.')
					: __('No topic yet.') }}
			</p>
			<div v-if="p.topics.length" class="mt-2 space-y-2">
				<p class="text-ink-gray-6">
					{{ p.topics_close_on
						? __('Choose a topic by {0}. You can change it until then.').format(formatWhen(p.topics_close_on))
						: __('Choose a topic. You can change it later.') }}
				</p>
				<div v-for="t in p.topics" :key="t.name" class="flex items-start justify-between gap-2 rounded border p-2"
					:class="t.mine ? 'border-outline-blue-2 bg-surface-blue-1' : ''">
					<div>
						<div class="font-medium">{{ t.title }}</div>
						<div v-if="t.description" class="whitespace-pre-line text-xs text-ink-gray-6">{{ t.description }}</div>
					</div>
					<Button v-if="t.mine" size="sm" variant="ghost" @click="choose(null)">{{ __('Let go') }}</Button>
					<Button v-else size="sm" :disabled="!t.free" @click="choose(t.name)">
						{{ t.free ? __('Choose') : __('Taken') }}
					</Button>
				</div>
			</div>
		</section>

		<!-- Reviews to do -->
		<section v-if="p.peer_review && p.reviews.length">
			<h3 class="mb-2 font-semibold text-ink-gray-9">{{ __('Peer reviews') }}</h3>
			<p v-if="p.dates.review_due_on && !p.dates.reviews_released_on" class="mb-2 text-ink-gray-6">
				{{ __('Due {0}.').format(formatWhen(p.dates.review_due_on)) }}
			</p>
			<div class="space-y-1">
				<router-link v-for="r in p.reviews" :key="r.name"
					:to="{ name: 'PeerReview', params: { courseName: course, review: r.name } }"
					class="flex items-center justify-between rounded border p-2 text-ink-gray-8 hover:bg-surface-gray-2">
					<span>{{ r.label }}<span v-if="r.extra" class="ml-1 text-xs text-ink-gray-5">({{ __('extra') }})</span></span>
					<Badge :theme="r.status === 'Submitted' ? 'green' : 'orange'">
						{{ r.status === 'Submitted' ? __('Handed in') : __('To do') }}
					</Badge>
				</router-link>
			</div>
			<Button v-if="p.may_take_extra" size="sm" variant="outline" class="mt-2" @click="takeExtra">
				{{ __('Review one more') }}
			</Button>
		</section>

		<!-- Teammate ratings -->
		<section v-if="p.ratings && p.ratings.teammates.length">
			<h3 class="mb-1 font-semibold text-ink-gray-9">{{ __('Rate your teammates') }}</h3>
			<p class="mb-2 text-xs text-ink-gray-5">
				{{ ratingsNote }}
			</p>
			<div v-for="m in ratingRows" :key="m.student" class="mb-3 rounded border p-2">
				<div class="mb-1 flex items-center justify-between">
					<span class="font-medium">{{ m.name }}</span>
					<Badge v-if="m.done" theme="green">{{ __('Rated') }}</Badge>
				</div>
				<fieldset v-for="c in p.ratings.criteria" :key="c" class="mb-1 flex flex-wrap items-center gap-2"
					:disabled="!p.ratings.open">
					<legend class="w-48 text-ink-gray-7">{{ c }}</legend>
					<label v-for="n in p.ratings.scale" :key="n" class="flex items-center gap-1">
						<input type="radio" :name="`rate-${m.student}-${c}`" :value="n" v-model="m.scores[c]" />
						<span>{{ n }}</span>
					</label>
				</fieldset>
				<FormControl v-model="m.comment" type="textarea" :disabled="!p.ratings.open"
					:placeholder="__('A comment (optional)')" />
			</div>
			<Button v-if="p.ratings.open" variant="solid" size="sm" :loading="saving" @click="saveRatings">
				{{ __('Save ratings') }}
			</Button>
		</section>

		<!-- What others said -->
		<section v-if="p.received.length">
			<h3 class="mb-2 font-semibold text-ink-gray-9">{{ __('Feedback from classmates') }}</h3>
			<div v-for="r in p.received" :key="r.name" class="mb-2 rounded border p-2">
				<div class="mb-1 text-xs text-ink-gray-5">{{ r.reviewer_name }}</div>
				<div v-if="Object.keys(r.rubric_levels || {}).length" class="mb-1 text-xs text-ink-gray-7">
					<span v-for="(lv, code) in r.rubric_levels" :key="code" class="mr-3">{{ code }}: {{ lv }}</span>
				</div>
				<SafeHtml v-if="r.comments" :html="r.comments" class="prose prose-sm max-w-none" />
				<div v-for="(m, i) in r.moments" :key="i" class="text-xs text-ink-gray-7">
					<span class="font-mono">{{ clock(m.t) }}</span> {{ m.note }}
				</div>
				<a v-if="r.attachment" :href="fileUrl(r.name)" class="text-xs text-ink-blue-3 underline">
					{{ __('Marked-up file') }}
				</a>
			</div>
		</section>
		<section v-if="p.ratings_received && p.ratings_received.count">
			<h3 class="mb-2 font-semibold text-ink-gray-9">{{ __('How your teammates rated you') }}</h3>
			<div class="text-ink-gray-8">
				{{ __('Average {0} of 5, from {1} teammates.').format(p.ratings_received.average, p.ratings_received.count) }}
			</div>
			<div class="text-xs text-ink-gray-6">
				<span v-for="(v, c) in p.ratings_received.by_criterion" :key="c" class="mr-3">{{ c }}: {{ v ?? '–' }}</span>
			</div>
			<div v-for="(c, i) in p.ratings_received.comments" :key="i" class="mt-1 text-ink-gray-7">
				“{{ c.comment }}”<span v-if="c.rater" class="text-xs text-ink-gray-5"> · {{ c.rater }}</span>
			</div>
		</section>

		<p v-if="p.review_share && p.credit !== null && p.credit !== undefined" class="text-xs text-ink-gray-6">
			{{ __('Reviews and ratings done on time: {0}%. They count for {1}% of the grade.').format(p.credit, p.review_share) }}
		</p>
	</div>
</template>
<script setup>
import { Badge, Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import SafeHtml from '@/components/SafeHtml.vue'

const props = defineProps({
	course: { type: String, required: true },
	activityDoctype: { type: String, required: true },
	activity: { type: String, required: true },
})
const emit = defineEmits(['changed'])
const router = useRouter()

const panel = createResource({
	url: 'seminary.seminary.peer_reviews.get_panel',
	makeParams: () => ({ course: props.course, activity_doctype: props.activityDoctype, activity: props.activity }),
	auto: true,
})
const p = computed(() => panel.data)
const shown = computed(
	() => p.value && (p.value.is_group_work || p.value.topic_mode || p.value.peer_review || p.value.teammate_ratings)
)

const ratingRows = ref([])
watch(
	() => p.value?.ratings,
	(r) => {
		ratingRows.value = (r?.teammates || []).map((m) => ({ ...m, scores: { ...(m.scores || {}) } }))
	},
	{ immediate: true }
)
const ratingsNote = computed(() => {
	const shownTo = p.value?.ratings_shown
	if (shownTo === 'Instructor only') return __('Only your instructor sees these ratings.')
	if (shownTo === 'Anonymous') return __('Each teammate sees the ratings they received, without your name.')
	return __('Each teammate sees the ratings they received, with your name. Rate honestly and kindly.')
})

const formatWhen = (v) => (v ? new Date(v).toLocaleString(userLocale()) : '')
const clock = (s) => {
	const t = Math.max(0, Math.floor(Number(s) || 0))
	return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}
const fileUrl = (review) =>
	`/api/method/seminary.seminary.peer_reviews.download?review=${encodeURIComponent(review)}&kind=markup`

const args = () => ({ course: props.course, activity_doctype: props.activityDoctype, activity: props.activity })
const run = async (method, extra = {}, done = null) => {
	try {
		const out = await call(`seminary.seminary.peer_reviews.${method}`, { ...args(), ...extra })
		if (done) toast.success(done)
		await panel.reload()
		emit('changed')
		return out
	} catch (e) {
		toast.error(e.messages?.[0] || __('That did not work.'))
	}
}
const join = (group) => run('join_group', { group }, __('You joined the group.'))
const leave = () => run('leave_group', {}, __('You left the group.'))
const start = () => run('start_group', {}, __('You started a group.'))
const choose = (topic) => run('choose_topic', { topic }, topic ? __('Topic chosen.') : __('Topic let go.'))
const takeExtra = async () => {
	const out = await run('take_extra_review')
	if (out?.review) router.push({ name: 'PeerReview', params: { courseName: props.course, review: out.review } })
}
const saving = ref(false)
const saveRatings = async () => {
	saving.value = true
	try {
		await run(
			'save_ratings',
			{
				ratings: JSON.stringify(
					ratingRows.value.map((m) => ({ student: m.student, scores: m.scores, comment: m.comment }))
				),
			},
			__('Ratings saved.')
		)
	} finally {
		saving.value = false
	}
}
defineExpose({ reload: () => panel.reload() })
</script>
