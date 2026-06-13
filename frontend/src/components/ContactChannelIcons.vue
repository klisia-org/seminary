<template>
	<template v-for="item in (channels || [])" :key="item.channel">
		<!-- Public deep-link (e.g. WhatsApp wa.me) — opens the external app. -->
		<a
			v-if="item.mode === 'weblink'"
			:href="item.url"
			target="_blank"
			rel="noopener"
			:title="item.channel_name"
			:class="iconClass"
		>
			<span v-html="item.svg_icon" class="inline-block h-full w-full [&>svg]:h-full [&>svg]:w-full"></span>
		</a>
		<!-- In-App — go to the portal inbox compose, pre-targeting the instructor. -->
		<router-link
			v-else-if="item.mode === 'inapp'"
			:to="{ name: 'Inbox', query: { compose: 1, recipient: item.person, ...(course ? { course } : {}) } }"
			:title="__('Send a message')"
			:class="iconClass"
		>
			<span v-html="item.svg_icon" class="inline-block h-full w-full [&>svg]:h-full [&>svg]:w-full"></span>
		</router-link>
		<!-- Logged comms send over the channel's provider. -->
		<button
			v-else-if="item.mode === 'comms'"
			type="button"
			@click.stop.prevent="openContact(item)"
			:title="__('Message on {0}').format(item.channel_name)"
			:class="iconClass"
		>
			<span v-html="item.svg_icon" class="inline-block h-full w-full [&>svg]:h-full [&>svg]:w-full"></span>
		</button>
	</template>

	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<p class="mb-3 text-sm text-ink-gray-6">
				{{ __('Sent through {0} and logged in your inbox — the instructor receives it there.').format(active?.channel_name || '') }}
			</p>
			<FormControl
				type="textarea"
				:rows="5"
				v-model="message"
				:placeholder="__('Write your message…')"
			/>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Dialog, FormControl, createResource } from 'frappe-ui'
import { createToast } from '@/utils'

const props = defineProps({
	// Action descriptors from get_instructor_contact_channels.
	channels: { type: Array, default: () => [] },
	// The Instructor docname — required to route a logged comms message.
	instructor: { type: String, required: true },
	// Optional Course Schedule to scope the inbox compose / pass as context.
	course: { type: String, default: '' },
	iconClass: {
		type: String,
		default:
			'inline-flex items-center justify-center h-4 w-4 text-ink-gray-4 hover:text-ink-blue-link transition-colors',
	},
})

const show = ref(false)
const active = ref(null)
const message = ref('')

function openContact(item) {
	active.value = item
	message.value = ''
	show.value = true
}

const sendRes = createResource({
	url: 'seminary.seminary.comms.contact_instructor',
	onSuccess: () => {
		show.value = false
		createToast({
			title: __('Message sent — see it in your inbox.'),
			icon: 'check',
			iconClasses: 'text-ink-green-3',
		})
	},
	onError: (err) => {
		const msg = err?.messages?.join(', ') || err?.message
		createToast({
			title: msg || __('Could not send the message.'),
			icon: 'alert-circle',
			iconClasses: 'text-ink-red-3',
		})
	},
})

function submit(close) {
	if (!message.value.trim()) {
		createToast({ title: __('Write a message first.'), icon: 'alert-circle' })
		return
	}
	sendRes.submit({
		instructor: props.instructor,
		channel: active.value.channel,
		message: message.value.trim(),
	})
}

const dialogOptions = computed(() => ({
	title: __('Message {0}').format(active.value?.channel_name || ''),
	actions: [
		{
			label: __('Send'),
			variant: 'solid',
			loading: sendRes.loading,
			onClick: (close) => submit(close),
		},
		{ label: __('Cancel'), variant: 'text', onClick: (close) => close() },
	],
}))
</script>
