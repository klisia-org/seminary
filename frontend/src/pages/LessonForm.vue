<template>
	<div class="min-h-screen bg-surface-gray-1">
		<PageHeader>
			<template #title>
				<Breadcrumbs class="text-ellipsis" :items="breadcrumbs" />
			</template>
			<template #actions>
				<div class="flex items-center gap-3 mt-3 md:mt-0">
					<span class="hidden sm:flex items-center gap-1.5 text-sm text-ink-gray-5">
						<span class="h-1.5 w-1.5 rounded-full" :class="saveStatus.dot"></span>
						{{ saveStatus.label }}
					</span>
					<Button v-if="lessonName" @click="historyOpen = true">
						{{ __('History') }}
					</Button>
					<Button v-if="lessonName" :route="lessonRoute">
						{{ __('Preview') }}
					</Button>
					<Button variant="solid" @click="saveLesson({ showSuccessMessage: true })">
						{{ __('Save lesson') }}
					</Button>
				</div>
			</template>
		</PageHeader>
		<LessonHistory v-model="historyOpen" :lesson="lessonName"
			:course="lessonDetails.data?.course_title || ''" @restore="restoreVersion" />

		<div class="mx-auto max-w-6xl px-4 py-6 grid gap-5 lg:grid-cols-[15rem,minmax(0,1fr)] items-start">
			<BlockPalette :groups="blockGroups" :drop="drop" />

			<div class="space-y-5 min-w-0">
				<!-- Lesson details -->
				<section class="rounded-xl border border-outline-gray-2 bg-surface-white p-6">
					<FormControl v-model="lesson.lesson_title" :label="__('Lesson title')" :required="true" size="lg"
						:disabled="Boolean(library)" :placeholder="__('e.g. The Doctrine of Revelation')" />
					<div v-if="!lessonName && !library" class="mt-3 flex items-center gap-2 text-sm text-ink-gray-6">
						<span>{{ __('Or use a lesson the school keeps in its library.') }}</span>
						<Button size="sm" @click="openLibraryPicker">{{ __('From the library') }}</Button>
					</div>
					<div class="mt-5">
						<div class="mb-1.5 flex items-baseline justify-between">
							<label for="lesson-summary" class="text-xs text-ink-gray-5">
								{{ __('Course page summary') }}
							</label>
							<span class="text-xs tabular-nums"
								:class="summaryLength > SUMMARY_LIMIT ? 'text-ink-amber-3' : 'text-ink-gray-5'">
								{{ summaryLength }} / {{ SUMMARY_LIMIT }}
							</span>
						</div>
						<Textarea id="lesson-summary" v-model="lesson.preview" :rows="2"
							:placeholder="__('One or two sentences students see before opening the lesson')" />
					</div>
					<div class="mt-5 border-t border-outline-gray-1 pt-4">
						<!-- Switch's own label and description name the control (102 §9). -->
						<Switch
							v-model="lesson.allow_discuss"
							size="md"
							:label="__('Allow discussion')"
							:description="__('Students can comment below the lesson. Turned off automatically for quizzes.')"
						/>
					</div>
				</section>

				<!-- A lesson placed from the library (decisions/122): its content is the library's. -->
				<section v-if="library" class="rounded-xl border border-outline-blue-2 bg-surface-white p-6">
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div class="min-w-0">
							<h2 class="text-lg font-semibold text-ink-gray-9">{{ __('From the school library') }}</h2>
							<p class="mt-0.5 text-sm text-ink-gray-5">
								{{ __('Every section that uses this lesson shows the same content. Edits made in the library appear here while the section is open.') }}
							</p>
							<p v-if="library.required" class="mt-2 text-sm text-ink-gray-7">
								<Badge theme="orange" class="mr-1">{{ __('Required by the school') }}</Badge>
								{{ library.reason }}
							</p>
						</div>
						<div class="flex gap-2">
							<Button v-if="library.can_edit" :route="{ name: 'LibraryLessonForm', params: { name: library.name } }">
								{{ __('Edit in the library') }}
							</Button>
							<Button v-if="!library.required" :loading="detaching" @click="detachFromLibrary">
								{{ __('Detach') }}
							</Button>
						</div>
					</div>
					<div id="library-content"
						class="mt-4 rounded-lg bg-surface-gray-1 px-4 md:pl-14 ProseMirror prose prose-sm max-w-none !whitespace-normal py-3">
					</div>
				</section>

				<!-- Instructor notes: folded away by default -->
				<section v-show="!library" class="rounded-xl border border-outline-gray-2 bg-surface-white">
					<button type="button" class="flex w-full items-center gap-3 px-6 py-4 text-left"
						:aria-expanded="openInstructorEditor" @click="openInstructorEditor = !openInstructorEditor">
						<span class="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-gray-2 text-ink-gray-6">
							<Lock class="h-4 w-4" />
						</span>
						<span class="flex-1">
							<span class="block text-base font-medium text-ink-gray-9">{{ __('Instructor notes') }}</span>
							<span class="block text-sm text-ink-gray-5">{{ __('Private — never shown to students') }}</span>
						</span>
						<span class="text-sm text-ink-gray-6">
							{{ openInstructorEditor ? __('Hide') : hasInstructorNotes ? __('Show notes') : __('Add notes') }}
						</span>
						<ChevronDown class="h-4 w-4 text-ink-gray-5 transition-transform duration-200"
							:class="{ 'rotate-180': openInstructorEditor }" />
					</button>
					<div v-show="openInstructorEditor" class="border-t border-outline-gray-1 px-6">
						<div id="instructor-notes"
							class="md:pl-14 ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal py-3">
						</div>
					</div>
				</section>

				<!-- Lesson content -->
				<section class="rounded-xl border border-outline-gray-2 bg-surface-white p-6">
					<div class="mb-3 flex items-baseline justify-between">
						<h2 class="text-lg font-semibold text-ink-gray-9">
							{{ library ? __('This section\'s activities') : __('Lesson content') }}
						</h2>
						<span class="text-sm text-ink-gray-5">
							{{ blockCount === 1 ? __('1 block') : __('{0} blocks').format(blockCount) }}
						</span>
					</div>
					<p v-if="library" class="mb-3 text-sm text-ink-gray-5">
						{{ __('Add this section\'s quizzes, assignments, exams or discussions here. They are shown after the library content. Other blocks aren\'t kept.') }}
					</p>
					<ContentIssues ref="contentChecker" class="mb-3" :issues="contentIssues" />
					<div v-if="blockCount === 0"
						class="mb-3 rounded-lg border border-dashed border-outline-gray-3 bg-surface-gray-1 px-4 py-5 text-center">
						<p class="text-base font-medium text-ink-gray-8">{{ __('Start building your lesson') }}</p>
						<p class="mt-1 text-sm text-ink-gray-5">
							{{ __('Drag a block here from the panel, click one to add it, or type / in the line below.') }}
						</p>
					</div>
					<BlockDropZone :drop="drop">
						<div id="content"
							class="md:pl-14 ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal py-3">
						</div>
					</BlockDropZone>
				</section>

				<!-- An external tool (decisions/110 §3): saved with the lesson, like its other fields. -->
				<section v-if="ltiTools.data?.length || lesson.lti_tool"
					class="rounded-xl border border-outline-gray-2 bg-surface-white p-6">
					<h2 class="text-lg font-semibold text-ink-gray-9">{{ __('External tool') }}</h2>
					<p class="mt-0.5 text-sm text-ink-gray-5">
						{{ __('Students open the tool from this lesson, signed in as themselves. Anything else in the lesson is shown above the button.') }}
					</p>
					<div class="mt-4 grid gap-4 md:grid-cols-2">
						<FormControl type="select" :label="__('Tool')" v-model="lesson.lti_tool" :options="ltiToolOptions" />
						<FormControl v-if="lesson.lti_tool" type="url" :label="__('Launch URL')" v-model="lesson.lti_url"
							:placeholder="__('The tool\'s own launch URL')" />
					</div>
					<FormControl v-if="lesson.lti_tool" class="mt-4" type="textarea" :label="__('Custom parameters')"
						v-model="lesson.lti_custom" :placeholder="__('One key=value per line, if the tool asks for any')" />
				</section>

				<!-- Captions and transcript (102 §6): saved with the lesson, like its other fields. -->
				<section v-if="!library" class="rounded-xl border border-outline-gray-2 bg-surface-white p-6">
					<h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Captions and transcript') }}</h2>
					<p class="mt-0.5 text-sm text-ink-gray-5">
						{{ __('Caption files for the videos uploaded or recorded in this lesson, one per language, in WebVTT (.vtt) format. YouTube and Vimeo videos keep their own captions.') }}
					</p>
					<CaptionsEditor class="mt-4" :captions="lesson.captions" :videos="lessonVideos"
						@add="addCaption" @remove="removeCaption" @review="reviewCaption" />
					<div class="mt-5 border-t border-outline-gray-1 pt-4">
						<div class="text-base font-medium text-ink-gray-9">{{ __('Transcript') }}</div>
						<p class="text-sm text-ink-gray-5">
							{{ __('Optional. A text version of the lesson\'s video or audio, linked below the lesson.') }}
						</p>
						<div v-if="lesson.transcript" class="mt-2 flex items-center gap-3 text-sm">
							<a :href="lesson.transcript" target="_blank" rel="noopener"
								class="min-w-0 flex-1 truncate text-ink-gray-6 underline">{{ fileName(lesson.transcript) }}</a>
							<Button variant="ghost" :aria-label="__('Remove transcript')" @click="lesson.transcript = ''">
								<template #icon>
									<X class="h-4 w-4" />
								</template>
							</Button>
						</div>
						<SmartFileUploader v-else class="mt-2"
							:fileTypes="['.txt', '.pdf', '.doc', '.docx', '.odt', '.html', '.vtt']"
							@success="(file) => (lesson.transcript = file.file_url)">
							<template #default="{ uploading, progress, openFileSelector }">
								<Button :loading="uploading" @click="openFileSelector">
									{{ uploading ? __('Uploading {0}%').format(progress) : __('Upload transcript') }}
								</Button>
							</template>
						</SmartFileUploader>
					</div>
				</section>
			</div>
		</div>
		<Dialog v-model="libraryPickerOpen" :options="{ title: __('Add a lesson from the library'), size: 'xl' }">
			<template #body-content>
				<FormControl v-model="librarySearch" :placeholder="__('Search by title or tag')" @input="searchLibrary" />
				<div class="mt-3 max-h-96 space-y-2 overflow-y-auto">
					<p v-if="!libraryResults.data?.length" class="text-sm text-ink-gray-5">
						{{ __('No library lessons match.') }}
					</p>
					<button v-for="row in libraryResults.data || []" :key="row.name" type="button"
						class="w-full rounded-lg border border-outline-gray-2 p-3 text-left hover:bg-surface-gray-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
						@click="placeFromLibrary(row.name)">
						<span class="block text-base font-medium text-ink-gray-9">{{ row.title }}</span>
						<span v-if="row.preview" class="block text-sm text-ink-gray-6">{{ row.preview }}</span>
						<span v-if="row.tags" class="block text-xs text-ink-gray-5">{{ row.tags }}</span>
					</button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
