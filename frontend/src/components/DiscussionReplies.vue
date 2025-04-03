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

		<div v-for="(reply, index) in replies.data">
			<div
				class="py-3"
				:class="{ 'border-b': index + 1 != replies.data.length }"
			>
				<div class="flex items-center justify-between mb-2">
					<div class="flex items-center text-ink-gray-5">
						<UserAvatar :user="reply.user" class="mr-2" />
						<span>
							{{ reply.user.full_name }}
						</span>
						<span class="text-sm ml-2">
							{{ timeAgo(reply.creation) }}
						</span>
					</div>
					<Dropdown
						v-if="user.data.name == reply.owner && !reply.editable"
						:options="[
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
						]"
					>
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
				<TextEditor
					:content="reply.reply"
					@change="(val) => (reply.reply = val)"
					:editable="reply.editable || false"
					:fixedMenu="reply.editable || false"
					:editorClass="
						reply.editable
							? 'ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none'
							: 'prose-sm'
					"
				/>
			</div>
		</div>

		<TextEditor
			v-if="renderEditor"
			class="mt-5"
			:content="newReply"
			:mentions="mentionUsers"
			@change="(val) => (newReply = val)"
			placeholder="Type your reply here..."
			:fixedMenu="true"
			editorClass="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none border border-outline-gray-2 rounded-b-md min-h-[7rem] py-1 px-2"
		/>
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
import { ref, inject, onMounted, onUnmounted } from 'vue'
import { createToast } from '../utils'
import { initSocket } from '@/socket'; // Import the socket initializer

const socket = initSocket(); // Initialize the socket once
const isLoadingUsers = ref(false); // Add a loading state
const showTopics = defineModel('showTopics')
const newReply = ref('')
const user = inject('$user')
console.log('User data:', user.data.is_student); // Debugging log
const mentionUsers = ref([])
const renderEditor = ref(false)

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

onMounted(() => {
  console.log('DiscussionReplies mounted. Registering socket listeners.');
  console.log('Topic received:', props.topic.name); // Debugging log
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
  )

  socket.on('publish_message', (data) => {
		replies.reload()
	})
	socket.on('update_message', (data) => {
		replies.reload()
	})
	socket.on('delete_message', (data) => {
		replies.reload()
	})

  // Cleanup listeners on unmount
//   onUnmounted(() => {
//     console.log('DiscussionReplies unmounted. Cleaning up socket listeners.');
//     socket.off('publish_message', reloadReplies);
//     socket.off('update_message', reloadReplies);
//     socket.off('delete_message', reloadReplies);
//   });
});

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
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Discussion Reply',
				reply: newReply.value,
				topic: props.topic.name,
			},
		}
	},
})

const fetchMentionUsers = () => {
	console.log('User data:', user.data); // Debugging log
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
			validate() {
				if (!newReply.value) {
					return 'Reply cannot be empty'
				}
			},
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
