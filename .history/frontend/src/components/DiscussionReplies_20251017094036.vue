<template>
	<div class="mt-6">
		<div v-if="!singleThread" class="flex items-center mb-5">
			<Button variant="outline" @click="showTopics = true">
				<template #icon>
					<ChevronLeft class="w-5 h-5 stroke-1.5 text-ink-gray-7" />
				</template>
			</Button>
			<span class="text-lg font-semibold ml-2 text-ink-gray-9">
				{{ topic.title }}
			</span>
		</div>

		<div v-for="(reply, index) in replies.data" :key="reply.name">
			<div class="py-3" :class="{ 'border-b': index + 1 != replies.data.length }">
				<div class="flex items-center justify-between mb-2">
					<div class="flex items-center text-ink-gray-5">
						<UserAvatar :user="reply.user" class="mr-2" />
						<span>
							{{ reply.user?.full_name || reply.owner }}
						</span>
						<span class="text-sm ml-2">
							{{ timeAgo(reply.creation) }}
						</span>
					</div>
					<Dropdown v-if="user.data.name == reply.owner && !reply.editable" :options="[
						{
							label: 'Edit',
							onClick() {
								reply.editable = true
							},
						},
						{
							label: 'Delete',
							onClick() {
								deleteReply(reply)
							},
						},
					]">
						<template v-slot="{ open }">
							<MoreHorizontal class="w-4 h-4 stroke-1.5 cursor-pointer" />
						</template>
					</Dropdown>
					<div v-if="reply.editable">
						<Button variant="ghost" @click="postEdited(reply)">
							{{ __('Post') }}
						</Button>
						<Button variant="ghost" @click="reply.editable = false">
							{{ __('Discard') }}
						</Button>
					</div>
				</div>
				<div v-if="reply.editable">
					<TextEditor :content="reply.reply" @change="(val) => (reply.reply = val)" :editable="true"
						:fixedMenu="true"
						:editorClass="'ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none'" />
				</div>
				<div v-else class="formatted-reply">
					<div v-html="reply.reply" class="p-2"></div>
				</div>
			</div>
		</div>

		<textarea v-show="renderEditor" class="mt-5" :value="newReply" @input="(value) => (newReply = value)"
			placeholder="Type your reply here..." :fixedMenu="true" />
		<div class="flex justify-between mt-2">
			<span> </span>
			<Button @click="postReply()">
				<span>
					{{ __('Post') }}
				</span>
			</Button>
		</div>
	</div>
</template>
<script setup>
import { createResource, TextEditor, Button, Dropdown } from 'frappe-ui'
import { timeAgo } from '../utils'
import UserAvatar from '@/components/UserAvatar.vue'
import { ChevronLeft, MoreHorizontal } from 'lucide-vue-next'
import { ref, inject, onMounted, onUnmounted, toRaw, watch } from 'vue'
import { createToast } from '../utils'
import { initSocket } from '@/socket'; // Import the socket initializer

const socket = initSocket(); // Initialize the socket once
const isLoadingUsers = ref(false); // Add a loading state
const showTopics = defineModel('showTopics')
const newReply = ref('')
const user = inject('$user')
console.log('User data:', user.data.is_student); // Debugging log
const mentionUsers = ref([])
const renderEditor = ref(false); // Keep it false initially

const props = defineProps({
	topic: {
		type: Object,
		required: true,
	},
	singleThread: {
		type: Boolean,
		default: false,
	},
})
const editorKey = `editor-${props.topic.name}`; // Set the key based on the topic name

onMounted(() => {
	console.log('DiscussionReplies mounted. Registering socket listeners.');
	console.log('Topic received:', props.topic.name); // Debugging log

	// Call fetchMentionUsers to ensure renderEditor is updated
	fetchMentionUsers();

	replies.reload(
		{},
		{
			onSuccess(data) {
				console.log('Replies fetched successfully:', data); // Debugging log
			},
			onError(error) {
				console.error('Error fetching replies:', error); // Debugging log
			},
		}
	);

	socket.on('publish_message', (data) => {
		replies.reload();
	});
	socket.on('update_message', (data) => {
		replies.reload();
	});
	socket.on('delete_message', (data) => {
		replies.reload();
	});

	// Defer rendering the editor until the component is fully mounted
	renderEditor.value = true;
	console.log('TextEditor renderEditor set to true.');
	console.log('Editor key:', editorKey); // Debugging log

});

