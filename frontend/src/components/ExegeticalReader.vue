<template>
	<div class="mt-2 flex flex-col gap-3">
		<!-- passages -->
		<div v-for="s in scripture" :key="s.resolved_ref"
			class="rounded-md border border-outline-gray-2 bg-surface-gray-1 p-3">
			<div class="mb-1 flex items-center gap-1 text-sm font-medium text-ink-gray-8">
				<BookOpen class="h-4 w-4" />{{ passages[s.resolved_ref]?.reference || s.display }}
			</div>
			<p class="whitespace-pre-line text-sm leading-relaxed text-ink-gray-7">
				{{ passages[s.resolved_ref]?.text || __('Passage text unavailable.') }}
			</p>
		</div>

		<!-- add a verse-anchored comment -->
		<div v-if="canComment" class="flex flex-col gap-2 sm:flex-row sm:items-center">
			<Input v-model="verseRef" type="text" :placeholder="__('Passage, e.g. Jn 3:16')" class="sm:w-40" />
			<Input v-model="commentText" type="text" :placeholder="__('Your insight on this passage…')"
				class="flex-1" @keyup.enter="postVerseComment" />
			<Button variant="solid" :loading="addComment.loading" @click="postVerseComment">
				<Send class="h-4 w-4" />
			</Button>
		</div>

		<!-- verse-anchored comments -->
		<div v-if="verseComments.length" class="flex flex-col gap-2">
			<div v-for="c in verseComments" :key="c.name" class="text-sm">
				<span class="mr-1 rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-7">
					📖 {{ c.anchor_ref }}
				</span>
				<span class="font-medium text-ink-gray-9">{{ c.author_name || c.author }}</span>
				<span class="prose-sm ml-1 text-ink-gray-8" v-html="c.content"></span>
			</div>
		</div>

		<!-- related across channels -->
		<div v-if="related.data?.length" class="rounded-md bg-surface-gray-1 p-2">
			<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Related across channels') }}</div>
			<ul class="flex flex-col gap-1">
				<li v-for="r in related.data" :key="r.name" class="flex items-center gap-2 text-sm text-ink-gray-8">
					<span class="truncate">{{ r.title || plain(r.content) }}</span>
					<span class="whitespace-nowrap text-xs text-ink-gray-5">· {{ r.channel_kind }}</span>
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Button, Input, createResource } from 'frappe-ui'
import { BookOpen, Send } from 'lucide-vue-next'

const props = defineProps({
	postName: { type: String, required: true },
	scripture: { type: Array, default: () => [] },
	canComment: { type: Boolean, default: true },
})

const passages = ref({})
const verseRef = ref(props.scripture[0]?.display || '')
const commentText = ref('')

const passageRes = createResource({ url: 'seminary.seminary.integrations.bible.passage_text' })
const thread = createResource({
	url: 'seminary.seminary.discipleship.feed_api.get_thread',
	params: { post: props.postName },
	auto: true,
})
const addComment = createResource({ url: 'seminary.seminary.discipleship.feed_api.add_comment' })
const related = createResource({
	url: 'seminary.seminary.discipleship.feed_api.related_posts',
	params: { post: props.postName },
	auto: true,
})

const verseComments = computed(() =>
	(thread.data?.comments || []).filter((c) => c.anchor_type === 'VerseRange'),
)

function plain(html) {
	return (html || '').replace(/<[^>]+>/g, '').slice(0, 60)
}
function postVerseComment() {
	if (!commentText.value.trim() || !verseRef.value.trim()) return
	addComment
		.submit({
			post: props.postName,
			content: commentText.value,
			anchor_type: 'VerseRange',
			anchor_data: JSON.stringify({ ref: verseRef.value }),
		})
		.then(() => { commentText.value = ''; thread.reload() })
		.catch((e) => window.frappe?.msgprint?.(e.messages?.[0] || 'Could not add comment.'))
}

onMounted(async () => {
	for (const s of props.scripture) {
		try {
			passages.value[s.resolved_ref] = await passageRes.submit({ resolved_ref: s.resolved_ref })
		} catch (_) {
			/* passage text unavailable (e.g. Bible API not configured) */
		}
	}
})
</script>
