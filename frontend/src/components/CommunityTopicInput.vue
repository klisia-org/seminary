<template>
	<div class="relative" @focusout="onFocusOut">
		<div class="flex min-h-[2.5rem] flex-wrap items-center gap-1.5 rounded-lg border bg-surface-white px-2 py-1.5"
			:class="open ? 'border-outline-gray-4' : 'border-outline-gray-2'"
			@click="inputEl?.focus()">
			<span v-for="(t, i) in modelValue" :key="t"
				class="flex items-center gap-1 rounded-md bg-surface-gray-2 py-0.5 pl-2 pr-1 text-sm text-ink-gray-8">
				#{{ t }}
				<button type="button" class="rounded p-0.5 text-ink-gray-5 hover:text-ink-gray-9"
					:aria-label="__('Remove {0}').format(t)" @click.stop="remove(i)">
					<X class="h-3 w-3" />
				</button>
			</span>
			<input ref="inputEl" v-model="query" type="text"
				class="min-w-[6rem] flex-1 border-0 bg-transparent p-0.5 text-sm text-ink-gray-8 focus:outline-none focus:ring-0"
				:placeholder="modelValue.length ? '' : __('e.g. grading')"
				@focus="open = true"
				@input="onInput"
				@keydown="onKeydown" />
		</div>
		<ul v-if="open && options.length"
			class="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white p-1 shadow-lg">
			<li v-for="(o, i) in options" :key="o.key">
				<button type="button" class="flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left text-sm"
					:class="i === active ? 'bg-surface-gray-2' : 'hover:bg-surface-gray-2'"
					@mousedown.prevent="choose(o)" @mouseenter="active = i">
					<span class="truncate text-ink-gray-8">{{ o.create ? __('Create "#{0}"').format(o.topic) : '#' + o.topic }}</span>
					<span v-if="!o.create" class="ml-3 shrink-0 text-xs text-ink-gray-5">
						{{ o.posts === 1 ? __('used in 1 post') : __('used in {0} posts').format(o.posts) }}
					</span>
				</button>
			</li>
		</ul>
	</div>
</template>

<script setup>
// Topics as chips (decisions/101 section 5.6). Enter or a comma adds what is
// typed; suggestions are topics on posts the author can read.
import { computed, ref } from 'vue'
import { createResource } from 'frappe-ui'
import { X } from 'lucide-vue-next'

const props = defineProps({ modelValue: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue'])

const inputEl = ref(null)
const query = ref('')
const open = ref(false)
const active = ref(0)
const suggestions = ref([])
const suggestRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.suggest_topics' })

const clean = (s) => (s || '').replace(/^#+/, '').trim()
const has = (t) => props.modelValue.some((m) => m.toLowerCase() === t.toLowerCase())

const options = computed(() => {
	const q = clean(query.value)
	if (!q) return []
	const rows = suggestions.value.filter((s) => !has(s.topic)).map((s) => ({ ...s, key: 's' + s.topic }))
	if (!has(q) && !rows.some((r) => r.topic.toLowerCase() === q.toLowerCase())) {
		rows.push({ topic: q, create: true, key: 'create' })
	}
	return rows
})

let timer = null
function onInput() {
	if (query.value.includes(',')) {
		query.value.split(',').slice(0, -1).forEach(add)
		query.value = query.value.split(',').pop()
	}
	active.value = 0
	open.value = true
	clearTimeout(timer)
	const q = clean(query.value)
	if (!q) { suggestions.value = []; return }
	timer = setTimeout(() => {
		suggestRes.submit({ query: q }).then((rows) => {
			if (clean(query.value) === q) suggestions.value = rows || []
		})
	}, 200)
}
function add(raw) {
	const t = clean(raw)
	if (!t || has(t)) return
	emit('update:modelValue', [...props.modelValue, t])
}
function remove(i) {
	emit('update:modelValue', props.modelValue.filter((_, j) => j !== i))
}
function choose(o) {
	add(o.topic)
	query.value = ''
	suggestions.value = []
	inputEl.value?.focus()
}
function onKeydown(e) {
	if (e.key === 'ArrowDown' && options.value.length) {
		e.preventDefault(); active.value = (active.value + 1) % options.value.length
	} else if (e.key === 'ArrowUp' && options.value.length) {
		e.preventDefault(); active.value = (active.value - 1 + options.value.length) % options.value.length
	} else if (e.key === 'Enter') {
		e.preventDefault()
		const o = options.value[active.value]
		if (o) choose(o)
	} else if (e.key === 'Backspace' && !query.value && props.modelValue.length) {
		remove(props.modelValue.length - 1)
	} else if (e.key === 'Escape' && open.value && options.value.length) {
		e.stopPropagation(); open.value = false
	}
}
function onFocusOut(e) {
	if (e.currentTarget.contains(e.relatedTarget)) return
	open.value = false
	// A typed topic left without Enter is still kept.
	if (clean(query.value)) { add(query.value); query.value = '' }
}
</script>
