<template>
	<div class="recorder-plugin rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-4">
		<!-- Permission / device error -->
		<div v-if="error" class="text-center py-6">
			<VideoOff class="mx-auto h-8 w-8 text-ink-gray-5 mb-2" />
			<p class="text-sm text-ink-gray-7 mb-3">{{ error }}</p>
			<Button @click="startCamera">{{ __('Try again') }}</Button>
		</div>

		<template v-else>
			<!-- Live camera preview (idle + recording) -->
			<div v-show="phase === 'ready' || phase === 'recording'" class="relative">
				<video ref="previewRef" autoplay muted playsinline
					class="w-full rounded-md bg-black aspect-video object-cover"></video>
				<div v-if="phase === 'recording'"
					class="absolute top-2 left-2 flex items-center gap-1.5 rounded-full bg-black/60 px-2 py-1">
					<span class="h-2.5 w-2.5 rounded-full bg-red-500 animate-pulse"></span>
					<span class="text-xs font-medium text-white tabular-nums">{{ formatTime(elapsed) }}</span>
					<span class="text-xs text-white/70">/ {{ formatTime(maxSeconds) }}</span>
				</div>
			</div>

			<!-- Recorded clip preview -->
			<div v-show="phase === 'recorded' || phase === 'uploading'">
				<video ref="playbackRef" controls playsinline
					class="w-full rounded-md bg-black aspect-video object-cover"></video>
			</div>

			<!-- Controls -->
			<div class="mt-3 flex flex-wrap items-center justify-center gap-2">
				<div v-if="phase === 'requesting'" class="text-sm text-ink-gray-6 py-2">
					{{ __('Requesting camera and microphone…') }}
				</div>

				<div v-if="phase === 'ready'" class="flex flex-col items-center gap-1.5">
					<Button variant="solid" theme="red" @click="startRecording">
						<template #prefix><Circle class="h-4 w-4 fill-current" /></template>
						{{ __('Start recording') }}
					</Button>
					<span class="text-xs text-ink-gray-5">
						<template v-if="capMb">
							{{ __('Up to {0} or {1} MB, whichever comes first.').format(formatTime(maxSeconds), capMb) }}
						</template>
						<template v-else>
							{{ __('Up to {0} — keep it short.').format(formatTime(maxSeconds)) }}
						</template>
					</span>
				</div>

				<Button v-if="phase === 'recording'" variant="solid" @click="stopRecording">
					<template #prefix><Square class="h-4 w-4 fill-current" /></template>
					{{ __('Stop') }}
				</Button>

				<div v-if="phase === 'recorded' && stoppedAtCap" class="w-full text-center text-xs text-ink-amber-3">
					{{ __('Recording stopped at the {0} MB limit. Everything up to that point was kept.').format(capMb) }}
				</div>

				<template v-if="phase === 'recorded'">
					<Button @click="reset">
						<template #prefix><RotateCcw class="h-4 w-4" /></template>
						{{ __('Re-record') }}
					</Button>
					<Button variant="solid" @click="useRecording">
						<template #prefix><Check class="h-4 w-4" /></template>
						{{ __('Use this recording') }}
					</Button>
				</template>

				<div v-if="phase === 'uploading'" class="text-sm text-ink-gray-6 py-2">
					{{ __('Uploading…') }} {{ progress }}%
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Button, FileUploadHandler, toast } from 'frappe-ui'
import { Circle, Square, RotateCcw, Check, VideoOff } from 'lucide-vue-next'
import { uploadLimits } from '@/utils'

const props = defineProps({
	maxSeconds: {
		type: Number,
		default: 180,
	},
	onRecorded: {
		type: Function,
		required: true,
	},
})

const previewRef = ref(null)
const playbackRef = ref(null)
// requesting -> ready -> recording -> recorded -> uploading
const phase = ref('requesting')
const error = ref('')
const elapsed = ref(0)
const progress = ref(0)

