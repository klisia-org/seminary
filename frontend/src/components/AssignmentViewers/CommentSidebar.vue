<template>
	<div class="border rounded-md bg-surface-white flex flex-col max-h-[calc(100vh-8rem)] sticky top-0">
		<div class="border-b px-3 py-2 font-semibold text-sm text-ink-gray-9 flex items-center justify-between">
			<span>
				{{ __('Comments') }}
				<span class="text-ink-gray-5 text-xs ml-1">({{ comments.length }})</span>
			</span>
		</div>

		<!-- New comment input (hidden for read-only viewers, e.g. the student) -->
		<div v-if="canComment" class="border-b p-3 space-y-2">
			<div v-if="pendingAnchor"
				class="text-xs text-ink-blue-2 bg-surface-blue-1 border border-outline-blue-1 px-2 py-1 rounded flex items-center justify-between">
				<span>{{ __('Anchor:') }} {{ anchorLabel(pendingAnchor) }}</span>
				<button class="underline ml-2" @click="$emit('cancel-pending')">{{ __('cancel') }}</button>
			</div>
			<textarea
				v-model="newText"
				rows="3"
				:placeholder="pendingAnchor ? __('Comment on this spot…') : __('Add a general comment…')"
				class="w-full border rounded-md p-2 text-sm focus:outline-none focus:ring focus:ring-outline-gray-modals"
			></textarea>
			<div class="flex justify-end">
				<Button
					variant="solid"
					size="sm"
					:loading="addLoading"
					:disabled="!newText.trim() || typeof onPost !== 'function'"
					@click="addComment"
				>
					{{ __('Post') }}
				</Button>
			</div>
		</div>

		<!-- Comment list -->
		<div class="overflow-y-auto flex-1">
			<div v-if="!comments.length" class="p-4 text-sm text-ink-gray-5 text-center">
				{{ __('No comments yet.') }}
			</div>
			<div
				v-for="c in comments"
				:key="c.name"
				:ref="(el) => setRowRef(el, c.name)"
				class="border-b p-3 text-sm cursor-pointer transition-colors"
				:class="{
					'opacity-60': c.resolved,
					'bg-surface-blue-1 border-l-2 border-l-outline-blue-3': activeCommentId === c.name,
					'hover:bg-surface-gray-2': activeCommentId !== c.name,
				}"
				@click="$emit('jump', c)"
				@mouseenter="$emit('active-changed', c.name)"
				@mouseleave="$emit('active-changed', null)"
			>
				<div class="flex items-center justify-between mb-1">
					<div class="font-medium text-ink-gray-7 truncate">{{ c.author_name }}</div>
					<div class="text-xs text-ink-gray-4 shrink-0 ml-2">{{ formatTime(c.creation) }}</div>
				</div>
				<div v-if="c.anchor_type !== 'General'" class="text-xs text-ink-blue-2 mb-1">
					📍 {{ anchorLabel(c) }}
				</div>
				<div
					v-if="editingId !== c.name"
					class="text-ink-gray-8 whitespace-pre-line"
					v-html="c.comment"
				></div>
				<div v-else @click.stop>
					<textarea
						v-model="editText"
						rows="3"
						class="w-full border rounded-md p-2 text-sm"
					></textarea>
					<div class="flex justify-end gap-2 mt-1">
						<Button variant="subtle" size="sm" @click.stop="cancelEdit">{{ __('Cancel') }}</Button>
						<Button variant="solid" size="sm" @click.stop="saveEdit(c)">{{ __('Save') }}</Button>
					</div>
				</div>
				<div v-if="canComment && editingId !== c.name" class="flex justify-end gap-1 mt-2">
					<Button v-if="c.author === currentUser" variant="ghost" size="sm" @click.stop="startEdit(c)">
						{{ __('Edit') }}
					</Button>
					<Button variant="ghost" size="sm" @click.stop="toggleResolved(c)">
						{{ c.resolved ? __('Reopen') : __('Resolve') }}
					</Button>
					<Button variant="ghost" size="sm" theme="red" @click.stop="deleteComment(c)">
						{{ __('Delete') }}
					</Button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, inject, watch, nextTick } from 'vue'
