<template>
	<div class="text-base">
			<div class="grid grid-cols-[70%,30%] mb-4 px-2">
				<div class="font-semibold text-lg leading-5 text-ink-gray-9">
					{{ (course) }}
				</div>
			</div>
			<div
				:class="{
					'border-2 rounded-md py-2 px-2': showOutline && outline.data?.length,
				}"
			>
				<Disclosure
					v-slot="{ open }"
					v-for="(chapter, index) in outline.data"
					:key="chapter.name"
					:defaultOpen="openChapterDetail(chapter.idx)"
				>
					<DisclosureButton ref="" class="flex items-center w-full p-2 group">
						<ChevronRight
							:class="{
								'rotate-90 transform duration-200': open,
								'duration-200': !open,
								hidden: chapter.is_scorm_package,
								open: index == 1,
							}"
							class="h-4 w-4 text-ink-gray-9 stroke-1"
						/>
						<div
							class="text-base text-left text-ink-gray-9 font-medium leading-5 ml-2"
							@click="redirectToChapter(chapter)"
						>
							{{ chapter.chapter_title }}
						</div>
					</DisclosureButton>
					<DisclosurePanel v-if="!chapter.is_scorm_package">
						<div
							v-for="lesson in chapter.lessons"
							:key="lesson.name"
							class="outline-lesson pl-8 py-2 pr-4 text-ink-gray-9"
							:class="isActiveLesson(lesson.number) ? 'bg-surface-selected' : ''"
						>
							<router-link
								:to="{
									name: 'Lesson',
									params: {
										courseName: courseName,
										chapterNumber: lesson.number.split('.')[0],
										lessonNumber: lesson.number.split('.')[1],
									},
								}"
							>
								<div class="flex items-center text-sm leading-5 group">
									<MonitorPlay
										v-if="lesson.icon === 'icon-youtube'"
										class="h-4 w-4 stroke-1 mr-2"
									/>
									<HelpCircle
										v-else-if="lesson.icon === 'icon-quiz'"
										class="h-4 w-4 stroke-1 mr-2"
									/>
									<FileText
										v-else-if="lesson.icon === 'icon-list'"
										class="h-4 w-4 text-ink-gray-9 stroke-1 mr-2"
									/>
									{{ lesson.lesson_title }}
									<Check
										v-if="lesson.is_complete"
										class="h-4 w-4 text-green-700 ml-2"
									/>
								</div>
							</router-link>
						</div>
					</DisclosurePanel>
				</Disclosure>
			</div>
		</div>
</template>
<script setup>
import { Button, createResource, Tooltip } from 'frappe-ui'
import { getCurrentInstance, inject, ref } from 'vue'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue'
import {
	Check,
	ChevronRight,
	FileText,
	FilePenLine,
	HelpCircle,
	MonitorPlay,
	Trash2,
} from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'

import { showToast } from '@/utils'

const route = useRoute()
const router = useRouter()
const user = inject('$user')
const showChapterModal = ref(false)
const currentChapter = ref(null)
const app = getCurrentInstance()
const { $dialog } = app.appContext.config.globalProperties

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
	showOutline: {
		type: Boolean,
		default: false,
	},
	title: {
		type: String,
		default: '',
	},
	allowEdit: {
		type: Boolean,
		default: false,
	},
	getProgress: {
		type: Boolean,
		default: false,
	},
})

const outline = createResource({
	url: 'seminary.seminary.utils.get_course_outline',
	cache: ['course_outline', props.courseName],
	params: {
		course: props.courseName,
		progress: props.getProgress,
	},
	auto: true,
})

const deleteLesson = createResource({
	url: 'seminary.seminary.api.delete_lesson',
	makeParams(values) {
		return {
			lesson: values.lesson,
			chapter: values.chapter,
		}
	},
	onSuccess() {
		outline.reload()
		showToast('Success', 'Lesson deleted successfully', 'check')
	},
})

const updateLessonIndex = createResource({
	url: 'seminary.seminary.api.update_lesson_index',
	makeParams(values) {
		return {
			lesson: values.lesson,
			sourceChapter: values.sourceChapter,
			targetChapter: values.targetChapter,
			idx: values.idx,
		}
	},
	onSuccess() {
		showToast('Success', 'Lesson moved successfully', 'check')
	},
})

const trashLesson = (lessonName, chapterName) => {
	$dialog({
		title: __('Delete this lesson?'),
		message: __(
			'Deleting this lesson will permanently remove it from the course. This action cannot be undone. Are you sure you want to continue?'
		),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(close) {
					deleteLesson.submit({
						lesson: lessonName,
						chapter: chapterName,
					})
					close()
				},
			},
		],
	})
}

const openChapterDetail = (index) => {
	return index == route.params.chapterNumber || index == 1
}

const openChapterModal = (chapter = null) => {
	currentChapter.value = chapter
	showChapterModal.value = true
}

const getCurrentChapter = () => {
	return currentChapter.value
}

const updateOutline = (e) => {
	updateLessonIndex.submit({
		lesson: e.item.__draggable_context.element.name,
		sourceChapter: e.from.dataset.chapter,
		targetChapter: e.to.dataset.chapter,
		idx: e.newIndex,
	})
}

const deleteChapter = createResource({
	url: 'seminary.seminary.api.delete_chapter',
	makeParams(values) {
		return {
			chapter: values.chapter,
		}
	},
	onSuccess() {
		outline.reload()
		showToast('Success', 'Chapter deleted successfully', 'check')
	},
})

const trashChapter = (chapterName) => {
	$dialog({
		title: __('Delete this chapter?'),
		message: __(
			'Deleting this chapter will also delete all its lessons and permanently remove it from the course. This action cannot be undone. Are you sure you want to continue?'
		),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(close) {
					deleteChapter.submit({ chapter: chapterName })
					close()
				},
			},
		],
	})
}

const redirectToChapter = (chapter) => {
	if (!chapter.is_scorm_package) return
	event.preventDefault()
	if (props.allowEdit) return
	if (!user.data) {
		showToast(
			__('You are not enrolled'),
			__('Please enroll for this course to view this lesson'),
			'alert-circle'
		)
		return
	}

	router.push({
		name: 'SCORMChapter',
		params: {
			courseName: props.courseName,
			chapterName: chapter.name,
		},
	})
}

const isActiveLesson = (lessonNumber) => {
	return (
		route.params.chapterNumber == lessonNumber.split('.')[0] &&
		route.params.lessonNumber == lessonNumber.split('.')[1]
	)
}
</script>