<script setup>
import PageHeader from '@/components/PageHeader.vue'
import ContentIssues from '@/components/ContentIssues.vue'
import SmartFileUploader from '@/components/SmartFileUploader.vue'
import CaptionsEditor from '@/components/CaptionsEditor.vue'
import LessonHistory from '@/components/LessonHistory.vue'
import BlockPalette from '@/components/BlockPalette.vue'
import BlockDropZone from '@/components/BlockDropZone.vue'
import { useBlockDrop } from '@/composables/useBlockDrop'
import { DEFAULT_BLOCK, blockGroups as blockGroupsFor } from '@/utils/blockPalette'
import { autoDirection } from '@/utils/textDirection'
import {
	Badge,
	Breadcrumbs,
	Button,
	call,
	createResource,
	Dialog,
	FormControl,
	Switch,
	Textarea,
	toast,
} from 'frappe-ui'
import {
	computed,
	nextTick,
	reactive,
	onMounted,
	inject,
	ref,
	watch,
	onBeforeUnmount,
} from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import EditorJS from '@editorjs/editorjs'
import dayjs from '@/utils/dayjs'
import { ChevronDown, Lock, X } from 'lucide-vue-next'
import { updateDocumentTitle, createToast, getEditorTools } from '@/utils'
import { checkBlocks } from '@/utils/contentCheck'
import { isVideo } from '@/utils/mediaTypes'
import { capture } from '@/telemetry'
import { useSettings } from '@/stores/settings'
import { examStore } from '@/stores/exam'

