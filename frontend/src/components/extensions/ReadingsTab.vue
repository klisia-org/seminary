<template>
	<div class="mx-auto max-w-4xl space-y-5">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('Readings') }}</h1>
				<p class="mt-1 text-sm text-ink-gray-6">{{ __('What this course reads, chapter by chapter.') }}</p>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button v-if="data.allow_export && rows.length" :link="risUrl">{{ __('Export to Zotero (RIS)') }}</Button>
				<template v-if="data.can_edit">
					<Button @click="openImport">{{ __('Import from Zotero') }}</Button>
					<Button @click="newWorkOpen = true">{{ __('New work') }}</Button>
					<Button variant="solid" @click="editing = !editing">{{ editing ? __('Done') : __('Edit list') }}</Button>
				</template>
			</div>
		</div>

		<p v-if="readings.loading && !rows.length" class="text-sm text-ink-gray-5">{{ __('Loading…') }}</p>
		<p v-else-if="!rows.length" class="text-sm text-ink-gray-5">{{ __('No readings yet.') }}</p>

		<!-- Reading -->
		<template v-if="!editing">
			<section v-for="group in groups" :key="group.key" class="rounded-lg border border-outline-gray-2 bg-surface-white">
				<h2 class="border-b border-outline-gray-1 px-4 py-2 text-base font-semibold text-ink-gray-9">
					{{ group.title }}
					<span v-if="group.release_on" class="ml-2 text-xs font-normal text-ink-gray-5">
						{{ __('Opens {0}').format(dayjs(group.release_on).format('D MMM YYYY')) }}
					</span>
				</h2>
				<ul class="divide-y divide-outline-gray-1">
					<li v-for="row in group.rows" :key="row.name" class="px-4 py-3">
						<!-- Zotero's browser button reads these (COinS). -->
						<span class="Z3988" :title="row.coins"></span>
						<div class="flex flex-wrap items-baseline gap-2">
							<Badge :theme="row.requirement === 'Required' ? 'blue' : 'gray'">{{ __(row.requirement) }}</Badge>
							<SafeHtml v-if="row.citation" as="span" profile="inline" class="text-ink-gray-9" :html="row.citation" />
							<span v-else class="text-ink-gray-9">{{ row.reference }}</span>
							<span v-if="row.portion" class="text-sm text-ink-gray-6">· {{ row.portion }}</span>
							<span v-if="row.lesson_title" class="text-xs text-ink-gray-5">· {{ row.lesson_title }}</span>
						</div>
						<div v-if="row.links.length" class="mt-1 flex flex-wrap gap-3 text-sm">
							<a v-for="link in row.links" :key="link.url" :href="link.url" target="_blank" rel="noopener"
								class="text-ink-blue-link underline">{{ link.label }}</a>
						</div>
						<p v-if="row.note" class="mt-1 text-sm text-ink-gray-6">{{ row.note }}</p>
					</li>
				</ul>
			</section>
		</template>

		<!-- Editing (staff) -->
		<section v-else class="space-y-3">
			<div v-for="(row, i) in draft" :key="row.name || i" class="rounded-lg border border-outline-gray-2 bg-surface-white p-4">
				<div class="grid gap-3 md:grid-cols-2">
					<Link v-model="row.record" doctype="Bibliographic Record" :label="__('Work')" />
					<FormControl type="select" v-model="row.requirement" :label="__('Requirement')"
						:options="[{ label: __('Required'), value: 'Required' }, { label: __('Recommended'), value: 'Recommended' }]" />
					<FormControl v-model="row.portion" :label="__('Portion')" :placeholder="__('ch. 3, or pp. 45-80')" />
					<FormControl type="number" v-model="row.pages_used" :label="__('Pages')" />
					<FormControl type="select" v-model="row.chapter" :label="__('Chapter')" :options="chapterOptions" />
					<FormControl type="select" v-model="row.access" :label="__('Access')" :options="accessOptions" />
					<template v-if="row.access === 'File in a folder'">
						<FormControl v-model="row.file" :label="__('File address')" :placeholder="__('Paste the file\'s link from the course folder')" />
						<FormControl type="select" v-model="row.copyright_basis" :label="__('Copyright basis')" :options="basisOptions" />
					</template>
					<FormControl class="md:col-span-2" v-model="row.note" :label="__('Note')" />
				</div>
				<div class="mt-2 flex justify-end">
					<Button variant="ghost" @click="draft.splice(i, 1)">{{ __('Remove') }}</Button>
				</div>
			</div>
			<div class="flex gap-2">
				<Button @click="draft.push(blankRow())">{{ __('Add a reading') }}</Button>
				<Button variant="solid" :loading="saving" @click="saveList">{{ __('Save list') }}</Button>
			</div>
		</section>

		<!-- Reading report (staff) -->
		<section v-if="data.can_edit && rows.length" class="rounded-lg border border-outline-gray-2 bg-surface-white p-4">
			<h2 class="text-base font-semibold text-ink-gray-9">{{ __('Reading report') }}</h2>
			<p class="mt-1 text-sm text-ink-gray-6">
				{{ __('A quiz where each student reports the pages they read. Points follow the pages read.') }}
			</p>
			<p v-if="data.report?.out_of_date" class="mt-2 rounded bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3">
				{{ __('The reading list changed since the report was built. Update it to match.') }}
			</p>
			<div class="mt-3 space-y-2">
				<label v-for="row in requiredRows" :key="row.name" class="flex flex-wrap items-center gap-3 text-sm">
					<input type="checkbox" v-model="report.rows" :value="row.name" />
					<span class="min-w-0 flex-1">{{ row.title }} <span class="text-ink-gray-5">({{ row.pages_used || 0 }} {{ __('pages') }})</span></span>
					<FormControl v-if="report.points_mode === 'Set per reading'" type="number" class="w-24"
						:modelValue="report.points[row.name] ?? Math.round((row.pages_used || 0) * report.rate)"
						@update:modelValue="(v) => (report.points[row.name] = v)" :aria-label="__('Points for {0}').format(row.title)" />
				</label>
			</div>
			<div class="mt-3 grid gap-3 md:grid-cols-3">
				<FormControl type="select" v-model="report.points_mode" :label="__('Points')"
					:options="[{ label: __('Per page'), value: 'Per page' }, { label: __('Set per reading'), value: 'Set per reading' }]" />
				<FormControl type="number" v-model="report.rate" :label="__('Points per page')" />
				<FormControl type="select" v-model="report.recommended" :label="__('Recommended readings')"
					:options="[{ label: __('Not graded'), value: 'Not graded' }, { label: __('In the same report'), value: 'In the same report' }, { label: __('Extra-credit report'), value: 'Extra-credit report' }]" />
				<template v-if="report.recommended !== 'Not graded'">
					<FormControl type="number" v-model="report.per_points" :label="__('Points (N)')" />
					<FormControl type="number" v-model="report.per_pages" :label="__('Per pages (X)')" />
				</template>
			</div>
			<div class="mt-3">
				<Button variant="solid" :loading="building" @click="buildReport">
					{{ data.report?.exists ? __('Update reading report') : __('Build reading report') }}
				</Button>
			</div>
		</section>

		<!-- New work -->
		<Dialog v-model="newWorkOpen" :options="{ title: __('New work'), size: 'xl' }">
			<template #body-content>
				<div class="grid gap-3 md:grid-cols-2">
					<FormControl type="select" v-model="work.work_type" :label="__('Type')" :options="typeOptions" />
					<div class="flex items-end gap-2">
						<FormControl class="flex-1" v-model="work.isbn" :label="__('ISBN')" />
						<Button :loading="looking" @click="lookup({ isbn: work.isbn })">{{ __('Look up') }}</Button>
					</div>
					<div class="flex items-end gap-2 md:col-span-2">
						<FormControl class="flex-1" v-model="work.doi" :label="__('DOI')" />
						<Button :loading="looking" @click="lookup({ doi: work.doi })">{{ __('Look up') }}</Button>
					</div>
					<FormControl class="md:col-span-2" v-model="work.title" :label="__('Title')" :required="true" />
					<FormControl class="md:col-span-2" v-model="work.authors" :label="__('Authors')"
						:description="__('Family name, given names; separate people with a semicolon')" />
					<FormControl v-if="['Chapter', 'Article'].includes(work.work_type)" class="md:col-span-2"
						v-model="work.container_title" :label="__('In (book or journal)')" />
					<FormControl v-model="work.publisher" :label="__('Publisher')" />
					<FormControl v-model="work.place" :label="__('Place')" />
					<FormControl type="number" v-model="work.year" :label="__('Year')" />
					<FormControl v-model="work.page_range" :label="__('Pages (chapter or article)')" />
					<FormControl type="number" v-model="work.total_pages" :label="__('Total pages')" />
					<FormControl v-model="work.url" :label="__('URL')" />
					<template v-if="work.work_type === 'Scripture'">
						<FormControl v-model="work.osis_start" :label="__('From (e.g. ROM.1.1)')" />
						<FormControl v-model="work.osis_end" :label="__('To (optional)')" />
					</template>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" :loading="creating" @click="createWork">{{ __('Add to the list') }}</Button>
			</template>
		</Dialog>

		<!-- Import from Zotero -->
		<Dialog v-model="importOpen" :options="{ title: __('Import from Zotero'), size: '3xl' }">
			<template #body-content>
				<p class="text-sm text-ink-gray-6">
					{{ __('In Zotero, export the collection as CSL JSON, RIS or BibTeX, then upload the file here.') }}
				</p>
				<FileUploader class="mt-3" :fileTypes="['.json', '.ris', '.bib']" :uploadArgs="{ private: true }" @success="previewFile">
					<template v-slot="{ uploading, openFileSelector }">
						<Button :loading="uploading || previewing" @click="openFileSelector">{{ __('Upload export') }}</Button>
					</template>
				</FileUploader>
				<div v-if="preview.length" class="mt-4 max-h-96 space-y-2 overflow-y-auto">
					<div v-for="(item, i) in preview" :key="i" class="rounded border border-outline-gray-2 p-3 text-sm">
						<div class="font-medium text-ink-gray-9">{{ item.fields.title }}</div>
						<div class="text-ink-gray-6">
							<template v-if="item.status === 'New'">{{ __('New') }}</template>
							<template v-else-if="item.status === 'Match'">{{ __('Matches {0}').format(item.record_title) }}</template>
							<template v-else>{{ __('Possible duplicate of {0}').format(item.record_title) }}</template>
						</div>
						<div v-if="item.status === 'Possible'" class="mt-1 flex gap-4">
							<label><input type="radio" v-model="item.choice" value="Use existing" /> {{ __('Use existing') }}</label>
							<label><input type="radio" v-model="item.choice" value="Create new" /> {{ __('Create new') }}</label>
						</div>
					</div>
				</div>
				<FormControl v-if="preview.length" class="mt-3" type="select" v-model="importRequirement" :label="__('Add to this section\'s list as')"
					:options="[{ label: __('Required'), value: 'Required' }, { label: __('Recommended'), value: 'Recommended' }, { label: __('Don\'t add, only keep the records'), value: '' }]" />
			</template>
			<template #actions>
				<Button variant="solid" :disabled="!preview.length" :loading="importing" @click="confirmImport">{{ __('Import') }}</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
