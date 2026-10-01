<template>
	<div>
		<PageHeader>
			<template #title>
				<Breadcrumbs class="h-7" :items="[{ label: __('My Formation') }]" />
			</template>
		</PageHeader>
		<div class="px-3 py-4 sm:px-5">
			<div class="max-w-5xl">
				<div class="flex flex-wrap items-end justify-between gap-3">
					<div>
						<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('My Formation') }}</h1>
						<p class="mt-1 text-sm text-ink-gray-6">
							{{ __('For each competency course: where you started, where you finished, and how your instructor and mentors see it.') }}
						</p>
					</div>
					<div class="flex items-end gap-2">
						<FormControl v-if="options.length > 1" type="select" :label="__('Course')"
							:options="options" v-model="course" />
						<router-link :to="{ name: 'SelfDevelopmentPlans' }">
							<Button variant="subtle">{{ __('Formation Journal') }}</Button>
						</router-link>
					</div>
				</div>

				<div v-if="sections.loading" class="flex justify-center py-12">
					<LoadingIndicator class="h-6 w-6" />
				</div>
				<p v-else-if="!options.length" class="mt-6 text-sm text-ink-gray-5">
					{{ __('You are not in any competency-based course yet.') }}
				</p>
				<template v-else-if="course">
					<div class="mt-4 mb-3">
						<router-link class="text-sm text-ink-gray-6 underline"
							:to="{ name: 'CourseDetail', params: { courseName: course }, query: { tab: 'review' } }">
							{{ __('Open this course') }}
						</router-link>
					</div>
					<CompetencyReview :key="course" :courseName="course" />
				</template>
			</div>
		</div>
	</div>
</template>

<script setup>
// The student's own entry to their competency reviews (privatedocs p012
// decision 3). Replaces the profile that sat under Transcripts.
import { Breadcrumbs, Button, FormControl, LoadingIndicator, createResource } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import CompetencyReview from '@/components/CompetencyReview.vue'

const route = useRoute()
const router = useRouter()
const course = ref(route.query.course || null)

const sections = createResource({
	url: 'seminary.seminary.cbe_api.get_my_formation',
	auto: true,
	onSuccess(data) {
		if (!course.value && data?.length) course.value = data[0].course_schedule
	},
})

const options = computed(() =>
	(sections.data || []).map((s) => ({
		label: [s.course, s.academic_term].filter(Boolean).join(' · '),
		value: s.course_schedule,
	}))
)

// Addressable, so a link can open one course's review.
const syncQuery = (value) => router.replace({ query: { ...route.query, course: value } })
watch(course, (v) => v && syncQuery(v))
</script>
