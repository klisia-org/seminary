<template>
	<div class="text-base">
			<div class="grid grid-cols-[70%,30%] mb-4 px-2">
				<div class="font-semibold text-lg leading-5 text-ink-gray-9">
					<!-- {{ (course_title) }} -->
				</div>
				<Button size="sm"  @click="openChapterModal()">
				{{ __('Add Chapter') }}
			</Button>
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
						<div class="flex ml-auto space-x-4">
						<Tooltip :text="__('Edit Chapter')" placement="bottom">
							<FilePenLine
								
								@click.prevent="openChapterModal(chapter)"
								class="h-4 w-4 text-ink-gray-9 invisible group-hover:visible"
							/>
						</Tooltip>
						<Tooltip :text="__('Delete Chapter')" placement="bottom">
							<Trash2
								
								@click.prevent="trashChapter(chapter.name)"
								class="h-4 w-4 text-red-500 invisible group-hover:visible"
								/>
							
						</Tooltip>
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
								<div class="flex flex-col items-start text-sm leading-5 group">
									<div class="flex items-center">
										<MonitorPlay
											v-if="lesson.icon === 'icon-youtube'"
											class="h-4 w-4 stroke-1 mr-2"
										/>
										<HelpCircle
											v-else-if="lesson.icon === 'icon-quiz'"
											class="h-4 w-4 stroke-1 mr-2"
										/>
										<BookOpenCheck
											v-else-if="lesson.icon === 'icon-exam'"
											class="h-4 w-4 stroke-1 mr-2"
										/>
										<FileUp
											v-else-if="lesson.icon === 'icon-assignment'"
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
									<div v-if="lesson.preview" class="rounded-md bg-[#E6F4FF] p-2 w-full mt-2">
										{{ lesson.preview }}
									</div>
									<div v-if="lesson.due_date" class="rounded-md bg-[#E6F7F4] p-2 mt-2">
										{{ __('Due: ') + new Intl.DateTimeFormat(user.data.language || 'en-US', { dateStyle: 'medium' }).format(new Date(lesson.due_date)) }}
									</div>
								</div>
							</router-link>
						</div>
						<div  class="flex mt-2 mb-4 pl-8">
						<router-link
							v-if="!chapter.is_scorm_package"
							:to="{
								name: 'LessonForm',
								params: {
									courseName: courseName,
									chapterNumber: chapter.idx,
									lessonNumber: chapter.lessons.length + 1,
								},
							}"
						>
							<Button>
								{{ __('Add Lesson') }}
							</Button>
						</router-link>
					</div>
					</DisclosurePanel>
				</Disclosure>
			</div>
		</div>
		<ChapterModal
		v-model="showChapterModal"
		v-model:outline="outline"
		:course="courseName"
		:chapterDetail="getCurrentChapter()"
	/>
</template>
<script setup>
import { Button, createResource, Tooltip, Dialog } from 'frappe-ui'
import { getCurrentInstance, inject, ref } from 'vue'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue'
import {
	Check,
	ChevronRight,
	FileText,
	FilePenLine,
	HelpCircle,
	MonitorPlay,
	BookOpenCheck,
	Trash2,
	FileUp,
} from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import ChapterModal from '@/components/Modals/ChapterModal.vue'
import { showToast} from '@/utils'
import { createDialog } from '@/utils/dialogs'

const route = useRoute()
const router = useRouter()
const user = inject('$user')
const showChapterModal = ref(false)
const currentChapter = ref(null)
const app = getCurrentInstance()

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

const course_title = createResource({
	url: 'seminary.seminary.utils.get_course_title',
	cache: ['course_title', props.courseName],
	params: {
		course: props.courseName,
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
	createDialog({
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
	console.log('trashChapter called with:', chapterName); // Add this line for debugging
	createDialog({
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
