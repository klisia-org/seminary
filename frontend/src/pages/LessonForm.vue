<template>
	<div class="">
		<div class="grid md:grid-cols-[75%,25%] h-screen">
			<div class="border-r">
				<header
					class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b overflow-hidden bg-surface-white px-3 py-2.5 sm:px-5">
					<Breadcrumbs class="text-ellipsis" :items="breadcrumbs" />
					<Button variant="solid" @click="saveLesson({ showSuccessMessage: true })" class="mt-3 md:mt-0">
						{{ __('Save') }}
					</Button>

				</header>
				<div class="py-5">
					<div class="w-5/6 mx-auto">

						<FormControl v-model="lesson.lesson_title" :label="__('Title')" class="mb-4" :required="true" />
						<FormControl v-model="lesson.preview" type="text" class="mb-4"
							:label="__('Text for Preview on the Course Page')" />
						<label class="flex items-center gap-2 mt-2 cursor-pointer">
							<input type="checkbox" v-model="lesson.allow_discuss"
								class="h-4 w-4 rounded border-outline-gray-2 bg-surface-white text-ink-gray-9 focus:ring-outline-gray-3" />
							<span class="text-sm text-ink-gray-7">
								{{ __('Allow Discussions? (Discussions will be automatically disabled for quizzes)') }}
							</span>
						</label>
					</div>
					<div class="border-t mt-4">
						<div class="w-5/6 mx-auto pt-4">
							<div class="flex justify-between cursor-pointer" @click="
								() => {
									openInstructorEditor = !openInstructorEditor
								}
							">
								<label class="block font-medium text-ink-gray-5 mb-1">
									{{ __('Instructor Notes') }}
								</label>
								<ChevronRight class="stroke-2 h-5 w-5 text-ink-gray-5" :class="{
									'rotate-90 transform duration-200': openInstructorEditor,
									'duration-200': !openInstructorEditor,
								}" />
							</div>
							<div v-show="openInstructorEditor" id="instructor-notes"
								class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal py-3">
							</div>
						</div>
					</div>
					<div class="border-t mt-4">
						<div class="w-5/6 mx-auto pt-4">
							<label class="block font-medium text-ink-gray-5 mb-1">
								{{ __('Content') }}
							</label>
							<p v-if="!lessonName" class="text-xs text-ink-gray-4 mb-2">
								{{ __('Click in the area below, then use the + on the left to add text, media, a quiz, exam, assignment or discussion.') }}
							</p>
							<div id="content"
								class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal py-3">
							</div>
						</div>
					</div>
				</div>
			</div>

		</div>
	</div>
</template>
<script setup>
import { Breadcrumbs, Button, createResource, FormControl, toast } from 'frappe-ui'
import {
	computed,
	reactive,
	onMounted,
	inject,
	ref,
	watch,
	onBeforeUnmount,
} from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import EditorJS from '@editorjs/editorjs'
import { ChevronRight } from 'lucide-vue-next'
import { updateDocumentTitle, createToast, getEditorTools } from '@/utils'
import { capture } from '@/telemetry'
import { useSettings } from '@/stores/settings'
import { examStore } from '@/stores/exam'

// Editor block type -> the data key that carries the linked activity's name.
const ACTIVITY_DATA_KEY = {
	quiz: 'quiz',
	exam: 'exam',
	assignment: 'assignment',
	discussionActivity: 'discussion',
}

const editor = ref(null)
const instructorEditor = ref(null)
const user = inject('$user')
const openInstructorEditor = ref(false)
const settingsStore = useSettings()
let autoSaveInterval
let titleSaveTimer
// Name of the persisted Course Lesson once it exists (loaded or autosaved).
const lessonName = ref(null)
// Editors are created exactly once, after the first details fetch resolves.
const initialized = ref(false)
// Serializes every save so autosave, the title debounce, the route-leave guard
// and the pending-insert flow can never race into creating duplicate lessons.
let saveChain = Promise.resolve()

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
	chapterNumber: {
		type: String,
		required: true,
	},
	lessonNumber: {
		type: String,
		required: true,
	},
})