// Blocks a lesson placed from the library may hold: the section's own activities.
const ACTIVITY_TYPES = ['quiz', 'exam', 'assignment', 'discussion', 'discussionActivity', 'discussionactivity', 'oralActivity']
// Fields of a placed lesson that the library owns, never sent back on save.
const LIBRARY_FIELDS = ['body', 'youtube', 'instructor_content', 'instructor_notes', 'preview', 'transcript', 'section_content', 'library_content', 'library']

// Editor block type -> the data key that carries the linked activity's name.
const ACTIVITY_DATA_KEY = {
	quiz: 'quiz',
	exam: 'exam',
	assignment: 'assignment',
	discussionActivity: 'discussion',
	oralActivity: 'oral',
}

// The palette's tiles. A lesson placed from the library holds only the section's
// activities, so that is all its palette offers (decisions/122 §2).
const blockGroups = computed(() =>
	library.value ? blockGroupsFor().filter((g) => g.activity) : blockGroupsFor(),
)

// Soft guide for the course page summary; the field itself has no cap.
const SUMMARY_LIMIT = 160

const editor = ref(null)
const instructorEditor = ref(null)
const hasInstructorNotes = ref(false)
// Blocks in the lesson that hold something; an empty text line doesn't count.
const blockCount = ref(0)
const saving = ref(false)
const savedOnce = ref(false)
const user = inject('$user')
const openInstructorEditor = ref(false)
const settingsStore = useSettings()
let autoSaveInterval
let titleSaveTimer
// Name of the persisted Course Lesson once it exists (loaded or autosaved).
const lessonName = ref(null)
// The library lesson this lesson is placed from, with whether the school requires it.
const library = ref(null)
const detaching = ref(false)
const libraryPickerOpen = ref(false)
const librarySearch = ref('')
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




