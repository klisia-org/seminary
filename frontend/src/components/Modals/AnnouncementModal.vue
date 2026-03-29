<template>
	<Dialog v-model="show" :options="dialogOptions" :disableOutsideClickToClose="true">
		<template #body-content>
			<div class="announcement-dialog flex flex-col gap-4 max-h-[70vh] overflow-y-auto">
				<div class="">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Subject') }}
						<span class="text-ink-red-3">*</span>
					</div>
					<Input type="text" v-model="announcement.subject" />
				</div>
				<div class="">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Reply To') }}
					</div>
					<Input type="text" v-model="announcement.replyTo" />
				</div>
				<div class="mb-4">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Announcement') }}
					</div>
					<div v-if="editorReady && editor" class="border rounded-md">
						<TextEditorFixedMenu
							class="w-full overflow-x-auto rounded-t-md border-b border-outline-gray-modals"
							:buttons="true"
						/>
						<EditorContent :editor="editor" class="prose-sm py-2 px-2 min-h-[200px]" />
					</div>
					<div v-else class="border rounded-md py-2 px-2 min-h-[200px] bg-surface-gray-3 text-ink-gray-4 text-sm">
						{{ __('Loading editor...') }}
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Dialog, Input, TextEditorFixedMenu, createResource, toast } from 'frappe-ui'
import { Editor, EditorContent } from '@tiptap/vue-3'
import { getTextEditorExtensions } from '@/utils/textEditorFull'
import { computed, provide, reactive, ref, watch, onBeforeUnmount } from 'vue'

const show = defineModel()

const props = defineProps({
	cs: {
		type: String,
		required: true,
	},
	students: {
		type: Array,
		required: true,
	},
})

const editorReady = ref(false)
const editor = ref(null)

provide('editor', editor)

const announcement = reactive({
	subject: '',
	replyTo: '',
	announcement: '',
})

const resetAnnouncement = () => {
	announcement.subject = ''
	announcement.replyTo = ''
	announcement.announcement = ''
}

const initEditor = () => {
	destroyEditor()
	editor.value = new Editor({
		content: announcement.announcement || '',
		extensions: getTextEditorExtensions({
			placeholder: __('Write your announcement...'),
		}),
		onUpdate: ({ editor: e }) => {
			announcement.announcement = e.getHTML()
		},
	})
}

const destroyEditor = () => {
	if (editor.value) {
		editor.value.destroy()
		editor.value = null
	}
}

const announcementResource = createResource({
	url: 'frappe.core.doctype.communication.email.make',
	makeParams(values) {
		return {
			recipients: props.students.join(', '),
			cc: announcement.replyTo,
			subject: announcement.subject,
			content: announcement.announcement,
			doctype: 'Course Schedule',
			name: props.cs,
			send_email: 1,
		}
	},
})

const makeAnnouncement = (close) => {
	announcementResource.submit(
		{},
		{
			validate() {
				if (!props.students.length) {
					return __('No students in this course')
				}
				if (!announcement.subject) {
					return __('Subject is required')
				}
			},
			onSuccess() {
				show.value = false
				resetAnnouncement()
				close()
				toast.success(__('Announcement has been sent successfully'))
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const handleCancel = (close) => {
	show.value = false
	resetAnnouncement()
	close?.()
}

watch(show, (value) => {
	if (value) {
		setTimeout(() => {
			initEditor()
			editorReady.value = true
		}, 150)
	} else {
		editorReady.value = false
		destroyEditor()
		resetAnnouncement()
	}
})

onBeforeUnmount(() => {
	destroyEditor()
})

const dialogOptions = computed(() => ({
	title: __('Make an Announcement'),
	size: 'xl',
	actions: [
		{
			label: __('Submit'),
			variant: 'solid',
			onClick: (close) => makeAnnouncement(close),
		},
		{
			label: __('Cancel'),
			variant: 'text',
			onClick: (close) => handleCancel(close),
		},
	],
}))
</script>
