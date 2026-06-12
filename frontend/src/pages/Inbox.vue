<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<div class="flex items-center gap-3">
			<h2 class="text-xl font-bold text-ink-gray-8">
				{{ __('Inbox') }}
			</h2>
			<span
				v-if="unread > 0"
				class="rounded-full bg-surface-blue-2 px-2 py-0.5 text-xs font-medium text-ink-blue-3"
			>
				{{ unread }} {{ __('unread') }}
			</span>
		</div>
		<div class="flex items-center gap-2">
			<Button
				v-if="canCompose"
				variant="solid"
				:label="__('Compose')"
				@click="openCompose"
			>
				<template #prefix><SquarePen class="size-4" /></template>
			</Button>
			<Button
				v-if="unread > 0 && box === 'inbox'"
				variant="subtle"
				:label="__('Mark all read')"
				@click="markAllRead"
			/>
		</div>
	</header>

	<div class="mx-auto w-full max-w-3xl px-5 pt-4">
		<div class="flex flex-wrap items-center gap-2">
			<div class="flex rounded-md border border-outline-gray-2 p-0.5">
				<button
					v-for="b in ['inbox', 'sent']"
					:key="b"
					class="rounded px-3 py-1 text-sm"
					:class="
						box === b
							? 'bg-surface-gray-3 font-medium text-ink-gray-8'
							: 'text-ink-gray-5'
					"
					@click="box = b"
				>
					{{ b === 'inbox' ? __('Received') : __('Sent') }}
				</button>
			</div>
			<select
				v-model="channelFilter"
				class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
			>
				<option value="">{{ __('All channels') }}</option>
				<option v-for="c in channels" :key="c" :value="c">{{ __(c) }}</option>
			</select>
			<select
				v-model="categoryFilter"
				class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
			>
				<option value="">{{ __('All categories') }}</option>
				<option v-for="c in categories" :key="c" :value="c">{{ __(c) }}</option>
			</select>
			<label
				v-if="box === 'inbox'"
				class="flex items-center gap-1.5 text-sm text-ink-gray-7"
			>
				<input v-model="unreadOnly" type="checkbox" class="rounded" />
				{{ __('Unread only') }}
			</label>
		</div>
	</div>

	<div v-if="inbox.loading && !inbox.data" class="p-5 text-ink-gray-5">
		{{ __('Loading messages...') }}
	</div>

	<div
		v-else-if="!messages.length"
		class="mt-32 md:mt-52 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5"
	>
		<InboxIcon class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No messages') }}</div>
		<div class="leading-5">
			{{ __('Messages from the seminary will appear here.') }}
		</div>
	</div>

	<div v-else class="mx-auto w-full max-w-3xl space-y-3 p-5">
		<article
			v-for="msg in messages"
			:key="msg.name"
			class="cursor-pointer rounded-lg border border-outline-gray-1 bg-surface-white p-4 shadow-sm"
			@click="toggle(msg)"
		>
			<header class="flex items-baseline justify-between gap-3">
				<div class="flex min-w-0 items-center gap-2">
					<span
						v-if="box === 'inbox' && !msg.read_at"
						class="size-2 shrink-0 rounded-full bg-surface-blue-3"
					></span>
					<h3
						class="truncate text-base text-ink-gray-8"
						:class="box === 'inbox' && !msg.read_at ? 'font-semibold' : 'font-medium'"
					>
						{{ msg.subject || __('(no subject)') }}
					</h3>
				</div>
				<span class="shrink-0 text-xs text-ink-gray-5">
					{{ timeAgo(msg.sent_at || msg.creation) }}
				</span>
			</header>
			<div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-gray-5">
				<span v-if="box === 'inbox' && msg.sender_name">
					{{ __('From') }} {{ msg.sender_name }}
				</span>
				<span v-if="box === 'sent' && msg.person_name">
					{{ __('To') }} {{ msg.person_name }}
				</span>
				<span class="rounded bg-surface-gray-2 px-1.5 py-0.5">{{ __(msg.channel) }}</span>
				<span v-if="msg.category" class="rounded bg-surface-gray-2 px-1.5 py-0.5">
					{{ __(msg.category) }}
				</span>
				<span v-if="box === 'sent'" class="rounded bg-surface-gray-2 px-1.5 py-0.5">
					{{ __(msg.status) }}
				</span>
				<span v-if="msg.reference_doctype" class="truncate">
					{{ __(msg.reference_doctype) }} · {{ msg.reference_name }}
				</span>
			</div>
			<div
				v-if="expanded.has(msg.name)"
				class="prose prose-sm mt-3 max-w-none text-ink-gray-7"
				v-html="msg.message"
				@click.stop
			></div>
			<div
				v-if="expanded.has(msg.name) && canReply(msg)"
				class="mt-3"
				@click.stop
			>
				<Button variant="subtle" size="sm" :label="__('Reply')" @click="openReply(msg)">
					<template #prefix><Reply class="size-4" /></template>
				</Button>
			</div>
		</article>
	</div>

	<Dialog v-model="showCompose" :options="composeDialogOptions">
		<template #body-content>
			<div class="flex flex-col gap-4">
				<div v-if="scope.data?.courses?.length">
					<div class="mb-1.5 text-sm text-ink-gray-5">{{ __('Course (optional filter)') }}</div>
					<select
						v-model="compose.course"
						class="w-full rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
					>
						<option value="">{{ __('All my courses') }}</option>
						<option v-for="c in scope.data.courses" :key="c.value" :value="c.value">
							{{ c.label }}
						</option>
					</select>
				</div>
				<div>
					<div class="mb-1.5 flex items-center justify-between text-sm text-ink-gray-5">
						<span>
							{{ __('To') }} <span class="text-ink-red-3">*</span>
							<span v-if="selectedCount" class="ml-1 text-xs">
								({{ selectedCount }} {{ __('selected') }})
							</span>
						</span>
						<label
							v-if="scope.data?.staff && studentCount"
							class="flex items-center gap-1.5 text-sm text-ink-gray-7"
						>
							<input v-model="compose.allStudents" type="checkbox" class="rounded" />
							{{ __('All students') }} ({{ studentCount }})
						</label>
					</div>
					<Input
						:value="recipientSearch"
						:debounce="200"
						type="text"
						class="mb-1.5"
						:placeholder="__('Search recipients...')"
						@input="(v) => (recipientSearch = v)"
					/>
					<div
						class="max-h-56 space-y-1 overflow-y-auto rounded-md border border-outline-gray-2 p-2"
					>
						<div v-if="scope.loading" class="text-sm text-ink-gray-5">
							{{ __('Loading...') }}
						</div>
						<Disclosure
							v-for="group in recipientGroups"
							:key="group.name + '|' + expandGroups"
							v-slot="{ open }"
							:defaultOpen="expandGroups"
							as="div"
						>
							<DisclosureButton
								class="flex w-full items-center gap-1.5 rounded px-1 py-1 text-left hover:bg-surface-gray-1"
							>
								<ChevronRight
									class="size-3.5 text-ink-gray-5"
									:class="{ 'rotate-90 transform': open }"
								/>
								<span
									class="text-xs font-medium uppercase tracking-wide text-ink-gray-5"
								>
									{{ __(group.name) }}
								</span>
								<span class="text-xs text-ink-gray-4">({{ group.items.length }})</span>
								<span
									v-if="groupSelectedCount(group)"
									class="ml-auto rounded-full bg-surface-blue-2 px-1.5 text-xs text-ink-blue-3"
								>
									{{ groupSelectedCount(group) }}
								</span>
							</DisclosureButton>
							<DisclosurePanel class="pl-5">
								<label
									v-for="r in group.items"
									:key="r.person"
									class="flex items-center gap-2 rounded px-1 py-0.5 text-sm text-ink-gray-8"
									:class="
										compose.allStudents && r.kind === 'Student'
											? 'opacity-50'
											: 'cursor-pointer hover:bg-surface-gray-1'
									"
								>
									<input
										v-model="compose.recipients"
										type="checkbox"
										:value="r.person"
										class="rounded"
										:disabled="compose.allStudents && r.kind === 'Student'"
									/>
									<span class="truncate">
										{{ r.label }}
										<span v-if="r.courses?.length" class="text-xs text-ink-gray-5">
											— {{ r.courses.join(', ') }}
										</span>
									</span>
								</label>
							</DisclosurePanel>
						</Disclosure>
						<div
							v-if="!scope.loading && !recipientGroups.length"
							class="text-sm text-ink-gray-5"
						>
							{{
								scope.data?.recipients?.length
									? __('No recipients match your search.')
									: __('No recipients available.')
							}}
						</div>
					</div>
				</div>
				<div>
					<div class="mb-1.5 text-sm text-ink-gray-5">{{ __('Subject') }}</div>
					<Input type="text" v-model="compose.subject" />
				</div>
				<div>
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Message') }} <span class="text-ink-red-3">*</span>
					</div>
					<RichTextEditor
						:id="'compose-' + composeKey"
						:content="composeInitialMessage"
						:teleport="false"
						:uploadFunction="privateImageUpload"
						:placeholder="__('Write your message...')"
						@change="onComposeMessage"
					/>
				</div>
				<div>
					<div class="mb-1.5 text-sm text-ink-gray-5">{{ __('Attachments') }}</div>
					<FileUploader
						:upload-args="{ folder: 'Home/Attachments', private: 1 }"
						:validate-file="validateFileSize"
						@success="onAttach"
					>
						<template #default="{ uploading, progress, openFileSelector }">
							<Button
								variant="outline"
								:loading="uploading"
								:label="
									uploading
										? __('Uploading {0}%').format(progress)
										: __('Attach file')
								"
								@click="openFileSelector"
							>
								<template #prefix><Paperclip class="size-4" /></template>
							</Button>
						</template>
					</FileUploader>
					<ul v-if="compose.attachments.length" class="mt-2 space-y-1">
						<li
							v-for="(a, i) in compose.attachments"
							:key="a.file_url"
							class="flex items-center gap-2 text-sm text-ink-gray-7"
						>
							<Paperclip class="size-3.5 shrink-0 text-ink-gray-4" />
							<span class="truncate">{{ a.file_name }}</span>
							<button
								class="ml-auto text-ink-gray-4 hover:text-ink-red-3"
								:title="__('Remove')"
								@click="compose.attachments.splice(i, 1)"
							>
								<X class="size-4" />
							</button>
						</li>
					</ul>
				</div>
			</div>
		</template>
	</Dialog>

	<Dialog v-model="showReply" :options="replyDialogOptions">
		<template #body-content>
			<div class="mb-1.5 text-sm text-ink-gray-5">
				{{ __('Reply to') }} {{ replyTo?.sender_name }}
			</div>
			<textarea
				v-model="replyText"
				rows="5"
				class="w-full rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-8 focus:ring-0"
				:placeholder="__('Write your reply...')"
			></textarea>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { Button, Dialog, Input, FileUploader, createResource } from 'frappe-ui'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue'