// A placed lesson shows the library content read-only above its own activities.
const renderLibraryContent = (content, course, courseName) => {
	let data = { blocks: [] }
	try {
		data = JSON.parse(content || '{"blocks": []}')
	} catch {
		/* shown empty */
	}
	const mount = () => {
		const holder = document.getElementById('library-content')
		if (!holder) return
		holder.innerHTML = ''
		new EditorJS({ holder: 'library-content', readOnly: true, tools: getEditorTools(course, courseName), data })
	}
	nextTick(mount)
}

const detachFromLibrary = async () => {
	detaching.value = true
	try {
		await call('seminary.seminary.library.detach', { lesson: lessonName.value })
		toast.success(__('The lesson is now this section\'s own copy.'))
		window.location.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The lesson could not be detached.'))
	} finally {
		detaching.value = false
	}
}

const libraryResults = createResource({
	url: 'seminary.seminary.library.search',
	makeParams() {
		return { txt: librarySearch.value, course_schedule: props.courseName }
	},
})

let librarySearchTimer
const searchLibrary = () => {
	clearTimeout(librarySearchTimer)
	librarySearchTimer = setTimeout(() => libraryResults.reload(), 300)
}

const openLibraryPicker = () => {
	libraryPickerOpen.value = true
	libraryResults.reload()
}

const placeFromLibrary = async (name) => {
	try {
		await call('seminary.seminary.library.place', {
			library_lesson: name,
			chapter: lessonDetails.data.chapter.name,
		})
		libraryPickerOpen.value = false
		toast.success(__('Lesson added from the library'))
		// The new lesson takes the next place in the chapter, which this form's route names.
		window.location.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The lesson could not be added.'))
	}
}