// The Readings tab (aretenic decisions/099), rendered here through the course page's
// extension slot (privatedocs p028 §1). Everything it shows comes from aretenic.
import { computed, reactive, ref, watch } from 'vue'
import { Badge, Button, call, createResource, Dialog, FileUploader, FormControl, toast } from 'frappe-ui'
import Link from '@/components/Controls/Link.vue'
import SafeHtml from '@/components/SafeHtml.vue'
import dayjs from '@/utils/dayjs'

const props = defineProps({
	courseName: { type: String, required: true },
	access: { type: String, default: 'student' },
})

const readings = createResource({
	url: 'aretenic.reading_lists.get_readings',
	makeParams: () => ({ course_schedule: props.courseName }),
	auto: true,
})
const data = computed(() => readings.data || { rows: [] })
const rows = computed(() => data.value.rows || [])
const risUrl = computed(
	() => `/api/method/aretenic.reading_lists.export_ris?course_schedule=${encodeURIComponent(props.courseName)}`,
)

const groups = computed(() => {
	const out = []
	const byKey = {}
	for (const row of rows.value) {
		const key = row.chapter || '_course'
		if (!byKey[key]) {
			byKey[key] = { key, title: row.chapter_title || __('Whole course'), release_on: row.release_on, rows: [] }
			out.push(byKey[key])
		}
		byKey[key].rows.push(row)
	}
	return out
})

