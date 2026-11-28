<template>
  <div v-if="rec.data" class="rounded-md border p-3 space-y-3 text-left">
    <div class="flex items-center justify-between text-xs text-ink-gray-5">
      <span v-if="!video">{{ __('Oral answer') }} · {{ clock(rec.data.duration_s || 0) }}</span>
      <span v-else>{{ __('Transcript') }}</span>
      <span v-if="rec.data.status === 'Processing' || rec.data.status === 'Recorded'">
        {{ __('Transcription in progress') }}
      </span>
      <span v-else-if="rec.data.status === 'Recording'">{{ __('Still recording') }}</span>
      <span v-else-if="rec.data.status === 'Failed'" class="text-ink-red-4">
        {{ __('Processing failed') }}<template v-if="rec.data.error">: {{ rec.data.error }}</template>
      </span>
    </div>

    <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -- its transcript is shown below it -->
    <video v-if="video && rec.data.audio" ref="audio" :src="rec.data.audio" controls preload="metadata"
      playsinline class="aspect-video w-full rounded-md bg-black"
      @timeupdate="now = $event.target.currentTime; emit('time', now)" />
    <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -- audio-only recording; its transcript is shown below it -->
    <audio v-else-if="rec.data.audio" ref="audio" :src="rec.data.audio" controls preload="metadata" class="w-full"
      @timeupdate="now = $event.target.currentTime; emit('time', now)" />
    <div v-else-if="rec.data.audio_deleted_on" class="text-xs text-ink-gray-5">
      {{
        (video
          ? __('The video was deleted on {0}, after the retention period. The transcript and comments are kept.')
          : __('The audio was deleted on {0}, after the retention period. The transcript is kept.')
        ).format(dayOf(rec.data.audio_deleted_on))
      }}
    </div>
    <div v-if="video && rec.data.transcript.length === 0 && rec.data.status === 'Ready'" class="text-xs text-ink-gray-5">
      {{ __('No transcript: transcription is not turned on for this assignment.') }}
    </div>

    <div v-if="labelling" class="space-y-1 border-t pt-2">
      <div class="text-xs font-medium text-ink-gray-7">{{ __('Who is speaking?') }}</div>
      <div v-for="s in rec.data.speakers" :key="s.label" class="flex items-center gap-2 text-xs">
        <span class="w-20">{{ s.label }}</span>
        <Button size="sm" variant="ghost" :disabled="firstStart(s.label) === undefined"
          @click="seek(firstStart(s.label))">{{ __('Listen') }}</Button>
        <select :aria-label="__('Student speaking as {0}').format(s.label)" class="form-select text-xs rounded border-outline-gray-2" :value="s.student || ''"
          @change="link(s.label, $event.target.value)">
          <option value="">{{ __('Not a student on the recording') }}</option>
          <option v-for="p in rec.data.people" :key="p.student" :value="p.student">{{ p.name }}</option>
        </select>
      </div>
    </div>

    <div v-if="!rec.data.is_staff && ownTalk" class="text-xs text-ink-gray-6">
      {{ __('You spoke for {0} ({1}% of the conversation), in {2} turns.').format(clock(ownTalk.talk_s), ownTalk.share, ownTalk.turns) }}
    </div>

    <div v-if="rec.data.is_staff && speakerBars.length > 1" class="space-y-1">
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
        class="block w-full min-h-6 text-left rounded px-1 py-0.5 hover:bg-surface-gray-2"
        :class="isCurrent(seg) ? 'bg-surface-blue-1' : ''" @click="seek(seg.start)">
        <span class="text-xs text-ink-gray-5 mr-2">{{ clock(seg.start) }}</span>
        <span v-if="seg.speaker && rec.data.speakers.length > 1" class="text-xs font-medium mr-1">{{ speakerName(seg.speaker) }}:</span>
        {{ seg.text }}
      </button>
    </div>

    <div v-if="panel" class="space-y-2 border-t pt-2 text-xs">
      <div class="font-medium text-ink-gray-7">{{ __('Score suggestions') }}</div>
      <p class="text-ink-gray-5">
        {{ __('For you only. Each model scored on its own; flagged criteria, where they disagree or found too little to go on, come first. You choose every level.') }}
      </p>
      <p v-if="panel.note" class="text-ink-gray-5">{{ panel.note }}</p>
      <div v-for="c in panel.criteria || []" :key="c.criterion_code" class="rounded border p-2"
        :class="c.flagged ? 'border-outline-amber-2 bg-surface-amber-1' : ''">
        <div class="flex items-center justify-between gap-2">
          <span class="font-medium">{{ c.criterion_code }} {{ c.title || '' }}</span>
          <span>
            {{ c.level || __('No level') }}
            <template v-if="c.flagged"> ·
              {{ c.insufficient_evidence ? __('too little to go on') : __('spread {0}').format(c.spread) }}
            </template>
          </span>
        </div>
        <div v-for="(m, i) in c.members" :key="i" class="mt-1 text-ink-gray-6">
          <span class="font-medium">{{ m.level || __('insufficient evidence') }}</span>
          <template v-if="m.reason">: {{ m.reason }}</template>
          <button v-for="(ev, j) in m.evidence || []" :key="j" type="button" class="ml-1 text-ink-blue-3 underline"
            @click="seek(ev.start)">{{ clock(ev.start) }}</button>
        </div>
      </div>
    </div>

    <div v-if="consistency" class="space-y-2 border-t pt-2 text-xs">
      <div class="font-medium text-ink-gray-7">{{ __('Consistency notes') }}</div>
      <p class="text-ink-gray-5">
        {{ __('For you only, and not evidence of misconduct on its own: points where what was said differs from the written work, to ask about.') }}
      </p>
      <p v-if="consistency.note || consistency.summary">{{ consistency.summary || consistency.note }}</p>
      <div v-for="(d, i) in consistency.differences || []" :key="i" class="rounded border p-2">
        <button v-if="d.start !== undefined && d.start !== null" type="button" class="text-ink-blue-3 underline mr-1"
          @click="seek(d.start)">{{ clock(d.start) }}</button>
        <span v-if="d.spoken">{{ __('Said') }}: {{ d.spoken }}. </span>
        <span v-if="d.written">{{ __('Written') }}: {{ d.written }}. </span>
        <span v-if="d.note" class="text-ink-gray-6">{{ d.note }}</span>
      </div>
    </div>

    <div v-if="rec.data.is_staff" class="space-y-2 border-t pt-2">
      <div v-if="marking" class="flex items-center gap-2">
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
  // A video submission (privatedocs p029 §6): a <video>, and its timestamp
  // comments are marked from the submission's own sidebar, not here.
  video: { type: Boolean, default: false },
  marking: { type: Boolean, default: true },
})
// The playing time, for a peer reviewer placing comments (decisions/120 §5).
// `changed`: a moment was kept or removed, so a video's comments may have changed.
const emit = defineEmits(['time', 'changed'])

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

