<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
		<template #actions>
			<Button variant="solid" :loading="saving" :label="__('Save')" @click="save" />
		</template>
	</PageHeader>

	<div class="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-6">
		<p v-if="loaded && !canEdit" class="rounded-lg bg-surface-amber-1 px-4 py-3 text-sm text-ink-amber-3">
			{{ __('Only this lesson\'s maintainers and the Seminary Manager can edit it.') }}
		</p>
		<section class="rounded-xl border border-outline-gray-2 bg-surface-white p-6 space-y-4">
			<FormControl v-model="form.title" :label="__('Title')" :required="true" size="lg" :disabled="!canEdit" />
			<FormControl v-model="form.tags" :label="__('Tags')" :disabled="!canEdit"
				:description="__('Words instructors search by, separated by commas.')" />
			<FormControl type="textarea" v-model="form.preview" :label="__('Course page summary')" :rows="2" :disabled="!canEdit" />
		</section>

		<section class="rounded-xl border border-outline-gray-2 bg-surface-white p-6">
			<h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Lesson content') }}</h2>
			<p class="mt-0.5 text-sm text-ink-gray-5">
				{{ __('Quizzes, assignments, exams and discussions belong to each section, so add them to the lesson in the section after placing it.') }}
			</p>
			<div id="library-lesson-content"
				class="mt-3 md:pl-14 ProseMirror prose prose-sm max-w-none !whitespace-normal py-3"></div>
		</section>

		<section class="rounded-xl border border-outline-gray-2 bg-surface-white p-6">
			<h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Instructor notes') }}</h2>
			<p class="mt-0.5 text-sm text-ink-gray-5">{{ __('Private — never shown to students') }}</p>
			<div id="library-lesson-notes"
				class="mt-3 md:pl-14 ProseMirror prose prose-sm max-w-none !whitespace-normal py-3"></div>
		</section>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Breadcrumbs, Button, call, FormControl, toast } from 'frappe-ui'
import EditorJS from '@editorjs/editorjs'
import PageHeader from '@/components/PageHeader.vue'
import { getEditorTools, updateDocumentTitle } from '@/utils'

const ACTIVITY_TYPES = ['quiz', 'exam', 'assignment', 'discussion', 'discussionActivity', 'discussionactivity', 'oralActivity']

const props = defineProps({
	name: { type: String, required: true },
})
const router = useRouter()
const form = reactive({ title: '', tags: '', preview: '' })
const saving = ref(false)
const loaded = ref(false)
const canEdit = ref(true)
let content = null
let notes = null

const isNew = computed(() => props.name === 'new')

const parse = (value) => {
	try {
		return JSON.parse(value || '{"blocks": []}')
	} catch {
		return { blocks: [] }
	}
}

const editor = (holder, data, readOnly) =>
	new EditorJS({ holder, tools: getEditorTools(), data, readOnly, minHeight: 80 })

onMounted(async () => {
	let doc = {}
	if (!isNew.value) {
		doc = await call('seminary.seminary.library.get', { name: props.name })
		form.title = doc.title || ''
		form.tags = doc.tags || ''
		form.preview = doc.preview || ''
		canEdit.value = Boolean(doc.can_edit)
	}
	content = editor('library-lesson-content', parse(doc.content), !canEdit.value)
	notes = editor('library-lesson-notes', parse(doc.instructor_content), !canEdit.value)
	loaded.value = true
})

const save = async () => {
	if (!form.title.trim()) {
		toast.error(__('Add a title first.'))
		return
	}
	saving.value = true
	try {
		const data = await content.save()
		if (data.blocks.some((b) => ACTIVITY_TYPES.includes(b.type))) {
			toast.error(__('Remove the quizzes, assignments, exams and discussions: they are added in each section.'))
			return
		}
		const out = await call('seminary.seminary.library.save', {
			name: isNew.value ? null : props.name,
			title: form.title,
			tags: form.tags,
			preview: form.preview,
			content: JSON.stringify(data),
			instructor_content: JSON.stringify(await notes.save()),
		})
		toast.success(__('Saved'))
		if (isNew.value) router.replace({ name: 'LibraryLessonForm', params: { name: out.name } })
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The lesson could not be saved.'))
	} finally {
		saving.value = false
	}
}

const breadcrumbs = computed(() => [
	{ label: __('Lesson Library'), route: { name: 'LessonLibrary' } },
	{ label: isNew.value ? __('New library lesson') : form.title || props.name },
])

updateDocumentTitle(computed(() => ({ title: form.title || __('Library lesson') })))
</script>