import {
	Inbox as InboxIcon,
	SquarePen,
	Reply,
	ChevronRight,
	Paperclip,
	X,
} from 'lucide-vue-next'
import { createToast, timeAgo, validateFileSize } from '@/utils'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { useFileUpload } from '../../node_modules/frappe-ui/src/utils/useFileUpload'

// Inline images in a portal message must upload PRIVATE (they're attached to the
// recipient's log and served by doc-permission, never made public).
function privateImageUpload(file) {
	return useFileUpload().upload(file, { private: true })
}

const user = inject('$user')

const box = ref('inbox')
const channelFilter = ref('')
const categoryFilter = ref('')
const unreadOnly = ref(false)
const expanded = ref(new Set())
const channels = ['In-App', 'Email', 'SMS', 'WhatsApp', 'Telegram']
const categories = ['Transactional', 'Academic', 'Community', 'Promotional', 'Emergency']

const inbox = createResource({
	url: 'seminary.seminary.comms.get_my_inbox',
	makeParams: () => ({
		channel: channelFilter.value || null,
		category: categoryFilter.value || null,
		unread_only: unreadOnly.value ? 1 : 0,
		box: box.value,
	}),
	auto: true,
})

watch([channelFilter, categoryFilter, unreadOnly, box], () => inbox.fetch())

