<!--
	A video assignment's answer: recorded here at 720p, or a video file the
	student already has (privatedocs p029 §3, §4). Either way the bytes go
	straight to storage in parts; `done` gives the File row to submit.

	<VideoSubmission :assignment="name" @done="(file) => saveSubmission(file)" />
-->
<template>
	<div class="space-y-3">
		<p class="text-xs text-ink-gray-6 leading-5">
			{{ notice }}
		</p>

		<div v-if="error" class="rounded-md bg-surface-red-1 p-2 text-sm text-ink-red-4">{{ error }}</div>

		<div v-if="phase === 'idle'" class="flex flex-wrap items-center gap-2">
			<Button variant="solid" :disabled="!limits.data?.offered" @click="startCamera">
				{{ __('Record a video') }}
			</Button>
			<Button :disabled="!limits.data?.offered" @click="fileInput?.click()">
				{{ __('Upload a video') }}
			</Button>
			<input ref="fileInput" type="file" class="hidden" accept="video/mp4,video/webm,video/quicktime,.mp4,.mov,.webm,.m4v"
				:aria-label="__('Upload a video')" @change="onFile" />
			<span class="text-sm text-ink-gray-5">
				{{ __('Up to {0} minutes ({1} MB).').format(maxMinutes, maxMb) }}
			</span>
		</div>

		<div v-show="['ready', 'recording', 'finishing'].includes(phase)" class="space-y-2">
			<!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -- live camera preview, muted -->
			<video ref="preview" muted playsinline autoplay class="aspect-video w-full rounded-md bg-black" />
			<div class="flex items-center gap-3">
				<Button v-if="phase === 'ready'" variant="solid" theme="red" @click="startRecording">
					{{ __('Start recording') }}
				</Button>
				<Button v-if="phase === 'ready'" @click="cancel">{{ __('Cancel') }}</Button>
				<template v-if="phase === 'recording'">
					<span class="flex items-center gap-1 text-sm font-medium text-ink-red-4" role="status">
						<span class="inline-block h-2 w-2 rounded-full bg-surface-red-5 animate-pulse" />
						{{ __('Recording') }} {{ clock(elapsed) }} / {{ clock(maxMinutes * 60) }}
					</span>
					<Button variant="solid" @click="stopRecording">{{ __('Stop and submit') }}</Button>
				</template>
				<span v-if="phase === 'finishing'" class="text-sm text-ink-gray-6" role="status">
					{{ __('Saving the video… {0}%').format(progress) }}
				</span>
			</div>
		</div>

		<div v-if="phase === 'uploading'" class="text-sm text-ink-gray-6" role="status">
			{{ __('Uploading {0}%').format(progress) }}
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { Button, createResource } from 'frappe-ui'
import { MultipartUpload, uploadVideoFile } from '@/utils/multipartUpload'

const props = defineProps({
	assignment: { type: String, required: true },
})
const emit = defineEmits(['done'])

const limits = createResource({
	url: 'seminary.seminary.video_submissions.video_limits',
	params: { assignment: props.assignment },
	auto: true,
})

const maxMinutes = computed(() => limits.data?.max_minutes || 20)
const maxMb = computed(() => Math.round((limits.data?.max_bytes || 0) / 1048576))

// Students are told, before they start, what happens to the video (100 §7).
const notice = computed(() => {
	const steps = limits.data?.steps || []
	const days = limits.data?.retention_days || 365
	const parts = [__('Your video is stored privately for your instructors.')]
	if (steps.length) parts.push(__('These run on it: {0}.').format(steps.join(', ')))
	parts.push(__('It is deleted {0} days after your course grades are sent; its transcript and comments are kept.').format(days))
	return parts.join(' ')
})

const phase = ref('idle')
const error = ref('')
const progress = ref(0)
const elapsed = ref(0)
const preview = ref(null)
const fileInput = ref(null)
let stream = null
let recorder = null
let upload = null
let timer = null