const renderEditor = (holder, course = null, courseName = null, onChange = null) => {
	// Clear the holder first
	const el = document.getElementById(holder)
	if (el) el.innerHTML = ''
	if (el) reachablePopovers(el)
	if (el) autoDirection(el)

	return new EditorJS({
		holder: holder,
		tools: getEditorTools(course, courseName),
		// No `autofocus`: it fires before the saved content is rendered, and
		// both editors are built here, so it ended up in the collapsed
		// instructor notes. focusFreeBlockAtEnd() places the caret instead,
		// once the content editor holds the lesson.
		defaultBlock: DEFAULT_BLOCK,
		...(onChange ? { onChange } : {}),
	})
}

// editorjs's block menus scroll but can't take focus, so a keyboard user can't scroll
// them (102 §9, WCAG 2.1.1): make each one focusable as it appears.
const reachablePopovers = (el) => {
	new MutationObserver(() => {
		el.querySelectorAll('.ce-popover__items:not([tabindex])').forEach((items) => {
			items.setAttribute('tabindex', '0')
		})
	}).observe(el, { childList: true, subtree: true })
}

const countBlocks = () => {
	const api = editor.value
	if (!api?.blocks) return
	let filled = 0
	for (let i = 0; i < api.blocks.getBlocksCount(); i++) {
		if (!api.blocks.getBlockByIndex(i)?.isEmpty) filled++
	}
	blockCount.value = filled
}

// The accessibility checker (102 §7): re-read the blocks a moment after the
// instructor stops typing, and whenever the captions change.
const contentChecker = ref(null)
const contentIssues = ref([])
let checkTimer

const runContentCheck = async () => {
	clearTimeout(checkTimer)
	if (!editor.value) return
	try {
		const data = await editor.value.save()
		contentIssues.value = checkBlocks(data.blocks, { captions: lesson.captions })
		lessonVideos.value = videosIn(data.blocks)
	} catch {
		/* the editor is mid-render; the next change checks again */
	}
}

const scheduleContentCheck = () => {
	clearTimeout(checkTimer)
	checkTimer = setTimeout(runContentCheck, 800)
}

const onContentChange = () => {
	countBlocks()
	scheduleContentCheck()
}

watch(() => lesson.captions.length, scheduleContentCheck)
watch(() => lesson.captions.map((c) => c.status).join('|'), scheduleContentCheck)

// The lesson's own uploaded or recorded videos, which captions can be drafted
// for (privatedocs p029 §7); found by the content check's read of the blocks.
const lessonVideos = ref([])
const videosIn = (blocks) => {
	const seen = new Set()
	return (blocks || [])
		.filter((b) => (b?.type === 'upload' && isVideo(b.data?.file_type)) || b?.type === 'recordVideo')
		.map((b) => b.data?.file_url)
		.filter((url) => url && !seen.has(url) && seen.add(url))
		.map((url) => ({ url, label: fileName(url) }))
}

// Captions (102 §6). The rows ride on the lesson and save with it.
const fileName = (url) => decodeURIComponent(String(url || '').split('?')[0].split('/').pop())

const addCaption = (row) => {
	lesson.captions.push(row)
	if (lessonName.value) persistLesson().catch(() => {})
}

// Lesson history (decision 109 §3): a restored version goes into the editors and is
// saved, which makes it the newest version.
const historyOpen = ref(false)

const restoreVersion = async ({ content, instructor_content, saved_at }) => {
	const parse = (json) => {
		try {
			const data = JSON.parse(json || '{}')
			return Array.isArray(data.blocks) ? data : { blocks: [] }
		} catch {
			return { blocks: [] }
		}
	}
	try {
		await editor.value.isReady
		await editor.value.render(parse(content))
		if (instructorEditor.value) {
			await instructorEditor.value.isReady
			const notes = parse(instructor_content)
			if (notes.blocks.length) await instructorEditor.value.render(notes)
			else instructorEditor.value.clear()
			hasInstructorNotes.value = hasInstructorNotes.value || notes.blocks.length > 0
		}
		countBlocks()
		runContentCheck()
		await persistLesson()
		toast.success(__('Restored the version saved {0}.').format(dayjs(saved_at).format('D MMM YYYY, HH:mm')))
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || __('Could not restore that version'))
	}
}