localStorage.setItem('activeCourseName', props.courseName);

onMounted(() => {
	if (!user.data?.is_moderator && !user.data?.is_instructor) {
		window.location.href = '/login'
	}
	capture('lesson_form_opened')
	window.addEventListener('keydown', keyboardShortcut)
})



const renderEditor = (holder, course = null, courseName = null) => {
	// Clear the holder first
	const el = document.getElementById(holder)
	if (el) el.innerHTML = ''

	console.log('renderEditor called with course:', course, 'and courseName:', courseName, 'for holder:', holder) // Debugging log
	return new EditorJS({
		holder: holder,
		tools: getEditorTools(course, courseName),
		autofocus: true,
		defaultBlock: 'markdown',
	})
}

const lesson = reactive({
	lesson_title: '',
	preview: '',
	body: '',
	instructor_notes: '',
	content: '',
	discussion_id: null,
	allow_discuss: false,
})

const lessonDetails = createResource({
	url: 'seminary.seminary.utils.get_lesson_creation_details',
	params: {
		course: props.courseName,
		chapter: props.chapterNumber,
		lesson: props.lessonNumber,
	},
	auto: true,
	onSuccess(data) {
		// Build the editors exactly once. Reloads (e.g. after an autosave) must
		// not re-render the editor or they would wipe what the user is typing.
		if (initialized.value) return
		initialized.value = true

		const course = data?.course_title
		const courseName = props.courseName

		editor.value = renderEditor('content', course, courseName)
		instructorEditor.value = renderEditor('instructor-notes', course, courseName)

		if (data.lesson) {
			lessonName.value = data.lesson.name
			Object.keys(data.lesson).forEach((key) => {
				if (key === 'allow_discuss' || key === 'include_in_preview') return
				lesson[key] = data.lesson[key]
			})

			lesson.include_in_preview = Boolean(data.lesson.include_in_preview)
			lesson.allow_discuss = Boolean(data.lesson.allow_discuss)

			addInstructorNotes(data)
		}

		// Render saved content and splice in any activity created via the
		// "create new activity -> back to lesson" round-trip.
		initContent(data)
		enableAutoSave()
	},
})

// Autosave a brand-new lesson as soon as it has a title, so adding activities
// (which navigates away) or a reload never discards the prof's work.
watch(
	() => lesson.lesson_title,
	(title) => {
		if (!initialized.value || lessonName.value) return
		if (!title || !title.trim()) return
		clearTimeout(titleSaveTimer)
		titleSaveTimer = setTimeout(() => persistLesson(), 1200)
	}
)


const initContent = async (data) => {
	await editor.value.isReady

	let contentObj = null
	if (data.lesson?.content) {
		try {
			contentObj = JSON.parse(data.lesson.content)
		} catch {
			contentObj = null
		}
	} else if (data.lesson?.body) {
		contentObj = { blocks: convertToJSON(data.lesson) }
	}

	// Returning from "create new activity": splice the freshly created activity
	// into the content, replacing the empty placeholder block left behind.
	const pending = examStore.pendingInsert
	const dataKey = pending ? ACTIVITY_DATA_KEY[pending.type] : null
	if (pending?.id && dataKey) {
		if (!contentObj || !Array.isArray(contentObj.blocks)) {
			contentObj = { blocks: [] }
		}
		contentObj.blocks = contentObj.blocks.filter(
			(b) => !(b.type === pending.type && !b.data?.[dataKey])
		)
		contentObj.blocks.push({ type: pending.type, data: { [dataKey]: pending.id } })
	}

	if (contentObj && Array.isArray(contentObj.blocks) && contentObj.blocks.length) {
		await editor.value.render(contentObj)
	}

	if (pending?.id) {
		examStore.clearPendingInsert()
		try {
			await persistLesson()
			toast.success(__('Activity added to the lesson'))
		} catch {
			toast.error(__('Add a lesson title to save this activity.'))
		}
	}
}

