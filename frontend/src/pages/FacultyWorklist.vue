<template>
  <div>
    <PageHeader :title="__('Faculty Worklist')">
      <template v-if="tabs.length" #tabs>
        <PageTabs :tabs="tabs" v-model="tab" :label="__('Worklist queues')" />
      </template>
    </PageHeader>

    <div class="px-3 py-4 sm:px-5 space-y-6">
      <div v-if="worklist.loading" class="flex justify-center py-12">
        <LoadingIndicator class="w-8 h-8" />
      </div>

      <template v-else>
        <!-- Verifications -->
        <section v-if="tab === 'verifications'">
          <h3 class="font-semibold text-ink-gray-8 mb-2">
            {{ __('Verifications') }}
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
        <section v-if="tab === 'placement'">
          <h3 class="font-semibold text-ink-gray-8 mb-2">
            {{ __('Placement Exams') }}
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

        <!-- Culminating project sign-offs (ADR 074). Present for anyone wired to
             the Thesis/CP Advisor capability (or already reading for a project),
             exactly like Verifications and Placement Exams — so an advisor with
             nothing pending sees a 0, not a missing section. -->
        <section v-if="tab === 'reviews'">
          <h3 class="font-semibold text-ink-gray-8 mb-2">
            {{ __('Project Reviews') }}
          </h3>
          <p v-if="!projectReviews.length" class="text-sm text-ink-gray-5">
            {{ __('No projects are awaiting your review.') }}
          </p>
          <div v-else class="border rounded-md divide-y">
            <div v-for="it in projectReviews" :key="it.name"
              class="flex items-center justify-between p-3 gap-3">
              <div class="min-w-0">
                <div class="font-medium text-ink-gray-8 truncate">
                  {{ it.project_title || it.name }}
                </div>
                <div class="text-xs text-ink-gray-5 truncate">
                  {{ [it.student_name, it.my_role, it.active_milestone].filter(Boolean).join(' · ') }}
                </div>
                <div v-if="it.due" class="text-xs mt-0.5"
                  :class="overdue(it) ? 'text-ink-red-3' : 'text-ink-gray-5'">
                  {{ overdue(it) ? __('Due {0} — overdue').format(it.due) : __('Due {0}').format(it.due) }}
                </div>
              </div>
              <router-link :to="{ name: 'CulminatingProject', query: { project: it.name } }">
                <Button variant="solid" size="sm">{{ __('Review') }}</Button>
              </router-link>
            </div>
          </div>
        </section>

        <!-- Competency assessments (ADR 065). Mentors are never added to a
             section, so this list is where a Personal Mentor finds out they
             have work to do. -->
        <section v-if="tab === 'competency'">
          <div class="flex items-center justify-between mb-2">
            <h3 class="font-semibold text-ink-gray-8">
              {{ __('Competency Assessments Due') }}
            </h3>
            <!-- The caseload the mentor never had to be assigned to; the arc
                 view is where their students' own words live (ADR 065 8a). -->
            <router-link v-if="mentees.data?.length" :to="{ name: 'SelfDevelopmentPlans' }">
              <Button variant="subtle" size="sm">
                {{ __('My Students’ Plans') }}
              </Button>
            </router-link>
          </div>
          <p v-if="!competency.data?.length" class="text-sm text-ink-gray-5">
            {{ __('Nothing outstanding right now.') }}
          </p>
          <div class="border rounded-md divide-y">
            <div v-for="it in competency.data" :key="it.roster"
              class="flex items-start justify-between p-3 gap-3">
              <div class="min-w-0">
                <div class="font-medium text-ink-gray-8 truncate">{{ it.student_name }}</div>
                <div class="text-xs text-ink-gray-5 truncate">{{ it.course_schedule }}</div>
                <ul v-if="it.activities?.length" class="mt-1 text-xs text-ink-gray-6 list-inside list-disc">
                  <li v-for="(a, i) in it.activities.slice(0, 4)" :key="i">{{ a }}</li>
                  <li v-if="it.activities.length > 4">
                    {{ __('and {0} more').format(it.activities.length - 4) }}
                  </li>
                </ul>
                <div v-if="it.verdicts?.length" class="mt-1 text-xs text-ink-gray-6">
                  {{ __('Final assessment pending:') }}
                  {{ it.verdicts.map((v) => v.label).join(', ') }}
                </div>
              </div>
              <router-link :to="{
                name: 'CompetencyGradebook',
                params: { courseName: it.course_schedule },
                query: { tab: 'student', roster: it.roster },
              }">
                <Button variant="solid" size="sm">{{ __('Open') }}</Button>
              </router-link>
            </div>
          </div>
        </section>

        <p v-if="!tabs.length" class="text-sm text-ink-gray-5">
          {{ __('You are not wired to any verification, examining, review or mentoring work.') }}
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
import { Button, Dialog, FileUploader, FormControl, LoadingIndicator, call, createResource, toast } from 'frappe-ui'
import { uploadLimits, validateFileSize } from '@/utils'
import PageHeader from '@/components/PageHeader.vue'
import PageTabs from '@/components/PageTabs.vue'
import { useTabParam } from '@/composables/useTabParam'

const uploadArgs = { private: 1, folder: 'Home/Attachments' }

const worklist = createResource({
  url: 'seminary.seminary.faculty.get_my_faculty_worklist',
  auto: true,
})

// Loaded separately and silently: a user with no mentoring assignments gets an
// empty list rather than an error, and the section simply does not render.
const mentees = createResource({
  url: 'seminary.seminary.cbe_api.get_mentees',
  auto: true,
  onError: () => { },
})

const competency = createResource({
  url: 'seminary.seminary.cbe_api.get_competency_worklist',
  auto: true,
  onError: () => {},
})

const verifications = computed(() => worklist.data?.['Manual-Verification Verifier'] || [])
const placements = computed(() => worklist.data?.['Placement Examiner'] || [])
const projectReviews = computed(() => worklist.data?.['Project Reviews'] || [])
const showVerifications = computed(() => 'Manual-Verification Verifier' in (worklist.data || {}))
const showPlacement = computed(() => 'Placement Examiner' in (worklist.data || {}))
const showProjectReviews = computed(() => 'Project Reviews' in (worklist.data || {}))

// One tab per queue the server says is this user's (ADR 075). The count rides on
// the tab so the whole picture stays visible at a glance -- the overview the
// stacked sections used to give -- while the panel below is one queue to work.
const tabs = computed(() => {
  const out = []
  if (showVerifications.value)
    out.push({ key: 'verifications', label: __('Verifications'), count: verifications.value.length })
  if (showPlacement.value)
    out.push({ key: 'placement', label: __('Placement Exams'), count: placements.value.length })
  if (showProjectReviews.value)
    out.push({ key: 'reviews', label: __('Project Reviews'), count: projectReviews.value.length })
  // Mentoring has no capability key; a mentee caseload or outstanding work is
  // what makes it this user's queue (ADR 065).
  if (competency.data?.length || mentees.data?.length)
    out.push({ key: 'competency', label: __('Competency Assessments'), count: competency.data?.length || 0 })
  return out
})

// Land on work, not on an empty queue: the first tab with something outstanding,
// else the first tab. `?tab=` still wins when present, so a link into a specific
// queue survives.
const defaultTab = computed(
  () => (tabs.value.find((t) => t.count) || tabs.value[0])?.key || '',
)
const tab = useTabParam(
  computed(() => tabs.value.map((t) => t.key)),
  defaultTab,
)

const today = new Date().toISOString().slice(0, 10)
const overdue = (it) => !!it.due && it.due < today

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
