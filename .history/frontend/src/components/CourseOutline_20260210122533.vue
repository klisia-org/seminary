<template>
	<div class="text-base">
		<div class="grid grid-cols-[70%,30%] mb-4 px-2">
			<div class="font-semibold text-lg leading-5 text-ink-gray-9">
				<!-- {{ (course_title) }} -->
			</div>
			<Button size="sm" @click="openChapterModal()" v-if="props.allowEdit">
				{{ __('Add Chapter') }}
			</Button>
		</div>
		<div :class="{
			'border-2 rounded-md py-2 px-2': showOutline && outline.data?.length,
		}">
			<Disclosure v-slot="{ open }" v-for="(chapter, index) in outline.data" :key="chapter.name"
				:defaultOpen="openChapterDetail(chapter.idx)">
				<DisclosureButton ref="" class="flex w-full items-center p-2 group">
					<ChevronRight :class="{
						'rotate-90 transform duration-200': open,
						'duration-200': !open,
						hidden: chapter.is_scorm_package,
						open: index == 1,
					}" class="h-4 w-4 text-ink-gray-9 stroke-1" />
					<div class="ml-2 text-left text-base font-medium leading-5 text-ink-gray-9"
						@click="redirectToChapter(chapter)">
						{{ chapter.chapter_title }}
					</div>
					<div v-if="props.allowEdit" class="ml-auto flex space-x-4">
						<Tooltip :text="__('Edit Chapter')" placement="bottom">
							<FilePenLine @click.prevent="openChapterModal(chapter)"
								class="h-4 w-4 text-ink-gray-9 invisible group-hover:visible" />
						</Tooltip>
						<Tooltip :text="__('Delete Chapter')" placement="bottom">
							<Trash2 @click.prevent="trashChapter(chapter.name)"
								class="h-4 w-4 text-red-500 invisible group-hover:visible" />
						</Tooltip>
					</div>
				</DisclosureButton>
				<DisclosurePanel v-if="!chapter.is_scorm_package">
					<div v-for="(lesson, lessonIndex) in chapter.lessons" :key="lesson.name" class="lesson-wrapper">
						<div v-if="props.allowEdit"
							class="ml-8 mr-4 h-3 rounded border border-dashed border-outline-gray-3 transition hover:border-outline-gray-4"
							@dragover.prevent="onDragOver($event)" @drop.prevent="onDrop($event, chapter, lessonIndex)">
						</div>
						<div class="group ml-8 mr-4 rounded-lg border border-outline-gray-2 bg-white p-4 transition hover:border-outline-gray-3"
							:class="{
								'bg-surface-selected': isActiveLesson(lesson.number),
								'cursor-grab': props.allowEdit,
							}" :draggable="props.allowEdit" @dragstart="onDragStart($event, chapter, lesson, lessonIndex)"
							@dragend="onDragFinish">
							<div class="flex items-start gap-3">
								<div v-if="props.allowEdit">
									<Tooltip :text="__('Delete Lesson')" placement="bottom">
										<button type="button"
											class="rounded-md p-1 text-red-500 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-50"
											@click.prevent="trashLesson(lesson.name, chapter.name)">
											<Trash2 class="h-4 w-4" />
										</button>
									</Tooltip>
								</div>
								<router-link class="flex-1" :to="{
									name: 'Lesson',
									params: {
										courseName: courseName,
										chapterNumber: lesson.number.split('.')[0],
										lessonNumber: lesson.number.split('.')[1],
									},
								}">
									<div class="flex flex-col items-start gap-2 text-sm leading-5">
										<div class="flex items-center gap-2">
											<MonitorPlay v-if="lesson.icon === 'icon-youtube'"
												class="h-4 w-4 stroke-1" />
											<HelpCircle v-else-if="lesson.icon === 'icon-quiz'"
												class="h-4 w-4 stroke-1" />
											<BookOpenCheck v-else-if="lesson.icon === 'icon-exam'"
												class="h-4 w-4 stroke-1" />
											<FileUp v-else-if="lesson.icon === 'icon-assignment'"
												class="h-4 w-4 stroke-1" />
											<FileText v-else class="h-4 w-4 text-ink-gray-7 stroke-1" />
											<span>{{ lesson.lesson_title }}</span>
											<Check v-if="lesson.is_complete" class="h-4 w-4 text-green-700" />
										</div>
										<div v-if="lesson.preview" class="w-full rounded-md bg-[#E6F4FF] p-2">
											{{ lesson.preview }}
										</div>
										<div v-if="lesson.due_date" class="rounded-md bg-[#E6F7F4] p-2">
											{{ __('Due: ') + new Intl.DateTimeFormat(user.data.language || 'en-US', {
												dateStyle: 'medium'
											}).format(new Date(lesson.due_date)) }}
										</div>
									</div>
								</router-link>
								<div v-if="props.allowEdit" class="ml-auto hidden items-center group-hover:flex">
									<GripVertical class="h-4 w-4 text-ink-gray-5" aria-hidden="true" />
								</div>
							</div>
						</div>
					</div>
					<div v-if="props.allowEdit"
						class="ml-8 mr-4 mt-2 rounded-md border border-dashed border-outline-gray-3 p-3 text-sm text-ink-gray-5 transition hover:border-outline-gray-4 hover:text-ink-gray-7"
						@dragover.prevent="onDragOver($event)"
						@drop.prevent="onDrop($event, chapter, chapter.lessons?.length || 0)">
						<span v-if="chapter.lessons?.length">{{ __('Drop here to move to the end of this chapter')
							}}</span>
						<span v-else>{{ __('Drop a lesson here to start this chapter') }}</span>
					</div>
					<div v-if="props.allowEdit" class="flex mt-2 mb-4 pl-8">
						<router-link v-if="!chapter.is_scorm_package" :to="{
							name: 'LessonForm',
							params: {
								courseName: courseName,
								chapterNumber: chapter.idx,
								lessonNumber: chapter.lessons.length + 1,
							},
						}">
							<Button>
								{{ __('Add Lesson') }}
							</Button>
						</router-link>
					</div>
				</DisclosurePanel>
			</Disclosure>
		</div>
	</div>
	<ChapterModal v-model="showChapterModal" v-model:outline="outline" :course="courseName"
		:chapterDetail="getCurrentChapter()" />
