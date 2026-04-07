<template>
	<div class="border-b px-4 py-4">
		<div class="flex items-center justify-between mb-2">
			<div class="text-sm font-semibold text-ink-gray-7">
				{{ __('My Notes') }}
			</div>
			<Button size="sm" variant="solid" @click="saveNote(currentContent)"
				:disabled="!isDirty" :loading="insertNote.loading || updateNote.loading">
				{{ __('Save') }}
			</Button>
		</div>
		<TextEditor
			:content="noteText"
			:editable="true"
			:fixedMenu="true"
			:placeholder="__('Take notes for quick revision...')"
			editorClass="prose-sm max-w-none min-h-[8rem] max-h-[20rem] overflow-y-auto"
			@change="onNoteChange"
			:bubbleMenu="false"
		/>
		<div v-if="saved" class="text-xs text-ink-gray-4 mt-1">
			{{ __('Saved') }}
		</div>
	</div>
</template>

<script setup>
import { ref, watch, inject, onBeforeUnmount } from 'vue'
import { TextEditor, Button, createResource, toast } from 'frappe-ui'

const props = defineProps({
	lesson: { type: String, required: true },
	courseName: { type: String, required: true },
})
console.log("Notes props: ", props.lesson, props.courseName)
const user = inject('$user')
const noteText = ref('')
const noteName = ref(null)
const currentContent = ref('')
const isDirty = ref(false)
const saved = ref(false)
let debounceTimer = null
let isLoadingContent = false

const fetchNote = createResource({
	url: 'seminary.seminary.doctype.seminary_lesson_note.seminary_lesson_note.get_note',
	onSuccess(data) {
		isLoadingContent = true
		if (data) {
			noteName.value = data.name
			noteText.value = data.note || ''
			currentContent.value = data.note || ''
		} else {
			noteName.value = null
			noteText.value = ''
			currentContent.value = ''
		}
		isDirty.value = false
		// Allow a tick for the editor to process the content change
		setTimeout(() => { isLoadingContent = false }, 500)
	},
})

const insertNote = createResource({
	url: 'frappe.client.insert',
	makeParams() {
		return {
			doc: {
				doctype: 'Seminary Lesson Note',
				lesson: props.lesson,
				course: props.courseName,
				member: user.data?.name,
				note: currentContent.value,
			},
		}
	},
	onSuccess(data) {
		noteName.value = data.name
		isDirty.value = false
		showSaved()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Failed to save note'))
	},
})

const updateNote = createResource({
	url: 'frappe.client.set_value',
	makeParams() {
		return {
			doctype: 'Seminary Lesson Note',
			name: noteName.value,
			fieldname: 'note',
			value: currentContent.value,
		}
	},
	onSuccess() {
		isDirty.value = false
		showSaved()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Failed to save note'))
	},
})

function onNoteChange(val) {
	if (isLoadingContent) return
	currentContent.value = val
	isDirty.value = true
	saved.value = false
	clearTimeout(debounceTimer)
	debounceTimer = setTimeout(() => saveNote(val), 2000)
}

function saveNote() {
	const content = currentContent.value
	if (!content || content === '<p></p>') return
	clearTimeout(debounceTimer)
	if (noteName.value) {
		updateNote.submit()
	} else {
		insertNote.submit()
	}
}

function showSaved() {
	saved.value = true
	setTimeout(() => { saved.value = false }, 3000)
}

watch(
	() => props.lesson,
	(newLesson) => {
		if (newLesson) {
			noteName.value = null
			noteText.value = ''
			currentContent.value = ''
			isDirty.value = false
			saved.value = false
			fetchNote.submit({ lesson: newLesson })
		}
	},
	{ immediate: true }
)

onBeforeUnmount(() => {
	clearTimeout(debounceTimer)
})
</script>
