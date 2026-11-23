<template>
	<div ref="root" class="relative">
		<button type="button"
			class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm"
			:class="modelValue ? 'border-outline-gray-4 bg-surface-gray-3 text-ink-gray-9' : 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:border-outline-gray-3'"
			:aria-expanded="open" @click="toggle">
			<BookOpen class="h-4 w-4" />
			<span class="whitespace-nowrap">{{ modelValue ? __('Passage: {0}').format(modelValue.label) : __('Passage') }}</span>
			<ChevronDown class="h-3.5 w-3.5 transition-transform" :class="{ 'rotate-180': open }" />
		</button>

		<div v-if="open"
			class="absolute left-0 z-30 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white shadow-xl">
			<div class="flex items-center gap-2 border-b border-outline-gray-1 px-3">
				<Search class="h-4 w-4 text-ink-gray-4" />
				<input ref="input" v-model="typed" type="text"
					class="w-full border-0 bg-transparent px-0 py-2.5 text-sm text-ink-gray-8 shadow-none focus:outline-none focus:ring-0"
					:placeholder="__('Type a book or reference, e.g. Jn 11, Rom 8:28')"
					:aria-label="__('Type a book or reference, e.g. Jn 11, Rom 8:28')"
					@keyup.enter="pickTyped" />
			</div>
			<div class="flex gap-1 px-3 pt-2">
				<button v-for="t in tabs" :key="t.key" type="button"
					class="rounded-md px-2.5 py-1 text-xs"
					:class="tab === t.key ? 'bg-surface-gray-3 font-medium text-ink-gray-9' : 'text-ink-gray-6 hover:text-ink-gray-8'"
					@click="setTab(t.key)">{{ t.label }}</button>
			</div>

			<div class="max-h-80 overflow-y-auto px-2 py-2">
				<div v-if="tab === 'tagged' && taggedRes.loading" class="px-2 py-4 text-center text-sm text-ink-gray-5">
					{{ __('Loading…') }}
				</div>
				<div v-else-if="!visibleBooks.length" class="px-2 py-4 text-center text-sm text-ink-gray-5">
					{{ tab === 'tagged' ? __('No post tags a passage yet.') : __('No book matches.') }}
				</div>
				<template v-for="group in groupedBooks" :key="group.label">
					<div v-if="group.books.length" class="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">
						{{ group.label }}
					</div>
					<div v-for="b in group.books" :key="b.osis" class="rounded-lg"
						:class="{ 'bg-surface-gray-1': expanded === b.osis }">
						<button type="button" class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface-gray-2"
							@click="expand(b)">
							<component :is="expanded === b.osis ? ChevronDown : ChevronRight" class="h-3.5 w-3.5 text-ink-gray-4" />
							<span class="flex-1 text-ink-gray-8">{{ b.name }}</span>
							<span v-if="b.count" class="text-xs text-ink-gray-5">
								{{ b.count === 1 ? __('1 post') : __('{0} posts').format(b.count) }}
							</span>
						</button>
						<div v-if="expanded === b.osis" class="flex flex-wrap gap-1.5 px-2 pb-2 pl-7">
							<button type="button" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-xs text-ink-gray-7 hover:border-outline-gray-3"
								@click="pick(b.name, b.start_ord, b.end_ord)">{{ __('Whole book') }}</button>
							<button v-for="c in chaptersOf(b)" :key="c.chapter" type="button"
								class="rounded-md border px-2 py-1 text-xs"
								:class="isPicked(c) ? 'border-outline-gray-4 bg-surface-gray-7 text-ink-white' : 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:border-outline-gray-3'"
								@click="pick(`${b.name} ${c.chapter}`, c.start_ord, c.end_ord)">
								{{ c.chapter }}<span v-if="c.count"> · {{ c.count }}</span>
							</button>
							<span v-if="tab === 'tagged' && chaptersRes.loading" class="text-xs text-ink-gray-5">{{ __('Loading…') }}</span>
						</div>
					</div>
				</template>
			</div>

			<div class="flex items-center justify-between gap-3 border-t border-outline-gray-1 bg-surface-gray-1 px-3 py-2">
				<button type="button" class="whitespace-nowrap text-sm font-medium text-ink-gray-8 hover:text-ink-gray-9" @click="clear">
					{{ __('Any passage') }}
				</button>
				<span class="text-right text-xs text-ink-gray-5">{{ __('Counts follow your cohort filter') }}</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from 'vue'