const messages = computed(() => inbox.data?.messages || [])
const unread = computed(() => inbox.data?.unread || 0)
const canCompose = computed(() =>
	Boolean(
		user?.data?.is_student ||
			user?.data?.is_evaluator ||
			user?.data?.is_instructor ||
			user?.data?.is_moderator
	)
)

const markRead = createResource({ url: 'seminary.seminary.comms.mark_inbox_read' })
const markAll = createResource({
	url: 'seminary.seminary.comms.mark_all_inbox_read',
	onSuccess: () => inbox.fetch(),
})

function toggle(msg) {
	const open = new Set(expanded.value)
	if (open.has(msg.name)) {
		open.delete(msg.name)
	} else {
		open.add(msg.name)
		if (box.value === 'inbox' && !msg.read_at) {
			msg.read_at = new Date().toISOString()
			if (inbox.data) inbox.data.unread = Math.max(0, inbox.data.unread - 1)
			markRead.submit({ name: msg.name })
		}
	}
	expanded.value = open
}

function markAllRead() {
	markAll.submit()
}

// ----- compose -----

const showCompose = ref(false)
const composeKey = ref(0)
// Drives the recipient filter. The field updates this via @input (frappe-ui's
// <Input> only emits update:modelValue on change/blur, not while typing), with
// frappe-ui's own :debounce coalescing the re-renders.
const recipientSearch = ref('')
const compose = reactive({
	course: '',
	recipients: [],
	allStudents: false,
	subject: '',
	message: '',
	attachments: [],
})

