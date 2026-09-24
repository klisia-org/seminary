<template>
	<div class="development-plan">
		<PageHeader>
			<template #title>
				<Breadcrumbs class="h-7" :items="breadcrumbs" />
			</template>
			<template #actions>
				<div class="flex items-center gap-2">
					<router-link v-if="planData?.is_cbe"
						:to="mentorMode
							? { name: 'SelfDevelopmentPlans', params: { student: planData.student } }
							: { name: 'SelfDevelopmentPlans' }">
						<Button variant="subtle" size="sm">{{ __('All plans') }}</Button>
					</router-link>
					<Badge v-if="planData?.status" :label="planData.status" :theme="statusThemeOf" />
				</div>
			</template>
		</PageHeader>

		<DevelopmentPlanPanel :course-name="props.courseName"
			:student="route.query.student || null" @loaded="(data) => (planData = data)" />
	</div>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
import DevelopmentPlanPanel from '@/components/DevelopmentPlanPanel.vue'
import { Badge, Breadcrumbs, Button } from 'frappe-ui'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps({
	courseName: { type: String, required: true },
})

const route = useRoute()
const planData = ref(null)

// A mentor reaches the same page with ?student=, which the server honours only
// for staff; the panel makes everything the student wrote read-only then.
const mentorMode = computed(() => !!route.query.student && !!planData.value?.viewer_is_staff)

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{
		label: props.courseName,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{ label: __('Development Plan') },
])

const statusThemeOf = computed(
	() => ({ Draft: 'gray', Submitted: 'blue', Reviewed: 'orange', Accepted: 'green' }[
		planData.value?.status
	] || 'gray')
)
</script>
