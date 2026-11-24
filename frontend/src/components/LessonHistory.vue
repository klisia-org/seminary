<!--
	The lesson's saved versions, in the lesson editor (decision 109 §3).

	<LessonHistory v-model="open" :lesson="lessonName" @restore="restore" />

	Lists editing sessions (who, when), opens one read-only, and emits `restore` with the
	session's { content, instructor_content }. The editor saves what it restores, which
	is itself a new version, so a restore can be undone the same way.
-->
<template>
	<Dialog v-model="show" :options="{ title: __('Lesson history'), size: '5xl' }">
		<template #body-content>
			<div class="grid gap-4 md:grid-cols-[16rem,minmax(0,1fr)]">
				<div>
					<p v-if="history.loading" class="text-sm text-ink-gray-5">{{ __('Loading…') }}</p>
					<p v-else-if="!sessions.length" class="text-sm text-ink-gray-5">
						{{ __('No saved versions yet.') }}
					</p>
					<ul v-else class="max-h-[60vh] space-y-1 overflow-y-auto" :aria-label="__('Saved versions')">
						<li v-for="s in sessions" :key="s.version">
							<button type="button"
								class="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-surface-gray-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
								:class="selected === s.version ? 'bg-surface-gray-3' : ''"
								:aria-current="selected === s.version ? 'true' : undefined"
								@click="open(s)">
								<span class="block font-medium text-ink-gray-9">{{ when(s.saved_at) }}</span>
								<span class="block text-ink-gray-6">{{ s.owner_name }}</span>
								<span v-if="s.current" class="block text-xs text-ink-gray-5">{{ __('Current version') }}</span>
							</button>
						</li>
					</ul>
				</div>
				<div class="min-w-0">
					<p v-if="!selected" class="text-sm text-ink-gray-5">
						{{ __('Choose a version to see the lesson as it was then.') }}
					</p>
					<p v-else-if="version.loading" class="text-sm text-ink-gray-5">{{ __('Loading…') }}</p>
					<div v-show="selected && !version.loading"
						class="max-h-[60vh] overflow-y-auto rounded-md border border-outline-gray-2 p-4">
						<div :id="holderId"
							class="ProseMirror prose prose-sm max-w-none !whitespace-normal"></div>
					</div>
				</div>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button @click="show = false">{{ __('Close') }}</Button>
				<Button variant="solid" :disabled="!canRestore" @click="restore">
					{{ __('Restore this version') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Button, Dialog, createResource } from 'frappe-ui'
import EditorJS from '@editorjs/editorjs'
import { getEditorTools } from '@/utils'
import { autoDirection } from '@/utils/textDirection'
import dayjs from '@/utils/dayjs'

const props = defineProps({
	lesson: { type: String, default: '' },
	course: { type: String, default: '' },
})
const show = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['restore'])

const holderId = `lesson-history-${Math.random().toString(36).slice(2, 8)}`
const selected = ref('')
const selectedSession = ref(null)
let preview = null

const history = createResource({
	url: 'seminary.seminary.lesson_history.get_lesson_history',
	makeParams: () => ({ lesson: props.lesson }),
})
const sessions = computed(() => history.data || [])

const version = createResource({
	url: 'seminary.seminary.lesson_history.get_lesson_version',
	makeParams: () => ({ lesson: props.lesson, version: selected.value }),
})

const canRestore = computed(
	() => Boolean(selected.value && version.data && !version.loading && !selectedSession.value?.current)
)

const when = (value) => dayjs(value).format('D MMM YYYY, HH:mm')

watch(show, (value) => {
	if (!value) return
	selected.value = ''
	selectedSession.value = null
	if (props.lesson) history.reload()
})

const blocksOf = (json) => {
	try {
		const data = JSON.parse(json || '{}')
		return Array.isArray(data.blocks) ? data : { blocks: [] }
	} catch {
		return { blocks: [] }
	}
}

async function open(session) {
	selected.value = session.version
	selectedSession.value = session
	const data = await version.reload()
	await nextTick()
	const holder = document.getElementById(holderId)
	if (!holder) return
	if (preview?.destroy) preview.destroy()
	holder.replaceChildren()
	autoDirection(holder)
	preview = new EditorJS({
		holder: holderId,
		tools: getEditorTools(props.course),
		data: blocksOf(data?.content),
		readOnly: true,
		minHeight: 0,
	})
}

function restore() {
	if (!canRestore.value) return
	emit('restore', {
		content: version.data.content || '',
		instructor_content: version.data.instructor_content || '',
		saved_at: version.data.saved_at,
	})
	show.value = false
}
</script>
