<template>
	<PageHeader :title="__('Lesson Library')">
		<template #actions>
			<Button variant="solid" :label="__('New library lesson')" :route="{ name: 'LibraryLessonForm', params: { name: 'new' } }">
				<template #prefix><Plus class="h-4 w-4" /></template>
			</Button>
		</template>
	</PageHeader>

	<div class="mx-auto flex w-full max-w-4xl flex-col gap-4 px-4 py-6">
		<p class="text-sm text-ink-gray-6">
			{{ __('Lessons the school keeps once and uses in many sections. A section that adds one shows the same content, and an edit here reaches every open section that uses it.') }}
		</p>
		<FormControl v-model="txt" :placeholder="__('Search by title or tag')" :aria-label="__('Search the library')" @input="search" />

		<div v-if="lessons.loading && !rows.length" class="py-10 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
		<div v-else-if="!rows.length" class="py-10 text-center text-sm text-ink-gray-5">{{ __('No library lessons yet.') }}</div>

		<div v-for="row in rows" :key="row.name" class="rounded-lg border border-outline-gray-2 bg-surface-white">
			<button type="button" class="flex w-full flex-wrap items-center gap-2 px-4 py-3 text-left"
				:aria-expanded="open === row.name" @click="toggle(row)">
				<component :is="open === row.name ? ChevronDown : ChevronRight" class="h-4 w-4 text-ink-gray-5" />
				<span class="font-medium text-ink-gray-9">{{ row.title }}</span>
				<Badge v-if="row.required" theme="orange">{{ __('Required') }}</Badge>
				<span class="ml-auto text-xs text-ink-gray-5">
					{{ row.placements === 1 ? __('Used in 1 section') : __('Used in {0} sections').format(row.placements) }}
				</span>
			</button>
			<div v-if="open === row.name" class="border-t border-outline-gray-1 px-4 py-3">
				<p v-if="row.preview" class="text-sm text-ink-gray-7">{{ row.preview }}</p>
				<p v-if="row.tags" class="mt-1 text-xs text-ink-gray-5">{{ row.tags }}</p>
				<div class="mt-3 flex flex-wrap gap-2">
					<Button size="sm" variant="solid" :label="__('Add to a chapter')" @click="openPlace(row)" />
					<Button v-if="row.can_edit" size="sm" :label="__('Edit')"
						:route="{ name: 'LibraryLessonForm', params: { name: row.name } }" />
				</div>
				<div v-if="detail.data?.name === row.name" class="mt-4">
					<div id="library-preview"
						class="rounded-lg bg-surface-gray-1 px-4 py-3 ProseMirror prose prose-sm max-w-none !whitespace-normal"></div>
					<h3 class="mt-4 text-sm font-semibold text-ink-gray-8">{{ __('Where it is used') }}</h3>
					<p v-if="!detail.data.placements.length" class="text-sm text-ink-gray-5">{{ __('No section uses it yet.') }}</p>
					<ul v-else class="mt-1 space-y-1 text-sm text-ink-gray-7">
						<li v-for="p in detail.data.placements" :key="p.lesson">
							{{ p.section || p.course_sc }}
							<span class="text-ink-gray-5">· {{ p.chapter_title }} · {{ p.academic_term }}</span>
							<Badge v-if="p.required_by" theme="orange" class="ml-1">{{ __('Required') }}</Badge>
						</li>
					</ul>
				</div>
			</div>
		</div>
	</div>

	<Dialog v-model="placeOpen" :options="{ title: __('Add {0} to a chapter').format(placing?.title || ''), size: 'lg' }">
		<template #body-content>
			<p v-if="chapters.loading" class="text-sm text-ink-gray-5">{{ __('Loading…') }}</p>
			<p v-else-if="!chapters.data?.length" class="text-sm text-ink-gray-5">
				{{ __('None of your open sections with chapters may use this lesson.') }}
			</p>
			<div v-else class="space-y-3">
				<FormControl type="select" v-model="chosenSection" :label="__('Section')" :options="sectionOptions" />
				<FormControl v-if="chosenSection" type="select" v-model="chosenChapter" :label="__('Chapter')" :options="chapterOptions" />
				<Switch v-model="atStart" :label="__('Put it first in the chapter')" />
			</div>
		</template>
		<template #actions>
			<Button variant="solid" :disabled="!chosenChapter" :loading="placingNow" :label="__('Add')" @click="place" />
		</template>
	</Dialog>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { Badge, Button, call, createResource, Dialog, FormControl, Switch, toast } from 'frappe-ui'
import { ChevronDown, ChevronRight, Plus } from 'lucide-vue-next'
import EditorJS from '@editorjs/editorjs'
import PageHeader from '@/components/PageHeader.vue'
import { getEditorTools, updateDocumentTitle } from '@/utils'

const txt = ref('')
const open = ref(null)
const placeOpen = ref(false)
const placing = ref(null)
const chosenSection = ref('')
const chosenChapter = ref('')
const atStart = ref(false)
const placingNow = ref(false)

const lessons = createResource({
	url: 'seminary.seminary.library.search',
	makeParams: () => ({ txt: txt.value }),
	auto: true,
})
const rows = computed(() => lessons.data || [])

let timer
const search = () => {
	clearTimeout(timer)
	timer = setTimeout(() => lessons.reload(), 300)
}

const detail = createResource({
	url: 'seminary.seminary.library.get',
	onSuccess(data) {
		nextTick(() => {
			const holder = document.getElementById('library-preview')
			if (!holder) return
			holder.innerHTML = ''
			let content = { blocks: [] }
			try {
				content = JSON.parse(data.content || '{"blocks": []}')
			} catch {
				/* shown empty */
			}
			new EditorJS({ holder: 'library-preview', readOnly: true, tools: getEditorTools(), data: content })
		})
	},
})

const toggle = (row) => {
	open.value = open.value === row.name ? null : row.name
	if (open.value) detail.submit({ name: row.name })
}

const chapters = createResource({ url: 'seminary.seminary.library.my_chapters' })
const sectionOptions = computed(() => [
	{ label: __('Choose a section'), value: '' },
	...(chapters.data || []).map((s) => ({ label: s.title || s.name, value: s.name })),
])
const chapterOptions = computed(() => {
	const section = (chapters.data || []).find((s) => s.name === chosenSection.value)
	return [
		{ label: __('Choose a chapter'), value: '' },
		...((section?.chapters || []).map((c) => ({ label: c.chapter_title || c.name, value: c.name }))),
	]
})

const openPlace = (row) => {
	placing.value = row
	chosenSection.value = ''
	chosenChapter.value = ''
	atStart.value = false
	placeOpen.value = true
	chapters.submit({ library_lesson: row.name })
}

const place = async () => {
	placingNow.value = true
	try {
		await call('seminary.seminary.library.place', {
			library_lesson: placing.value.name,
			chapter: chosenChapter.value,
			at_start: atStart.value ? 1 : 0,
		})
		toast.success(__('Lesson added'))
		placeOpen.value = false
		lessons.reload()
		if (open.value) detail.submit({ name: open.value })
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The lesson could not be added.'))
	} finally {
		placingNow.value = false
	}
}

updateDocumentTitle(computed(() => ({ title: __('Lesson Library') })))
</script>
