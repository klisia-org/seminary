<template>
	<Dialog
		v-model="show"
		:options="dialogOptions"
		:disableOutsideClickToClose="true"
	>
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
					<TextEditor
						:content="announcement.announcement"
						:fixedMenu="true"
						@change="(val) => (announcement.announcement = val)"
						editorClass="prose-sm py-2 px-2 min-h-[200px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Dialog, Input, TextEditor, createResource, toast } from 'frappe-ui'
import { computed, reactive, watch } from 'vue'

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
					return 'No students in this course'
				}
				if (!announcement.subject) {
					return 'Subject is required'
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
	if (!value) {
		resetAnnouncement()
	}
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