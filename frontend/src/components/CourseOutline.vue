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
			<template v-for="(chapter, index) in outline.data" :key="chapter.name">
			<!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a pointer shortcut: each chapter's Move menu does the same by keyboard -->
			<div v-if="props.allowEdit"
				class="mx-2 h-3 rounded border border-dashed border-outline-gray-3 transition hover:border-outline-gray-4"
				@dragover.prevent="onChapterDragOver($event)" @drop.prevent="onChapterDrop($event, index)">
			</div>
			<Disclosure v-slot="{ open }" :defaultOpen="openChapterDetail(chapter.idx)">
				<!-- The row is what drags; the disclosure inside it stays a div with
				     role/tabindex, not a button: Firefox and Safari do not reliably
				     start a native drag from a <button>. headlessui wires its
				     click/keydown handlers and aria-expanded. The chapter's actions
				     sit beside it, not inside it, so no button holds another. -->
				<!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a pointer shortcut: the Move menu in this row does the same by keyboard -->
				<div class="flex w-full items-center group"
					:class="{ 'cursor-grab': props.allowEdit }" :draggable="props.allowEdit"
					@dragstart="onChapterDragStart($event, chapter, index)" @dragend="onChapterDragFinish">
					<DisclosureButton as="div" role="button" tabindex="0"
						class="flex flex-1 items-center p-2">
						<!-- The chevron used to be hidden on a SCORM chapter because
						     such a chapter had nothing to expand. Its SCOs are its
						     lessons now (p009 §2.10), so it expands like any other. -->
						<ChevronRight :class="{
							'rotate-90 transform duration-200': open,
							'duration-200': !open,
							open: index == 1,
						}" class="h-4 w-4 text-ink-gray-9 stroke-1" />
						<div class="ml-2 text-left text-base font-medium leading-5"
							:class="chapter.release?.locked ? 'text-ink-gray-5' : 'text-ink-gray-9'">
							{{ chapter.chapter_title }}
						</div>
						<!-- Release date and prerequisites (decisions/107): a
						     locked chapter stays in view, greyed out, and says why. -->
						<template v-if="chapter.release?.locked">
							<Lock class="ml-2 h-4 w-4 text-ink-gray-5" aria-hidden="true" />
							<span class="sr-only">{{ __('Locked') }}</span>
						</template>
						<span v-if="chapter.release?.staff_note"
							class="ml-2 rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">
							{{ chapter.release.staff_note }}
						</span>
						<span v-if="chapter.release?.has_prerequisites"
							class="ml-2 rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">
							{{ __('Has prerequisites') }}
						</span>
					</DisclosureButton>
					<!-- Shown on hover and on focus (decision 103): hidden
					     controls can't take focus. -->
					<div v-if="props.allowEdit"
						class="ml-auto flex items-center gap-1 pr-2 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
						<Tooltip :text="__('Edit Chapter')" placement="bottom">
							<button type="button" :aria-label="__('Edit Chapter')"
								class="rounded-md p-1 text-ink-gray-9 hover:bg-surface-gray-2"
								@click="openChapterModal(chapter)">
								<FilePenLine class="h-4 w-4" aria-hidden="true" />
							</button>
						</Tooltip>
						<Tooltip v-if="!holdsReflection(chapter)" :text="__('Delete Chapter')" placement="bottom">
							<button type="button" :aria-label="__('Delete Chapter')"
								class="rounded-md p-1 text-ink-red-3 hover:bg-surface-red-1"
								@click="trashChapter(chapter.name)">
								<Trash2 class="h-4 w-4" aria-hidden="true" />
							</button>
						</Tooltip>
						<Dropdown v-if="chapterMoves(index).length" :options="chapterMoves(index)">
							<button type="button" :data-move="`chapter:${chapter.name}`"
								:aria-label="__('Move {0}', [chapter.chapter_title])" @click="focusFirstMove"
								class="rounded-md p-1 text-ink-gray-6 hover:bg-surface-gray-2">
								<ArrowUpDown class="h-4 w-4" aria-hidden="true" />
							</button>
						</Dropdown>
						<GripVertical class="h-4 w-4 text-ink-gray-5" aria-hidden="true" />
					</div>
				</div>
				<!-- p009 §2.10: a SCO *is* a lesson, so a SCORM chapter expands
				     like any other. This panel used to be suppressed for one,
				     because before p009 such a chapter genuinely had nothing
				     inside it. S8 un-hid the chevron above and left this
				     condition behind, so the chevron turned and revealed an
				     empty space -- the chapter title and nothing else. -->
				<DisclosurePanel>
					<div v-if="chapter.release?.locked" role="note"
						class="ml-8 mr-4 mb-3 flex items-start gap-2 rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-3 text-sm text-ink-gray-6">
						<Lock class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
						<ul class="space-y-1">
							<li v-for="reason in chapter.release.reasons" :key="reason">{{ reason }}</li>
						</ul>
					</div>
					<!-- Competency guidance and lock state (ADR 065). The student
					     reads what they are being formed into in the same place
					     they do the work, and a lock always says why. -->
					<div v-if="competencyOf(chapter)" class="ml-8 mr-4 mb-3 rounded-lg border p-3"
						:class="competencyOf(chapter).locked
							? 'border-outline-gray-3 bg-surface-gray-1'
							: 'border-outline-blue-1 bg-surface-blue-1'">
						<div class="flex flex-wrap items-center gap-2">
							<Lock v-if="competencyOf(chapter).locked" class="h-4 w-4 text-ink-gray-6" />
							<span class="text-sm font-medium text-ink-gray-8">
								{{ competencyOf(chapter).competency_name }}
							</span>
							<span v-if="competencyOf(chapter).self_assessment_submitted?.length"
								class="rounded bg-surface-green-1 px-1.5 py-0.5 text-xs text-ink-green-3">
								{{ __('Self-assessed') }}
							</span>
						</div>
						<SafeHtml v-if="competencyOf(chapter).statement"
							class="prose-sm mt-1 text-ink-gray-6" :html="competencyOf(chapter).statement" />
						<dl v-if="!competencyOf(chapter).locked" class="mt-2 space-y-1">
							<div v-for="d in competencyOf(chapter).dimensions" :key="d.dimension_code"
								class="text-xs">
								<dt class="inline font-medium text-ink-gray-7">{{ d.dimension }}:</dt>
								<SafeHtml class="ml-1 inline text-ink-gray-6" :html="d.demonstrated_by" as="dd" />
							</div>
						</dl>
						<p v-if="competencyOf(chapter).reason && !chapter.release?.locked" class="mt-2 text-xs text-ink-gray-6">
							{{ competencyOf(chapter).reason }}
						</p>
						<!-- A lock links to the lesson that lifts it (ADR 079
						     decision 4); the page is the fallback for a section
						     whose lesson cannot be found. -->
						<router-link v-if="competencyOf(chapter).unlock_competency"
							:to="unlockRoute(competencyOf(chapter))">
							<Button size="sm" variant="subtle" class="mt-2">
								{{ __('Open that self-assessment') }}
							</Button>
						</router-link>
					</div>

					<template v-if="chapter.lessons">
					<div v-for="(lesson, lessonIndex) in chapter.lessons" :key="lesson.name" class="lesson-wrapper">
						<!-- Not on a SCORM chapter: the manifest owns which SCOs
						     exist and in what order, and `lessons.reconcile`
						     rewrites both on every re-upload. A lesson dragged
						     out of one would keep a `scorm_sco_identifier` its
						     new chapter has no package for, and nothing would
						     play it. -->
						<!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a pointer shortcut: each lesson's Move menu does the same by keyboard -->
						<div v-if="props.allowEdit && !chapter.is_scorm_package"
							class="ml-8 mr-4 h-3 rounded border border-dashed border-outline-gray-3 transition hover:border-outline-gray-4"
							@dragover.prevent="onDragOver($event)" @drop.prevent="onDrop($event, chapter, lessonIndex)">
						</div>
						<!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a pointer shortcut: the Move menu on this card does the same by keyboard -->
						<div class="group ml-8 mr-4 rounded-lg border border-outline-gray-2 bg-surface-white p-4 transition hover:border-outline-gray-3"
							:class="{
								'opacity-60': chapter.release?.locked,
								'bg-surface-selected': isActiveLesson(lesson.number),
								'cursor-grab': props.allowEdit && !chapter.is_scorm_package && !reflectionOf(lesson),
							}" :draggable="props.allowEdit && !chapter.is_scorm_package && !reflectionOf(lesson)"
							@dragstart="onDragStart($event, chapter, lesson, lessonIndex)"
							@dragend="onDragFinish">
							<div class="flex items-start gap-3">
								<div v-if="props.allowEdit && reflectionOf(lesson)">
									<Tooltip :text="__('Placed by the Competency Framework: it stays in place, but you can edit its title and text.')"
										placement="bottom">
										<span class="block rounded-md p-1 text-ink-gray-5">
											<Lock class="h-4 w-4" />
										</span>
									</Tooltip>
								</div>
								<div v-else-if="props.allowEdit">
									<Tooltip :text="__('Delete Lesson')" placement="bottom">
										<button :aria-label="__('Delete Lesson')" type="button"
											class="rounded-md p-1 text-ink-red-3 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:bg-surface-red-1"
											@click.prevent="trashLesson(lesson.name, chapter.name)">
											<Trash2 class="h-4 w-4" />
										</button>
									</Tooltip>
								</div>
								<!-- A locked chapter's lessons are titles, not links. -->
								<component :is="chapter.release?.locked ? 'div' : 'router-link'" class="flex-1"
									:aria-disabled="chapter.release?.locked ? 'true' : undefined"
									v-bind="chapter.release?.locked ? {} : { to: lessonRoute(lesson) }">
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
											<MessageSquare v-else-if="lesson.icon === 'icon-discussion'"
												class="h-4 w-4 stroke-1" />
											<Mic v-else-if="lesson.icon === 'icon-oral'"
												class="h-4 w-4 stroke-1" />
											<FolderOpen v-else-if="lesson.icon === 'icon-folder'"
												class="h-4 w-4 stroke-1" />
											<Sprout v-else-if="lesson.icon === 'icon-self-assessment'"
												class="h-4 w-4 stroke-1" />
											<Compass v-else-if="lesson.icon === 'icon-development-plan'"
												class="h-4 w-4 stroke-1" />
											<FileText v-else class="h-4 w-4 text-ink-gray-7 stroke-1" />
											<span>{{ lesson.lesson_title }}</span>
											<span
												v-if="lesson.has_graded_activity"
												class="rounded bg-surface-amber-1 px-1.5 py-0.5 text-xs font-medium text-ink-amber-3"
												:title="__('This lesson has a graded activity')"
											>
												{{ __('Graded') }}
											</span>
											<span
												v-if="lesson.has_graded_activity && chapter.release?.activities_locked && !chapter.release?.locked"
												class="flex items-center gap-1 rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6"
												:title="(chapter.release.reasons || []).join(' ')"
											>
												<Lock class="h-3 w-3" />
												{{ __('Locked') }}
											</span>
											<span v-if="reflectionOf(lesson)?.required"
												class="rounded bg-surface-amber-1 px-1.5 py-0.5 text-xs font-medium text-ink-amber-3">
												{{ __('Required') }}
											</span>
											<span v-if="reflectionOf(lesson)?.review_new"
												class="rounded bg-surface-blue-1 px-1.5 py-0.5 text-xs font-medium text-ink-blue-3">
												{{ __('New review') }}
											</span>
											<span v-else-if="reflectionOf(lesson)?.mentor_feedback"
												class="rounded bg-surface-blue-1 px-1.5 py-0.5 text-xs font-medium text-ink-blue-3">
												{{ __('Mentor feedback') }}
											</span>
											<span v-if="lesson.discussion_unread"
												class="rounded bg-surface-blue-1 px-1.5 py-0.5 text-xs font-medium text-ink-blue-3"
												:title="__('New posts and replies in this lesson\'s discussion')">
												{{ __('{0} new').format(lesson.discussion_unread) }}
											</span>
											<Check v-if="lesson.is_complete || lesson.assessments_submitted"
												class="h-4 w-4 text-ink-green-3"
												:title="lesson.is_complete ? __('Lesson complete') : __('Assessments submitted')" />
										</div>
										<div v-if="lesson.preview" class="w-full rounded-md bg-surface-blue-1 text-ink-blue-2 p-2">
											{{ lesson.preview }}
										</div>
										<div v-if="lesson.due_date" class="rounded-md bg-surface-green-1 text-ink-green-3 p-2">
											{{ __('Due: ') + formatDate(lesson.due_date) }}
										</div>
									</div>
								</component>
								<div v-if="props.allowEdit && !reflectionOf(lesson) && !chapter.is_scorm_package"
									class="ml-auto flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
									<Dropdown v-if="lessonMoves(chapter, lessonIndex).length"
										:options="lessonMoves(chapter, lessonIndex)">
										<button type="button" :data-move="`lesson:${lesson.name}`"
											:aria-label="__('Move {0}', [lesson.lesson_title])" @click="focusFirstMove"
											class="rounded-md p-1 text-ink-gray-6 hover:bg-surface-gray-2">
											<ArrowUpDown class="h-4 w-4" aria-hidden="true" />
										</button>
									</Dropdown>
									<GripVertical class="h-4 w-4 text-ink-gray-5" aria-hidden="true" />
								</div>
							</div>
						</div>
					</div>
					</template>
					<!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a pointer shortcut: a lesson's Move menu moves it to the end of any chapter -->
					<div v-if="props.allowEdit && !chapter.is_scorm_package"
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
						<!-- decisions/110 §5: choose content inside a tool; each pick becomes a lesson. -->
						<Dropdown v-if="!chapter.is_scorm_package && deepLinkTools.length" class="ml-2"
							:options="deepLinkTools.map((t) => ({ label: t.tool_name, onClick: () => addFromTool(chapter, t) }))">
							<Button>{{ __('Add from tool') }}</Button>
						</Dropdown>
					</div>
				</DisclosurePanel>
			</Disclosure>
			</template>
			<!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a pointer shortcut: a chapter's Move menu does the same by keyboard -->
			<div v-if="props.allowEdit && outline.data?.length"
				class="mx-2 mt-2 rounded-md border border-dashed border-outline-gray-3 p-3 text-sm text-ink-gray-5 transition hover:border-outline-gray-4 hover:text-ink-gray-7"
				@dragover.prevent="onChapterDragOver($event)"
				@drop.prevent="onChapterDrop($event, outline.data.length)">
				{{ __('Drop here to move to the end of the course') }}
			</div>
		</div>
	</div>
	<ChapterModal v-model="showChapterModal" v-model:outline="outline" :course="courseName"
		:chapterDetail="getCurrentChapter()" />
