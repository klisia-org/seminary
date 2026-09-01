<template>
	<div class="development-arc">
		<header
			class="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 border-b bg-surface-white px-3 py-2.5 sm:px-5">
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<FormControl v-if="mentees.data?.length" type="select" :options="menteeOptions"
				v-model="selected" class="min-w-[14rem]" />
		</header>

		<div v-if="arc.loading" class="flex justify-center py-16">
			<LoadingIndicator class="h-8 w-8" />
		</div>

		<div v-else-if="!arc.data" class="mx-5 my-8 max-w-xl">
			<h1 class="text-xl font-bold text-ink-gray-8">{{ __('Nothing here yet') }}</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ mentees.data?.length
					? __('Choose one of your students above.')
					: __('This page collects development plans from competency-based courses.') }}
			</p>
		</div>

		<div v-else class="px-3 py-4 sm:px-5">
			<h1 class="text-2xl font-bold text-ink-gray-9">
				{{ isOwner ? __('My Formation Journal') : (arc.data.student_name || arc.data.student) }}
			</h1>
			<p class="mt-1 max-w-2xl text-sm text-ink-gray-6">
				{{ isOwner
					? __('Every plan you have written, read together. Nothing here is carried between courses — this is the arc, not a ledger.')
					: __('Their plans and notes across every course. You read here; you respond on the plan itself.') }}
			</p>

			<div class="mt-5 flex flex-wrap gap-2">
				<Button v-for="t in tabs" :key="t.value" size="sm"
					:variant="tab === t.value ? 'solid' : 'subtle'" @click="tab = t.value">
					{{ t.label }}
				</Button>
			</div>

			<!-- By question: the same prompt, answered across the years -->
			<div v-if="tab === 'question'" class="mt-5 space-y-6">
				<p v-if="!arc.data.by_question.length" class="text-sm text-ink-gray-5">
					{{ __('No answers to the school’s standard questions yet.') }}
				</p>
				<section v-for="q in arc.data.by_question" :key="q.question_key">
					<div class="prose-sm font-semibold text-ink-gray-8" v-html="q.question_text" />
					<ol class="mt-2 space-y-3 border-l border-outline-gray-2 pl-4">
						<li v-for="(a, i) in q.answers" :key="i">
							<div class="text-xs text-ink-gray-5">
								{{ a.course_name }}
								<span v-if="a.start_date"> · {{ formatDate(a.start_date) }}</span>
								<Badge class="ml-1" :label="a.status" :theme="goalTheme(a.status)" />
							</div>
							<div class="prose-sm mt-1 text-ink-gray-7" v-html="a.goal" />
						</li>
					</ol>
				</section>
			</div>

			<!-- By competency and dimension, cutting across courses -->
			<div v-else-if="tab === 'competency'" class="mt-5 space-y-6">
				<p v-if="!arc.data.by_competency.length" class="text-sm text-ink-gray-5">
					{{ __('No goals have been anchored to a competency yet.') }}
				</p>
				<section v-for="(c, i) in arc.data.by_competency" :key="i">
					<h2 class="font-semibold text-ink-gray-8">
						{{ c.competency_name }}
						<span v-if="c.dimension_code" class="text-ink-gray-5">· {{ c.dimension_code }}</span>
					</h2>
					<ol class="mt-2 space-y-3 border-l border-outline-gray-2 pl-4">
						<li v-for="(g, j) in c.goals" :key="j">
							<div class="text-xs text-ink-gray-5">
								{{ g.course_name }}
								<Badge class="ml-1" :label="g.status" :theme="goalTheme(g.status)" />
							</div>
							<div class="prose-sm mt-1 text-ink-gray-7" v-html="g.goal" />
						</li>
					</ol>
				</section>
			</div>

			<!-- By course: the plans as they were written -->
			<div v-else-if="tab === 'course'" class="mt-5 space-y-5">
				<p v-if="!arc.data.courses.length" class="text-sm text-ink-gray-5">
					{{ __('No development plans yet.') }}
				</p>
				<section v-for="p in arc.data.courses" :key="p.name"
					class="rounded-md border border-outline-gray-2 px-4 py-4">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<h2 class="font-semibold text-ink-gray-8">{{ p.course_name }}</h2>
						<Badge :label="p.status" :theme="planTheme(p.status)" />
					</div>
					<div v-if="p.reflection" class="prose-sm mt-2 text-ink-gray-6"
						v-html="p.reflection" />
					<ul class="mt-3 space-y-2">
						<li v-for="(g, i) in p.goals" :key="i" class="text-sm">
							<div class="prose-sm text-ink-gray-7" v-html="g.goal" />
							<div class="mt-0.5 text-xs text-ink-gray-5">
								<span v-if="g.question_text" class="mr-2">{{ stripHtml(g.question_text) }}</span>
								<Badge :label="g.status" :theme="goalTheme(g.status)" />
							</div>
						</li>
					</ul>
					<div v-if="p.mentor_feedback"
						class="mt-3 rounded-md bg-surface-gray-1 px-3 py-2">
						<div class="text-xs font-medium text-ink-gray-6">{{ __('Mentor') }}</div>
						<div class="prose-sm text-ink-gray-6" v-html="p.mentor_feedback" />
					</div>
				</section>
			</div>

			<!-- Journal -->
			<div v-else class="mt-5">
				<div v-if="isOwner" class="rounded-md border border-outline-gray-2 px-4 py-4">
					<FormControl type="textarea" :rows="4" v-model="draft"
						:label="__('Write a note')" />
					<div class="mt-3 grid gap-3 sm:grid-cols-2">
						<FormControl type="select" :label="__('About a competency (optional)')"
							:options="competencyOptions" v-model="anchorCompetency" />
						<FormControl type="select" :label="__('Course (optional)')"
							:options="courseOptions" v-model="anchorCourse" />
					</div>
					<!-- Said here, where the decision to write is made, rather than
					     in a settings page the student will never open. -->
					<p class="mt-3 text-sm text-ink-gray-5">
						{{ __('Your mentors can read your notes. That is the point of having one — accountability, not surveillance. Anyone who stops mentoring you loses access.') }}
					</p>
					<div class="mt-3">
						<Button variant="solid" :loading="saving" :disabled="!draft.trim()"
							@click="saveNote">
							{{ __('Save Note') }}
						</Button>
					</div>
				</div>

				<p v-if="!arc.data.notes.length" class="mt-4 text-sm text-ink-gray-5">
					{{ __('No notes yet.') }}
				</p>
				<ol v-else class="mt-4 space-y-3">
					<li v-for="n in arc.data.notes" :key="n.name"
						class="rounded-md border border-outline-gray-2 px-4 py-3">
						<div class="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-gray-5">
							<span>
								{{ formatDate(n.note_date) }}
								<span v-if="n.competency_name"> · {{ n.competency_name }}</span>
								<span v-if="n.course_name"> · {{ n.course_name }}</span>
							</span>
							<Button v-if="isOwner" size="sm" variant="ghost" theme="red"
								@click="removeNote(n)">
								{{ __('Delete') }}
							</Button>
						</div>
						<div class="prose-sm mt-1 text-ink-gray-7" v-html="n.note" />
					</li>
				</ol>
			</div>
		</div>
	</div>
