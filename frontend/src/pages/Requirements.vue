<template>
	<PageHeader :title="__('Requirements')" />

	<div class="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
		<div v-if="reqs.loading && !reqs.data" class="py-10 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>

		<template v-else>
			<div v-if="!openRows.length" class="rounded border border-outline-gray-2 bg-surface-white px-4 py-6 text-center text-sm text-ink-gray-6">
				{{ __('Nothing to sign or upload right now.') }}
			</div>

			<div v-for="row in openRows" :key="row.name"
				class="rounded border bg-surface-white px-4 py-3"
				:class="row.overdue ? 'border-outline-red-2' : 'border-outline-gray-2'">
				<div class="flex flex-wrap items-start justify-between gap-2">
					<div>
						<div class="font-medium text-ink-gray-9">{{ row.label }}</div>
						<div class="mt-0.5 text-xs text-ink-gray-5">
							{{ row.for }}<span v-if="row.period"> · {{ row.period }}</span>
						</div>
					</div>
					<div class="flex flex-wrap items-center gap-1.5 text-xs">
						<Badge v-if="row.blocking" theme="orange" :label="__('Required to enroll')" />
						<Badge :theme="row.overdue ? 'red' : 'gray'"
							:label="row.overdue ? __('Overdue since {0}').format(fmt(row.due_date)) : __('Due {0}').format(fmt(row.due_date))" />
					</div>
				</div>

				<p v-if="row.instructions" class="mt-2 whitespace-pre-line text-sm text-ink-gray-7">{{ row.instructions }}</p>
				<p v-if="row.description" class="mt-1 whitespace-pre-line text-sm text-ink-gray-6">{{ row.description }}</p>
				<p v-if="row.last_document && row.last_document.status === 'Rejected'"
					class="mt-2 rounded bg-surface-red-1 px-2 py-1 text-sm text-ink-red-4">
					{{ __('Your last upload was not accepted: {0}').format(row.last_document.rejection_reason || '') }}
				</p>

				<div class="mt-3 flex flex-wrap items-center gap-2">
					<template v-if="row.status === 'Submitted'">
						<span class="text-sm text-ink-gray-6">
							{{ row.kind === 'Agreement' ? __('Signed. Waiting for the school to countersign.') : __('Sent. Waiting for the school to review it.') }}
						</span>
					</template>
					<template v-else-if="row.kind === 'Agreement'">
						<Button variant="solid" :label="__('Read and sign')" @click="openSign(row)" />
					</template>
					<template v-else>
						<FileUploader :fileTypes="fileTypes(row)" :uploadArgs="{ private: true }"
							:validateFile="validateFileSize" @success="(file) => sendDocument(row, file)">
							<template #default="{ uploading, progress, openFileSelector }">
								<Button variant="solid" :loading="uploading || sending === row.name" @click="openFileSelector">
									{{ uploading ? __('Uploading {0}%').format(progress) : __('Upload') }}
								</Button>
							</template>
						</FileUploader>
						<span v-if="row.allowed_extensions && row.allowed_extensions.length" class="text-xs text-ink-gray-5">
							{{ row.allowed_extensions.join(', ') }}
						</span>
					</template>
				</div>
			</div>

			<div v-if="doneRows.length" class="mt-4">
				<button class="text-sm text-ink-gray-6 underline" @click="showDone = !showDone">
					{{ showDone ? __('Hide completed') : __('Show completed ({0})').format(doneRows.length) }}
				</button>
				<div v-if="showDone" class="mt-2 divide-y divide-outline-gray-1 rounded border border-outline-gray-2 bg-surface-white">
					<div v-for="row in doneRows" :key="row.name" class="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
						<div>
							<span class="text-ink-gray-8">{{ row.label }}</span>
							<span class="text-xs text-ink-gray-5"> · {{ row.for }}<span v-if="row.period"> · {{ row.period }}</span></span>
						</div>
						<div class="flex items-center gap-2">
							<a v-if="row.signed && (row.signed.final_pdf || row.signed.pdf)" :href="row.signed.final_pdf || row.signed.pdf"
								target="_blank" rel="noopener" class="text-xs text-ink-gray-7 underline">{{ __('Signed PDF') }}</a>
							<Badge :theme="row.status === 'Waived' ? 'gray' : 'green'" :label="row.status === 'Waived' ? __('Waived') : __('Done')" />
						</div>
					</div>
				</div>
			</div>
		</template>
	</div>

	<Dialog v-model="signOpen" :options="{ title: preview.data?.title || __('Agreement'), size: '3xl' }">
		<template #body-content>
			<div v-if="preview.loading" class="py-8 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
			<div v-else-if="preview.data" class="flex flex-col gap-3">
				<div ref="textBox" class="max-h-[50vh] overflow-y-auto rounded border border-outline-gray-2 bg-surface-white p-4" @scroll="onScroll">
					<SafeHtml :html="preview.data.html" class="prose prose-sm max-w-none" />
				</div>
				<p v-if="!readToEnd" class="text-xs text-ink-gray-5">{{ __('Scroll to the end of the text to sign.') }}</p>
				<label class="flex items-start gap-2 text-sm text-ink-gray-8">
					<input type="checkbox" v-model="consent" :disabled="!readToEnd" class="mt-0.5" />
					<span>{{ __('I have read this agreement and I agree to its terms. I understand that typing my name below is my electronic signature.') }}</span>
				</label>
				<FormControl v-model="signerName" :label="__('Type your full name')" :placeholder="preview.data.full_name" :disabled="!readToEnd" />
				<div>
					<div class="mb-1 flex items-center justify-between text-xs text-ink-gray-6">
						<span>{{ __('Draw your signature (optional)') }}</span>
						<button class="underline" @click="clearPad">{{ __('Clear') }}</button>
					</div>
					<canvas ref="pad" width="560" height="140"
						class="w-full touch-none rounded border border-outline-gray-2 bg-surface-white text-ink-gray-9"
						@pointerdown="padDown" @pointermove="padMove" @pointerup="padUp" @pointerleave="padUp" />
				</div>
				<p v-if="preview.data.countersigned" class="text-xs text-ink-gray-5">{{ __('The school countersigns after you sign.') }}</p>
			</div>
		</template>
		<template #actions>
			<Button variant="solid" class="w-full" :label="__('Sign')" :loading="signRes.loading"
				:disabled="!canSign" @click="submitSign" />
		</template>
	</Dialog>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