</template>
<script setup>
import { Button, createResource, Dropdown, Tooltip, toast } from 'frappe-ui'
import { computed, inject, nextTick, onBeforeUnmount, ref } from 'vue'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue'
import {
	Check,
	ChevronRight,
	FileText,
	FilePenLine,
	FolderOpen,
	HelpCircle,
	MessageSquare,
	Mic,
	MonitorPlay,
	BookOpenCheck,
	Trash2,
	FileUp,
	GripVertical,
	ArrowUpDown,
	Lock,
	Sprout,
	Compass,
} from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { formatDate, refiledMessage } from '@/utils'
import ChapterModal from '@/components/Modals/ChapterModal.vue'
import { createDialog } from '@/utils/dialogs'

const route = useRoute()
const router = useRouter()
const user = inject('$user')
const showChapterModal = ref(false)
const currentChapter = ref(null)
const draggedLesson = ref(null); // Use a ref to store the dragged lesson
const draggedChapter = ref(null); // Same, for a chapter being reordered

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

// Optional-feature gate: an ordinary section returns is_cbe false and every
// panel below simply does not render.
const competencies = createResource({
	url: 'seminary.seminary.cbe_api.get_outline_competencies',
	params: {
		course_schedule: props.courseName,
	},
	auto: true,
	onError: () => {},
})

