<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
	</PageHeader>
	<!-- Groups, topics, peer reviews and teammate ratings of one activity on
	     one section, for its instructors (decisions/120). -->
	<div v-if="m" class="mx-5 space-y-5 py-5 md:mx-auto md:w-11/12">
		<div>
			<h2 class="text-xl font-semibold text-ink-gray-9">{{ m.settings.title }}</h2>
			<p class="text-sm text-ink-gray-5">
				<template v-if="m.row.due_date">{{ __('Due {0}.').format(formatWhen(m.row.due_date)) }}</template>
			</p>
		</div>

		<div class="flex flex-wrap gap-2 border-b pb-2" role="tablist">
			<Button v-for="t in tabs" :key="t.key" :variant="tab === t.key ? 'solid' : 'ghost'" role="tab"
				:aria-selected="tab === t.key" @click="tab = t.key">{{ t.label }}</Button>
		</div>

		<!-- Groups -->
		<section v-if="tab === 'groups'" class="space-y-4">
			<div v-if="m.may_edit" class="flex flex-wrap items-end gap-3 rounded-lg border p-3">
				<FormControl v-model="make.source" type="select" :label="__('Make the groups')" class="w-64" :options="[
					{ label: __('From the section\'s student groups'), value: 'Section groups' },
					{ label: __('At random'), value: 'Random' },
					{ label: __('Empty, for students to sign up'), value: 'Empty' },
				]" />
				<FormControl v-if="make.source === 'Random'" v-model.number="make.size" type="number" min="2"
					:label="__('Group size')" class="w-28" />
				<FormControl v-if="make.source === 'Empty'" v-model.number="make.count" type="number" min="1"
					:label="__('How many groups')" class="w-32" />
				<Button variant="solid" @click="makeGroups">{{ __('Make groups') }}</Button>
				<p class="w-full text-xs text-ink-gray-5">
					{{ __('Replaces the groups that have not handed in work.') }}
				</p>
			</div>

			<div v-if="m.may_edit && (m.settings.group_source === 'Self sign-up' || m.settings.topic_mode === 'Students choose')"
				class="flex flex-wrap items-end gap-3 rounded-lg border p-3">
				<label v-if="m.settings.group_source === 'Self sign-up'" class="text-sm text-ink-gray-7">
					{{ __('Group sign-up closes') }}
					<input v-model="windows.signup" type="datetime-local" class="form-input mt-1 block rounded border-outline-gray-2 text-sm" />
				</label>
				<label v-if="m.settings.topic_mode === 'Students choose'" class="text-sm text-ink-gray-7">
					{{ __('Topic choice closes') }}
					<input v-model="windows.topics" type="datetime-local" class="form-input mt-1 block rounded border-outline-gray-2 text-sm" />
				</label>
				<Button @click="saveWindows">{{ __('Save dates') }}</Button>
			</div>

			<div class="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
				<div v-for="g in m.groups" :key="g.name" class="space-y-2 rounded-lg border p-3">
					<div class="flex items-center gap-2">
						<FormControl v-model="names[g.name]" class="flex-1" :disabled="!m.may_edit" :aria-label="__('Group name')"
							@blur="rename(g)" />
						<Badge v-if="g.has_work" theme="green">{{ __('Handed in') }}</Badge>
					</div>
					<div v-if="g.topic" class="text-xs text-ink-gray-6">{{ __('Topic') }}: {{ topicTitle(g.topic) }}</div>
					<div v-for="s in g.members" :key="s.student" class="flex items-center justify-between gap-2 text-sm">
						<span>{{ s.name }}</span>
						<select v-if="m.may_edit" class="form-select rounded border-outline-gray-2 text-xs"
							:aria-label="__('Move {0}').format(s.name)" :value="g.name"
							@change="move(s.student, $event.target.value)">
							<option v-for="o in m.groups" :key="o.name" :value="o.name">{{ o.group_name }}</option>
							<option value="">{{ __('No group') }}</option>
						</select>
					</div>
					<p v-if="!g.members.length" class="text-xs text-ink-gray-5">{{ __('No members yet.') }}</p>
					<div v-if="m.may_edit" class="flex flex-wrap gap-2 pt-1">
						<Button size="sm" variant="ghost" @click="openExtend(g)">{{ __('Extend for the group') }}</Button>
						<Button v-if="!g.has_work" size="sm" variant="ghost" theme="red" @click="removeGroup(g)">{{ __('Delete') }}</Button>
					</div>
				</div>
			</div>

			<div v-if="m.ungrouped.length" class="rounded-lg border p-3">
				<div class="mb-2 font-medium text-ink-gray-8">{{ __('Not in a group') }}</div>
				<div v-for="s in m.ungrouped" :key="s.student" class="flex items-center justify-between gap-2 text-sm">
					<span>{{ s.name }}</span>
					<select v-if="m.may_edit && m.groups.length" class="form-select rounded border-outline-gray-2 text-xs"
						:aria-label="__('Place {0}').format(s.name)" value="" @change="move(s.student, $event.target.value)">
						<option value="" disabled>{{ __('Place in…') }}</option>
						<option v-for="o in m.groups" :key="o.name" :value="o.name">{{ o.group_name }}</option>
					</select>
				</div>
			</div>

			<div v-if="m.may_edit" class="flex items-end gap-2">
				<FormControl v-model="newGroup" :label="__('New group')" :placeholder="__('Name')" />
				<Button :disabled="!newGroup" @click="addGroup">{{ __('Add') }}</Button>
			</div>
		</section>

		<!-- Topics -->
		<section v-if="tab === 'topics'" class="space-y-4">
			<div class="space-y-2">
				<div v-for="(t, i) in topicRows" :key="t.name || 'new' + i" class="grid gap-2 rounded-lg border p-3 md:grid-cols-[1fr,2fr,6rem,auto]">
					<FormControl v-model="t.title" :label="__('Title')" :disabled="!m.may_edit" />
					<FormControl v-model="t.description" type="textarea" :label="__('Description')" :disabled="!m.may_edit" />
					<FormControl v-model.number="t.capacity" type="number" min="1" :label="__('Places')" :disabled="!m.may_edit" />
					<div class="flex flex-col justify-end text-xs text-ink-gray-6">
						<span v-for="h in t.holders || []" :key="h.name">{{ h.label }}</span>
						<Button v-if="m.may_edit && !(t.holders || []).length" size="sm" variant="ghost" @click="topicRows.splice(i, 1)">
							{{ __('Remove') }}
						</Button>
					</div>
				</div>
			</div>
			<div v-if="m.may_edit" class="flex flex-wrap gap-2">
				<Button @click="topicRows.push({ title: '', description: '', capacity: 1 })">{{ __('Add a topic') }}</Button>
				<Button variant="solid" @click="saveTopics">{{ __('Save topics') }}</Button>
				<Button variant="outline" @click="drawTopics">{{ __('Draw topics at random for the rest') }}</Button>
			</div>

			<div class="rounded-lg border p-3">
				<div class="mb-2 font-medium text-ink-gray-8">
					{{ m.settings.is_group_work ? __('Topics by group') : __('Topics by student') }}
				</div>
				<div v-for="h in holderRows" :key="h.name" class="flex items-center justify-between gap-2 text-sm">
					<span>{{ h.label }}</span>
					<select class="form-select rounded border-outline-gray-2 text-xs" :disabled="!m.may_edit"
						:aria-label="__('Topic for {0}').format(h.label)" :value="h.topic || ''"
						@change="assignTopic(h.name, $event.target.value)">
						<option value="">{{ __('No topic') }}</option>
						<option v-for="t in m.topics" :key="t.name" :value="t.name">{{ t.title }}</option>
					</select>
				</div>
			</div>
		</section>

		<!-- Reviews -->
		<section v-if="tab === 'reviews'" class="space-y-4">
			<div class="flex flex-wrap items-center gap-3 rounded-lg border p-3 text-sm">
				<span v-if="!m.row.review_opened_on">{{ opensNote }}</span>
				<span v-else-if="!m.row.reviews_released_on">
					{{ __('Open since {0}; due {1}.').format(formatWhen(m.row.review_opened_on), formatWhen(m.row.review_due_on)) }}
				</span>
				<span v-else>{{ __('Released {0}.').format(formatWhen(m.row.reviews_released_on)) }}</span>
				<Button v-if="m.may_edit && !m.row.review_opened_on" variant="solid" size="sm" @click="act('open_now')">
					{{ __('Open now') }}
				</Button>
				<Button v-if="m.may_edit && m.row.review_opened_on && !m.row.reviews_released_on" size="sm" @click="act('release_now')">
					{{ __('Release now') }}
				</Button>
			</div>

			<div v-if="m.work.length" class="rounded-lg border p-3">
				<div class="mb-2 font-medium text-ink-gray-8">{{ __('Work handed in') }}</div>
				<div v-for="w in m.work" :key="w.key" class="flex flex-wrap items-center justify-between gap-2 border-b py-1 text-sm last:border-0">
					<span>{{ w.label }}</span>
					<span class="text-xs" :class="w.reviews < m.settings.reviews_per_student ? 'text-ink-amber-3' : 'text-ink-gray-6'">
						{{ __('{0} of {1} reviews').format(w.reviews, m.settings.reviews_per_student) }}
					</span>
					<select v-if="m.may_edit && m.row.review_opened_on && !m.row.reviews_released_on"
						class="form-select rounded border-outline-gray-2 text-xs" :aria-label="__('Add a reviewer for {0}').format(w.label)"
						value="" @change="assignReview(w.key, $event.target.value)">
						<option value="" disabled>{{ __('Add a reviewer…') }}</option>
						<option v-for="s in m.students.filter((x) => !w.authors.includes(x.student))" :key="s.student" :value="s.student">
							{{ s.name }}
						</option>
					</select>
				</div>
			</div>

			<div v-if="m.reviews.length" class="overflow-x-auto rounded-lg border">
				<table class="w-full text-sm">
					<thead class="bg-surface-gray-2 text-left text-xs text-ink-gray-6">
						<tr>
							<th class="p-2">{{ __('Reviewer') }}</th>
							<th class="p-2">{{ __('Work') }}</th>
							<th class="p-2">{{ __('Status') }}</th>
							<th class="p-2"><span class="sr-only">{{ __('Actions') }}</span></th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="r in m.reviews" :key="r.name" class="border-t">
							<td class="p-2">{{ r.reviewer_name }}<span v-if="r.extra" class="ml-1 text-xs text-ink-gray-5">({{ __('extra') }})</span></td>
							<td class="p-2">{{ r.work }}</td>
							<td class="p-2">
								<Badge :theme="r.status === 'Submitted' ? 'green' : 'orange'">{{ r.status === 'Submitted' ? __('Handed in') : __('To do') }}</Badge>
								<Badge v-if="r.hidden" class="ml-1" theme="gray">{{ __('Hidden') }}</Badge>
								<Badge v-if="r.credit_withdrawn" class="ml-1" theme="red">{{ __('No credit') }}</Badge>
							</td>
							<td class="space-x-1 whitespace-nowrap p-2 text-right">
								<router-link v-if="r.status === 'Submitted'" :to="{ name: 'PeerReview', params: { courseName, review: r.name } }">
									<Button size="sm" variant="ghost">{{ __('Read') }}</Button>
								</router-link>
								<template v-if="m.may_edit">
									<Button v-if="r.status === 'Submitted'" size="sm" variant="ghost" @click="moderate(r, { hidden: r.hidden ? 0 : 1 })">
										{{ r.hidden ? __('Show') : __('Hide') }}
									</Button>
									<Button v-if="r.status === 'Submitted'" size="sm" variant="ghost" @click="moderate(r, { credit_withdrawn: r.credit_withdrawn ? 0 : 1 })">
										{{ r.credit_withdrawn ? __('Give credit') : __('Withdraw credit') }}
									</Button>
									<Button v-else size="sm" variant="ghost" theme="red" @click="removeReview(r)">{{ __('Remove') }}</Button>
								</template>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<p v-else class="text-sm text-ink-gray-5">{{ __('No reviews yet.') }}</p>
		</section>

		<!-- Ratings -->
		<section v-if="tab === 'ratings'" class="grid gap-3 md:grid-cols-2">
			<div v-for="g in m.groups" :key="g.name" class="rounded-lg border p-3">
				<div class="mb-2 font-medium text-ink-gray-8">{{ g.group_name }}</div>
				<div v-for="s in g.members" :key="s.student" class="mb-2 text-sm">
					<div class="flex items-center justify-between">
						<span>{{ s.name }}</span>
						<span v-if="g.ratings[s.student]" class="text-ink-gray-7">
							{{ __('{0} of 5 · spread {1} · {2} ratings').format(g.ratings[s.student].average, g.ratings[s.student].spread, g.ratings[s.student].count) }}
						</span>
						<span v-else class="text-xs text-ink-gray-5">{{ __('Not rated yet') }}</span>
					</div>
					<div v-if="g.ratings[s.student]" class="text-xs text-ink-gray-6">
						<span v-for="(v, c) in g.ratings[s.student].by_criterion" :key="c" class="mr-3">{{ c }}: {{ v ?? '–' }}</span>
					</div>
					<div v-for="(c, i) in g.ratings[s.student]?.comments || []" :key="i" class="text-xs text-ink-gray-7">
						“{{ c.comment }}” <span class="text-ink-gray-5">· {{ c.rater }}</span>
					</div>
				</div>
			</div>
		</section>

		<Dialog v-model="extend.open" :options="{ title: __('Extend for the group'), size: 'md' }">
			<template #body-content>
				<div class="space-y-3 text-sm">
					<p class="text-ink-gray-6">{{ __('Every member of {0} gets these dates.').format(extend.group?.group_name || '') }}</p>
					<label class="block">{{ __('Due') }}
						<input v-model="extend.due" type="datetime-local" class="form-input mt-1 block w-full rounded border-outline-gray-2" />
					</label>
					<label class="block">{{ __('Cut-off (optional)') }}
						<input v-model="extend.cutoff" type="datetime-local" class="form-input mt-1 block w-full rounded border-outline-gray-2" />
					</label>
					<FormControl v-model="extend.reason" :label="__('Reason')" />
					<Button variant="solid" :disabled="!extend.due" @click="saveExtend">{{ __('Extend') }}</Button>
				</div>
			</template>
		</Dialog>
	</div>
	<p v-else-if="res.error" class="p-5 text-sm text-ink-gray-5">
		{{ res.error.messages?.[0] || __('This page could not be loaded.') }}
	</p>