// --- editing ---------------------------------------------------------------
const editing = ref(false)
const saving = ref(false)
const draft = ref([])
const blankRow = () => ({ record: '', requirement: 'Required', portion: '', pages_used: null, chapter: '', access: '' })
watch(editing, (on) => {
	if (on) draft.value = rows.value.map((r) => ({ ...r }))
})
const chapters = createResource({
	url: 'seminary.seminary.library.my_chapters',
	auto: props.access === 'instructor',
	onError: () => {},
})
const chapterOptions = computed(() => {
	const section = (chapters.data || []).find((s) => s.name === props.courseName)
	return [{ label: __('Whole course'), value: '' }, ...((section?.chapters || []).map((c) => ({ label: c.chapter_title, value: c.name })))]
})
const accessOptions = [
	{ label: __('Not said'), value: '' },
	{ label: __('Library e-resource'), value: 'Library e-resource' },
	{ label: __('File in a folder'), value: 'File in a folder' },
	{ label: __('Purchase'), value: 'Purchase' },
	{ label: __('Open web'), value: 'Open web' },
]
const basisOptions = [
	{ label: __('Choose one'), value: '' },
	...['Public domain', 'Open licence', 'Library licence', 'Permission obtained', 'Collective licence', 'Fair use or fair dealing'].map(
		(v) => ({ label: __(v), value: v }),
	),
]
const typeOptions = ['Book', 'Chapter', 'Article', 'Web page', 'Video', 'Scripture'].map((v) => ({ label: __(v), value: v }))