const competencyOf = (chapter) => competencies.data?.chapters?.[chapter.name]

// Reflection lessons are placed by the Competency Framework (ADR 079): their
// badges, and what an instructor may not do to them, key off this.
const reflectionOf = (lesson) => competencies.data?.reflections?.[lesson.name]
const holdsReflection = (chapter) => (chapter.lessons || []).some((l) => reflectionOf(l))

const lessonRoute = (lesson) => {
	const [chapterNumber, lessonNumber] = lesson.number.split('.')
	return { name: 'Lesson', params: { courseName: props.courseName, chapterNumber, lessonNumber } }
}

const unlockRoute = (competency) => {
	const target = competency.unlock_lesson
	for (const ch of outline.data || []) {
		const found = (ch.lessons || []).find((l) => l.name === target)
		if (found) {
			const [chapterNumber, lessonNumber] = found.number.split('.')
			return { name: 'Lesson', params: { courseName: props.courseName, chapterNumber, lessonNumber } }
		}
	}
	return {
		name: 'CompetencySelfAssessment',
		params: { courseName: props.courseName, competency: competency.unlock_competency },
	}
}

const outline = createResource({
	url: 'seminary.seminary.utils.get_course_outline',
	cache: ['course_outline', props.courseName],
	params: {
		course: props.courseName,
		progress: props.getProgress,
	},
	auto: true,
})

