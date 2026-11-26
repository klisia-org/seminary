<template>
	<PageHeader>
		<template #title>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
	</PageHeader>
	<!-- One student's review of a classmate's work (decisions/120 §5). -->
	<div v-if="r" class="mx-5 grid gap-5 py-5 md:mx-auto md:w-11/12 md:grid-cols-[1fr,24rem]">
		<div class="space-y-4">
			<div>
				<h2 class="text-xl font-semibold text-ink-gray-9">{{ r.activity_title }}</h2>
				<div class="text-sm text-ink-gray-5">{{ r.work_label }}</div>
			</div>
			<details v-if="r.prompt" class="rounded-lg border p-3">
				<summary class="cursor-pointer text-sm font-medium text-ink-gray-7">{{ __('The assignment') }}</summary>
				<SafeHtml :html="r.prompt" class="prose prose-sm mt-2 max-w-none !whitespace-normal" />
			</details>

			<template v-if="r.work.kind === 'assignment'">
				<SafeHtml v-if="r.work.type === 'Text' && r.work.answer" :html="r.work.answer"
					class="prose max-w-none rounded-lg border p-4 !whitespace-normal" />
				<a v-else-if="['URL', 'YouTube'].includes(r.work.type) && r.work.answer" :href="safeUrl(r.work.answer)"
					target="_blank" rel="noopener noreferrer" class="break-all text-ink-blue-3 underline">
					{{ r.work.answer }}
				</a>
				<a v-if="r.work.file" :href="r.work.file"
					class="flex items-center gap-2 rounded-md border p-3 text-ink-gray-8 !no-underline hover:bg-surface-gray-2">
					<FileText class="h-5 w-5 stroke-1.5" />
					<span>{{ __('Download the work') }}<template v-if="r.work.file_name">: {{ r.work.file_name }}</template></span>
				</a>
				<p v-if="r.work.file" class="text-xs text-ink-gray-5">
					{{ __('To comment in the text, mark up your own copy in your editor and attach it here.') }}
				</p>
			</template>
			<template v-else-if="r.work.recording">
				<OralPlayer ref="player" :recording="r.work.recording" @time="(t) => (now = t)" />
			</template>
		</div>

		<div class="space-y-4">
			<div class="space-y-3 rounded-lg border p-4">
				<div class="flex items-center justify-between">
					<h3 class="text-lg font-semibold text-ink-gray-9">{{ __('Your review') }}</h3>
					<Badge :theme="r.review.status === 'Submitted' ? 'green' : 'orange'">
						{{ r.review.status === 'Submitted' ? __('Handed in') : __('Draft') }}
					</Badge>
				</div>
				<p v-if="r.due" class="text-xs text-ink-gray-5">{{ __('Due {0}.').format(formatWhen(r.due)) }}</p>

				<div v-if="r.rubric" class="space-y-3">
					<fieldset v-for="c in r.rubric.criteria" :key="c.criterion_code" :disabled="!r.editable">
						<legend class="text-sm font-medium text-ink-gray-8">{{ c.title || c.criterion_code }}</legend>
						<p v-if="c.description" class="text-xs text-ink-gray-5">{{ c.description }}</p>
						<div class="mt-1 flex flex-wrap gap-2">
							<label v-for="lv in r.rubric.levels" :key="lv.label"
								class="flex cursor-pointer items-center gap-1 rounded border px-2 py-1 text-xs"
								:class="levels[c.criterion_code] === lv.label ? 'border-outline-blue-2 bg-surface-blue-1' : ''">
								<input v-model="levels[c.criterion_code]" type="radio" :name="`lvl-${c.criterion_code}`"
									:value="lv.label" class="sr-only" />
								{{ lv.label }}
							</label>
						</div>
					</fieldset>
				</div>

				<div>
					<div class="mb-1 text-sm text-ink-gray-7">{{ __('Comments') }}</div>
					<RichTextEditor v-if="r.editable" :id="'peer-review-' + review" :content="comments || ''"
						:placeholder="__('What works, and what would make it better?')" @change="(v) => (comments = v)" />
					<SafeHtml v-else-if="comments" :html="comments" class="prose prose-sm max-w-none" />
				</div>

				<div v-if="r.work.kind === 'oral'" class="space-y-2">
					<div class="text-sm text-ink-gray-7">{{ __('Comments at moments in the recording') }}</div>
					<div v-if="r.editable" class="flex items-center gap-2">
						<FormControl v-model="moment" class="flex-1" :placeholder="__('What you noticed here')" />
						<Button size="sm" :disabled="!moment" @click="addMoment">{{ __('At {0}').format(clock(now)) }}</Button>
					</div>
					<div v-for="(m, i) in moments" :key="i" class="flex items-start gap-2 text-xs">
						<button type="button" class="font-mono text-ink-blue-3 underline" @click="player?.seek(m.t)">{{ clock(m.t) }}</button>
						<span class="flex-1">{{ m.note }}</span>
						<Button v-if="r.editable" size="sm" variant="ghost" @click="moments.splice(i, 1)">{{ __('Remove') }}</Button>
					</div>
				</div>

				<div>
					<div class="mb-1 text-sm text-ink-gray-7">{{ __('Marked-up file (optional)') }}</div>
					<div v-if="attachment" class="flex items-center gap-2 text-sm">
						<a :href="markupUrl" class="text-ink-blue-3 underline">{{ attachmentName || __('Your file') }}</a>
						<Button v-if="r.editable" size="sm" variant="ghost" @click="attachment = null">{{ __('Remove') }}</Button>
					</div>
					<FileUploader v-else-if="r.editable" :upload-args="{ private: 1 }"
						@success="(f) => { attachment = f.file_url; attachmentName = f.file_name }">
						<template #default="{ uploading, progress, openFileSelector }">
							<Button variant="outline" :loading="uploading" @click="openFileSelector">
								{{ uploading ? __('Uploading {0}%').format(progress) : __('Attach a file') }}
							</Button>
						</template>
					</FileUploader>
				</div>

				<div v-if="r.editable" class="flex gap-2">
					<Button :loading="saving" @click="save(0)">{{ __('Save draft') }}</Button>
					<Button variant="solid" :loading="saving" @click="save(1)">
						{{ r.review.status === 'Submitted' ? __('Update') : __('Hand in') }}
					</Button>
				</div>
				<p v-else-if="!r.is_staff" class="text-xs text-ink-gray-5">
					{{ __('Reviews have been released, so this review can no longer change.') }}
				</p>
			</div>
		</div>
	</div>
	<p v-else-if="res.error" class="p-5 text-sm text-ink-gray-5">
		{{ res.error.messages?.[0] || __('The review could not be loaded.') }}
	</p>
