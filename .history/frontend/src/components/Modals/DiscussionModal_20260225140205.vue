<template>
	<Dialog v-model="showing2" :disableOutsideClickToClose="true" :options="dialogOptions">
		<template #body-content>
			<div class="discussion-dialog flex flex-col gap-4 max-h-[70vh] overflow-y-auto">
				<div>
					<FormControl v-model="topic.title" :label="__('Title')" type="text" />
				</div>
				<div>
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Details') }}
					</div>
					<TextEditor :content="topic.reply" @change="(val) => (topic.reply = val)" :editable="true"
						:fixedMenu="true"
						editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]" />
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, FormControl, TextEditor, createResource, toast } from 'frappe-ui'
import { computed, reactive, watch, ref, onMounted, onUnmounted } from 'vue'
import { singularize } from '@/utils'
import { on } from 'events'


const showing2 = ref(false)


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
	showing: {
		type: Boolean,
		required: true,
	},
})
console.log('DiscussionModal props:', props) // Debugging: Check if props are received correctly
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

onMounted(() => {
	console.log('DiscussionModal mounted with props:', props) // Debugging: Check when the component is mounted
	if (props.showing) {
		showing2.value = true
	}
})

onUnmounted(() => {
	console.log('DiscussionModal unmounted') // Debugging: Check when the component is unmounted
	showing2.value = false
})

watch(showing2, async (value) => {
	console.log('DiscussionModal show changed:', value) // Debugging: Check when the modal is shown or hidden
	if (value) {
		console.log('DiscussionModal opened, resetting topic and preparing editor') // Debugging
		await nextTick()
		setTimeout(() => {
			editorReady.value = true
		}, 150)
	} else {
		editorReady.value = false
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