const saveList = async () => {
	saving.value = true
	try {
		readings.data = await call('aretenic.reading_lists.save_readings', {
			course_schedule: props.courseName,
			rows: draft.value,
		})
		editing.value = false
		toast.success(__('Reading list saved'))
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The list could not be saved.'))
	} finally {
		saving.value = false
	}
}

// --- a new work ------------------------------------------------------------
const newWorkOpen = ref(false)
const looking = ref(false)
const creating = ref(false)
const work = reactive({ work_type: 'Book', title: '', authors: '' })
const lookup = async (args) => {
	looking.value = true
	try {
		const found = await call('aretenic.reading_lists.lookup', args)
		if (!found) {
			toast.warning(__('Nothing found. Type the details instead.'))
			return
		}
		Object.assign(work, { ...found, authors: (found.contributors || []).map((c) => [c.family_name, c.given_names].filter(Boolean).join(', ')).join('; ') })
	} finally {
		looking.value = false
	}
}
const createWork = async () => {
	creating.value = true
	try {
		const contributors = (work.authors || '')
			.split(';')
			.map((s) => s.trim())
			.filter(Boolean)
			.map((s) => {
				const [family, given] = s.split(',').map((x) => x.trim())
				return { family_name: family, given_names: given || '', role: 'Author' }
			})
		const { authors, ...fields } = work
		const doc = await call('frappe.client.insert', { doc: { doctype: 'Bibliographic Record', ...fields, contributors } })
		const list = rows.value.map((r) => ({ ...r }))
		list.push({ ...blankRow(), record: doc.name, pages_used: doc.total_pages || null })
		readings.data = await call('aretenic.reading_lists.save_readings', { course_schedule: props.courseName, rows: list })
		newWorkOpen.value = false
		Object.assign(work, { work_type: 'Book', title: '', authors: '', isbn: '', doi: '' })
		toast.success(__('Added to the list'))
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The work could not be saved.'))
	} finally {
		creating.value = false
	}
}

// --- import from Zotero ----------------------------------------------------
const importOpen = ref(false)
const previewing = ref(false)
const importing = ref(false)
const preview = ref([])
const importRequirement = ref('Required')
const openImport = () => {
	preview.value = []
	importOpen.value = true
}
const previewFile = async (file) => {
	previewing.value = true
	try {
		const items = await call('aretenic.reading_lists.preview_import', { file_url: file.file_url })
		preview.value = items.map((i) => ({ ...i, choice: i.status === 'Possible' ? 'Use existing' : null }))
		if (!items.length) toast.warning(__('The file holds no works.'))
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The file could not be read.'))
	} finally {
		previewing.value = false
	}
}
const confirmImport = async () => {
	importing.value = true
	try {
		const out = await call('aretenic.reading_lists.confirm_import', {
			items: preview.value,
			course_schedule: props.courseName,
			requirement: importRequirement.value,
		})
		if (out.errors?.length) {
			toast.warning(__('{0} works were left out: {1}').format(out.errors.length, out.errors.map((e) => e.title).join('; ')))
		} else {
			toast.success(__('{0} works imported').format(out.records.length))
		}
		importOpen.value = false
		readings.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The import failed.'))
	} finally {
		importing.value = false
	}
}

// --- reading report --------------------------------------------------------
const requiredRows = computed(() => rows.value.filter((r) => r.requirement === 'Required'))
const report = reactive({ rows: [], points_mode: 'Per page', rate: 0.1, points: {}, recommended: 'Not graded', per_points: 1, per_pages: 10 })
watch(requiredRows, (list) => {
	if (!report.rows.length) report.rows = list.map((r) => r.name)
}, { immediate: true })
const building = ref(false)
const buildReport = async () => {
	building.value = true
	try {
		await call('aretenic.reading_lists.build_reading_report', { course_schedule: props.courseName, options: report })
		toast.success(__('Reading report saved. Add it to a lesson and to the assessment plan.'))
		readings.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('The report could not be built.'))
	} finally {
		building.value = false
	}
}
</script>
