<template>
	<div v-if="defense.data?.required" class="mt-6 rounded-lg border p-4 space-y-3 text-left">
		<div class="flex items-center justify-between gap-2">
			<div class="font-semibold text-ink-gray-9">{{ __('Oral defense') }}</div>
			<Badge :theme="defense.data.status === 'Done' ? 'green' : 'orange'">
				{{ defense.data.status === 'Done' ? __('Done') : __('Incomplete') }} · {{ __(defense.data.status) }}
			</Badge>
		</div>
		<div class="text-xs text-ink-gray-5 space-x-3">
			<span v-if="defense.data.opened_on">{{ __('Opened {0}').format(formatWhen(defense.data.opened_on)) }}</span>
			<span v-if="defense.data.due">{{ __('Due {0}').format(formatWhen(defense.data.due)) }}</span>
			<span v-if="defense.data.done_on">{{ __('Done {0}').format(formatWhen(defense.data.done_on)) }}</span>
		</div>

		<div v-if="defense.data.status === 'Waiting for Release'" class="flex items-center gap-2">
			<p class="flex-1 text-sm text-ink-gray-6">
				{{ __('The student cannot start until you release the questions. The time to answer counts from then.') }}
			</p>
			<Button variant="solid" @click="release">{{ __('Release questions') }}</Button>
		</div>
		<p v-else-if="defense.data.status === 'Waiting for Questions'" class="text-sm text-ink-gray-6">
			{{ __('No questions yet. They are being written, or add your own below.') }}
		</p>

		<div v-for="(q, i) in defense.data.questions" :key="q.name" class="rounded border p-3 space-y-2"
			:class="q.follow_up_of ? 'ml-6' : ''">
			<template v-if="editing === q.name">
				<FormControl v-model="draft.question" type="textarea" rows="2" :label="__('Question')" />
				<FormControl v-model="draft.passage" type="textarea" rows="2" :label="__('Passage')" />
				<FormControl v-model="draft.good_answer" type="textarea" rows="2"
					:label="__('What a good answer addresses')" />
				<div class="flex gap-2">
					<Button variant="solid" size="sm" @click="save(q.name)">{{ __('Save') }}</Button>
					<Button size="sm" @click="editing = null">{{ __('Cancel') }}</Button>
				</div>
			</template>
			<template v-else>
				<div class="flex items-start gap-2 text-sm">
					<span class="font-medium">{{ q.follow_up_of ? __('Follow-up') : i + 1 }}.</span>
					<span class="flex-1">{{ q.question }}</span>
					<Badge v-if="q.source === 'Suggested'" theme="blue">{{ __('Suggested') }}</Badge>
					<template v-if="defense.data.editable && !q.follow_up_of">
						<Button size="sm" variant="ghost" @click="edit(q)">{{ __('Edit') }}</Button>
						<Button size="sm" variant="ghost" @click="remove(q.name)">{{ __('Remove') }}</Button>
					</template>
				</div>
				<div v-if="q.passage" class="text-xs text-ink-gray-6">{{ __('Passage') }}: {{ q.passage }}</div>
				<div v-if="q.good_answer" class="text-xs text-ink-gray-6">
					{{ __('A good answer addresses') }}: {{ q.good_answer }}
				</div>
				<div v-if="q.follow_up_state === 'Timed Out'" class="text-xs text-ink-gray-5">
					{{ __('No follow-up: none was ready within 20 seconds.') }}
				</div>
				<OralPlayer v-if="q.recording" :recording="q.recording" :question="q.question" />
				<div v-else-if="q.answer_text" class="rounded bg-surface-gray-2 p-2 text-sm whitespace-pre-wrap">
					{{ q.answer_text }}
				</div>
			</template>
		</div>

		<div v-if="defense.data.editable">
			<template v-if="editing === 'new'">
				<FormControl v-model="draft.question" type="textarea" rows="2" :label="__('Question')" />
				<FormControl v-model="draft.passage" type="textarea" rows="2" :label="__('Passage')" />
				<FormControl v-model="draft.good_answer" type="textarea" rows="2"
					:label="__('What a good answer addresses')" />
				<div class="mt-2 flex gap-2">
					<Button variant="solid" size="sm" @click="save(null)">{{ __('Add') }}</Button>
					<Button size="sm" @click="editing = null">{{ __('Cancel') }}</Button>
				</div>
			</template>
			<Button v-else size="sm" @click="edit(null)">{{ __('Add a question') }}</Button>
		</div>
	</div>
</template>

<script setup>
// The instructor's view of a paper's oral defense (decisions/100c): the
// questions, which they may edit until the student starts, and each answer.
import { Badge, Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { reactive, ref } from 'vue'
import OralPlayer from '@/components/OralPlayer.vue'

const props = defineProps({
	submission: { type: String, required: true },
})

const editing = ref(null)
const draft = reactive({ question: '', passage: '', good_answer: '' })

const defense = createResource({
	url: 'seminary.seminary.oral_defense.get_defense',
	makeParams: () => ({ submission: props.submission }),
	auto: true,
})
const formatWhen = (value) => (value ? new Date(value).toLocaleString(userLocale()) : '')

const edit = (q) => {
	editing.value = q ? q.name : 'new'
	draft.question = q?.question || ''
	draft.passage = q?.passage || ''
	draft.good_answer = q?.good_answer || ''
}

const run = async (method, args, done) => {
	try {
		await call(`seminary.seminary.oral_defense.${method}`, { submission: props.submission, ...args })
		if (done) toast.success(done)
		editing.value = null
		defense.reload()
	} catch (e) {
		toast.error(e.messages?.[0] || __('That did not work.'))
	}
}

const save = (name) => run('save_question', { name, ...draft }, __('Saved.'))
const remove = (name) => run('delete_question', { name })
const release = () => run('release', {}, __('Released. The student can start now.'))
</script>