// decisions/110 §5. Only editors are offered tools, and only tools that offer
// content selection. The tool's window is opened from the click (an await first
// would make it a blocked popup) and cut off from this page; when the editor
// comes back to this tab, the outline reloads to show what was added.
const ltiTools = createResource({
	url: 'seminary.lti.launch.tools_for_lessons',
	params: { course: props.courseName },
	auto: Boolean(props.allowEdit),
})
const deepLinkTools = computed(() =>
	(ltiTools.data || []).filter((t) => t.allow_deep_linking && t.deep_linking_url)
)
const startDeepLink = createResource({ url: 'seminary.lti.launch.start_deep_link' })
let reloadOnReturn = false
const onReturn = () => {
	if (reloadOnReturn && document.visibilityState === 'visible') {
		reloadOnReturn = false
		outline.reload()
	}
}
document.addEventListener('visibilitychange', onReturn)
window.addEventListener('focus', onReturn)
onBeforeUnmount(() => {
	document.removeEventListener('visibilitychange', onReturn)
	window.removeEventListener('focus', onReturn)
})
async function addFromTool(chapter, tool) {
	const win = window.open('', '_blank')
	try {
		const data = await startDeepLink.submit({ chapter: chapter.name, tool: tool.name })
		reloadOnReturn = true
		if (win) {
			win.opener = null
			win.location = data.url
		} else {
			window.location.assign(data.url)
		}
	} catch (e) {
		win?.close()
		toast.error(e?.messages?.[0] || __('The tool could not be opened.'))
	}
}

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
	onError(err) {
		toast.error(err.messages?.[0] || err.message || __('Could not delete the lesson'))
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
	onSuccess(data) {
		reloadAndFocus()
		toast.success(moveMessage.value || __('Lesson moved successfully'))
		moveMessage.value = ''

		const refiled = refiledMessage(data?.refiled)
		if (refiled) toast.info(refiled, { duration: 10 })
	},
	onError(err) {
		outline.reload()
		toast.error(err.messages?.[0] || err.message || __('Could not move the lesson'))
	},
})