const addInstructorNotes = (data) => {
	instructorEditor.value.isReady.then(() => {
		if (data.lesson.instructor_content) {
			instructorEditor.value.render(JSON.parse(data.lesson.instructor_content))
		} else if (data.lesson.instructor_notes) {
			let blocks = convertToJSON(data.lesson)
			instructorEditor.value.render({
				blocks: blocks,
			})
		}
	})
}

const enableAutoSave = () => {
	autoSaveInterval = setInterval(() => {
		if (lesson.lesson_title && lesson.lesson_title.trim()) {
			persistLesson()
		}
	}, 10000)
}

const keyboardShortcut = (e) => {
	if (
		e.key === 's' &&
		(e.ctrlKey || e.metaKey) &&
		!e.target.classList.contains('ProseMirror')
	) {
		saveLesson({ showSuccessMessage: true })
		e.preventDefault()
	}
}

//Remove activeCourseName from local storage when the user leaves the page
onBeforeUnmount(() => {
	localStorage.removeItem('activeCourseName');
	clearInterval(autoSaveInterval)
	clearTimeout(titleSaveTimer)
	window.removeEventListener('keydown', keyboardShortcut)
})

// Persist before navigating away (e.g. jumping to an activity form) so content
// is never lost. Best-effort: never block navigation on a save failure.
onBeforeRouteLeave(async () => {
	if (lesson.lesson_title && lesson.lesson_title.trim()) {
		try {
			await persistLesson()
		} catch {
			/* don't trap the user on the page */
		}
	}
	return true
})


const newLessonResource = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Course Lesson',
				course_sc: props.courseName,
				chapter: lessonDetails.data.chapter.name,
				...lesson,
			},
		}
	},
})

const editLesson = createResource({
	url: 'frappe.client.set_value',
	makeParams(values) {
		return {
			doctype: 'Course Lesson',
			name: values.lesson,
			fieldname: lesson,
		}
	},
})

const lessonReference = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Course Schedule Lesson Reference',
				parent: lessonDetails.data?.chapter.name,
				parenttype: 'Course Schedule Chapter',
				parentfield: 'lessons',
				lesson: values.lesson,
				idx: props.lessonNumber,
			},
		}
	},
})

const convertToJSON = (lessonData) => {
	let blocks = []
	if (lessonData.youtube) {
		let youtubeID = lessonData.youtube.split('/').pop()
		blocks.push({
			type: 'embed',
			data: {
				service: 'youtube',
				embed: `https://www.youtube.com/embed/${youtubeID}`,
			},
		})
	}
	lessonData.body.split('\n').forEach((block) => {
		if (block.includes('{{ YouTubeVideo')) {
			let youtubeID = block.match(/\(["']([^"']+?)["']\)/)[1]
			if (!youtubeID.includes('https://'))
				youtubeID = `https://www.youtube.com/embed/${youtubeID}`
			blocks.push({
				type: 'embed',
				data: {
					service: 'youtube',
					embed: youtubeID,
				},
			})
		} else if (block.includes('{{ Quiz')) {
			let quiz = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'quiz',
				data: {
					quiz: quiz,
				},
			})
		} else if (block.includes('{{ Exam')) {
			let exam = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'exam',
				data: {
					exam: exam,
				},
			})
		} else if (block.includes('{{ DiscussionActivity')) {
			let discussionActivity = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'discussionActivity',
				data: {
					discussionID: discussionActivity,
				},
			})
		} else if (block.includes('{{ Folder')) {
			let folder = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'folder',
				data: {
					folder: folder,
				},
			})
		} else if (block.includes('{{ Video')) {
			let video = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: video,
					file_type: video.split('.').pop(),
				},
			})
		} else if (block.includes('{{ Audio')) {
			let audio = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: audio,
					file_type: audio.split('.').pop(),
				},
			})
		} else if (block.includes('{{ PDF')) {
			let pdf = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: pdf,
					file_type: 'pdf',
				},
			})
		} else if (block.includes('{{ Embed')) {
			let embed = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'embed',
				data: {
					service: embed.split('|||')[0],
					embed: embed.split('|||')[1],
				},
			})
		} else if (block.includes('![]')) {
			let image = block.match(/\((.*?)\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: image,
					file_type: 'image',
				},
			})
		} else if (block.includes('#')) {
			let level = (block.match(/#/g) || []).length
			blocks.push({
				type: 'header',
				data: {
					text: block.replace(/#/g, '').trim(),
					level: level,
				},
			})
		} else {
			blocks.push({
				type: 'paragraph',
				data: {
					text: block,
				},
			})
		}
	})

	if (lessonData.quizId) {
		blocks.push({
			type: 'quiz',
			data: {
				quiz: lessonData.quizId,
			},
		})
	}
	if (lessonData.examId) {
		blocks.push({
			type: 'exam',
			data: {
				exam: lessonData.examId,
			},
		})
	}
	if (lessonData.discussionID) {
		blocks.push({
			type: 'discussionActivity',
			data: {
				discussionID: lessonData.discussionID,
			},
		})
	}
	if (lessonData.folder) {
		blocks.push({
			type: 'folder',
			data: {
				folder: lessonData.folder,
			},
		})
	}

	return blocks
}

