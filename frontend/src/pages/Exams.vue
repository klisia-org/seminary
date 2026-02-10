<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<router-link
			:to="{
				name: 'ExamForm',
				params: {
					examID: 'new',
				},
			}"
		>
			<Button variant="solid">
				<template #prefix>
					<Plus class="w-4 h-4" />
				</template>
				{{ __('New Exam') }}
			</Button>
		</router-link>
	</header>
	<div v-if="exams.data?.length" class="md:w-3/4 md:mx-auto py-5 mx-5">
		<ListView
			:columns="examColumns"
			:rows="exams.data"
			row-key="name"
			:options="{ showTooltip: false, selectable: false }"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in examColumns">
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<router-link
					v-for="row in exams.data"
					:to="{
						name: 'ExamForm',
						params: {
							examID: row.name,
						},
					}"
				>
					<ListRow :row="row" />
				</router-link>
			</ListRows>
		</ListView>
		<div class="flex justify-center my-5">
			<Button v-if="exams.hasNextPage" @click="exams.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<div
		v-else
		class="text-center p-5 text-ink-gray-5 mt-52 w-3/4 md:w-1/2 mx-auto space-y-2"
	>
		<BookOpen class="size-10 mx-auto stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">
			{{ __('No exams found') }}
		</div>
		<div class="leading-5">
			{{
				__(
					'You have not created any exams yet. To create a new exam, click on the "New Exam" button above.'
				)
			}}
		</div>
	</div>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	createListResource,
	ListView,
	ListRows,
	ListRow,
	ListHeader,
	ListHeaderItem
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { computed, inject, onMounted } from 'vue'
import { BookOpen, Plus } from 'lucide-vue-next'
import { updateDocumentTitle } from '@/utils'

const user = inject('$user')
const router = useRouter()

onMounted(() => {
	if (!user.data?.is_moderator && !user.data?.is_instructor) {
		router.push({ name: 'Courses' })
	}
})

const examFilter = computed(() => {
	if (user.data?.is_moderator) return {}
	return {
		owner: user.data?.name,
	}
})

const exams = createListResource({
	doctype: 'Exam Activity',
	filters: examFilter,
	fields: ['name', 'title', 'total_points'],
	auto: true,
	cache: ['exams', user.data?.name],
	orderBy: 'modified desc',
})

const examColumns = computed(() => {
	return [
		{
			label: __('Title'),
			key: 'title',
			width: 2,
		},
		{
			label: __('Total Points'),
			key: 'total_points',
			width: 1,
			align: 'center',
		},

	]
})

const breadcrumbs = computed(() => {
	return [
		{
			label: __('Exams'),
			route: {
				name: 'Exams',
			},
		},
	]
})

const pageMeta = computed(() => {
	return {
		title: __('Exams'),
		description: __('List of exams'),
	}
})

updateDocumentTitle(pageMeta)
</script>
