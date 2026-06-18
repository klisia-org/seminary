<template>
  <div>
    <h2 class="text-xl font-bold text-ink-gray-8 sticky top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
      {{ __('Faculty Worklist') }}
    </h2>

    <div class="px-3 py-4 sm:px-5 space-y-6">
      <div v-if="worklist.loading" class="flex justify-center py-12">
        <LoadingIndicator class="w-8 h-8" />
      </div>

      <template v-else>
        <!-- Verifications -->
        <section v-if="showVerifications">
          <h3 class="font-semibold text-ink-gray-8 mb-2">
            {{ __('Verifications') }}
            <Badge :label="String(verifications.length)" theme="gray" class="ml-1" />
          </h3>
          <p v-if="!verifications.length" class="text-sm text-ink-gray-5">
            {{ __('No pending manual verifications.') }}
          </p>
          <div v-else class="border rounded-md divide-y">
            <div v-for="it in verifications" :key="it.sgr" class="flex items-center justify-between p-3 gap-3">
              <div class="min-w-0">
                <div class="font-medium text-ink-gray-8 truncate">{{ it.requirement_name }}</div>
                <div class="text-xs text-ink-gray-5 truncate">{{ it.program_enrollment }} · {{ it.unit }}</div>
              </div>
              <Button variant="solid" size="sm" :loading="busy === it.sgr" @click="verify(it)">
                {{ __('Mark Verified') }}
              </Button>
            </div>
          </div>
        </section>

        <!-- Placement exams -->
        <section v-if="showPlacement">
          <h3 class="font-semibold text-ink-gray-8 mb-2">
            {{ __('Placement Exams') }}
            <Badge :label="String(placements.length)" theme="gray" class="ml-1" />
          </h3>
          <p v-if="!placements.length" class="text-sm text-ink-gray-5">
            {{ __('No placement exams awaiting a score.') }}
          </p>
          <div v-else class="border rounded-md divide-y">
            <div v-for="it in placements" :key="it.program_enrollment + it.assessment"
              class="flex items-center justify-between p-3 gap-3">
              <div class="min-w-0">
                <div class="font-medium text-ink-gray-8 truncate">{{ it.assessment }}</div>
                <div class="text-xs text-ink-gray-5 truncate">{{ it.program_enrollment }} · {{ it.unit }}</div>
              </div>
              <Button variant="solid" size="sm" @click="openScore(it)">{{ __('Record Score') }}</Button>
            </div>
          </div>
        </section>

        <p v-if="!showVerifications && !showPlacement" class="text-sm text-ink-gray-5">
          {{ __('You are not wired to any verification or examining work.') }}
        </p>
      </template>
    </div>

    <Dialog v-model="scoreDialog" :options="{ title: __('Record Placement Score') }">
      <template #body-content>
        <p class="text-sm text-ink-gray-6 mb-3" v-if="scoring">{{ scoring.assessment }} — {{ scoring.program_enrollment }}</p>
        <FormControl type="number" :label="__('Score')" v-model="scoreValue" class="mb-3" />
        <div v-if="scoring && scoring.staff_evidence_required">
          <FileUploader :upload-args="uploadArgs" :validate-file="validateFileSize"
            @success="(f) => (attachment = f.file_url)">
            <template #default="{ uploading, openFileSelector }">
              <div class="flex items-center gap-2">
                <Button @click="openFileSelector" :loading="uploading" variant="outline" iconLeft="paperclip">
                  {{ attachment ? __('Replace file') : (scoring.staff_evidence_label || __('Attach evidence')) }}
                </Button>
                <span v-if="uploadLimits.data?.max_upload_mb" class="text-sm text-ink-gray-5">
                  {{ __('Max {0} MB').format(uploadLimits.data.max_upload_mb) }}
                </span>
              </div>
            </template>
          </FileUploader>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="busy === 'score'"
          :disabled="scoreValue === '' || scoreValue === null || (scoring && scoring.staff_evidence_required && !attachment)"
          @click="recordScore">{{ __('Save Score') }}</Button>
      </template>
    </Dialog>

    <Dialog v-model="verifyDialog" :options="{ title: __('Mark Verified') }">
      <template #body-content>
        <p class="text-sm text-ink-gray-6 mb-3" v-if="verifying">{{ verifying.requirement_name }} — {{ verifying.program_enrollment }}</p>
        <FileUploader :upload-args="uploadArgs" :validate-file="validateFileSize"
          @success="(f) => (verifyAttachment = f.file_url)">
          <template #default="{ uploading, openFileSelector }">
            <div class="flex items-center gap-2">
              <Button @click="openFileSelector" :loading="uploading" variant="outline" iconLeft="paperclip">
                {{ verifyAttachment ? __('Replace file') : (verifying?.staff_evidence_label || __('Attach evidence')) }}
              </Button>
              <span v-if="uploadLimits.data?.max_upload_mb" class="text-sm text-ink-gray-5">
                {{ __('Max {0} MB').format(uploadLimits.data.max_upload_mb) }}
              </span>
            </div>
          </template>
        </FileUploader>
      </template>
      <template #actions>
        <Button variant="solid" :loading="busy === verifying?.sgr" :disabled="!verifyAttachment"
          @click="doVerify(verifying, verifyAttachment)">{{ __('Mark Verified') }}</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Dialog, FileUploader, FormControl, LoadingIndicator, call, createResource, toast } from 'frappe-ui'
import { uploadLimits, validateFileSize } from '@/utils'

const uploadArgs = { private: 1, folder: 'Home/Attachments' }

const worklist = createResource({
  url: 'seminary.seminary.faculty.get_my_faculty_worklist',
  auto: true,
})

const verifications = computed(() => worklist.data?.['Manual-Verification Verifier'] || [])
const placements = computed(() => worklist.data?.['Placement Examiner'] || [])
const showVerifications = computed(() => 'Manual-Verification Verifier' in (worklist.data || {}))
const showPlacement = computed(() => 'Placement Examiner' in (worklist.data || {}))

const busy = ref(null)

function verify(it) {
  // Requirements that demand staff evidence open a labeled-upload dialog;
  // otherwise verifying is one click.
  if (it.staff_evidence_required) {
    verifying.value = it
    verifyAttachment.value = ''
    verifyDialog.value = true
  } else {
    doVerify(it, null)
  }
}
async function doVerify(it, attachment_url) {
  busy.value = it.sgr
  try {
    await call('seminary.seminary.graduation.mark_sgr_verified', {
      program_enrollment: it.program_enrollment,
      sgr_name: it.sgr,
      attachment_url: attachment_url || null,
    })
    toast.success(__('Verified'))
    verifyDialog.value = false
    worklist.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not verify'))
  } finally {
    busy.value = null
  }
}

const verifyDialog = ref(false)
const verifying = ref(null)
const verifyAttachment = ref('')

const scoreDialog = ref(false)
const scoring = ref(null)
const scoreValue = ref('')
const attachment = ref('')
function openScore(it) {
  scoring.value = it
  scoreValue.value = ''
  attachment.value = ''
  scoreDialog.value = true
}
async function recordScore() {
  busy.value = 'score'
  try {
    await call('seminary.seminary.leveling.mark_placement_scored', {
      program_enrollment: scoring.value.program_enrollment,
      assessment: scoring.value.assessment,
      score: scoreValue.value,
      attachment_url: attachment.value || null,
    })
    toast.success(__('Score recorded'))
    scoreDialog.value = false
    worklist.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not record score'))
  } finally {
    busy.value = null
  }
}
</script>