// Core save. Serialized through saveChain so concurrent triggers (the 10s
// autosave, the title debounce, the route-leave guard and the pending-insert
// flow) can never race into creating two lessons for the same slot.
const persistLesson = () => {
	saveChain = saveChain.then(() => persistLessonInner())
	return saveChain
}

const persistLessonInner = async () => {
	if (!editor.value) return

	const contentData = await editor.value.save()
	lesson.content = JSON.stringify(contentData)

	if (instructorEditor.value) {
		const instructorData = await instructorEditor.value.save()
		lesson.instructor_content = JSON.stringify(instructorData)
	}

	// Keep the legacy discussion_id field in step with the content (the content
	// JSON remains the source of truth). Blocks created by the tool use the
	// `discussion` key; older ones used `discussionID`.
	const discussionBlock = contentData.blocks.find(
		(block) =>
			['discussionActivity', 'discussionactivity'].includes(block.type) &&
			(block.data?.discussion || block.data?.discussionID)
	)
	lesson.discussion_id = discussionBlock
		? discussionBlock.data.discussion || discussionBlock.data.discussionID
		: null

	if (lessonName.value) {
		await editLesson.submit({ lesson: lessonName.value }, { validate: validateLesson })
	} else {
		const data = await newLessonResource.submit({}, { validate: validateLesson })
		lessonName.value = data.name
		await lessonReference.submit({ lesson: data.name })
		capture('lesson_created')
	}
}

const saveLesson = async (e) => {
	const wantsMessage = typeof e !== 'undefined' && e.showSuccessMessage
	const wasNew = !lessonName.value
	try {
		await persistLesson()
		if (wantsMessage) {
			toast.success(
				wasNew ? __('Lesson created successfully') : __('Lesson updated successfully')
			)
		}
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || __('Could not save the lesson'))
	}
}

const validateLesson = () => {
	if (!lesson.lesson_title) {
		return __('Title is required')
	}
}

const showToast = (lesson_title, text, icon) => {
	createToast({
		lesson_title: lesson_title,
		text: text,
		icon: icon,
		iconClasses:
			icon == 'check'
				? 'bg-surface-green-3 text-ink-white rounded-md p-px'
				: 'bg-surface-red-5 text-ink-white rounded-md p-px',
		position: icon == 'check' ? 'bottom-right' : 'top-center',
		timeout: icon == 'check' ? 5 : 10,
	})
}