import { Button, call, toast } from 'frappe-ui'
import { timeAgo } from '@/utils'

const props = defineProps({
	submissionName: { type: String, default: '' },
	comments: { type: Array, default: () => [] },
	pendingAnchor: { type: Object, default: null },
	activeCommentId: { type: String, default: null },
	// Students view comments read-only; only graders post / resolve / delete.
	canComment: { type: Boolean, default: true },
	// Provided by SubmissionViewer so the anchor is read from its scope at
	// click time (not from a prop), avoiding a reactivity race.
	onPost: { type: Function, default: null },
})

const emit = defineEmits(['changed', 'cancel-pending', 'jump', 'active-changed'])

const user = inject('$user')
const currentUser = computed(() => user.data?.name)

const newText = ref('')
const addLoading = ref(false)
const editingId = ref(null)
const editText = ref('')

// Bring the active row into view when the activeCommentId changes from
// outside (e.g. the user hovered a pin on the canvas).
const rowRefs = new Map()
function setRowRef(el, name) {
	if (el) rowRefs.set(name, el)
	else rowRefs.delete(name)
}
watch(
	() => props.activeCommentId,
	async (name) => {
		if (!name) return
		await nextTick()
		const el = rowRefs.get(name)
		if (el && typeof el.scrollIntoView === 'function') {
			el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
		}
	}
)

async function addComment() {
	if (!newText.value.trim()) return
	if (typeof props.onPost !== 'function') return
	addLoading.value = true
	try {
		// SubmissionViewer owns `pendingAnchor` and resolves it at call time —
		// passing it through a prop introduced a reactivity race where the
		// anchor read here could lag the click that set it (image/PDF pins
		// silently became General → reproducibly lost).
		await props.onPost(newText.value)
		newText.value = ''
	} catch (err) {
		toast.error(err.messages?.[0] || err)
	} finally {
		addLoading.value = false
	}
}

function startEdit(c) {
	editingId.value = c.name
	// Strip HTML to plain text for the textarea
	const tmp = document.createElement('div')
	tmp.innerHTML = c.comment || ''
	editText.value = tmp.textContent || ''
}

function cancelEdit() {
	editingId.value = null
	editText.value = ''
}

async function saveEdit(c) {
	try {
		await call('seminary.seminary.api.update_submission_comment', {
			name: c.name,
			comment: editText.value,
		})
		editingId.value = null
		editText.value = ''
		emit('changed')
	} catch (err) {
		toast.error(err.messages?.[0] || err)
	}
}

async function toggleResolved(c) {
	try {
		await call('seminary.seminary.api.update_submission_comment', {
			name: c.name,
			resolved: c.resolved ? 0 : 1,
		})
		emit('changed')
	} catch (err) {
		toast.error(err.messages?.[0] || err)
	}
}

async function deleteComment(c) {
	if (!window.confirm(__('Delete this comment?'))) return
	try {
		await call('seminary.seminary.api.delete_submission_comment', { name: c.name })
		emit('changed')
	} catch (err) {
		toast.error(err.messages?.[0] || err)
	}
}

function anchorLabel(a) {
	switch (a?.anchor_type) {
		case 'Page':
			return `${__('page')} ${a.page || 1}`
		case 'Region':
			return (a.page || 1) > 1 ? `${__('page')} ${a.page}, ${__('pin')}` : __('pin')
		case 'TextRange':
			return __('text selection')
		case 'Timestamp':
			return `${__('at')} ${formatSeconds(a.timestamp_s)}`
		default:
			return __('general')
	}
}

function formatSeconds(s) {
	s = parseInt(s) || 0
	const m = Math.floor(s / 60)
	const r = (s % 60).toString().padStart(2, '0')
	return `${m}:${r}`
}

function formatTime(t) {
	try {
		return timeAgo(t)
	} catch {
		return ''
	}
}
</script>
