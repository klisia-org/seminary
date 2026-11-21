<template>
  <div class="rounded-md border p-4 text-left">
    <div v-if="phase === 'idle'" class="space-y-3">
      <p class="text-sm text-ink-gray-7">{{ noticeText }}</p>
      <Button variant="solid" @click="begin">
        {{ prepareS ? __('Show the question and start') : __('Start recording') }}
      </Button>
    </div>

    <div v-else-if="phase === 'preparing'" class="space-y-2">
      <slot name="question" />
      <div class="text-sm text-ink-gray-7">
        {{ __('Recording starts in {0} seconds.').format(countdown) }}
      </div>
      <ProgressBar :progress="(countdown / Math.max(prepareS, 1)) * 100" />
      <Button variant="solid" :loading="startingEarly" @click="startNow">{{ __('Start now') }}</Button>
    </div>

    <div v-else-if="phase === 'recording'" class="space-y-3">
      <slot name="question" />
      <div class="flex items-center gap-2 text-ink-red-4 font-medium" role="status">
        <span class="inline-block w-3 h-3 rounded-full bg-surface-red-5 animate-pulse" />
        {{ __('Recording') }} {{ clock(elapsed) }} / {{ clock(maxS) }}
      </div>
      <p class="text-xs text-ink-gray-5">{{ noticeText }}</p>
      <Button variant="outline" @click="stop">{{ __('Stop and save') }}</Button>
    </div>

    <div v-else-if="phase === 'saving'" class="text-sm text-ink-gray-7" role="status">
      {{ __('Saving your answer... ({0} of {1} pieces sent)').format(sent, chunks.length) }}
    </div>

    <div v-else-if="phase === 'done'" class="text-sm text-ink-green-3">
      {{ __('Your answer was saved.') }}
    </div>

    <div v-else-if="phase === 'error'" class="space-y-2">
      <p class="text-sm text-ink-red-4">{{ errorText }}</p>
      <Button v-if="recording && chunks.length" variant="outline" @click="finish">
        {{ __('Try saving again') }}
      </Button>
    </div>
  </div>
</template>

<script setup>
// Records one oral answer (decisions/100 §3). Audio is sent in pieces while
// it records, so a dropped connection loses seconds, not the answer: every
// piece stays in memory until the server confirms the whole recording.
import { Button, call } from 'frappe-ui'
import { computed, onBeforeUnmount, ref } from 'vue'
import ProgressBar from '@/components/ProgressBar.vue'
import { getCsrfToken } from '@/utils/csrf'

const props = defineProps({
  referenceDoctype: { type: String, required: true },
  referenceName: { type: String, required: true },
  prepareS: { type: Number, default: 0 },
  maxS: { type: Number, default: 180 },
  notice: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['started', 'finished'])

const CHUNK_MS = 5000
const phase = ref('idle')
const countdown = ref(0)
const elapsed = ref(0)
const sent = ref(0)
const errorText = ref('')
const recording = ref(null)
const chunks = ref([])
const uploaded = new Set()
let stream = null
let recorder = null
let ticker = null
let queue = Promise.resolve()

const noticeText = computed(() => {
  const parts = [__('This answer is recorded. Your instructors and school staff can listen to it.')]
  if (props.notice?.steps?.length) {
    parts.push(__('It will be processed by: {0}.').format(props.notice.steps.join(', ')))
  }
  if (props.notice?.retention_days) {
    parts.push(
      __('The audio is kept for {0} days after your grades are sent.').format(props.notice.retention_days)
    )
  }
  parts.push(__('There is no pause once recording starts.'))
  return parts.join(' ')
})

const clock = (s) => {
  const m = Math.floor(s / 60)
  const r = Math.floor(s % 60)
  return `${m}:${String(r).padStart(2, '0')}`
}

const pickMimeType = () => {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
  return types.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || ''
}

const fail = (text) => {
  errorText.value = text
  phase.value = 'error'
  clearInterval(ticker)
}

const begin = async () => {
  try {
    // Ask for the microphone first, so the permission prompt does not eat
    // the reading time.
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch (e) {
    fail(__('The microphone is not available. Allow microphone access for this site and try again.'))
    return
  }
  if (props.prepareS > 0) {
    startingEarly.value = false
    phase.value = 'preparing'
    countdown.value = props.prepareS
    ticker = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) {
        clearInterval(ticker)
        start()
      }
    }, 1000)
  } else {
    start()
  }
}

