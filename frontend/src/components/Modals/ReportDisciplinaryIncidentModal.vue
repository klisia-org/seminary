<template>
  <Dialog v-model="show" :options="dialogOptions" :disableOutsideClickToClose="true">
    <template #body-content>
      <div class="space-y-4 text-base max-h-[70vh] overflow-y-auto">
        <!-- Record mode: confirm an action on an existing incident -->
        <template v-if="mode === 'record'">
          <div class="rounded-md bg-surface-gray-1 p-3 text-sm text-ink-gray-7 space-y-1">
            <div><span class="font-medium">{{ __('Student') }}:</span> {{ studentName || student }}</div>
            <div><span class="font-medium">{{ __('Reason') }}:</span> {{ reasonLabel || reason }}</div>
            <div><span class="font-medium">{{ __('Occurrence') }}:</span> #{{ occurrenceNumber }}</div>
          </div>
          <FormControl
            v-if="recordOptions.length > 1"
            type="select"
            v-model="selectedAction"
            :label="__('Action to record')"
            :options="recordOptions"
          />
          <p v-else class="text-sm text-ink-gray-7">
            {{ __('Recommended action') }}: <span class="font-medium">{{ selectedAction }}</span>
          </p>
        </template>

        <!-- Report mode: course or assessment -->
        <template v-else>
          <!-- Subject -->
          <div v-if="mode === 'course'" class="space-y-1.5">
            <label class="block text-xs text-ink-gray-5">
              {{ __('Student') }} <span class="text-ink-red-3">*</span>
            </label>
            <Autocomplete
              :options="ceiOptions"
              :modelValue="cei"
              :placeholder="__('Select a student')"
              @update:modelValue="(val) => (cei = val?.value || '')"
            />
          </div>
          <div
            v-else
            class="rounded-md bg-surface-gray-1 p-3 text-sm text-ink-gray-7 space-y-1"
          >
            <div><span class="font-medium">{{ __('Student') }}:</span> {{ studentName || student }}</div>
            <div><span class="font-medium">{{ __('Assessment') }}:</span> {{ assessmentName || assessment }}</div>
          </div>

          <!-- Reason -->
          <div class="space-y-1.5">
            <label class="block text-xs text-ink-gray-5">
              {{ __('Disciplinary reason') }} <span class="text-ink-red-3">*</span>
            </label>
            <Autocomplete
              :options="reasonOptions"
              :modelValue="selectedReason"
              :placeholder="__('Select a reason')"
              @update:modelValue="(val) => (selectedReason = val?.value || '')"
            />
          </div>

          <!-- Recommendation preview -->
          <div
            v-if="selectedReason && hasSubject"
            class="rounded-md border border-outline-gray-2 p-3 text-sm"
          >
            <p v-if="loadingPreview" class="text-ink-gray-5">{{ __('Evaluating…') }}</p>
            <template v-else>
              <p class="text-ink-gray-7">
                {{ __('This will be occurrence') }} <span class="font-medium">#{{ occurrence }}</span>
                {{ __('for this student and reason.') }}
              </p>
              <p v-if="recommended.length" class="mt-1 text-ink-gray-8">
                {{ __('Recommended action(s)') }}:
                <span class="font-medium">{{ recommendedLabels }}</span>
              </p>
              <p v-if="recommended.length && !canRecord" class="mt-1 text-ink-amber-600">
                {{ __('This action requires review and will be forwarded for adjudication.') }}
              </p>
              <p v-else-if="!recommended.length" class="mt-1 text-ink-gray-5">
                {{ __('No recommended action configured for this occurrence.') }}
              </p>
            </template>
          </div>

          <!-- Evidence -->
          <FormControl
            type="textarea"
            v-model="evidence"
            :label="__('Evidence / description')"
            :placeholder="__('Describe what happened (optional).')"
            :rows="4"
          />
          <div class="space-y-1.5">
            <label class="block text-xs text-ink-gray-5">{{ __('Attachment') }}</label>
            <FileUploader @success="(f) => (evidenceAttach = f.file_url)">
              <template #default="{ uploading, openFileSelector }">
                <Button :loading="uploading" @click="openFileSelector">
                  {{ evidenceAttach ? __('Replace attachment') : __('Add attachment') }}
                </Button>
                <span v-if="evidenceAttach" class="ml-2 text-sm text-ink-gray-6">
                  {{ __('Attached') }}
                </span>
              </template>
            </FileUploader>
          </div>
        </template>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { Dialog, FormControl, FileUploader, Button, call, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import Autocomplete from '@/components/Controls/Autocomplete.vue'

const show = defineModel({ default: false })

const props = defineProps({
  mode: { type: String, default: 'course' }, // 'course' | 'assessment' | 'record'
  course: { type: String, default: '' }, // Course Schedule
  // assessment / record context
  student: { type: String, default: '' },
  studentName: { type: String, default: '' },
  assessment: { type: String, default: '' },
  assessmentName: { type: String, default: '' },
  // record mode
  incident: { type: String, default: '' },
  reason: { type: String, default: '' },
  reasonLabel: { type: String, default: '' },
  occurrenceNumber: { type: [Number, String], default: 0 },
  recommendedActions: { type: Array, default: () => [] },
})

const emit = defineEmits(['reported', 'recorded'])

const selectedReason = ref('')
const cei = ref('')
const ceiOptions = ref([])
const evidence = ref('')
const evidenceAttach = ref('')

const occurrence = ref(0)
const recommended = ref([])
const loadingPreview = ref(false)
const submitting = ref(false)

const selectedAction = ref('')
const recordOptions = computed(() =>
  (props.recommendedActions || []).map((a) => ({ label: a, value: a }))
)

const reasonOptions = ref([])

const hasSubject = computed(() =>
  props.mode === 'course' ? !!cei.value : !!props.student
)

const canRecord = computed(
  () =>
    recommended.value.length > 0 &&
    recommended.value.every((r) => r.instructor_action && !r.triggers_dismissal)
)

const recommendedLabels = computed(() =>
  recommended.value.map((r) => r.action).join(', ')
)

function resetReportState() {
  selectedReason.value = ''
  cei.value = ''
  evidence.value = ''
  evidenceAttach.value = ''
  occurrence.value = 0
  recommended.value = []
}

async function loadCeiOptions() {
  if (props.mode !== 'course' || !props.course) return
  try {
    ceiOptions.value = await call(
      'seminary.seminary.disciplinary.list_course_enrollments',
      { course: props.course }
    )
  } catch (e) {
    ceiOptions.value = []
  }
}

async function loadReasonOptions() {
  try {
    reasonOptions.value = await call(
      'seminary.seminary.disciplinary.list_portal_reasons',
      { mode: props.mode }
    )
  } catch (e) {
    reasonOptions.value = []
  }
}

async function loadPreview() {
  if (!selectedReason.value || !hasSubject.value) {
    occurrence.value = 0
    recommended.value = []
    return
  }
  loadingPreview.value = true
  try {
    const r = await call('seminary.seminary.disciplinary.preview_recommendation', {
      reason: selectedReason.value,
      cei: props.mode === 'course' ? cei.value : undefined,
      student: props.mode === 'assessment' ? props.student : undefined,
    })
    occurrence.value = r.occurrence_number
    recommended.value = r.recommended || []
  } catch (e) {
    recommended.value = []
  } finally {
    loadingPreview.value = false
  }
}

watch([selectedReason, cei], loadPreview)

async function submitReport(recordAction) {
  if (submitting.value) return
  if (!selectedReason.value || !hasSubject.value) {
    toast.error(__('Please select the student and a reason.'))
    return
  }
  submitting.value = true
  try {
    const res = await call('seminary.seminary.disciplinary.report_incident', {
      reason: selectedReason.value,
      cei: props.mode === 'course' ? cei.value : undefined,
      student: props.mode === 'assessment' ? props.student : undefined,
      course: props.mode === 'assessment' ? props.course : undefined,
      assessment: props.mode === 'assessment' ? props.assessment : undefined,
      evidence: evidence.value,
      evidence_attach: evidenceAttach.value,
      record_action: recordAction ? 1 : 0,
    })
    if (res.status === 'Action Taken') {
      toast.success(__('Reported and action recorded.'))
    } else {
      toast.success(__('The incident has been successfully reported.'))
    }
    emit('reported', res)
    show.value = false
  } catch (e) {
    toast.error(e?.messages?.[0] || e?.message || String(e))
  } finally {
    submitting.value = false
  }
}

async function recordOnly() {
  if (submitting.value) return
  submitting.value = true
  try {
    await call('seminary.seminary.disciplinary.record_incident_action', {
      incident: props.incident,
      action: selectedAction.value,
    })
    toast.success(__('Action recorded.'))
    emit('recorded', { incident: props.incident })
    show.value = false
  } catch (e) {
    toast.error(e?.messages?.[0] || e?.message || String(e))
  } finally {
    submitting.value = false
  }
}

watch(show, (open) => {
  if (open) {
    if (props.mode === 'record') {
      selectedAction.value = (props.recommendedActions || [])[0] || ''
    } else {
      resetReportState()
      loadCeiOptions()
      loadReasonOptions()
    }
  }
})

const dialogOptions = computed(() => {
  if (props.mode === 'record') {
    return {
      title: __('Record Disciplinary Action'),
      size: 'md',
      actions: [
        {
          label: __('Record Action'),
          variant: 'solid',
          onClick: () => recordOnly(),
        },
      ],
    }
  }
  const actions = []
  if (canRecord.value) {
    actions.push({
      label: __('Report & Record Action'),
      variant: 'solid',
      onClick: () => submitReport(true),
    })
    actions.push({
      label: __('Report Only'),
      variant: 'subtle',
      onClick: () => submitReport(false),
    })
  } else {
    actions.push({
      label: __('Report'),
      variant: 'solid',
      onClick: () => submitReport(false),
    })
  }
  return {
    title:
      props.mode === 'assessment'
        ? __('Report Disciplinary Incident for this Submission')
        : __('Report Disciplinary Incident'),
    size: 'lg',
    actions,
  }
})
</script>
