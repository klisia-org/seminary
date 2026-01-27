<template>
	<div>
		<Button v-if="!singleThread && props.type === 'multi'" class="float-right" @click="openTopicModal()">
			{{ __('New {0}').format(singularize(title)) }}
		</Button>
		<div class="text-xl font-semibold text-ink-gray-9">
			{{ __(title) }}
		</div>
	</div>
	<div v-if="loading && props.type === 'single'">
		<div class="text-center py-10">
			<span>Loading discussion...</span>
		</div>
	</div>
	<div v-if="props.type === 'single' && !loading">

		<div class="flex flex-col items-center justify-center">

		</div>
		<DiscussionModal v-model="showTopicModal" :title="title" :doctype="props.doctype" :docname="props.docname" />
		<DiscussionReplies v-if="currentTopic.value" :topic="currentTopic.value" :singleThread="true"
			v-model:showTopics="showTopics" />
	</div>
	<div v-if="topics.data?.length && !singleThread">
		<div v-if="showTopics" v-for="(topic, index) in topics.data" :key="index">
			<div @click="showReplies(topic)" class="flex items-center cursor-pointer py-5 w-full"
				:class="{ 'border-b': index + 1 != topics.data.length }">
				<UserAvatar :user="topic.user" size="2xl" class="mr-4" />
				<div>
					<div class="text-lg font-semibold mb-1 text-ink-gray-7">
						{{ topic.title }}
					</div>
					<div class="flex items-center text-ink-gray-5">
						<span>
							{{ topic.user.full_name }}
						</span>
						<span class="text-sm ml-3">
							{{ timeAgo(topic.creation) }}
						</span>
					</div>
				</div>
			</div>
		</div>
		<div v-else>
			<DiscussionReplies :topic="currentTopic" v-model:showTopics="showTopics" />
		</div>
	</div>
	<div v-else class="flex flex-col items-center justify-center border-2 border-dashed mt-5 py-8 rounded-md">
		<MessageSquareText class="w-7 h-7 text-ink-gray-4 stroke-1.5 mr-2" />
		<div class="">
			<div v-if="emptyStateTitle" class="font-medium mb-2">
				{{ __(emptyStateTitle) }}
			</div>
			<div class="text-ink-gray-5">
				{{ __(emptyStateText) }}
			</div>
		</div>
	</div>
	<DiscussionModal v-model="showTopicModal" :title="__('New {0}').format(title)" :doctype="props.doctype"
		:docname="props.docname" v-model:reloadTopics="topics" />
</template>
<script setup>
console.log('Discussions.vue script setup executed'); // Debugging: Ensure script is running

import { createResource, Button } from 'frappe-ui'
import UserAvatar from '@/components/UserAvatar.vue'
import { singularize, timeAgo } from '../utils'
import { ref, onMounted, inject, watch } from 'vue'
import DiscussionReplies from '@/components/DiscussionReplies.vue'
import DiscussionModal from '@/components/Modals/DiscussionModal.vue'
import { MessageSquareText } from 'lucide-vue-next'
import { getScrollContainer } from '@/utils/scrollContainer'
import { initSocket } from '@/socket'; // Import the socket initializer

const showTopics = ref(true)
const currentTopic = ref(null)
const user = inject('$user')
const showTopicModal = ref(false)
const loading = ref(true); // Add a loading state
const socketConnected = ref(false); // Track socket connection status

// Initialize the socket directly
const socket = initSocket(); // Use the default namespace or specify one if needed

if (!socket) {
	console.error('Socket connection not initialized in Discussions.vue.');
} else {
	console.log('Socket connection initialized in Discussions.vue:', socket);

	// Add event listeners for debugging and connection tracking
	socket.on('connect', () => {
		console.log('Socket connected:', socket.id);
		socketConnected.value = true; // Mark socket as connected
	});

	socket.on('connect_error', (error) => {
		console.error('Socket connection error:', error);
	});

	socket.on('disconnect', (reason) => {
		console.warn('Socket disconnected:', reason);
		socketConnected.value = false; // Mark socket as disconnected
	});
}

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
	emptyStateTitle: {
		type: String,
		default: '',
	},
	emptyStateText: {
		type: String,
		default: 'Start a discussion',
	},
	singleThread: {
		type: Boolean,
		default: false,
	},
	scrollToBottom: {
		type: Boolean,
		default: false,
	},
	type: {
		type: String,
		default: 'single', // Default to multi-topic mode but can be single for assignment feedback
	},
})

// Watch for socket connection and execute onMounted logic once connected
watch(socketConnected, (isConnected) => {
	if (isConnected) {
		console.log('Socket is connected, proceeding with onMounted logic.');
		executeOnMountedLogic();
	}
});

const executeOnMountedLogic = () => {
	console.log('onMounted logic executed'); // Debugging: Ensure this is called
	console.log('Props:', props); // Debugging: Log props

	if (user.data) {
		if (props.type === 'single') {
			console.log('Single-topic mode detected'); // Debugging
			singleTopicResource.reload(); // Trigger the resource to fetch the single topic
			console.log('Topic', currentTopic.value)
		} else {
			loading.value = false; // Immediately stop loading for multi-topic mode
		}
		topics.reload();
	}

	socket.on('new_discussion_topic', (data) => {
		topics.refresh();
	});

	if (props.scrollToBottom) {
		setTimeout(() => {
			scrollToEnd();
		}, 100);
	}
};

const scrollToEnd = () => {
	let scrollContainer = getScrollContainer()
	scrollContainer.scrollTop = scrollContainer.scrollHeight
}

const singleTopicResource = createResource({
	url: 'seminary.seminary.utils.ensure_single_topic',
	cache: false, // No need to cache this since it's a one-time call
	makeParams() {
		return {
			doctype: props.doctype,
			docname: props.docname,
			title: props.title,
		};
	},
	onSuccess(data) {
		console.log('Ensure single topic response:', data); // Debugging
		if (data) {
			currentTopic.value = data; // Set the single topic as the current topic
			console.log('Current topic set:', currentTopic.value); // Debugging
			showTopics.value = false; // Automatically show replies for the single topic
			loading.value = false; // Mark loading as complete
		}
		console.log('Changed loading to:', loading.value); // Debugging
	},
	onError(error) {
		console.error('Error ensuring single topic:', error); // Log the error
		loading.value = false; // Ensure loading is stopped even on error
	},
});


const topics = createResource({
	url: 'seminary.seminary.utils.get_discussion_topics',
	cache: ['topics', props.doctype, props.docname],
	makeParams() {
		return {
			doctype: props.doctype,
			docname: props.docname,
			single_thread: props.singleThread,
		}
	},
})

const showReplies = (topic) => {
	showTopics.value = false
	currentTopic.value = topic
}

const openTopicModal = () => {
	showTopicModal.value = true
}
</script>