// The student may end the reading time early (100a §2).
const startingEarly = ref(false)
const startNow = () => {
  if (startingEarly.value) return
  startingEarly.value = true
  clearInterval(ticker)
  start()
}

const start = async () => {
  const mimeType = pickMimeType()
  try {
    const r = await call('seminary.seminary.oral.start_recording', {
      reference_doctype: props.referenceDoctype,
      reference_name: props.referenceName,
      mime_type: mimeType || 'audio/webm',
    })
    recording.value = r.recording
  } catch (e) {
    stream?.getTracks().forEach((t) => t.stop())
    fail(e.messages?.[0] || __('The recording could not start.'))
    return
  }
  emit('started', recording.value)
  recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
  recorder.ondataavailable = (e) => {
    if (!e.data || !e.data.size) return
    const seq = chunks.value.length
    chunks.value.push(e.data)
    queue = queue.then(() => upload(seq))
  }
  recorder.onstop = () => finish()
  recorder.start(CHUNK_MS)
  phase.value = 'recording'
  elapsed.value = 0
  const started = Date.now()
  ticker = setInterval(() => {
    elapsed.value = Math.floor((Date.now() - started) / 1000)
    if (elapsed.value >= props.maxS) stop()
  }, 250)
}

const stop = () => {
  clearInterval(ticker)
  if (recorder && recorder.state !== 'inactive') recorder.stop()
  stream?.getTracks().forEach((t) => t.stop())
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const upload = async (seq) => {
  // Retry with backoff; the piece stays in memory, so nothing is lost while
  // the connection is down.
  for (let attempt = 0; ; attempt++) {
    try {
      const form = new FormData()
      form.append('recording', recording.value)
      form.append('seq', String(seq))
      form.append('chunk', chunks.value[seq], `chunk-${seq}`)
      const headers = {}
      const token = getCsrfToken()
      if (token) headers['X-Frappe-CSRF-Token'] = token
      const response = await fetch('/api/method/seminary.seminary.oral.upload_chunk', {
        method: 'POST',
        body: form,
        headers,
        credentials: 'same-origin',
      })
      if (response.ok) {
        uploaded.add(seq)
        sent.value = uploaded.size
        return
      }
      if (response.status === 403 || response.status === 417) {
        // Refused, not a network problem: retrying will not help.
        const body = await response.json().catch(() => ({}))
        throw Object.assign(new Error('refused'), { refused: true, body })
      }
    } catch (e) {
      if (e.refused) throw e
    }
    await sleep(Math.min(30000, 1000 * 2 ** attempt))
  }
}

const finish = async () => {
  phase.value = 'saving'
  try {
    await queue
    for (let round = 0; round < 3; round++) {
      try {
        await call('seminary.seminary.oral.finish_recording', {
          recording: recording.value,
          chunks: chunks.value.length,
        })
        phase.value = 'done'
        emit('finished', recording.value)
        return
      } catch (e) {
        // Resend whatever the server says it has not got, then try again.
        const have = new Set(
          await call('seminary.seminary.oral.received_chunks', { recording: recording.value }).catch(() => [])
        )
        for (let seq = 0; seq < chunks.value.length; seq++) {
          if (!have.has(seq)) await upload(seq)
        }
      }
    }
    fail(__('Your answer could not be saved yet. Check your connection and try again.'))
  } catch (e) {
    fail(__('Your answer could not be saved. Ask your instructor for help.'))
  }
}

const busy = computed(() => ['preparing', 'recording', 'saving'].includes(phase.value))
defineExpose({ busy })

const beforeUnload = (e) => {
  if (busy.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnload)
  clearInterval(ticker)
  if (recorder && recorder.state !== 'inactive') recorder.stop()
  stream?.getTracks().forEach((t) => t.stop())
})
</script>