const reviewCaption = (index) => {
	lesson.captions[index].status = 'Reviewed'
	if (lessonName.value) persistLesson().catch(() => {})
}

const removeCaption = (index) => {
	lesson.captions.splice(index, 1)
	if (lessonName.value) persistLesson().catch(() => {})
}

const drop = useBlockDrop(editor, 'content', {
	onAdded: () => {
		capture('lesson_block_added')
		countBlocks()
	},
})

/**
 * Leave the caret in a free block at the end of the content, with the toolbar
 * beside it: on a new lesson that is the first block, on an existing one a new
 * block under the last. Someone opening the form then sees where to type and
 * where the "+" is, rather than a page that looks inert -- and it is the one
 * spot that works whatever the lesson ends with, including a block that has no
 * contenteditable of its own. Reuse a trailing block that is already an empty
 * default one instead of stacking another, which is editorjs's own rule for
 * the click-to-append strip below the last block.
 */
const focusFreeBlockAtEnd = () => {
	const api = editor.value
	if (!api) return

	const count = api.blocks.getBlocksCount()
	const last = count ? api.blocks.getBlockByIndex(count - 1) : null

	if (last && last.name === DEFAULT_BLOCK && last.isEmpty) {
		api.caret.setToLastBlock('end')
	} else {
		api.blocks.insert(DEFAULT_BLOCK, {}, {}, count, true)
	}
	// Move the "+" to the block the caret is now in.
	api.toolbar.open()
}

const lesson = reactive({
	lesson_title: '',
	preview: '',
	body: '',
	instructor_notes: '',
	content: '',
	discussion_id: null,
	allow_discuss: false,
	// Course Lesson Caption rows and the transcript file (102 §6).
	captions: [],
	transcript: '',
	// decisions/110
	lti_tool: '',
	lti_url: '',
	lti_custom: '',
})

const ltiTools = createResource({
	url: 'seminary.lti.launch.tools_for_lessons',
	params: { course: props.courseName },
	auto: true,
})