import SafeHtml from '@/components/SafeHtml.vue'
import { computed, nextTick, ref } from 'vue'
import { Badge, Button, Dialog, FileUploader, FormControl, createResource } from 'frappe-ui'
import { createToast, formatDate, validateFileSize } from '@/utils'
import { usersStore } from '@/stores/user'

const { userResource } = usersStore()

const reqs = createResource({
	url: 'seminary.seminary.requirements.my_requirements',
	auto: true,
})
const openRows = computed(() => reqs.data?.open || [])
const doneRows = computed(() => reqs.data?.done || [])
const showDone = ref(false)

function fmt(d) {
	return d ? formatDate(d) : ''
}

function fileTypes(row) {
	return (row.allowed_extensions || []).map((e) => '.' + e)
}

function refresh() {
	reqs.reload()
	userResource.reload()
}

// ---------------------------------------------------------------- documents
const sending = ref(null)
const uploadRes = createResource({ url: 'seminary.seminary.requirements.upload_document' })

function sendDocument(row, file) {
	sending.value = row.name
	uploadRes.submit(
		{ requirement: row.name, file_url: file.file_url },
		{
			onSuccess: () => {
				createToast({ title: __('Sent'), icon: 'check', iconClasses: 'text-ink-green-3' })
				refresh()
			},
			onError: (e) => createToast({ title: __('Not sent'), text: e.messages?.[0] || e.message, icon: 'x', iconClasses: 'text-ink-red-4' }),
			onSettled: () => { sending.value = null },
		},
	)
}

// ---------------------------------------------------------------- agreements
const signOpen = ref(false)
const current = ref(null)
const consent = ref(false)
const signerName = ref('')
const readToEnd = ref(false)
const textBox = ref(null)
const preview = createResource({ url: 'seminary.seminary.requirements.agreement_preview' })
const signRes = createResource({ url: 'seminary.seminary.requirements.sign_agreement' })

function openSign(row) {
	current.value = row
	consent.value = false
	signerName.value = ''
	readToEnd.value = false
	signOpen.value = true
	hasInk.value = false
	preview.submit({ requirement: row.name }, {
		onSuccess: () => nextTick(() => {
			onScroll()
			clearPad()
		}),
	})
}

function onScroll() {
	const el = textBox.value
	if (!el) return
	if (el.scrollTop + el.clientHeight >= el.scrollHeight - 8) readToEnd.value = true
}

const canSign = computed(() => readToEnd.value && consent.value && signerName.value.trim().length >= 3)

function submitSign() {
	signRes.submit(
		{
			requirement: current.value.name,
			signer_name: signerName.value,
			consent: consent.value ? 1 : 0,
			signature: hasInk.value ? exportSignature() : null,
		},
		{
			onSuccess: () => {
				signOpen.value = false
				createToast({ title: __('Signed'), icon: 'check', iconClasses: 'text-ink-green-3' })
				refresh()
			},
			onError: (e) => createToast({ title: __('Not signed'), text: e.messages?.[0] || e.message, icon: 'x', iconClasses: 'text-ink-red-4' }),
		},
	)
}

// ---------------------------------------------------------------- signature pad
const pad = ref(null)
const hasInk = ref(false)
let drawing = false
// Strokes are kept so the saved image is dark ink on a transparent background,
// whatever theme the pad was drawn in.
let strokes = []

function point(e) {
	const rect = pad.value.getBoundingClientRect()
	return {
		x: ((e.clientX - rect.left) * pad.value.width) / rect.width,
		y: ((e.clientY - rect.top) * pad.value.height) / rect.height,
	}
}

function padDown(e) {
	if (!pad.value) return
	drawing = true
	const ctx = pad.value.getContext('2d')
	const p = point(e)
	ctx.lineWidth = 2
	ctx.lineCap = 'round'
	ctx.strokeStyle = getComputedStyle(pad.value).color
	ctx.beginPath()
	ctx.moveTo(p.x, p.y)
	strokes.push([p])
	pad.value.setPointerCapture?.(e.pointerId)
}

function padMove(e) {
	if (!drawing) return
	const ctx = pad.value.getContext('2d')
	const p = point(e)
	ctx.lineTo(p.x, p.y)
	ctx.stroke()
	strokes[strokes.length - 1].push(p)
	hasInk.value = true
}

function padUp() {
	drawing = false
}

function clearPad() {
	if (!pad.value) return
	pad.value.getContext('2d').clearRect(0, 0, pad.value.width, pad.value.height)
	strokes = []
	hasInk.value = false
}

function exportSignature() {
	const out = document.createElement('canvas')
	out.width = pad.value.width
	out.height = pad.value.height
	const ctx = out.getContext('2d')
	ctx.lineWidth = 2
	ctx.lineCap = 'round'
	ctx.strokeStyle = '#111111'
	for (const stroke of strokes) {
		ctx.beginPath()
		stroke.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)))
		ctx.stroke()
	}
	return out.toDataURL('image/png')
}
</script>
