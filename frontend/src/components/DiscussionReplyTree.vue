<!-- Replies to one discussion post, nested three levels deep (decisions/097 §2).
     Deeper answers are shown flat at the third level. Each reply can be answered
     in place; the attachment uploader stays on the post's own reply box. -->
<template>
	<div class="replies pl-4 border-l border-outline-gray-2">
		<div v-for="item in rows" :key="item.reply.name || item.reply.creation" class="mb-3"
			:style="{ marginLeft: `${item.depth * 1.25}rem` }"
			:class="item.depth ? 'border-l border-outline-gray-1 pl-3' : ''">
			<div class="flex items-center gap-2">
				<span class="font-semibold">{{ item.reply.member_name || item.reply.owner }}</span>
				<Badge v-if="item.reply.by_instructor" theme="blue" size="sm">{{ __('Instructor') }}</Badge>
				<Badge v-if="item.reply.is_new" theme="orange" size="sm">{{ __('New') }}</Badge>
			</div>
			<div class="text-sm text-ink-gray-5 mt-1 mb-2">
				{{ formatDate(item.reply.reply_dt || item.reply.creation) }}
			</div>
			<SafeHtml :html="item.reply.reply" class="text-sm" />
			<a v-if="item.reply.reply_attach" :href="item.reply.reply_attach" target="_blank"
				class="text-ink-blue-3 underline">
				{{ __('View Attachment') }}
			</a>
			<div v-if="item.reply.name" class="mt-1">
				<button v-if="answering !== item.reply.name" type="button"
					class="text-xs text-ink-gray-5 hover:text-ink-gray-8" @click="startAnswer(item.reply.name)">
					{{ __('Reply') }}
				</button>
				<div v-else class="mt-2 space-y-2">
					<LightEditor :id="`answer-${item.reply.name}`" :key="`answer-${item.reply.name}`"
						:placeholder="__('Write a reply...')" @change="(val) => (draft = val)" />
					<div class="flex justify-end gap-2">
						<Button variant="subtle" size="sm" @click="answering = null">{{ __('Cancel') }}</Button>
						<Button variant="solid" size="sm" :loading="posting" @click="postAnswer(item.reply.name)">
							{{ __('Post Reply') }}
						</Button>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, call, toast } from 'frappe-ui'
import dayjsModule from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import LightEditor from '@/components/LightEditor.vue'

const dayjs = dayjsModule
dayjs.extend(relativeTime)

const MAX_DEPTH = 2 // three levels: 0, 1, 2

const props = defineProps({
	submission: { type: String, required: true },
	replies: { type: Array, default: () => [] },
})
const emit = defineEmits(['posted'])

const answering = ref(null)
const draft = ref('')
const posting = ref(false)

// Depth-first, oldest first, so each answer sits under what it answers.
const rows = computed(() => {
	const byParent = {}
	const names = new Set(props.replies.map((r) => r.name).filter(Boolean))
	for (const reply of props.replies) {
		// An answer whose reply is gone is shown as answering the post.
		const parent = reply.in_reply_to && names.has(reply.in_reply_to) ? reply.in_reply_to : ''
		;(byParent[parent] ||= []).push(reply)
	}
	const out = []
	const walk = (parent, depth) => {
		for (const reply of byParent[parent] || []) {
			out.push({ reply, depth: Math.min(depth, MAX_DEPTH) })
			if (reply.name) walk(reply.name, depth + 1)
		}
	}
	walk('', 0)
	return out
})

const formatDate = (value) => {
	if (!value) return ''
	return dayjs(String(value).split('.')[0]).fromNow()
}

const startAnswer = (name) => {
	answering.value = name
	draft.value = ''
}

const postAnswer = async (inReplyTo) => {
	if (!draft.value || draft.value === '<p><br></p>') {
		toast.error(__('Please write a reply before posting.'))
		return
	}
	posting.value = true
	try {
		await call('seminary.seminary.api.reply_to_discussion_submission', {
			submission: props.submission,
			reply: draft.value,
			in_reply_to: inReplyTo,
		})
		toast.success(__('Reply posted successfully'))
		answering.value = null
		draft.value = ''
		emit('posted')
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || __('Could not post the reply.'))
	} finally {
		posting.value = false
	}
}
</script>