// The clock is not a size limit. `videoBitsPerSecond` is a *hint* a browser may
// ignore, and screen capture of a moving window routinely encodes far above it,
// so a clip well inside `maxSeconds` can still be several times the size the
// server accepts. Watching the bytes as they arrive is what makes the ceiling
// real; the alternative is discovering it only after a full take, when the
// recording cannot be recovered.
const capBytes = computed(
	() => (uploadLimits.data?.max_recording_mb || 0) * 1024 * 1024
)
const capMb = computed(() => uploadLimits.data?.max_recording_mb || 0)
const stoppedAtCap = ref(false)

let stream = null
let recorder = null
let chunks = []
let recordedBytes = 0
let timer = null
let recordedBlob = null
let recordedExt = 'webm'
let playbackUrl = null
// Guards against a getUserMedia promise resolving after the block has been
// torn down — otherwise the camera would stay held with nothing to show it.
let alive = true

const pickMimeType = () => {
	const candidates = [
		'video/webm;codecs=vp9,opus',
		'video/webm;codecs=vp8,opus',
		'video/webm',
		'video/mp4',
	]
	for (const type of candidates) {
		if (window.MediaRecorder && MediaRecorder.isTypeSupported(type)) return type
	}
	return ''
}

const attachPreview = async () => {
	const v = previewRef.value
	if (!v || !stream) return
	v.srcObject = stream
	try {
		// Binding srcObject to a just-shown element doesn't reliably autoplay on
		// repeat use, leaving a black preview — start playback explicitly.
		await v.play()
	} catch (e) {
		/* muted playback should still proceed; ignore autoplay rejection */
	}
}

const startCamera = async () => {
	error.value = ''
	phase.value = 'requesting'
	// Drop any stream still held from a previous attempt before requesting again.
	stopStream()
	try {
		const media = await navigator.mediaDevices.getUserMedia({
			video: { width: { ideal: 1280 }, height: { ideal: 720 } },
			audio: true,
		})
		// The block may have been torn down while permission was pending.
		if (!alive) {
			media.getTracks().forEach((t) => t.stop())
			return
		}
		stream = media
		// Make the preview visible first, then bind + play once it's in the DOM.
		phase.value = 'ready'
		await nextTick()
		await attachPreview()
	} catch (e) {
		if (e?.name === 'NotAllowedError') {
			error.value = __('Camera/microphone access was blocked. Allow it in your browser, then try again.')
		} else if (e?.name === 'NotFoundError') {
			error.value = __('No camera or microphone was found on this device.')
		} else {
			error.value = __('Could not start the camera: ') + (e?.message || e)
		}
		phase.value = 'requesting'
	}
}

const startRecording = () => {
	if (!stream) return
	const mimeType = pickMimeType()
	if (!window.MediaRecorder) {
		error.value = __('Recording is not supported in this browser. Please use a recent Chrome, Edge or Firefox.')
		return
	}
	recordedExt = mimeType.includes('mp4') ? 'mp4' : 'webm'
	chunks = []
	recordedBytes = 0
	stoppedAtCap.value = false
	// Cap the bitrate so a short clip stays small (~11 MB/min) — the point of
	// recording in-platform is to avoid the huge files raw recorders produce.
	const options = { videoBitsPerSecond: 1_500_000, audioBitsPerSecond: 96_000 }
	if (mimeType) options.mimeType = mimeType
	try {
		recorder = new MediaRecorder(stream, options)
	} catch (e) {
		recorder = new MediaRecorder(stream)
	}
	recorder.ondataavailable = (e) => {
		if (!e.data || e.data.size <= 0) return
		chunks.push(e.data)
		recordedBytes += e.data.size
		// Stop on the last chunk that still fits. Everything recorded so far is
		// kept and usable — better than letting the take run on and refusing all
		// of it at upload.
		if (capBytes.value && recordedBytes >= capBytes.value) {
			stoppedAtCap.value = true
			stopRecording()
		}
	}
	recorder.onstop = () => finalizeRecording()
	recorder.start(1000)
	phase.value = 'recording'
	elapsed.value = 0
	timer = setInterval(() => {
		elapsed.value += 1
		if (elapsed.value >= props.maxSeconds) stopRecording()
	}, 1000)
}

