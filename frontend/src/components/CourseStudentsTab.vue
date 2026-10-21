<template>
	<div>
		<div class="mb-4">
			<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('Students') }}</h1>
			<p class="mt-1 text-sm text-ink-gray-6">
				{{ __('Who is waiting on you, who has gone quiet, and who may need help to pass.') }}
			</p>
		</div>

		<!-- Interaction summary, when the school's quality app supplies one. -->
		<div v-if="summary" class="mb-4 rounded-lg border bg-surface-gray-1 p-3">
			<div class="flex flex-wrap gap-2">
				<div v-for="(item, i) in summary.items || []" :key="i"
					class="rounded border px-2 py-1 text-sm"
					:class="item.flagged
						? 'border-outline-amber-2 bg-surface-amber-1 text-ink-amber-3'
						: 'bg-surface-white text-ink-gray-7'">
					<span :class="item.flagged ? 'text-ink-amber-3' : 'text-ink-gray-5'">{{ item.label }}:</span>
					<span class="ml-1 font-medium">{{ item.value }}</span>
				</div>
			</div>
			<div v-for="(flag, i) in summary.flags || []" :key="'f' + i"
				class="mt-2 flex items-start gap-2 text-sm text-ink-amber-3">
				<AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
				<span>{{ flag }}</span>
			</div>
			<p v-if="summary.computed_on" class="mt-2 text-xs text-ink-gray-5">
				{{ summary.frozen
					? __('Final, as of {0}.').format(formatDate(summary.computed_on))
					: __('Updated {0}.').format(formatDate(summary.computed_on)) }}
			</p>
		</div>

		<div v-if="students.loading && !students.data" class="text-sm text-ink-gray-5">
			{{ __('Loading…') }}
		</div>
		<div v-else-if="students.error" class="text-sm text-ink-red-4">
			{{ __('The student list could not be loaded.') }}
		</div>
		<div v-else-if="!rows.length" class="text-sm text-ink-gray-5">
			{{ __('No active students in this course.') }}
		</div>
		<div v-else class="overflow-x-auto rounded-lg border">
			<table class="min-w-full border-collapse text-sm">
				<thead>
					<tr class="bg-surface-gray-2 text-left">
						<th class="px-3 py-2 font-medium">{{ __('Student') }}</th>
						<th class="px-3 py-2 font-medium">{{ __('Waiting for feedback') }}</th>
						<th class="px-3 py-2 font-medium">{{ __('Last activity') }}</th>
						<th v-if="showRisk" class="px-3 py-2 font-medium">{{ __('At risk of failing') }}</th>
						<th class="px-3 py-2 font-medium">{{ __('Attendance') }}</th>
						<template v-if="hasInteraction">
							<th class="px-3 py-2 font-medium">{{ __('Last instructor interaction') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Messages waiting') }}</th>
						</template>
					</tr>
				</thead>
				<tbody>
					<tr v-for="s in rows" :key="s.roster" class="border-t align-top">
						<td class="px-3 py-2 text-ink-gray-8">
							{{ s.student_name }}
							<span v-if="s.auditing" class="ml-1 text-xs text-ink-gray-5">({{ __('auditing') }})</span>
						</td>
						<td class="px-3 py-2">
							<template v-if="s.waiting">
								<span class="font-medium text-ink-gray-8">{{ s.waiting }}</span>
								<span class="ml-1 text-xs text-ink-gray-5">
									{{ __('oldest {0} days').format(s.oldest_waiting_days) }}
								</span>
							</template>
							<span v-else class="text-ink-gray-4">—</span>
						</td>
						<td class="px-3 py-2">
							<template v-if="s.last_activity">
								<span class="text-ink-gray-8">{{ formatDate(s.last_activity) }}</span>
								<span class="ml-1 text-xs text-ink-gray-5">
									{{ daysAgo(s.days_since_activity) }}
								</span>
							</template>
							<span v-else class="text-ink-gray-4">{{ __('None yet') }}</span>
						</td>
						<td v-if="showRisk" class="px-3 py-2">
							<Badge v-if="s.at_risk" theme="red" variant="subtle"
								:label="__('At risk ({0})').format(s.projected_grade?.grade || '—')" />
							<span v-else-if="s.at_risk === false" class="text-ink-gray-6">
								{{ __('On track ({0})').format(s.projected_grade?.grade || '—') }}
							</span>
							<span v-else class="text-ink-gray-4">—</span>
						</td>
						<td class="px-3 py-2">
							<Badge v-if="s.attendance_alert_level >= 2" theme="red" variant="subtle"
								:label="__('Over the absence limit')" />
							<Badge v-else-if="s.attendance_alert_level === 1" theme="orange" variant="subtle"
								:label="__('Near the absence limit')" />
							<span v-else class="text-ink-gray-4">—</span>
						</td>
						<template v-if="hasInteraction">
							<td class="px-3 py-2">
								<span v-if="s.last_instructor_interaction" class="text-ink-gray-8">
									{{ formatDate(s.last_instructor_interaction) }}
								</span>
								<span v-else class="text-ink-gray-4">{{ __('None yet') }}</span>
							</td>
							<td class="px-3 py-2">
								<span v-if="s.messages_waiting" class="font-medium text-ink-amber-3">{{ s.messages_waiting }}</span>
								<span v-else class="text-ink-gray-4">—</span>
							</td>
						</template>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup>
// The Students tab on a course page, for its instructors (privatedocs p015 §4).
import { computed } from 'vue'
import { createResource, Badge } from 'frappe-ui'
import { AlertTriangle } from 'lucide-vue-next'
import { formatDate } from '@/utils'

const props = defineProps({
	courseName: { type: String, required: true },
})

const students = createResource({
	url: 'seminary.seminary.course_students.get_course_students',
	makeParams: () => ({ course_schedule: props.courseName }),
	auto: true,
	onError: () => {},
})

const rows = computed(() => students.data?.students || [])
// Competency sections have no projected grade, so the column is left out.
const showRisk = computed(() => students.data && !students.data.is_cbe)
const summary = computed(() => students.data?.interaction?.summary || null)
// The two interaction columns appear only when the quality app answered.
const hasInteraction = computed(() => !!students.data?.interaction)

const daysAgo = (days) => {
	if (days == null) return ''
	if (days <= 0) return __('today')
	if (days === 1) return __('yesterday')
	return __('{0} days ago').format(days)
}
</script>