const dayOf = (value) => String(value || '').slice(0, 10)

const seek = (t) => {
  if (!audio.value) return
  audio.value.currentTime = t
  audio.value.play()
}

const isCurrent = (seg) => now.value >= seg.start && now.value < seg.end

const nameOf = (student) => rec.data?.people?.find((p) => p.student === student)?.name || student

const speakerName = (label) => {
  const s = rec.data?.speakers?.find((r) => r.label === label)
  return s?.student ? nameOf(s.student) : label
}

// Talk time per speaker (100b §6). The server sends a student only their own.
const speakerBars = computed(() => {
  const speakers = (rec.data?.speakers || []).filter((s) => s.talk_s !== undefined)
  const total = speakers.reduce((sum, s) => sum + (s.talk_s || 0), 0) || 1
  return speakers.map((s) => ({
    ...s,
    name: s.student ? nameOf(s.student) : s.label,
    share: Math.round(((s.talk_s || 0) / total) * 100),
  }))
})
// Results only the section's staff receive (score suggestions, consistency).
const latest = (step) => (rec.data?.step_results || []).find((r) => r.step === step)?.result || null
const panel = computed(() => latest('score_suggestions'))
const consistency = computed(() => latest('consistency'))

const ownTalk = computed(() => (rec.data?.speakers || []).find((s) => s.talk_s !== undefined))

const labelling = computed(
  () =>
    rec.data?.may_label &&
    (rec.data?.speakers || []).length > 0 &&
    ((rec.data?.speakers || []).length > 1 || (rec.data?.people || []).length > 1)
)
const firstStart = (label) => rec.data?.transcript?.find((seg) => seg.speaker === label)?.start

const link = async (label, student) => {
  try {
    await call('seminary.seminary.oral.link_speaker', { recording: props.recording, label, student: student || null })
    rec.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || __('The speaker could not be linked.'))
  }
}

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
    emit('changed')
  } catch (e) {
    toast.error(e.messages?.[0] || __('The moment could not be changed.'))
  }
}
defineExpose({ seek, reload: () => rec.reload(), currentTime: () => audio.value?.currentTime || 0 })
</script>