const stopRecording = () => {
	clearInterval(timer)
	timer = null
	if (recorder && recorder.state !== 'inactive') {
		recorder.stop()
	}
}

const finalizeRecording = () => {
	recordedBlob = new Blob(chunks, { type: recorder?.mimeType || 'video/webm' })
	if (playbackUrl) URL.revokeObjectURL(playbackUrl)
	playbackUrl = URL.createObjectURL(recordedBlob)
	phase.value = 'recorded'
	// Stop the live camera; we keep the recorded blob.
	stopStream()
	setTimeout(() => {
		const v = playbackRef.value
		if (!v) return
		v.src = playbackUrl
		// Resolve the real duration up front so the native scrubber isn't stuck
		// at Infinity for the freshly recorded WebM blob.
		v.onloadedmetadata = () => {
			if (!isFinite(v.duration)) {
				v.ontimeupdate = () => {
					v.ontimeupdate = null
					v.currentTime = 0
				}
				v.currentTime = 1e101
			}
		}
	}, 0)
}

const useRecording = async () => {
	if (!recordedBlob) return
	// The byte watch above normally prevents this, but a browser that delivers
	// one very large final chunk can still overshoot, and the server refuses an
	// oversized body before any app code runs — so the failure would arrive as a
	// bare 413 with no message in it. Say the number here instead.
	if (capBytes.value && recordedBlob.size > capBytes.value) {
		toast.error(
			__('This recording is {0} MB, over the {1} MB limit. Please record a shorter clip.').format(
				Math.round(recordedBlob.size / (1024 * 1024)),
				capMb.value
			)
		)
		return
	}
	phase.value = 'uploading'
	progress.value = 0
	const fileName = `lesson-recording-${Date.now()}.${recordedExt}`
	const file = new File([recordedBlob], fileName, { type: recordedBlob.type })
	const uploader = new FileUploadHandler()
	uploader.on('progress', (data) => {
		if (data?.total) progress.value = Math.floor((data.uploaded / data.total) * 100)
	})
	try {
		const doc = await uploader.upload(file, {
			private: false,
			folder: 'Home/Attachments',
		})
		props.onRecorded({ file_url: doc.file_url, file_type: recordedExt })
	} catch (e) {
		// "Try again" is bad advice for a size refusal — the same bytes fail the
		// same way. Name the limit when that is what happened.
		const tooLarge = e?.status === 413 || /413|too large|entity/i.test(e?.message || '')
		toast.error(
			tooLarge && capMb.value
				? __('This recording is too large for the server ({0} MB limit). Please record a shorter clip.').format(
						capMb.value
				  )
				: __('Upload failed. Please try again.')
		)
		phase.value = 'recorded'
	}
}

const reset = () => {
	if (playbackUrl) {
		URL.revokeObjectURL(playbackUrl)
		playbackUrl = null
	}
	recordedBlob = null
	chunks = []
	elapsed.value = 0
	startCamera()
}

const stopStream = () => {
	if (stream) {
		stream.getTracks().forEach((t) => t.stop())
		stream = null
	}
}

const formatTime = (totalSeconds) => {
	const m = Math.floor(totalSeconds / 60)
	const s = Math.floor(totalSeconds % 60)
	return `${m}:${s < 10 ? '0' : ''}${s}`
}

onMounted(() => startCamera())

onBeforeUnmount(() => {
	alive = false
	clearInterval(timer)
	stopStream()
	if (playbackUrl) URL.revokeObjectURL(playbackUrl)
})
</script>
