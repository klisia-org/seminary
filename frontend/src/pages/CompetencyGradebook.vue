<template>
	<div class="competency-gradebook">
		<PageHeader>
			<template #title>
				<Breadcrumbs class="h-7" :items="breadcrumbs" />
			</template>
			<template v-if="context.data?.is_cbe" #tabs>
				<PageTabs :tabs="tabs" v-model="tab" :label="__('Gradebook views')" />
			</template>
		</PageHeader>

		<div v-if="context.loading" class="flex justify-center py-16">
			<LoadingIndicator class="h-8 w-8" />
		</div>

		<div v-else-if="context.data && !context.data.is_cbe" class="mx-5 my-8 max-w-xl">
			<h1 class="text-xl font-bold text-ink-gray-8">{{ __('Not a competency-based course') }}</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ __('This section is graded numerically. Use the gradebook instead.') }}
			</p>
			<router-link :to="{ name: 'Gradebook', params: { courseName: props.courseName } }">
				<Button variant="solid" class="mt-4">{{ __('Open Gradebook') }}</Button>
			</router-link>
		</div>

		<template v-else-if="context.data">
			<div class="border-b px-3 py-3 sm:px-5">
				<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('Competency Assessment') }}</h1>
				<p class="mt-1 text-sm text-ink-gray-6">{{ props.courseName }}</p>

				<div v-if="isFinalized" class="mt-3 rounded-md bg-surface-blue-1 px-4 py-3 text-sm text-ink-blue-3">
					{{ __('Grades for this course have been sent. This view is read-only.') }}
				</div>

				<!-- Send Selected appears only for open-ended sections (ADR 065 7a);
				     everywhere else grades are sent for the whole class at once. -->
				<div v-if="canSendSelected" class="mt-3 flex flex-wrap items-center gap-2">
					<Button variant="solid" theme="blue" :disabled="!selected.length || sending"
						:loading="sending" @click="sendSelected">
						<template #prefix><Send class="h-4 w-4" /></template>
						{{ __('Send Grades for Selected') }}
						<span v-if="selected.length">&nbsp;({{ selected.length }})</span>
					</Button>
					<span class="text-sm text-ink-gray-6">
						{{ __('This section has no end date, so students can be finalized as they finish. Sending is final for those students.') }}
					</span>
				</div>
			</div>

			<section v-if="tab === 'overview'" class="px-3 py-4 sm:px-5">
				<div v-if="matrix.loading" class="flex justify-center py-12">
					<LoadingIndicator class="h-6 w-6" />
				</div>
				<template v-else-if="matrix.data?.is_cbe">
					<p v-if="!matrix.data.students.length" class="text-sm text-ink-gray-5">
						{{ __('There are no students enrolled in this course.') }}
					</p>
					<p v-else-if="!gradedGroups.length" class="text-sm text-ink-gray-5">
						{{ __('No assessment is mapped to a competency yet. Set that in Configure Assessments.') }}
					</p>
					<div v-else class="overflow-x-auto">
						<table class="min-w-full border-collapse text-sm">
							<thead>
								<tr>
									<th rowspan="3"
										class="sticky left-0 z-10 border border-outline-gray-2 bg-surface-gray-2 px-3 py-2 text-left">
										{{ __('Student') }}
									</th>
									<th v-for="g in gradedGroups" :key="g.course_competency" :colspan="g.span"
										class="border border-outline-gray-2 bg-surface-gray-2 px-3 py-2">
										{{ g.competency_name }}
									</th>
								</tr>
								<tr>
									<template v-for="g in gradedGroups" :key="g.course_competency">
										<th v-for="a in g.assessments" :key="a.name" :colspan="a.leaves.length"
											class="border border-outline-gray-2 bg-surface-gray-1 px-3 py-1 text-xs font-medium">
											{{ a.title }}
										</th>
									</template>
								</tr>
								<tr>
									<template v-for="g in gradedGroups" :key="g.course_competency">
										<template v-for="a in g.assessments" :key="a.name">
											<th v-for="leaf in a.leaves" :key="leaf.key"
												class="border border-outline-gray-2 bg-surface-gray-1 px-2 py-1 text-xs font-normal text-ink-gray-6">
												<div v-if="leaf.instructor_category">{{ leaf.instructor_category }}</div>
												<div>{{ leaf.label }}</div>
											</th>
										</template>
									</template>
								</tr>
							</thead>
							<tbody>
								<tr v-for="s in matrix.data.students" :key="s.roster"
									class="hover:bg-surface-gray-1">
									<th
										class="sticky left-0 z-10 border border-outline-gray-2 bg-surface-white px-3 py-2 text-left font-medium">
										<div class="flex items-center gap-1.5">
											<button class="truncate text-left hover:underline"
												@click="openStudent(s.roster)">
												{{ s.student_name }}
											</button>
											<!-- The faculty mentor arbitrates a grade someone else
											     recorded, so the person to ask is named here. -->
											<Tooltip v-if="s.mentors.length" :text="mentorText(s)">
												<UserRound class="h-3.5 w-3.5 shrink-0 text-ink-gray-5" />
											</Tooltip>
										</div>
									</th>
									<template v-for="g in gradedGroups" :key="g.course_competency">
										<template v-for="a in g.assessments" :key="a.name">
											<td v-for="leaf in a.leaves" :key="leaf.key"
												class="border border-outline-gray-2 px-2 py-2 text-center">
												<Tooltip v-if="s.cells[leaf.key]" :text="s.cells[leaf.key].instructor">
													<span class="text-ink-gray-9">{{ s.cells[leaf.key].level_code }}</span>
												</Tooltip>
												<span v-else class="text-ink-gray-4">—</span>
											</td>
										</template>
									</template>
								</tr>
							</tbody>
						</table>

						<!-- The verdicts the framework's arbiters give, below the
						     evidence they were formed from. -->
						<h3 class="mt-8 text-sm font-semibold uppercase tracking-wide text-ink-gray-6">
							{{ __('Competency verdicts') }}
						</h3>
						<p class="mb-2 text-xs text-ink-gray-5">
							{{ verdictBy }}
						</p>
						<table class="min-w-full border-collapse text-sm">
							<thead>
								<tr>
									<th
										class="sticky left-0 z-10 border border-outline-gray-2 bg-surface-gray-2 px-3 py-2 text-left">
										{{ __('Student') }}
									</th>
									<th v-for="g in matrix.data.groups" :key="g.course_competency"
										class="border border-outline-gray-2 bg-surface-gray-2 px-3 py-2">
										{{ g.competency_name }}
									</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="s in matrix.data.students" :key="s.roster">
									<th
										class="sticky left-0 z-10 border border-outline-gray-2 bg-surface-white px-3 py-2 text-left font-medium">
										{{ s.student_name }}
									</th>
									<td v-for="g in matrix.data.groups" :key="g.course_competency"
										class="border border-outline-gray-2 px-3 py-2 text-center">
										<Badge v-if="s.verdicts[g.course_competency]?.final_code"
											:label="s.verdicts[g.course_competency].final_code"
											:theme="s.verdicts[g.course_competency].status === 'Competent' ? 'green' : 'orange'" />
										<span v-else class="text-ink-gray-4">—</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</template>
			</section>

			<CompetencyStudentPane v-show="tab === 'student'" ref="pane" padded
				:courseName="props.courseName" :context="context.data"
				:selectable="canSendSelected" v-model:selected="selected"
				:initialRoster="route.query.roster || null" @graded="matrix.reload()" />
		</template>

		<AbsenceDecisionModal ref="absenceDecisions" />
	</div>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