const updateChapterIndex = createResource({
	url: 'seminary.seminary.api.update_chapter_index',
	makeParams(values) {
		return {
			course: props.courseName,
			chapter: values.chapter,
			idx: parseInt(values.idx, 10),
		}
	},
	onSuccess() {
		reloadAndFocus()
		toast.success(moveMessage.value || __('Chapter moved successfully'))
		moveMessage.value = ''

	},
	onError(err) {
		toast.error(err.messages?.[0] || err.message || __('Could not move the chapter'))
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
	onError(err) {
		toast.error(err.messages?.[0] || err.message || __('Could not delete the chapter'))
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

// `redirectToChapter` lived here. p008 F8 replaced a push to a `SCORMChapter`
// route that has never existed with a "not yet playable" toast; p009 §2.11
// replaces the toast with nothing, which is the correct end state. A SCORM
// chapter's SCOs *are* its lessons, so it navigates like any other chapter and
// no route is added.

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

const onChapterDragStart = (event, chapter, chapterIndex) => {
	if (!props.allowEdit) {
		return
	}
	if (event?.dataTransfer) {
		event.dataTransfer.effectAllowed = 'move'
		event.dataTransfer.setData('text/plain', chapter.name)
	}
	draggedChapter.value = {
		chapterName: chapter.name,
		sourceIndex: chapterIndex,
	}
}

const onChapterDragOver = (event) => {
	// Guarded on draggedChapter so a lesson dragged over a chapter drop zone
	// is not accepted there (and vice versa in onDragOver).
	if (!props.allowEdit || !draggedChapter.value) {
		return
	}
	if (event?.dataTransfer) {
		event.dataTransfer.dropEffect = 'move'
	}
}

const onChapterDrop = (event, targetIndex) => {
	if (!props.allowEdit || !draggedChapter.value) {
		return
	}
	event?.preventDefault?.()

	const { chapterName, sourceIndex } = draggedChapter.value

	// Removing the chapter first shifts every later slot down by one.
	let insertionIndex = targetIndex
	if (targetIndex > sourceIndex) {
		insertionIndex = targetIndex - 1
	}

	if (insertionIndex === sourceIndex) {
		draggedChapter.value = null
		return
	}

	updateChapterIndex.submit({
		chapter: chapterName,
		idx: insertionIndex + 1,
	})

	draggedChapter.value = null
}

const onChapterDragFinish = () => {
	draggedChapter.value = null
}

// Decision 103: every drag has a keyboard route through the Move menus. They
// call the same endpoints as a drop, with the 1-based position it would send.
const moveMessage = ref('')
const focusAfterMove = ref('')

async function reloadAndFocus() {
	await outline.reload()
	await nextTick()
	const [kind, name, fallback] = focusAfterMove.value.split('|')
	focusAfterMove.value = ''
	if (!kind) return
	const target =
		document.querySelector(`[data-move="${kind}:${CSS.escape(name)}"]`) ||
		(fallback && document.querySelector(`[data-move="chapter:${CSS.escape(fallback)}"]`))
	target?.focus()
}

// The menu opens with its first item focused however it is opened. reka-ui does that only for
// a key press; a click, and Enter from a screen reader in browse mode (which arrives as one),
// left the focus on the menu itself, one Down press short of the first move.
function focusFirstMove(event) {
	const trigger = event.currentTarget
	requestAnimationFrame(() => {
		if (trigger.getAttribute('aria-expanded') !== 'true') return
		const menu = document.getElementById(trigger.getAttribute('aria-controls'))
		menu?.querySelector('[role="menuitem"]')?.focus()
	})
}

function moveChapter(chapter, idx) {
	moveMessage.value = __('Moved to position {0}', [idx])
	focusAfterMove.value = `chapter|${chapter.name}`
	updateChapterIndex.submit({ chapter: chapter.name, idx })
}

function moveLesson(lesson, source, target, idx) {
	moveMessage.value = __('Moved to position {0} in {1}', [idx, target.chapter_title])
	focusAfterMove.value = `lesson|${lesson.name}|${target.name}`
	updateLessonIndex.submit({
		lesson: lesson.name,
		sourceChapter: source.name,
		targetChapter: target.name,
		idx,
	})
}

const chapterMoves = (index) => {
	const chapters = outline.data || []
	const chapter = chapters[index]
	const moves = []
	if (index > 0) moves.push({ label: __('Move up'), onClick: () => moveChapter(chapter, index) })
	if (index < chapters.length - 1) {
		moves.push({ label: __('Move down'), onClick: () => moveChapter(chapter, index + 2) })
	}
	return moves
}

const lessonMoves = (chapter, lessonIndex) => {
	const lessons = chapter.lessons || []
	const lesson = lessons[lessonIndex]
	const moves = []
	if (lessonIndex > 0) {
		moves.push({ label: __('Move up'), onClick: () => moveLesson(lesson, chapter, chapter, lessonIndex) })
	}
	if (lessonIndex < lessons.length - 1) {
		moves.push({
			label: __('Move down'),
			onClick: () => moveLesson(lesson, chapter, chapter, lessonIndex + 2),
		})
	}
	const others = (outline.data || []).filter((c) => c.name !== chapter.name && !c.is_scorm_package)
	if (others.length) {
		moves.push({
			group: __('Move to the end of'),
			items: others.map((c) => ({
				label: c.chapter_title,
				onClick: () => moveLesson(lesson, chapter, c, (c.lessons?.length || 0) + 1),
			})),
		})
	}
	return moves
}
</script>
