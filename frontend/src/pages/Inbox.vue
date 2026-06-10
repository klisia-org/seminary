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
					<div
						class="max-h-48 space-y-0.5 overflow-y-auto rounded-md border border-outline-gray-2 p-2"
					>
						<div v-if="scope.loading" class="text-sm text-ink-gray-5">
							{{ __('Loading...') }}
						</div>
						<template v-for="kind in recipientKinds" :key="kind">
							<div
								class="px-1 pt-1 text-xs font-medium uppercase tracking-wide text-ink-gray-5"
							>
								{{ __(kind === 'Instructor' ? 'Instructors' : 'Students') }}
							</div>
							<label
								v-for="r in recipientsByKind(kind)"
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
						</template>
						<div
							v-if="!scope.loading && !scope.data?.recipients?.length"
							class="text-sm text-ink-gray-5"
						>
							{{ __('No recipients available.') }}
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
					<textarea
						v-model="compose.message"
						rows="6"
						class="w-full rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-8 focus:ring-0"
						:placeholder="__('Write your message...')"
					></textarea>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { Button, Dialog, Input, createResource } from 'frappe-ui'
import { Inbox as InboxIcon, SquarePen } from 'lucide-vue-next'
import { createToast, timeAgo } from '@/utils'

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
const compose = reactive({
	course: '',
	recipients: [],
	allStudents: false,
	subject: '',
	message: '',
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

const recipientKinds = computed(() => {
	const kinds = new Set((scope.data?.recipients || []).map((r) => r.kind))
	return ['Instructor', 'Student'].filter((k) => kinds.has(k))
})

function recipientsByKind(kind) {
	return (scope.data?.recipients || []).filter((r) => r.kind === kind)
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

function submitCompose(close) {
	if ((!compose.recipients.length && !compose.allStudents) || !compose.message.trim()) {
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