import AbsenceDecisionModal from '@/components/Modals/AbsenceDecisionModal.vue'
import PageTabs from '@/components/PageTabs.vue'
import CompetencyStudentPane from '@/components/CompetencyStudentPane.vue'
import { useTabParam } from '@/composables/useTabParam'
import {
	Badge, Breadcrumbs, Button, LoadingIndicator, Tooltip,
	createResource, call, toast,
} from 'frappe-ui'
import { computed, inject, ref, watch } from 'vue'
import { Send, UserRound } from 'lucide-vue-next'
import { useRoute } from 'vue-router'

const user = inject('$user')
const props = defineProps({
	courseName: { type: String, required: true },
})

const route = useRoute()
const selected = ref([])
const sending = ref(false)
// The "By student" view (shared with the course page's Competency Review tab).
const pane = ref(null)

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{
		label: props.courseName,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{ label: __('Competency Assessment') },
])

const context = createResource({
	url: 'seminary.seminary.cbe_api.get_competency_context',
	makeParams: () => ({ course_schedule: props.courseName }),
	auto: true,
})

const matrix = createResource({
	url: 'seminary.seminary.cbe_api.get_cbe_gradebook',
	makeParams: () => ({ course_schedule: props.courseName }),
	onError: () => {},
})

watch(
	() => context.data?.is_cbe,
	(isCbe) => {
		if (isCbe) matrix.reload()
	},
	{ immediate: true }
)

