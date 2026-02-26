<template>
	<Dialog v-model="show" :disableOutsideClickToClose="true" :options="dialogOptions">
		<template #body-content>
			<div class="discussion-dialog flex flex-col gap-4 max-h-[70vh] overflow-y-auto">
				<div>
					<FormControl v-model="topic.title" :label="__('Title')" type="text" />
				</div>
				<div class="text-sm text-ink-gray-5">
					{{ __('Make the title descriptive, so others may understand the topic.') }}
				</div>
				<div>
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Details') }}
					</div>
					<RichTextInput :id="'discussion-reply'" :content="topic.reply"
						@change="(val) => (topic.reply = val)" :editable="true" />
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, FormControl, createResource, toast } from 'frappe-ui'
import { computed, reactive, watch } from 'vue'
import { singularize } from '@/utils'
import RichTextInput from '@/components/RichTextInput.vue'
import { Divide } from 'lucide-vue-next'

const show = defineModel()
const topics = defineModel('reloadTopics')

const props = defineProps({
	title: {
		type: String,
		required: true,
	},
	doctype: {
		type: String,
		required: true,
	},
	docname: {
		type: String,
		required: true,
	},
})

const topic = reactive({
	title: '',
	reply: '',
})

const resetTopic = () => {
	topic.title = ''
	topic.reply = ''
}

const topicResource = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Discussion Topic',
				reference_doctype: props.doctype,
				reference_docname: props.docname,
				title: topic.title,
			},
		}
	},
})

const replyResource = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Discussion Reply',
				topic: values.topic,
				reply: topic.reply,
			},
		}
	},
})

const submitTopic = (close) => {
	topicResource.submit(
		{},
		{
			validate() {
				if (!topic.title) {
					return __('Title cannot be empty.')
				}
				if (!topic.reply) {
					return __('Reply cannot be empty.')
				}
			},
			onSuccess(data) {
				replyResource.submit(
					{
						topic: data.name,
					},
					{
						onSuccess() {
							show.value = false
							topics.value.reload()
							resetTopic()
							close()
						},
					}
				)
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const handleCancel = (close) => {
	show.value = false
	resetTopic()
	close?.()
}

watch(show, (value) => {
	if (!value) {
		resetTopic()
	}
})

const dialogOptions = computed(() => ({
	title: singularize(props.title),
	size: '2xl',
	actions: [
		{
			label: __('Post'),
			variant: 'solid',
			onClick: (close) => submitTopic(close),
		},
		{
			label: __('Cancel'),
			variant: 'text',
			onClick: (close) => handleCancel(close),
		},
	],
}))
</script>
<style scoped>
/* Darken the backdrop overlay */
:deep(.dialog-overlay),
:deep([data-dialog-overlay]),
:deep(.fixed.inset-0) {
	background-color: rgba(0, 0, 0, 0.6) !important;
	backdrop-filter: blur(4px) !important;
}

/* Add stronger shadow and border to the dialog panel */
:deep(.dialog-content),
:deep([data-dialog-content]),
:deep(.relative.bg-white),
:deep(.rounded-xl) {
	box-shadow:
		0 25px 50px -12px rgba(0, 0, 0, 0.4),
		0 0 0 1px rgba(0, 0, 0, 0.1) !important;
	border: 1px solid #e5e7eb !important;
}
</style>