const ltiToolOptions = computed(() => [
	{ label: __('None'), value: '' },
	...(ltiTools.data || []).map((t) => ({ label: t.tool_name, value: t.name })),
	// A tool since disabled stays selectable on the lesson that already names it.
	...(lesson.lti_tool && !(ltiTools.data || []).some((t) => t.name === lesson.lti_tool)
		? [{ label: lesson.lti_tool, value: lesson.lti_tool }]
		: []),
])

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

		editor.value = renderEditor('content', course, courseName, onContentChange)
		instructorEditor.value = renderEditor('instructor-notes', course, courseName)

		if (data.lesson?.library) {
			library.value = data.lesson.library
			renderLibraryContent(data.lesson.library_content, course, courseName)
		}

		if (data.lesson) {
			lessonName.value = data.lesson.name
			Object.keys(data.lesson).forEach((key) => {
				if (key === 'allow_discuss' || key === 'include_in_preview') return
				lesson[key] = data.lesson[key]
			})

			lesson.captions = Array.isArray(data.lesson.captions) ? data.lesson.captions : []
			lesson.transcript = data.lesson.transcript || ''
			lesson.include_in_preview = Boolean(data.lesson.include_in_preview)
			lesson.allow_discuss = Boolean(data.lesson.allow_discuss)

			if (library.value) {
				// The library owns these; the section's lesson keeps only its activities.
				for (const key of LIBRARY_FIELDS) delete lesson[key]
				lesson.captions = []
			} else {
				addInstructorNotes(data)
			}
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
	if (library.value) {
		contentObj = JSON.parse(data.lesson.section_content || '{"blocks": []}')
	} else if (data.lesson?.content) {
		try {
			contentObj = JSON.parse(data.lesson.content)
		} catch {
			contentObj = null
		}
	} else if (data.lesson?.body) {
		await ensureFoldersFor(data.lesson)
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

	focusFreeBlockAtEnd()
	countBlocks()
	runContentCheck()

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
	hasInstructorNotes.value = Boolean(data.lesson.instructor_content || data.lesson.instructor_notes)
	instructorEditor.value.isReady.then(async () => {
		if (data.lesson.instructor_content) {
			instructorEditor.value.render(JSON.parse(data.lesson.instructor_content))
		} else if (data.lesson.instructor_notes) {
			await ensureFoldersFor(data.lesson)
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
	clearTimeout(checkTimer)
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

// Legacy lessons name a folder by `foldername`; blocks now carry the Course
// Folder docname (p006 §2.2a). The embeddable list for this section is fetched
// once, lazily, only when a legacy lesson actually mentions a folder.
const embeddableFolders = { list: [], instructor: null, loaded: false }
let embeddableFoldersPromise = null

const mentionsFolder = (lessonData) =>
	Boolean(
		lessonData?.folder ||
			(lessonData?.body && lessonData.body.includes('{{ Folder')) ||
			(lessonData?.instructor_notes && lessonData.instructor_notes.includes('{{ Folder'))
	)

const ensureFoldersFor = (lessonData) => {
	if (!mentionsFolder(lessonData) || embeddableFolders.loaded) return Promise.resolve()
	if (!embeddableFoldersPromise) {
		const params = { course_schedule: props.courseName }
		embeddableFoldersPromise = Promise.all([
			createResource({
				url: 'seminary.seminary.doctype.course_folder.course_folder.folder_context',
				params,
			}).fetch(),
			createResource({
				url: 'seminary.seminary.doctype.course_folder.course_folder.list_embeddable_folders',
				params,
			}).fetch(),
		])
			.then(([context, list]) => {
				embeddableFolders.instructor = context?.instructor || null
				embeddableFolders.list = Array.isArray(list) ? list : []
			})
			.catch((error) => {
				// Leave the list empty: the block is still emitted with only
				// `folder`, so the reader sees the re-link notice, not lost content.
				console.error('Error listing embeddable folders:', error)
			})
			.finally(() => {
				embeddableFolders.loaded = true
			})
	}
	return embeddableFoldersPromise
}

// Resolve a legacy folder name to a block payload. Course scope wins, then the
// current user's own Instructor folder, then Section (this section first), then
// School. No match: emit `folder` alone, which renders the re-link notice.
const folderBlockData = (foldername) => {
	const candidates = embeddableFolders.list.filter((f) => f.foldername === foldername)
	const rank = (f) => {
		switch (f.scope) {
			case 'Course':
				return 0
			case 'Instructor':
				return f.instructor && f.instructor === embeddableFolders.instructor ? 1 : 5
			case 'Section':
				return f.course_schedule === props.courseName ? 2 : 3
			case 'School':
				return 4
			default:
				return 6
		}
	}
	const match = candidates.sort((a, b) => rank(a) - rank(b))[0]
	return match ? { folder_ref: match.name, folder: match.foldername } : { folder: foldername }
}

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
				data: folderBlockData(folder),
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
			data: folderBlockData(lessonData.folder),
		})
	}

	return blocks
}

// Core save. Serialized through saveChain so concurrent triggers (the 10s
// autosave, the title debounce, the route-leave guard and the pending-insert
// flow) can never race into creating two lessons for the same slot.
// The chain itself swallows a failure: a rejected link would otherwise skip
// every later save and hand back the same error -- one save attempted before
// the lesson had a title then blocked saving for good with "Title is required".
// Each caller still gets its own save's outcome.
const persistLesson = () => {
	const run = saveChain.then(() => persistLessonInner())
	saveChain = run.catch(() => {})
	return run
}

const persistLessonInner = async () => {
	if (!editor.value) return
	saving.value = true
	try {
		await writeLesson()
		savedOnce.value = true
	} finally {
		saving.value = false
	}
}

const writeLesson = async () => {
	// Without editorjs's save `time`, which changes on every save, and without the empty
	// line focusFreeBlockAtEnd() leaves for the caret: an autosave with no edit then
	// changes nothing, and the lesson's history (decision 109 §3) gets a version only
	// when the lesson did change.
	const untimed = ({ time, ...data }) => {
		const blocks = [...(data.blocks || [])]
		const blank = (b) =>
			['markdown', 'paragraph'].includes(b?.type) && !String(b.data?.text || '').replace(/<br\s*\/?>|&nbsp;|\s/g, '')
		while (blocks.length && blank(blocks[blocks.length - 1])) blocks.pop()
		return { ...data, blocks }
	}
	const contentData = untimed(await editor.value.save())
	if (library.value) {
		contentData.blocks = contentData.blocks.filter((b) => ACTIVITY_TYPES.includes(b.type))
	}
	lesson.content = JSON.stringify(contentData)

	if (instructorEditor.value && !library.value) {
		const instructorData = untimed(await instructorEditor.value.save())
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
		const saved = await editLesson.submit({ lesson: lessonName.value }, { validate: validateLesson })
		adoptCaptionNames(saved)
	} else {
		const data = await newLessonResource.submit({}, { validate: validateLesson })
		adoptCaptionNames(data)
		lessonName.value = data.name
		await lessonReference.submit({ lesson: data.name })
		capture('lesson_created')
	}
}

// Keep the saved rows' names, so the next save updates them rather than
// replacing every caption row.
const adoptCaptionNames = (saved) => {
	const rows = saved?.captions
	if (!Array.isArray(rows)) return
	rows.forEach((row, i) => {
		const local = lesson.captions[i]
		if (local && !local.name && local.caption_file === row.caption_file) local.name = row.name
	})
}

const saveLesson = async (e) => {
	const wantsMessage = typeof e !== 'undefined' && e.showSuccessMessage
	const wasNew = !lessonName.value
	// An explicit save shows what the checker found and lets the instructor go
	// ahead anyway; the autosave never asks (102 §7).
	if (wantsMessage && editor.value) {
		await runContentCheck()
		if (!(await contentChecker.value?.confirm(contentIssues.value) ?? true)) return
	}
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

const summaryLength = computed(() => (lesson.preview || '').length)

const saveStatus = computed(() => {
	if (saving.value) return { label: __('Saving…'), dot: 'bg-surface-gray-4' }
	if (!lessonName.value) return { label: __('Draft · not saved yet'), dot: 'bg-surface-amber-3' }
	return {
		label: savedOnce.value ? __('All changes saved') : __('Saved'),
		dot: 'bg-surface-green-3',
	}
})

const lessonRoute = computed(() => ({
	name: 'Lesson',
	params: {
		courseName: props.courseName,
		chapterNumber: props.chapterNumber,
		lessonNumber: props.lessonNumber,
	},
}))

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
/* simple-image's caption stays visible here: it is the image's alt text (102 §7). */
.embed-tool__caption {
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

/* editorjs appends a new block when you click the empty strip below the last
   one, and that is the only way to reach the end of a lesson that finishes in
   a block with no contenteditable -- a video embed, a PDF, a table. Set the
   strip here rather than inheriting editorjs's default, so an unscoped rule on
   another page cannot take it away again. */
#content .codex-editor__redactor,
#instructor-notes .codex-editor__redactor {
	padding-bottom: 160px;
}

/* While a palette tile is dragged: outline the drop area, and let the pointer
   pass over embedded frames, which would otherwise swallow the dragover events
   and hide the drop position. */
/* A hover band on framed blocks. An iframe keeps mouse events to itself, so
   moving the pointer over a video never reaches the editor: editorjs never
   hears "block hovered", the toolbar never moves there, and the "+" stays on
   whichever block was hovered last. The band belongs to the block, so hovering
   it targets the right one -- and the frame stays interactive, unlike making
   it click-through. */
#content .ce-block__content:has(iframe),
#instructor-notes .ce-block__content:has(iframe) {
	padding-top: 14px;
	padding-bottom: 14px;
}
</style>