</template>
<script setup>
import PageHeader from '@/components/PageHeader.vue'
import { Badge, Breadcrumbs, Button, Dialog, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { computed, reactive, ref, watch } from 'vue'
import { updateDocumentTitle } from '@/utils'

const props = defineProps({
	courseName: { type: String, required: true },
	activityDoctype: { type: String, required: true },
	activity: { type: String, required: true },
})
const base = () => ({ course: props.courseName, activity_doctype: props.activityDoctype, activity: props.activity })

const res = createResource({
	url: 'seminary.seminary.peer_reviews.get_manage',
	makeParams: base,
	auto: true,
})
const m = computed(() => res.data)

const tabs = computed(() => {
	const s = m.value?.settings || {}
	const out = []
	if (s.is_group_work) out.push({ key: 'groups', label: __('Groups') })
	if (s.topic_mode) out.push({ key: 'topics', label: __('Topics') })
	if (s.peer_review) out.push({ key: 'reviews', label: __('Peer reviews') })
	if (s.teammate_ratings && s.is_group_work) out.push({ key: 'ratings', label: __('Teammate ratings') })
	return out
})
const tab = ref('')
watch(tabs, (t) => {
	if (!t.find((x) => x.key === tab.value)) tab.value = t[0]?.key || ''
})

const names = reactive({})
const topicRows = ref([])
const windows = reactive({ signup: '', topics: '' })
const toLocal = (v) => (v ? String(v).replace(' ', 'T').slice(0, 16) : '')
watch(
	m,
	(d) => {
		if (!d) return
		d.groups.forEach((g) => (names[g.name] = g.group_name))
		topicRows.value = d.topics.map((t) => ({ ...t }))
		windows.signup = toLocal(d.row.signup_closes_on)
		windows.topics = toLocal(d.row.topics_close_on)
	},
	{ immediate: true }
)

const make = reactive({ source: 'Random', size: 3, count: 4 })
const newGroup = ref('')
const extend = reactive({ open: false, group: null, due: '', cutoff: '', reason: '' })

const formatWhen = (v) => (v ? new Date(v).toLocaleString(userLocale()) : '')
const topicTitle = (name) => m.value?.topics.find((t) => t.name === name)?.title || ''
const opensNote = computed(() => {
	const s = m.value?.settings || {}
	if (s.review_opens === 'By hand') return __('Reviews open when you open them.')
	if (s.review_opens === 'At the cut-off') return __('Reviews open at the cut-off.')
	return __('Reviews open at the due date.')
})
const holderRows = computed(() => {
	const d = m.value
	if (!d) return []
	const held = {}
	d.topics.forEach((t) => (t.holders || []).forEach((h) => (held[h.name] = t.name)))
	const rows = d.settings.is_group_work
		? d.groups.map((g) => ({ name: g.name, label: g.group_name }))
		: d.students.map((s) => ({ name: s.student, label: s.name }))
	return rows.map((r) => ({ ...r, topic: held[r.name] }))
})

const run = async (method, extra = {}, ok = null) => {
	try {
		const out = await call(`seminary.seminary.peer_reviews.${method}`, extra)
		if (ok) toast.success(ok)
		await res.reload()
		return out
	} catch (e) {
		toast.error(e.messages?.[0] || __('That did not work.'))
	}
}
const makeGroups = () =>
	run('make_groups', { ...base(), source: make.source, size: make.size, count: make.count }, __('Groups made.'))
const addGroup = async () => {
	await run('save_group', { ...base(), group_name: newGroup.value, students: '[]' }, __('Group added.'))
	newGroup.value = ''
}
const rename = (g) => {
	if (names[g.name] && names[g.name] !== g.group_name)
		run('save_group', { ...base(), group: g.name, group_name: names[g.name], students: JSON.stringify(g.members.map((s) => s.student)) })
}
const move = (student, group) => run('move_member', { ...base(), student, group: group || null })
const removeGroup = (g) => run('delete_group', { group: g.name }, __('Group deleted.'))
const saveWindows = () =>
	run('set_windows', { ...base(), signup_closes_on: windows.signup || null, topics_close_on: windows.topics || null }, __('Dates saved.'))
const saveTopics = () => run('save_topics', { ...base(), topics: JSON.stringify(topicRows.value) }, __('Topics saved.'))
const drawTopics = async () => {
	const out = await run('draw_topics', base())
	if (out) toast.success(__('{0} topics drawn.').format(out.given))
}
const assignTopic = (holder, topic) => run('assign_topic', { ...base(), holder, topic: topic || null })
const act = (method) => run(method, base())
const assignReview = (work, reviewer) => run('assign_review', { ...base(), work, reviewer }, __('Reviewer added.'))
const moderate = (r, change) => run('moderate_review', { review: r.name, ...change })
const removeReview = (r) => run('remove_review', { review: r.name })
const openExtend = (g) => Object.assign(extend, { open: true, group: g, due: '', cutoff: '', reason: '' })
const saveExtend = async () => {
	await run(
		'extend_for_group',
		{ group: extend.group.name, due_date: extend.due, cutoff_date: extend.cutoff || null, reason: extend.reason || null },
		__('Dates extended for the group.')
	)
	extend.open = false
}

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{ label: props.courseName, route: { name: 'CourseDetail', params: { courseName: props.courseName } } },
	{ label: __('Group work and reviews'), route: { name: 'ActivityGroupWork', params: props } },
])
updateDocumentTitle(computed(() => ({ title: __('Group Work and Reviews'), description: m.value?.settings.title || '' })))
</script>