const scope = createResource({
	url: 'seminary.seminary.comms.get_my_messaging_scope',
	makeParams: () => ({ course: compose.course || null }),
})

watch(
	() => compose.course,
	() => {
		compose.recipients = []
		compose.allStudents = false
		scope.fetch()
	}
)

// Recipients grouped by `group` (role / Instructors / Students / Support …).
// Group headings are alphabetical (Students last, as the catch-all roster);
// every group's members are sorted alphabetically by name.
const recipientGroups = computed(() => {
	const all = scope.data?.recipients || []
	const q = recipientSearch.value.trim().toLowerCase()
	const matched = q
		? all.filter((r) => (r.label || '').toLowerCase().includes(q))
		: all
	const buckets = {}
	for (const r of matched) {
		const g = r.group || 'Other'
		;(buckets[g] = buckets[g] || []).push(r)
	}
	const names = Object.keys(buckets)
		.filter((n) => n !== 'Students')
		.sort((a, b) => a.localeCompare(b))
	if (buckets['Students']) names.push('Students')
	return names.map((name) => ({
		name,
		items: [...buckets[name]].sort((a, b) =>
			(a.label || '').localeCompare(b.label || '')
		),
	}))
})

// Collapse groups by default so a large roster stays light in the DOM; expand
// when the user is searching (filtered set is small) or the list is short.
const expandGroups = computed(
	() => !!recipientSearch.value || (scope.data?.recipients?.length || 0) <= 40
)