import { createResource } from 'frappe-ui'
import { BookOpen, ChevronDown, ChevronRight, Search } from 'lucide-vue-next'

// The passage filter: a book, a chapter or a typed reference (decisions/101
// section 5.3). Emits {label, start, end} for a picked range, {label, ref} for
// a typed reference the server resolves, or null for any passage.
const props = defineProps({
	modelValue: { type: Object, default: null },
	cohort: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const tab = ref('tagged')
const typed = ref('')
const expanded = ref(null)
const root = ref(null)
const input = ref(null)
const tabs = [
	{ key: 'tagged', label: __('Tagged in posts') },
	{ key: 'all', label: __('All books') },
]

const taggedRes = createResource({
	url: 'seminary.seminary.discipleship.scripture.scripture_books',
	makeParams: () => ({ cohort: props.cohort || null }),
})
const allRes = createResource({
	url: 'seminary.seminary.discipleship.scripture.all_books',
	cache: 'community-all-books',
})
const chaptersRes = createResource({
	url: 'seminary.seminary.discipleship.scripture.scripture_chapters',
})

const tagged = computed(() => taggedRes.data || [])
const visibleBooks = computed(() => {
	const counts = Object.fromEntries(tagged.value.map((b) => [b.osis, b.count]))
	const books = tab.value === 'tagged'
		? tagged.value.map((b) => ({ ...b, testament: b.index <= 39 ? 'OT' : 'NT' }))
		: (allRes.data || []).map((b) => ({ ...b, count: counts[b.osis] || 0 }))
	const q = typed.value.trim().toLowerCase()
	// While typing a reference, narrow the books to the ones it can name.
	const word = q.replace(/[\d:.\-–\s]+$/, '').trim()
	return word ? books.filter((b) => b.name.toLowerCase().startsWith(word) || b.osis.toLowerCase().startsWith(word)) : books
})
const groupedBooks = computed(() => [
	{ label: __('Old Testament'), books: visibleBooks.value.filter((b) => b.testament === 'OT') },
	{ label: __('New Testament'), books: visibleBooks.value.filter((b) => b.testament === 'NT') },
])

function chaptersOf(b) {
	if (tab.value === 'tagged') return expanded.value === b.osis ? chaptersRes.data || [] : []
	const tally = Object.fromEntries((chaptersRes.data || []).map((c) => [c.chapter, c.count]))
	return Array.from({ length: b.chapters || 0 }, (_, i) => ({
		chapter: i + 1,
		count: tally[i + 1] || 0,
		start_ord: b.index * 1_000_000 + (i + 1) * 1_000,
		end_ord: b.index * 1_000_000 + (i + 1) * 1_000 + 999,
	}))
}
function isPicked(c) {
	return props.modelValue && props.modelValue.start === c.start_ord && props.modelValue.end === c.end_ord
}
function expand(b) {
	if (expanded.value === b.osis) { expanded.value = null; return }
	expanded.value = b.osis
	if (b.count || tab.value === 'tagged') chaptersRes.fetch({ book: b.osis, cohort: props.cohort || null })
	else chaptersRes.data = []
}
function setTab(key) {
	tab.value = key
	expanded.value = null
	if (key === 'all' && !allRes.data) allRes.fetch()
}
function pick(label, start, end) {
	emit('update:modelValue', { label, start, end })
	open.value = false
}
function pickTyped() {
	const ref = typed.value.trim()
	if (!ref) return
	emit('update:modelValue', { label: ref, ref })
	open.value = false
}
function clear() {
	emit('update:modelValue', null)
	typed.value = ''
	open.value = false
}
function toggle() {
	open.value = !open.value
	if (open.value) {
		taggedRes.fetch()
		nextTick(() => input.value?.focus())
	}
}
function onClickAway(e) {
	if (open.value && root.value && !root.value.contains(e.target)) open.value = false
}
function onKey(e) {
	if (e.key === 'Escape') open.value = false
}
watch(() => props.cohort, () => { if (open.value) taggedRes.fetch() })
onMounted(() => {
	document.addEventListener('mousedown', onClickAway)
	document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
	document.removeEventListener('mousedown', onClickAway)
	document.removeEventListener('keydown', onKey)
})
</script>