</template>
<script setup>
import PageHeader from '@/components/PageHeader.vue'
import SafeHtml from '@/components/SafeHtml.vue'
import OralPlayer from '@/components/OralPlayer.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { Badge, Breadcrumbs, Button, FileUploader, FormControl, call, createResource, toast } from 'frappe-ui'
import { userLocale } from '@seminary/portal-shell'
import { FileText } from 'lucide-vue-next'
import { computed, reactive, ref } from 'vue'
import { updateDocumentTitle } from '@/utils'

const props = defineProps({
	courseName: { type: String, required: true },
	review: { type: String, required: true },
})

const levels = reactive({})
const comments = ref('')
const moments = ref([])
const attachment = ref(null)
const attachmentName = ref('')
const moment = ref('')
const now = ref(0)
const player = ref(null)
const saving = ref(false)

const res = createResource({
	url: 'seminary.seminary.peer_reviews.get_review',
	makeParams: () => ({ review: props.review }),
	auto: true,
	onSuccess(data) {
		Object.assign(levels, data.review.rubric_levels || {})
		comments.value = data.review.comments || ''
		moments.value = [...(data.review.moments || [])]
		attachment.value = data.review.attachment_url || null
	},
})
const r = computed(() => res.data)

// A saved file is read through the review; a new upload is the reviewer's own.
const markupUrl = computed(() =>
	attachment.value && attachment.value !== res.data?.review.attachment_url
		? attachment.value
		: `/api/method/seminary.seminary.peer_reviews.download?review=${encodeURIComponent(props.review)}&kind=markup`
)
const formatWhen = (v) => (v ? new Date(v).toLocaleString(userLocale()) : '')
const clock = (s) => {
	const t = Math.max(0, Math.floor(Number(s) || 0))
	return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}
const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : '#')
const addMoment = () => {
	moments.value.push({ t: Math.round(now.value), note: moment.value })
	moments.value.sort((a, b) => a.t - b.t)
	moment.value = ''
}

const save = async (submit) => {
	saving.value = true
	try {
		await call('seminary.seminary.peer_reviews.save_review', {
			review: props.review,
			rubric_levels: JSON.stringify(levels),
			comments: comments.value,
			moments: JSON.stringify(moments.value),
			attachment: attachment.value || '',
			submit,
		})
		toast.success(submit ? __('Review handed in.') : __('Draft saved.'))
		await res.reload()
	} catch (e) {
		toast.error(e.messages?.[0] || __('The review could not be saved.'))
	} finally {
		saving.value = false
	}
}

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{ label: props.courseName, route: { name: 'CourseDetail', params: { courseName: props.courseName } } },
	{ label: __('Peer review'), route: { name: 'PeerReview', params: props } },
])
updateDocumentTitle(computed(() => ({ title: __('Peer review'), description: r.value?.activity_title || '' })))
</script>
