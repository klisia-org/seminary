<template>
  <div v-if="rec.data" class="rounded-md border p-3 space-y-3 text-left">
    <div class="flex items-center justify-between text-xs text-ink-gray-5">
      <span>{{ __('Oral answer') }} · {{ clock(rec.data.duration_s || 0) }}</span>
      <span v-if="rec.data.status === 'Processing' || rec.data.status === 'Recorded'">
        {{ __('Transcription in progress') }}
      </span>
      <span v-else-if="rec.data.status === 'Recording'">{{ __('Still recording') }}</span>
      <span v-else-if="rec.data.status === 'Failed'" class="text-ink-red-4">
        {{ __('Processing failed') }}<template v-if="rec.data.error">: {{ rec.data.error }}</template>
      </span>
    </div>

    <audio v-if="rec.data.audio" ref="audio" :src="rec.data.audio" controls preload="metadata" class="w-full"
      @timeupdate="now = $event.target.currentTime" />
    <div v-else-if="rec.data.audio_deleted_on" class="text-xs text-ink-gray-5">
      {{ __('The audio was deleted after the retention period. The transcript is kept.') }}
    </div>

    <div v-if="speakerBars.length > 1" class="space-y-1">
      <div v-for="s in speakerBars" :key="s.label" class="flex items-center gap-2 text-xs">
        <span class="w-28 truncate">{{ s.name }}</span>
        <div class="flex-1 h-2 rounded bg-surface-gray-2">
          <div class="h-2 rounded bg-surface-gray-7" :style="{ width: s.share + '%' }" />
        </div>
        <span class="w-24 text-right">{{ clock(s.talk_s) }} · {{ s.share }}%</span>
      </div>
    </div>

    <div v-if="rec.data.transcript.length" class="max-h-64 overflow-y-auto space-y-1 text-sm">
      <button v-for="(seg, i) in rec.data.transcript" :key="i" type="button"
        class="block w-full text-left rounded px-1 hover:bg-surface-gray-2"
        :class="isCurrent(seg) ? 'bg-surface-blue-1' : ''" @click="seek(seg.start)">
        <span class="text-xs text-ink-gray-5 mr-2">{{ clock(seg.start) }}</span>
        <span v-if="seg.speaker && speakerBars.length > 1" class="text-xs font-medium mr-1">{{ seg.speaker }}:</span>
        {{ seg.text }}
      </button>
    </div>

    <div v-if="rec.data.is_staff" class="space-y-2 border-t pt-2">
      <div class="flex items-center gap-2">
        <FormControl v-model="note" class="flex-1" :placeholder="__('Note for this moment')" />
        <Button size="sm" @click="mark">{{ __('Mark moment at {0}').format(clock(now)) }}</Button>
      </div>
      <div v-for="m in rec.data.moments" :key="m.name" class="flex items-start gap-2 text-xs">
        <button type="button" class="text-ink-blue-3 underline" @click="seek(m.start)">{{ clock(m.start) }}</button>
        <span class="flex-1">
          <span v-if="m.source === 'Suggested'" class="mr-1 rounded bg-surface-amber-1 px-1">{{ __('Suggested') }}</span>
          <span v-if="m.criterion_code" class="mr-1 font-medium">{{ m.criterion_code }}</span>
          {{ m.note }}
        </span>
        <template v-if="m.state === 'Suggested'">
          <Button size="sm" variant="ghost" @click="setState(m, 'Kept')">{{ __('Keep') }}</Button>
          <Button size="sm" variant="ghost" @click="setState(m, 'Dismissed')">{{ __('Dismiss') }}</Button>
        </template>
        <Button v-else size="sm" variant="ghost" @click="setState(m, 'Dismissed')">{{ __('Remove') }}</Button>
      </div>
    </div>
  </div>
</template>

<script setup>
// Plays one oral recording beside its transcript (decisions/100 §2, 100a §4).
// Clicking a line seeks to it; the section's staff also see and mark moments.
import { Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
  recording: { type: String, required: true },
  question: { type: String, default: null },
})

const audio = ref(null)
const now = ref(0)
const note = ref('')

const rec = createResource({
  url: 'seminary.seminary.oral.get_recording',
  makeParams: () => ({ recording: props.recording }),
  auto: true,
})
watch(() => props.recording, () => rec.reload())

const clock = (s) => {
  const v = Math.max(0, Math.floor(s || 0))
  return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`
}

const seek = (t) => {
  if (!audio.value) return
  audio.value.currentTime = t
  audio.value.play()
}

const isCurrent = (seg) => now.value >= seg.start && now.value < seg.end

const speakerBars = computed(() => {
  const speakers = rec.data?.speakers || []
  const total = speakers.reduce((sum, s) => sum + (s.talk_s || 0), 0) || 1
  return speakers.map((s) => ({
    ...s,
    name: s.student || s.label,
    share: Math.round(((s.talk_s || 0) / total) * 100),
  }))
})

const mark = async () => {
  try {
    await call('seminary.seminary.oral.add_moment', {
      recording: props.recording,
      start: now.value,
      note: note.value,
      question: props.question,
    })
    note.value = ''
    rec.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || __('The moment could not be saved.'))
  }
}

const setState = async (m, state) => {
  try {
    await call('seminary.seminary.oral.set_moment_state', { moment: m.name, state })
    rec.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || __('The moment could not be changed.'))
  }
}
</script>