watch(
	props.topic,
	(newTopic, oldTopic) => {
		if (newTopic.name !== oldTopic.name) {
			editorKey.value = `editor-${newTopic.name}`; // Update key when topic changes
			console.log('Editor key updated:', editorKey.value);
		}
	}
);

watch(
	newReply,
	(value) => {
		console.log('New reply value:', value); // Debugging log
		if (!value) {
			console.warn('Reply is empty. Ensure the input is being updated correctly.');
		}
	}
);

watch(
	renderEditor,
	(value) => {
		if (value) {
			console.log('TextEditor is now visible and ready for initialization.');
		}
	}
);

const replies = createResource({
	url: 'seminary.seminary.utils.get_discussion_replies',
	auto: false, // Do not fetch automatically
	makeParams() {
		return {
			topic: props.topic.name,
		};
	},
	onSuccess(data) {
		console.log('Replies fetched successfully:', data); // Debugging log
	},
	onError(error) {
		console.error('Error fetching replies:', error); // Debugging log
	},
});


const newReplyResource = createResource({
	url: 'seminary.seminary.utils.insert_discussion_reply',
	makeParams(values) {
		return {
			reply: newReply.value, // Use newReply.value directly
			topic: props.topic.name,

		}
	},
	onSuccess(data) {
		console.log('Discussion saved successfully:', data); // Debugging log
	},
	onError(error) {
		console.error('Error inserting replies:', error); // Debugging log
	},
});

const fetchMentionUsers = () => {
	console.log('User data in fetchMentionUsers:', user.data); // Debugging log
	if (user.data?.is_student) {
		renderEditor.value = true;
	} else {
		isLoadingUsers.value = true; // Set loading state
		allUsers.reload(
			{},
			{
				onSuccess(data) {
					mentionUsers.value = Object.values(data).map((user) => {
						return {
							value: user.name,
							label: user.full_name,
						};
					});
					renderEditor.value = true; // Render the editor after users are loaded
					isLoadingUsers.value = false; // Reset loading state
				},
				onError(err) {
					console.error('Error fetching mention users:', err);
					isLoadingUsers.value = false; // Reset loading state
				},
			}
		);
	}
};

const postReply = () => {
	newReplyResource.submit(
		{},
		{

			onSuccess() {
				newReply.value = ''
				replies.reload()
			},
			onError(err) {
				createToast({
					title: 'Error',
					text: err.messages?.[0] || err,
					icon: 'x',
					iconClasses: 'bg-surface-red-5 text-ink-white rounded-md p-px',
					position: 'top-center',
					timeout: 10,
				})
			},
		}
	)
}

const editReplyResource = createResource({
	url: 'frappe.client.set_value',
	makeParams(values) {
		return {
			doctype: 'Discussion Reply',
			name: values.name,
			fieldname: 'reply',
			value: values.reply,
		}
	},
})

const postEdited = (reply) => {
	editReplyResource.submit(
		{
			name: reply.name,
			reply: reply.reply,
		},
		{
			validate() {
				if (!reply.reply) {
					return 'Reply cannot be empty'
				}
			},
			onSuccess() {
				reply.editable = false
				replies.reload()
			},
		}
	)
}

const deleteReplyResource = createResource({
	url: 'frappe.client.delete',
	makeParams(values) {
		return {
			doctype: 'Discussion Reply',
			name: values.name,
		}
	},
})

const deleteReply = (reply) => {
	deleteReplyResource.submit(
		{
			name: reply.name,
		},
		{
			onSuccess() {
				replies.reload()
			},
		}
	)
}

const allUsers = createResource({
	url: 'seminary.seminary.utils.get_all_users',

})
console.log('All Users:', allUsers) // Debugging log
</script>