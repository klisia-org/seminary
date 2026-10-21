<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
	</PageHeader>
	<div class="pt-5 pb-10 px-5">
		<Exam :examName="examID" />
	</div>
</template>
<script setup>
import PageHeader from '@/components/PageHeader.vue'
import Exam from '@/components/Exam.vue'
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
	examID: {
		type: String,
		required: true,
	},
})

const title = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'Exam Activity',
		fieldname: 'title',
		filters: {
			name: props.examID,
		},
	},
	auto: true,
})

const breadcrumbs = computed(() => {
	return [{ label: __('Exam Submission') }, { label: title.data?.title }]
})

const pageMeta = computed(() => {
	return {
		title: title.data?.title,
		description: __('Exam Submission'),
	}
})

updateDocumentTitle(pageMeta)
</script>
