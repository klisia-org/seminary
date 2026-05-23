<template>
	<div v-if="!url" class="text-sm text-ink-gray-5 p-4">
		{{ __('No PDF attached.') }}
	</div>
	<div v-else class="space-y-3">
		<div v-if="loading" class="text-sm text-ink-gray-5">
			{{ __('Loading PDF…') }}
		</div>
		<div v-else-if="loadError" class="text-sm text-ink-red-3">
			{{ __('Could not load PDF.') }}
			<a :href="url" target="_blank" rel="noopener" class="underline ml-1">
				{{ __('Download') }}
			</a>
		</div>
		<div v-else class="flex items-center justify-between text-xs text-ink-gray-5">
			<span>{{ __('Page') }} 1 – {{ pageCount }}</span>
			<span v-if="canComment">{{ __('Click a page to drop a pin.') }}</span>
		</div>

		<div
			v-for="page in pageList"
			:key="page.num"
			:ref="(el) => setPageRef(el, page.num)"
			class="pdf-page relative border rounded-md overflow-hidden bg-surface-white select-none"
			:class="canComment ? 'cursor-crosshair' : ''"
			@click="onPageClick($event, page.num)"
		>
			<canvas :ref="(el) => setCanvasRef(el, page.num)" class="block w-full h-auto"></canvas>
			<!-- Pin for each Region comment on this page -->
			<button
				v-for="(pin, i) in pinsByPage[page.num] || []"
				:key="pin.name"
				type="button"
				class="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-surface-blue-1 border-2 border-outline-blue-1 text-xs font-semibold text-ink-blue-2 shadow flex items-center justify-center hover:scale-110 transition-transform"
				:class="{
					'ring-2 ring-outline-amber-2 animate-pulse': pulseId === pin.name,
					'ring-2 ring-outline-blue-3 scale-110': activeCommentId === pin.name && pulseId !== pin.name,
					'opacity-50': pin.resolved,
				}"
				:style="{ left: pin.x_pct + '%', top: pin.y_pct + '%' }"
				:title="textPreview(pin.comment)"
				@click.stop="onPinClick(pin)"
				@mouseenter="$emit('active-changed', pin.name)"
				@mouseleave="$emit('active-changed', null)"
			>
				{{ pinNumber(page.num, i) }}
			</button>
			<!-- Pending anchor preview on this page -->
			<div
				v-if="pendingAnchor && pendingAnchor.anchor_type === 'Region' && pendingAnchor.page === page.num"
				class="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-surface-amber-1 border-2 border-outline-amber-2 ring-2 ring-outline-amber-2"
				:style="{ left: pendingAnchor.x_pct + '%', top: pendingAnchor.y_pct + '%' }"
			></div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
	url: { type: String, default: '' },
	scale: { type: Number, default: 1.6 },
	comments: { type: Array, default: () => [] },
	pendingAnchor: { type: Object, default: null },
	activeCommentId: { type: String, default: null },
	canComment: { type: Boolean, default: true },
})

const emit = defineEmits(['anchor-selected', 'active-changed'])

const loading = ref(true)
const loadError = ref(false)
const pageCount = ref(0)
const pageList = ref([])
const pulseId = ref(null)

const pageRefs = new Map()
const canvasRefs = new Map()
let pdfjsLib = null
let pdfDoc = null
let renderToken = 0

function setPageRef(el, num) {
	if (el) pageRefs.set(num, el)
	else pageRefs.delete(num)
}
function setCanvasRef(el, num) {
	if (el) canvasRefs.set(num, el)
	else canvasRefs.delete(num)
}

const pinsByPage = computed(() => {
	const map = {}
	for (const c of props.comments) {
		if (c.anchor_type !== 'Region') continue
		const p = c.page || 1
		if (!map[p]) map[p] = []
		map[p].push(c)
	}
	return map
})

function pinNumber(pageNum, indexInPage) {
	// Number pins across the whole document so the sidebar list aligns.
	let n = 0
	for (let i = 1; i < pageNum; i++) n += (pinsByPage.value[i] || []).length
	return n + indexInPage + 1
}

async function ensurePdfjs() {
	if (pdfjsLib) return pdfjsLib
	const lib = await import('pdfjs-dist')
	const workerUrl = (await import('pdfjs-dist/build/pdf.worker.min.mjs?url')).default
	lib.GlobalWorkerOptions.workerSrc = workerUrl
	pdfjsLib = lib
	return lib
}

async function renderPdf() {
	if (!props.url) return
	const token = ++renderToken
	loading.value = true
	loadError.value = false
	pageList.value = []
	pageRefs.clear()
	canvasRefs.clear()

	try {
		const lib = await ensurePdfjs()
		pdfDoc = await lib.getDocument(props.url).promise
		if (token !== renderToken) return
		pageCount.value = pdfDoc.numPages
		pageList.value = Array.from({ length: pdfDoc.numPages }, (_, i) => ({ num: i + 1 }))
		loading.value = false
		await nextTick()
		// Render each page into its canvas, in order. Skip if a newer load started.
		for (let i = 1; i <= pdfDoc.numPages; i++) {
			if (token !== renderToken) return
			const page = await pdfDoc.getPage(i)
			const viewport = page.getViewport({ scale: props.scale })
			const canvas = canvasRefs.get(i)
			if (!canvas) continue
			canvas.width = viewport.width
			canvas.height = viewport.height
			await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise
		}
	} catch (err) {
		console.error('PDF render failed:', err)
		loadError.value = true
		loading.value = false
	}
}

function onPageClick(e, pageNum) {
	// Students review read-only — no fake pin on click.
	if (!props.canComment) return
	const wrapper = pageRefs.get(pageNum)
	if (!wrapper) return
	const rect = wrapper.getBoundingClientRect()
	const x = ((e.clientX - rect.left) / rect.width) * 100
	const y = ((e.clientY - rect.top) / rect.height) * 100
	emit('anchor-selected', {
		anchor_type: 'Region',
		page: pageNum,
		x_pct: Math.max(0, Math.min(100, x)),
		y_pct: Math.max(0, Math.min(100, y)),
	})
}

function onPinClick(pin) {
	pulseId.value = pin.name
	setTimeout(() => {
		if (pulseId.value === pin.name) pulseId.value = null
	}, 1500)
}

function jumpTo(comment) {
	if (!comment) return
	if (comment.anchor_type !== 'Region' && comment.anchor_type !== 'Page') return
	const pageNum = comment.page || 1
	const wrapper = pageRefs.get(pageNum)
	if (wrapper) {
		wrapper.scrollIntoView({ behavior: 'smooth', block: 'start' })
	}
	pulseId.value = comment.name
	setTimeout(() => {
		if (pulseId.value === comment.name) pulseId.value = null
	}, 1500)
}

function textPreview(html) {
	const tmp = document.createElement('div')
	tmp.innerHTML = html || ''
	return (tmp.textContent || '').slice(0, 120)
}

defineExpose({ jumpTo })

onMounted(renderPdf)
watch(() => props.url, renderPdf)
</script>