// Two ways into the same section: the whole class at a glance, and one student
// in full (ADR 065 11d). Addressable, so a link can open either (ADR 075).
const tabs = computed(() => [
	{ key: 'overview', label: __('Overview') },
	{ key: 'student', label: __('By student') },
])
const tab = useTabParam(['overview', 'student'], 'overview')

// A competency nothing is assessed under would render as an empty column group
// with a zero colspan, which browsers collapse into a broken header.
const gradedGroups = computed(() =>
	(matrix.data?.groups || []).filter((g) => g.span > 0)
)

const verdictBy = computed(() => {
	const cats = matrix.data?.verdict_categories || []
	return cats.length
		? __('Given by: {0}').format(cats.join(', '))
		: __('No evaluator category in this framework gives a competency verdict.')
})

const mentorText = (student) =>
	student.mentors
		.map((m) => `${m.instructor_category}: ${m.instructor_name}`)
		.join('\n')

const openStudent = (name) => {
	tab.value = 'student'
	pane.value?.select(name)
}

const isFinalized = computed(() =>
	['Closed', 'Cancelled'].includes(context.data?.workflow_state)
)

const canSendSelected = computed(
	() =>
		context.data?.open_ended &&
		context.data?.workflow_state === 'Grading' &&
		context.data?.viewer?.access === 'instructor' &&
		(user?.data?.is_moderator || user?.data?.is_instructor || user?.data?.is_evaluator)
)

// --- send selected --------------------------------------------------------
// Students over the absence limit need a decision before grades go (ADR 081).
const absenceDecisions = ref(null)

const sendSelected = async () => {
	const names = (pane.value?.roster?.data || [])
		.filter((r) => selected.value.includes(r.name))
		.map((r) => r.stuname_roster)
	const message = __(
		'Send grades for {0}? This writes their transcript and cannot be undone. The section stays open for everyone else.'
	).format(names.join(', '))
	if (!window.confirm(message)) return

	sending.value = true
	try {
		if (!(await absenceDecisions.value.ask(props.courseName, selected.value))) return
		const res = await call('seminary.seminary.api.send_selected_grades', {
			course_schedule: props.courseName,
			rosters: JSON.stringify(selected.value),
		})
		toast.success(__('Grades sent for {0} student(s)').format(res.finalized))
		selected.value = []
		pane.value?.reload()
	} catch (e) {
		toast.error(errorMessage(e, __('Could not send grades.')))
	} finally {
		sending.value = false
	}
}

function errorMessage(e, fallback) {
	if (Array.isArray(e?.messages) && e.messages.length) return e.messages.join('\n')
	const m = (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()
	return m || fallback
}
</script>