</template>
<script setup>
import { Button, createResource, Tooltip, toast } from 'frappe-ui'
import { inject, ref } from 'vue'
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
	GripVertical,
} from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import ChapterModal from '@/components/Modals/ChapterModal.vue'
import { createDialog } from '@/utils/dialogs'

const route = useRoute()
const router = useRouter()
const user = inject('$user')
const showChapterModal = ref(false)
const currentChapter = ref(null)
const draggedLesson = ref(null); // Use a ref to store the dragged lesson

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
		toast.success(__('Lesson deleted successfully'))
	},
})

const updateLessonIndex = createResource({
	url: 'seminary.seminary.api.update_lesson_index',
	makeParams(values) {
		return {
			lesson: values.lesson,
			source_chapter: values.sourceChapter,
			target_chapter: values.targetChapter,
			idx: parseInt(values.idx, 10),
		}
	},
	onSuccess() {
		outline.reload()
		toast.success(__('Lesson moved successfully'))
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
	if (!props.allowEdit) {
		return
	}
	currentChapter.value = chapter
	showChapterModal.value = true
}

const getCurrentChapter = () => {
	return currentChapter.value
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
		toast.success(__('Chapter deleted successfully'))
	},
})

const trashChapter = (chapterName) => {
	if (!props.allowEdit) {
		return
	}
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
		toast.warning(
			__('You are not enrolled'),
			__('Please enroll for this course to view this lesson')
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

const onDragStart = (event, chapter, lesson, lessonIndex) => {
	if (!props.allowEdit) {
		return
	}
	if (event?.dataTransfer) {
		event.dataTransfer.effectAllowed = 'move'
		event.dataTransfer.setData('text/plain', lesson.name)
	}
	draggedLesson.value = {
		lessonName: lesson.name,
		sourceChapter: chapter.name,
		sourceIndex: lessonIndex,
	}
}

const onDragOver = (event) => {
	if (!props.allowEdit || !draggedLesson.value) {
		return
	}
	if (event?.dataTransfer) {
		event.dataTransfer.dropEffect = 'move'
	}
}

const onDrop = (event, chapter, targetIndex) => {
	if (!props.allowEdit || !draggedLesson.value) {
		return
	}
	event?.preventDefault?.()

	const { lessonName, sourceChapter, sourceIndex } = draggedLesson.value
	const targetChapter = chapter.name

	let insertionIndex = targetIndex

	if (sourceChapter === targetChapter && targetIndex > sourceIndex) {
		insertionIndex = targetIndex - 1
	}

	if (sourceChapter === targetChapter && insertionIndex === sourceIndex) {
		draggedLesson.value = null
		return
	}

	const newIdx = insertionIndex + 1

	updateLessonIndex.submit({
		lesson: lessonName,
		sourceChapter,
		targetChapter,
		idx: newIdx,
	})

	draggedLesson.value = null
}

const onDragFinish = () => {
	draggedLesson.value = null
}
</script>