function groupSelectedCount(group) {
	if (compose.allStudents && group.name === 'Students') return group.items.length
	return group.items.filter((r) => compose.recipients.includes(r.person)).length
}

// The editor owns its content; we only seed it once per compose (via the keyed
// `composeInitialMessage`) and read edits back, so typing elsewhere never feeds
// reactive content back into the editor.
const composeInitialMessage = ref('')
function onComposeMessage(val) {
	compose.message = val
}

function onAttach(file) {
	compose.attachments.push({
		file_url: file.file_url,
		file_name: file.file_name || file.file_url,
	})
}

const studentCount = computed(
	() => (scope.data?.recipients || []).filter((r) => r.kind === 'Student').length
)
const selectedCount = computed(
	() => compose.recipients.length + (compose.allStudents ? studentCount.value : 0)
)

function openCompose() {
	compose.course = ''
	compose.recipients = []
	compose.allStudents = false
	compose.subject = ''
	compose.message = ''
	composeInitialMessage.value = ''
	compose.attachments = []
	recipientSearch.value = ''
	composeKey.value += 1
	scope.fetch()
	showCompose.value = true
}

const sendMessage = createResource({ url: 'seminary.seminary.comms.send_portal_message' })

const composeDialogOptions = computed(() => ({
	title: __('New Message'),
	size: 'lg',
	actions: [
		{
			label: __('Send'),
			variant: 'solid',
			onClick: (close) => submitCompose(close),
		},
		{
			label: __('Cancel'),
			variant: 'text',
			onClick: (close) => close(),
		},
	],
}))

// ----- reply -----

const showReply = ref(false)
const replyTo = ref(null)
const replyText = ref('')
const replyRes = createResource({
	url: 'seminary.seminary.comms.reply_portal_message',
	onSuccess: () => {
		showReply.value = false
		createToast({
			title: __('Reply sent'),
			icon: 'check',
			iconClasses: 'text-ink-green-3',
		})
		if (box.value === 'sent') inbox.fetch()
	},
	onError: (err) => {
		const msg = err?.messages?.join(', ') || err?.message
		createToast({
			title: msg || __('Could not send reply.'),
			icon: 'alert-circle',
			iconClasses: 'text-ink-red-3',
		})
	},
})

// Only person-to-person messages (Community) can be replied to; broadcasts /
// system notices have no individual sender within your messaging scope.
function canReply(msg) {
	return box.value === 'inbox' && msg.category === 'Community' && msg.sender_name
}

function openReply(msg) {
	replyTo.value = msg
	replyText.value = ''
	showReply.value = true
}

const replyDialogOptions = computed(() => ({
	title: __('Reply'),
	actions: [
		{ label: __('Send'), variant: 'solid', onClick: () => submitReply() },
	],
}))

function submitReply() {
	if (!replyText.value.trim()) {
		createToast({ title: __('Write a reply.'), icon: 'alert-circle' })
		return
	}
	replyRes.submit({ in_reply_to: replyTo.value.name, message: replyText.value })
}

function submitCompose(close) {
	const hasText = compose.message.replace(/<[^>]*>/g, '').trim()
	if ((!compose.recipients.length && !compose.allStudents) || !hasText) {
		createToast({ title: __('Pick a recipient and write a message.'), icon: 'alert-circle' })
		return
	}
	sendMessage
		.submit({
			recipients: compose.recipients,
			all_students: compose.allStudents ? 1 : 0,
			subject: compose.subject,
			message: compose.message,
			course: compose.course || null,
			attachments: compose.attachments,
		})
		.then((r) => {
			close()
			createToast({
				title: __('Message sent to {0} recipient(s)').format(r?.sent ?? selectedCount.value),
				icon: 'check',
				iconClasses: 'text-ink-green-3',
			})
			if (box.value === 'sent') inbox.fetch()
		})
}
</script>

<style scoped>
.prose :deep(p) {
	margin: 0 0 0.5rem;
}
</style>
