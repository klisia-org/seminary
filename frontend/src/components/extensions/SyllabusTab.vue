<template>
	<div class="mx-auto max-w-4xl space-y-5">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div class="flex items-center gap-2">
				<h1 class="text-2xl font-bold text-ink-gray-9">{{ __('Syllabus') }}</h1>
				<Badge v-if="data.can_edit" :theme="statusTheme">{{ __(data.status || 'Draft') }}</Badge>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button v-if="data.html && data.status === 'Published'" :link="pdfUrl">{{ __('Download PDF') }}</Button>
				<template v-if="data.can_edit">
					<Button :variant="editing ? 'solid' : 'subtle'" @click="editing = !editing">
						{{ editing ? __('Preview') : __('Write') }}
					</Button>
				</template>
			</div>
		</div>

		<p v-if="syllabus.loading && !syllabus.data" class="text-sm text-ink-gray-5">{{ __('Loading…') }}</p>
		<p v-else-if="!data.html && !data.can_edit" class="text-sm text-ink-gray-5">
			{{ __('The syllabus for this section isn\'t published yet.') }}
		</p>

		<p v-if="data.changed_since_published" role="status"
			class="rounded-md bg-surface-amber-1 px-4 py-2 text-sm text-ink-amber-3">
			{{ __('Updated since it was published on {0}.').format(dayjs(data.published_on).format('D MMM YYYY')) }}
			<button type="button" class="underline" @click="openSnapshot">{{ __('See the published copy') }}</button>
		</p>

		<!-- Writing (staff) -->
		<section v-if="editing" class="space-y-4">
			<div v-for="section in sections" :key="section.key"
				class="rounded-lg border border-outline-gray-2 bg-surface-white p-4">
				<div class="flex items-baseline justify-between gap-2">
					<h2 class="text-base font-semibold text-ink-gray-9">{{ section.heading }}</h2>
					<span class="text-xs text-ink-gray-5">
						<template v-if="section.kind === 'From records'">{{ __('Filled in from the course: {0}').format(__(section.source)) }}</template>
						<template v-else-if="section.kind === 'School text'">{{ __('The school\'s text') }}</template>
						<template v-else-if="section.required">{{ __('Required') }}</template>
					</span>
				</div>
				<template v-if="section.kind === 'Instructor text'">
					<p v-if="section.guidance" class="mt-1 text-sm text-ink-gray-6">{{ section.guidance }}</p>
					<TextEditor class="mt-2 min-h-24 rounded border border-outline-gray-2 p-2" :content="texts[section.key]"
						:editable="true" :fixedMenu="true" :bubbleMenu="false" @change="(v) => (texts[section.key] = v)" />
				</template>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button :loading="busy === 'save'" @click="save">{{ __('Save') }}</Button>
				<Button v-if="data.status !== 'Published' || data.changed_since_published" variant="solid" :loading="busy === 'submit'" @click="submit">
					{{ data.requires_review && !data.can_approve ? __('Submit for review') : __('Publish') }}
				</Button>
				<template v-if="data.can_approve && data.status === 'Submitted'">
					<Button variant="solid" :loading="busy === 'approve'" @click="act('approve')">{{ __('Approve and publish') }}</Button>
					<Button :loading="busy === 'return_to_draft'" @click="act('return_to_draft')">{{ __('Return to the instructor') }}</Button>
				</template>
			</div>
		</section>

		<!-- The syllabus -->
		<article v-else-if="data.html" class="rounded-lg border border-outline-gray-2 bg-surface-white p-6">
			<SafeHtml :html="data.html" class="prose prose-sm max-w-none syllabus" />
		</article>

		<Dialog v-model="snapshotOpen" :options="{ title: __('Published copy'), size: '4xl' }">
			<template #body-content>
				<SafeHtml :html="snapshot.data?.html || ''" class="prose prose-sm max-w-none max-h-[70vh] overflow-y-auto" />
			</template>
		</Dialog>
	</div>
</template>

<script setup>
// The Syllabus tab (aretenic decisions/100), rendered here through the course page's
// extension slot (privatedocs p028 §1). The syllabus itself is built by aretenic.
import { computed, reactive, ref, watch } from 'vue'
import { Badge, Button, call, createResource, Dialog, TextEditor, toast } from 'frappe-ui'
import SafeHtml from '@/components/SafeHtml.vue'
import dayjs from '@/utils/dayjs'

const props = defineProps({
	courseName: { type: String, required: true },
	access: { type: String, default: 'student' },
})

const syllabus = createResource({
	url: 'aretenic.syllabus.get_syllabus',
	makeParams: () => ({ course_schedule: props.courseName }),
	auto: true,
})
const data = computed(() => syllabus.data || {})
const sections = computed(() => data.value.sections || [])
const texts = reactive({})
watch(sections, (list) => {
	for (const s of list) if (s.kind === 'Instructor text' && texts[s.key] === undefined) texts[s.key] = s.text || ''
}, { immediate: true })
const editing = ref(false)
// A draft opens ready to write; a published syllabus opens as students see it.
watch(() => data.value.status, (status, before) => {
	if (data.value.can_edit && status === 'Draft' && before === undefined) editing.value = true
})
const statusTheme = computed(() => ({ Published: 'green', Submitted: 'blue' })[data.value.status] || 'gray')
const pdfUrl = computed(
	() => `/api/method/aretenic.syllabus.download_pdf?course_schedule=${encodeURIComponent(props.courseName)}`,
)

const busy = ref('')
const run = async (key, method, args) => {
	busy.value = key
	try {
		syllabus.data = await call(method, { course_schedule: props.courseName, ...args })
		return true
	} catch (e) {
		toast.error(e?.messages?.[0] || __('That didn\'t work.'))
		return false
	} finally {
		busy.value = ''
	}
}
const save = async () => {
	if (await run('save', 'aretenic.syllabus.save_texts', { texts })) toast.success(__('Saved'))
}
const submit = async () => {
	if (!(await run('save', 'aretenic.syllabus.save_texts', { texts }))) return
	if (await run('submit', 'aretenic.syllabus.submit', {})) {
		toast.success(data.value.status === 'Published' ? __('Published') : __('Sent for review'))
		editing.value = false
	}
}
const act = async (what) => {
	if (await run(what, `aretenic.syllabus.${what}`, {})) editing.value = false
}

const snapshotOpen = ref(false)
const snapshot = createResource({ url: 'aretenic.syllabus.get_snapshot' })
const openSnapshot = () => {
	snapshotOpen.value = true
	snapshot.submit({ name: data.value.snapshot })
}
</script>
