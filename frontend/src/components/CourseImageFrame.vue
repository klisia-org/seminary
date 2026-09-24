<template>
	<!-- The course tile's image, framed by a focus point and zoom (ADR 080).
	     The same component draws the tile and the editor preview, so what the
	     instructor frames is what the course list shows. -->
	<div
		ref="box"
		class="relative overflow-hidden bg-surface-gray-2"
		:class="editable ? 'cursor-grab touch-none select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-4' : ''"
		style="aspect-ratio: 3 / 2"
		:tabindex="editable ? 0 : undefined"
		:role="editable ? 'application' : undefined"
		:aria-label="editable ? __('Course image framing. Drag or use the arrow keys to move, + and - to zoom.') : undefined"
		@pointerdown="onPointerDown"
		@pointermove="onPointerMove"
		@pointerup="onPointerUp"
		@pointercancel="onPointerUp"
		@wheel="onWheel"
		@keydown="onKeydown"
	>
		<img
			v-if="src"
			ref="img"
			:src="src"
			alt=""
			draggable="false"
			class="absolute inset-0 size-full object-cover"
			:style="{
				objectPosition: `${x}% ${y}%`,
				transform: `scale(${zoom})`,
				transformOrigin: `${x}% ${y}%`,
			}"
		/>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
	src: { type: String, default: '' },
	focusX: { type: Number, default: 50 },
	focusY: { type: Number, default: 50 },
	zoom: { type: Number, default: 1 },
	editable: { type: Boolean, default: false },
})

const emit = defineEmits(['update:focusX', 'update:focusY', 'update:zoom'])

const MIN_ZOOM = 1
const MAX_ZOOM = 3

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi)

// Records saved before the fields existed read as null.
const x = computed(() => clamp(props.focusX ?? 50, 0, 100))
const y = computed(() => clamp(props.focusY ?? 50, 0, 100))
const zoom = computed(() => clamp(props.zoom || 1, MIN_ZOOM, MAX_ZOOM))

const box = ref(null)
const img = ref(null)
let drag = null

// How far, in pixels, the zoomed image overhangs the box on each axis. The
// image's edge sits at -focus% of that overhang, so a drag of d pixels moves
// the focus by d / overhang.
const overhang = () => {
	const el = img.value
	const b = box.value
	if (!el?.naturalWidth || !b) return { w: 0, h: 0 }
	const bw = b.clientWidth
	const bh = b.clientHeight
	const cover = Math.max(bw / el.naturalWidth, bh / el.naturalHeight)
	return {
		w: el.naturalWidth * cover * zoom.value - bw,
		h: el.naturalHeight * cover * zoom.value - bh,
	}
}

const moveBy = (dx, dy) => {
	const o = overhang()
	if (o.w > 0.5) emit('update:focusX', round(clamp(x.value - (dx / o.w) * 100, 0, 100)))
	if (o.h > 0.5) emit('update:focusY', round(clamp(y.value - (dy / o.h) * 100, 0, 100)))
}

const zoomTo = (z) => emit('update:zoom', round(clamp(z, MIN_ZOOM, MAX_ZOOM)))

const round = (v) => Math.round(v * 100) / 100

const onPointerDown = (e) => {
	if (!props.editable || !props.src) return
	box.value.setPointerCapture(e.pointerId)
	drag = { x: e.clientX, y: e.clientY }
}

const onPointerMove = (e) => {
	if (!drag) return
	moveBy(e.clientX - drag.x, e.clientY - drag.y)
	drag = { x: e.clientX, y: e.clientY }
}

const onPointerUp = () => {
	drag = null
}

const onWheel = (e) => {
	if (!props.editable || !props.src) return
	e.preventDefault()
	zoomTo(zoom.value * Math.exp(-e.deltaY * 0.002))
}

const onKeydown = (e) => {
	if (!props.editable || !props.src) return
	const step = e.shiftKey ? 40 : 10
	const moves = {
		ArrowLeft: [step, 0],
		ArrowRight: [-step, 0],
		ArrowUp: [0, step],
		ArrowDown: [0, -step],
	}
	if (moves[e.key]) {
		moveBy(...moves[e.key])
	} else if (e.key === '+' || e.key === '=') {
		zoomTo(zoom.value + 0.1)
	} else if (e.key === '-') {
		zoomTo(zoom.value - 0.1)
	} else {
		return
	}
	e.preventDefault()
}
</script>
