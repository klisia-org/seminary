<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
	</PageHeader>
	<div class="md:w-7/12 md:mx-auto mx-4 py-10">
		<Quiz :quizName="quizID" />
	</div>
</template>
<script setup>
import PageHeader from '@/components/PageHeader.vue'
import Quiz from '@/components/Quiz.vue'
import { createResource, Breadcrumbs } from 'frappe-ui'
import { computed, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { updateDocumentTitle } from '@/utils'

const user = inject('$user')
const router = useRouter()

onMounted(() => {
	if (!user.data) {
		router.push({ name: 'Courses' })
	}
})

const props = defineProps({
	quizID: {
		type: String,
		required: true,
	},
})

const title = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'Quiz',
		fieldname: 'title',
		filters: {
			name: props.quizID,
		},
	},
	auto: true,
})

const breadcrumbs = computed(() => {
	return [{ label: __('Quiz Submission') }, { label: title.data?.title }]
})

const pageMeta = computed(() => {
	return {
		title: title.data?.title,
		description: __('Quiz Submission'),
	}
})

updateDocumentTitle(pageMeta)
</script>