</template>

<script setup>
import {
	Badge, Breadcrumbs, Button, FormControl, LoadingIndicator, call, createResource, toast,
} from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { formatDate } from '@/utils'

const props = defineProps({
	student: { type: String, default: null },
})

const tab = ref('question')
const selected = ref(props.student || '')
const draft = ref('')
const anchorCompetency = ref('')
const anchorCourse = ref('')
const saving = ref(false)

const tabs = [
	{ label: __('By question'), value: 'question' },
	{ label: __('By competency'), value: 'competency' },
	{ label: __('By course'), value: 'course' },
	{ label: __('Journal'), value: 'journal' },
]

const breadcrumbs = computed(() => [
	{ label: __('Development Plans') },
])

// Only populated for a mentor; a student gets an empty list and no selector.
const mentees = createResource({
	url: 'seminary.seminary.cbe_api.get_mentees',
	auto: true,
	onError: () => {},
})

const menteeOptions = computed(() =>
	(mentees.data || []).map((m) => ({
		label: m.student_name || m.student,
		value: m.student,
	}))
)

const arc = createResource({
	url: 'seminary.seminary.cbe_api.get_development_arc',
	makeParams: () => ({ student: selected.value || undefined }),
	auto: true,
	onError: () => {},
})

watch(selected, () => arc.reload())

// A mentor viewing a student is not the owner; the composer and the delete
// buttons key off this rather than off which route was used.
const isOwner = computed(() => !!arc.data?.viewer_is_owner)

const courseOptions = computed(() => [
	{ label: '—', value: '' },
	...(arc.data?.courses || []).map((c) => ({
		label: c.course_name,
		value: c.course_schedule,
	})),
])

const competencyOptions = computed(() => [
	{ label: '—', value: '' },
	...Object.entries(arc.data?.competency_names || {}).map(([value, label]) => ({
		label,
		value,
	})),
])

const goalTheme = (s) =>
	({ Planned: 'gray', 'In Progress': 'blue', Achieved: 'green' }[s] || 'gray')

const planTheme = (s) =>
	({ Draft: 'gray', Submitted: 'blue', Reviewed: 'orange', Accepted: 'green' }[s]
		|| 'gray')

const stripHtml = (html) => {
	const el = document.createElement('div')
	el.innerHTML = html || ''
	return (el.textContent || '').trim()
}

const errorText = (e) =>
	Array.isArray(e?.messages) && e.messages.length
		? e.messages.join('\n')
		: (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()

const saveNote = async () => {
	saving.value = true
	try {
		await call('seminary.seminary.cbe_api.save_development_note', {
			note: draft.value,
			course_competency: anchorCompetency.value || undefined,
			course_schedule: anchorCourse.value || undefined,
		})
		draft.value = ''
		anchorCompetency.value = ''
		anchorCourse.value = ''
		toast.success(__('Note saved'))
		arc.reload()
	} catch (e) {
		toast.error(errorText(e) || __('Could not save your note.'))
	} finally {
		saving.value = false
	}
}

const removeNote = async (n) => {
	if (!window.confirm(__('Delete this note? It cannot be recovered.'))) return
	try {
		await call('seminary.seminary.cbe_api.delete_development_note', { name: n.name })
		toast.success(__('Note deleted'))
		arc.reload()
	} catch (e) {
		toast.error(errorText(e) || __('Could not delete the note.'))
	}
}
</script>