const clock = (s) => {
	const v = Math.max(0, Math.floor(s || 0))
	return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`
}

// MP4 first: it seeks better than the WebM a recorder writes (decisions/101).
const MIME_TYPES = [
	'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
	'video/mp4',
	'video/webm;codecs=vp9,opus',
	'video/webm;codecs=vp8,opus',
	'video/webm',
]
const pickMimeType = () =>
	MIME_TYPES.find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || ''

const stopStream = () => {
	stream?.getTracks().forEach((t) => t.stop())
	stream = null
}

const startCamera = async () => {
	error.value = ''
	try {
		stream = await navigator.mediaDevices.getUserMedia({
			video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30, max: 30 } },
			audio: true,
		})
		phase.value = 'ready'
		preview.value.srcObject = stream
		await preview.value.play().catch(() => {})
	} catch (e) {
		error.value =
			e?.name === 'NotAllowedError'
				? __('Camera/microphone access was blocked. Allow it in your browser, then try again.')
				: e?.name === 'NotFoundError'
					? __('No camera or microphone was found on this device.')
					: __('Could not start the camera: ') + (e?.message || e)
		phase.value = 'idle'
	}
}

const startRecording = async () => {
	if (!stream || !window.MediaRecorder) {
		error.value = __('Recording is not supported in this browser. Please use a recent Chrome, Edge, Safari or Firefox.')
		return
	}
	const mimeType = pickMimeType()
	const ext = mimeType.includes('mp4') ? 'mp4' : 'webm'
	try {
		upload = await MultipartUpload.start({
			fileName: `video-${Date.now()}.${ext}`,
			contentType: mimeType.split(';')[0] || 'video/webm',
			assignment: props.assignment,
		})
	} catch (e) {
		error.value = e.message
		return
	}
	const options = { videoBitsPerSecond: 1_200_000, audioBitsPerSecond: 96_000 }
	if (mimeType) options.mimeType = mimeType
	try {
		recorder = new MediaRecorder(stream, options)
	} catch (e) {
		recorder = new MediaRecorder(stream)
	}
	recorder.ondataavailable = (e) => {
		if (!e.data?.size) return
		upload.push(e.data)
		// Stop on the last piece that fits: what is recorded is kept.
		if (upload.size >= upload.maxBytes - upload.partSize) stopRecording()
	}
	recorder.onstop = finish
	recorder.start(1000)
	phase.value = 'recording'
	elapsed.value = 0
	timer = setInterval(() => {
		elapsed.value += 1
		if (elapsed.value >= maxMinutes.value * 60) stopRecording()
	}, 1000)
}

const stopRecording = () => {
	clearInterval(timer)
	timer = null
	if (recorder && recorder.state !== 'inactive') recorder.stop()
}

const finish = async () => {
	phase.value = 'finishing'
	const total = upload.size || 1
	upload.onProgress = (sent) => (progress.value = Math.min(100, Math.round((sent / total) * 100)))
	try {
		const file = await upload.finish()
		stopStream()
		phase.value = 'idle'
		emit('done', file)
	} catch (e) {
		error.value = __('The video could not be saved: {0}').format(e.message)
		phase.value = 'ready'
	}
}

const onFile = async (event) => {
	const file = event.target.files?.[0]
	event.target.value = ''
	if (!file) return
	error.value = ''
	phase.value = 'uploading'
	progress.value = 0
	try {
		const saved = await uploadVideoFile(file, props.assignment, (p) => (progress.value = p))
		emit('done', saved)
	} catch (e) {
		error.value = e.message
	}
	phase.value = 'idle'
}

const cancel = () => {
	stopStream()
	phase.value = 'idle'
}

onBeforeUnmount(() => {
	clearInterval(timer)
	if (recorder && recorder.state !== 'inactive') {
		recorder.onstop = null
		recorder.stop()
		upload?.abort()
	}
	stopStream()
})
</script>