const breadcrumbs = computed(() => {
	let crumbs = [
		{
			label: __('Courses'),
			route: { name: 'Courses' },
		},
		{
			label: lessonDetails.data?.course_title,
			route: { name: 'CourseDetail', params: { courseName: props.courseName } },
		},
	]

	if (lessonName.value) {
		crumbs.push({
			label: lesson.lesson_title || lessonDetails.data?.lesson?.lesson_title,
			route: {
				name: 'Lesson',
				params: {
					courseName: props.courseName,
					chapterNumber: props.chapterNumber,
					lessonNumber: props.lessonNumber,
				},
			},
		})
	}
	crumbs.push({
		label: lessonName.value ? __('Edit Lesson') : __('Create Lesson'),
		route: {
			name: 'LessonForm',
			params: {
				courseName: props.courseName,
				chapterNumber: props.chapterNumber,
				lessonNumber: props.lessonNumber,
			},
		},
	})
	return crumbs
})

const pageMeta = computed(() => {
	return {
		title: __('Lesson Editor'),
		description: __('Create and edit lessons for your course'),
	}
})

updateDocumentTitle(pageMeta)

</script>
<style>
.embed-tool__caption,
.cdx-simple-image__caption {
	display: none;
}

.ce-block__content {
	max-width: none;
}

.codex-editor--narrow .ce-toolbar__actions {
	right: 100%;
}

.ce-toolbar__content {
	max-width: none;
}

.codeBoxHolder {
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
}

.codeBoxTextArea {
	width: 100%;
	min-height: 30px;
	padding: 10px;
	border-radius: 2px 2px 2px 0;
	border: none !important;
	outline: none !important;
	font: 14px monospace;
}

.codeBoxSelectDiv {
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
	position: relative;
}

.codeBoxSelectInput {
	border-radius: 0 0 20px 2px;
	padding: 2px 26px;
	padding-top: 0;
	padding-right: 0;
	text-align: left;
	cursor: pointer;
	border: none !important;
	outline: none !important;
}

.codeBoxSelectDropIcon {
	position: absolute !important;
	left: 10px !important;
	bottom: 0 !important;
	width: unset !important;
	height: unset !important;
	font-size: 16px !important;
}

.codeBoxSelectPreview {
	display: none;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
	border-radius: 2px;
	box-shadow: 0 3px 15px -3px rgba(13, 20, 33, 0.13);
	position: absolute;
	top: 100%;
	margin: 5px 0;
	max-height: 30vh;
	overflow-x: hidden;
	overflow-y: auto;
	z-index: 10000;
}

.codeBoxSelectItem {
	width: 100%;
	padding: 5px 20px;
	margin: 0;
	cursor: pointer;
}

.codeBoxSelectedItem {
	background-color: lightblue !important;
}

.codeBoxShow {
	display: flex !important;
}

.dark {
	color: #abb2bf;
	background-color: #282c34;
}

.light {
	color: #383a42;
	background-color: #fafafa;
}

.codeBoxTextArea {
	line-height: 1.7;
}

.prose :where(pre):not(:where([class~='not-prose'], [class~='not-prose'] *)) {
	overflow-x: unset;
}

iframe {
	border-top: 3px solid theme('colors.gray.700');
	border-bottom: 3px solid theme('colors.gray.700');
}

.tc-table {
	border-left: 1px solid #e8e8eb;
}

/* editorjs hard-codes a near-black icon colour for the add-block (+) and the
   drag/settings handle, so they vanish on a dark background. Restore them. */
[data-theme='dark'] .ce-toolbar__plus,
[data-theme='dark'] .ce-toolbar__settings-btn {
	color: var(--ink-gray-7);
}

[data-theme='dark'] .ce-toolbar__plus:hover,
[data-theme='dark'] .ce-toolbar__settings-btn:hover {
	background-color: var(--surface-gray-3);
	color: var(--ink-gray-8);
}

/* Keep the "+" add-block button visible at all times (editorjs only shows the
   toolbar once a block is hovered/focused) so a blank new lesson is
   discoverable instead of looking like an empty canvas. */
#content .ce-toolbar,
#instructor-notes .ce-toolbar {
	display: block;
}
</style>
