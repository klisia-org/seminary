<template>
  <div v-if="isStudent">
    <h2
      class="text-xl font-bold text-ink-gray-8 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
      {{ __('Program Audit') }}
    </h2>

    <div class="px-5 py-4">
      <!-- PE Selector -->
      <div v-if="enrollments.data && enrollments.data.length > 1" class="mb-4">
        <label class="text-sm font-medium text-ink-gray-6 mb-1 block">{{ __('Program Enrollment') }}</label>
        <select v-model="selectedPE" @change="loadAudit"
          class="border border-outline-gray-2 bg-surface-white text-ink-gray-9 rounded-md px-3 py-2 text-sm w-full max-w-md">
          <option v-for="pe in enrollments.data" :key="pe.name" :value="pe.name">
            {{ pe.program }} {{ pe.pgmenrol_active ? '' : '(Inactive)' }}
          </option>
        </select>
      </div>

      <!-- Loading -->
      <div v-if="audit.loading" class="flex justify-center py-12">
        <LoadingIndicator class="w-8 h-8" />
      </div>

      <!-- Audit Data -->
      <div v-else-if="audit.data">
        <!-- Disclaimer -->
        <div v-if="audit.data.disclaimer" class="mb-3 text-xs text-ink-gray-4 italic">
          {{ audit.data.disclaimer }}
        </div>

        <!-- Graduation Eligibility Banner -->
        <div class="mb-4 px-4 py-3 rounded-lg text-sm font-semibold"
          :class="audit.data.graduation_eligible ? 'bg-surface-green-1 text-ink-green-3' : 'bg-surface-amber-2 text-ink-amber-3'">
          {{ audit.data.graduation_eligible ? __('Eligible for Graduation') : __('Not Yet Eligible for Graduation') }}
        </div>

        <!-- Progress Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <!-- Credits Card -->
          <div v-if="audit.data.program_type === 'Credits-based'" class="border rounded-lg p-4 bg-surface-white">
            <div class="text-sm text-ink-gray-5 mb-1">{{ __('Program Credits') }}</div>
            <div class="text-lg font-bold text-ink-gray-8 mb-2">
              {{ audit.data.credits_earned }} / {{ audit.data.effective_credits_required }}
            </div>
            <ProgressBar :progress="creditPercent" size="md" />
          </div>

          <!-- Terms Card (Time-based) -->
          <div v-if="audit.data.program_type === 'Time-based'" class="border rounded-lg p-4 bg-surface-white">
            <div class="text-sm text-ink-gray-5 mb-1">{{ __('Term Progress') }}</div>
            <div class="text-lg font-bold text-ink-gray-8 mb-2">
              {{ __('Term') }} {{ audit.data.current_term }} {{ __('of') }} {{ audit.data.terms_required }}
            </div>
            <ProgressBar :progress="termPercent" size="md" />
          </div>

          <!-- Emphasis Cards -->
          <div v-for="emph in audit.data.emphases" :key="emph.emphasis_track"
            class="border rounded-lg p-4 bg-surface-white">
            <div class="text-sm text-ink-gray-5 mb-1">{{ emph.track_name }}</div>
            <div class="text-lg font-bold text-ink-gray-8 mb-2">
              {{ emph.credits_capped }} / {{ emph.credits_required }}
              <span v-if="emph.max_credits > 0" class="text-xs text-ink-gray-4 font-normal">
                ({{ __('cap') }}: {{ emph.max_credits }})
              </span>
            </div>
            <ProgressBar :progress="emphPercent(emph)" size="md" />
            <div v-if="emph.mandatory_remaining.length" class="mt-2 text-xs text-ink-amber-3">
              {{ __('Remaining') }}: {{ emph.mandatory_remaining.join(', ') }}
            </div>
          </div>

          <!-- Elective Credits Card -->
          <div v-if="audit.data.program_type === 'Credits-based'" class="border rounded-lg p-4 bg-surface-white">
            <div class="text-sm text-ink-gray-5 mb-1">{{ __('Elective Credits') }}</div>
            <div class="text-lg font-bold text-ink-gray-8 mb-2">
              {{ audit.data.elective_credits_earned }} / {{ audit.data.elective_credits_needed || '—' }}
            </div>
          </div>
        </div>

        <!-- Mandatory Courses Table: Program Requirements -->
        <div class="mb-6">
          <h3 class="text-md font-semibold text-ink-gray-7 mb-3">{{ __('Program Requirements') }}</h3>
          <div v-if="programMandatoryCourses.length">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-ink-gray-6">
                  <th class="py-2 px-3 font-medium">{{ __('Course') }}</th>
                  <th class="py-2 px-3 font-medium">{{ __('Credits') }}</th>
                  <th class="py-2 px-3 font-medium">{{ __('Status') }}</th>
                  <th class="py-2 px-3 font-medium">{{ __('Grade') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="mc in programMandatoryCourses" :key="mc.course" class="border-b">
                  <td class="py-2 px-3">{{ mc.course_name }}</td>
                  <td class="py-2 px-3">{{ mc.credits }}</td>
                  <td class="py-2 px-3">
                    <Badge :theme="statusTheme(mc.status)" :label="mc.status" />
                  </td>
                  <td class="py-2 px-3">{{ mc.grade_code }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="text-sm text-ink-gray-4">{{ __('No mandatory courses defined') }}</div>
        </div>

        <!-- Mandatory Courses Table: Per-Emphasis Track Requirements -->
        <div v-for="emph in audit.data.emphases" :key="'track-' + emph.emphasis_track" class="mb-6">
          <h3 class="text-md font-semibold text-ink-gray-7 mb-1">
            {{ __('Track Requirements') }}: {{ emph.track_name }}
          </h3>
          <p class="text-xs text-ink-gray-4 mb-3 italic">
            {{ __('Courses mandatory for both the program and this emphasis are shown here only.') }}
          </p>
          <div v-if="trackMandatoryCourses(emph.emphasis_track).length">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-ink-gray-6">
                  <th class="py-2 px-3 font-medium">{{ __('Course') }}</th>
                  <th class="py-2 px-3 font-medium">{{ __('Credits') }}</th>
                  <th class="py-2 px-3 font-medium">{{ __('Status') }}</th>
                  <th class="py-2 px-3 font-medium">{{ __('Grade') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="mc in trackMandatoryCourses(emph.emphasis_track)" :key="mc.course" class="border-b">
                  <td class="py-2 px-3">{{ mc.course_name }}</td>
                  <td class="py-2 px-3">{{ mc.credits }}</td>
                  <td class="py-2 px-3">
                    <Badge :theme="statusTheme(mc.status)" :label="mc.status" />
                  </td>
                  <td class="py-2 px-3">{{ mc.grade_code }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Graduation Requirements (non-course evidence) -->
        <div v-if="hasGradRequirements" class="mb-6">
          <h3 class="text-md font-semibold text-ink-gray-7 mb-1">
            {{ __('Graduation Requirements') }}
          </h3>
          <p v-if="audit.data.expected_graduation_date" class="text-xs text-ink-gray-4 mb-3 italic">
            {{ __('Expected graduation') }}: {{ audit.data.expected_graduation_date }}
          </p>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left text-ink-gray-6">
                <th class="py-2 px-3 font-medium">{{ __('Requirement') }}</th>
                <th class="py-2 px-3 font-medium">{{ __('Type') }}</th>
                <th class="py-2 px-3 font-medium">{{ __('Status') }}</th>
                <th class="py-2 px-3 font-medium">{{ __('Due') }}</th>
                <th class="py-2 px-3 font-medium">{{ __('Action') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="req in activeGradRequirements" :key="req.name" class="border-b">
                <td class="py-2 px-3">
                  {{ requirementDisplayName(req) }}
                  <span v-if="req.mandatory" class="text-xs text-ink-red-3 ml-1">*</span>
                </td>
                <td class="py-2 px-3 text-xs text-ink-gray-5">{{ req.requirement_type }}</td>
                <td class="py-2 px-3">
                  <Badge :theme="statusTheme(req.status)" :label="req.status" />
                </td>
                <td class="py-2 px-3 text-xs text-ink-gray-5">{{ req.due_date || '—' }}</td>
                <td class="py-2 px-3">
                  <a v-if="req.linked_doc"
                    :href="linkedDocUrl(req)"
                    class="text-ink-blue-3 hover:underline text-xs">
                    {{ __('Open') }}
                  </a>
                  <button v-else-if="canStartRecommendation(req)"
                    class="text-ink-blue-3 hover:underline text-xs"
                    @click="openRecommendationDialog(req)">
                    {{ __('Request Recommendation') }}
                  </button>
                  <button v-else-if="canStartProject(req)"
                    class="text-ink-blue-3 hover:underline text-xs"
                    @click="openProjectDialog(req)">
                    {{ __('Start Project') }}
                  </button>
                  <FileUploader v-else-if="canStudentUpload(req)"
                    :upload-args="{ doctype: 'Program Enrollment', docname: audit.data.program_enrollment, folder: 'Home/Attachments', private: 1 }"
                    @success="(file) => onStudentEvidenceUploaded(req, file)">
                    <template #default="{ openFileSelector }">
                      <button class="text-ink-blue-3 hover:underline text-xs" @click="openFileSelector">
                        {{ __('Submit Evidence') }}
                      </button>
                    </template>
                  </FileUploader>
                  <span v-else class="text-xs text-ink-gray-4">—</span>
                </td>
              </tr>
            </tbody>
          </table>

          <details v-if="pendingGradRequirements.length" class="mt-3">
            <summary class="text-xs text-ink-gray-5 cursor-pointer">
              {{ __('Pending requirements not yet active') }} ({{ pendingGradRequirements.length }})
            </summary>
            <ul class="mt-2 text-xs text-ink-gray-5 ml-4 list-disc">
              <li v-for="req in pendingGradRequirements" :key="req.name">
                {{ requirementDisplayName(req) }}
                <span v-if="req.due_date" class="text-ink-gray-4">— {{ __('due') }} {{ req.due_date }}</span>
              </li>
            </ul>
          </details>
        </div>
      </div>

      <!-- No data -->
      <div v-else-if="!enrollments.loading">
        <MissingData :message="__('No program enrollment found')" />
      </div>
    </div>
  </div>
  <div v-else class="flex flex-col items-center justify-center py-20">
    <p class="text-lg font-bold text-ink-gray-5">{{ __('Program Audit is only available for Students') }}</p>
  </div>

  <!-- Request Recommendation modal -->
  <Dialog v-model="showRecDialog" :options="{ title: __('Request a Recommendation Letter') }">
    <template #body-content>
      <p v-if="recForReq" class="text-xs text-ink-gray-5 mb-3">
        {{ __('For') }}: <span class="font-medium">{{ requirementDisplayName(recForReq) }}</span>
      </p>
      <FormControl v-model="recForm.recommender_name" type="text"
        :label="__('Recommender Name')" required class="mb-3" />
      <FormControl v-model="recForm.recommender_email" type="email"
        :label="__('Recommender Email')" required class="mb-3" />
      <FormControl v-model="recForm.recommender_role" type="text"
        :label="__('Relationship (e.g. Pastor, Mentor)')" class="mb-3" />
      <p class="text-xs text-ink-gray-4 italic">
        {{ __('An email with a secure submission link will be sent to the recommender.') }}
      </p>
    </template>
    <template #actions>
      <Button @click="showRecDialog = false">{{ __('Cancel') }}</Button>
      <Button variant="solid" :loading="recSubmitting" @click="submitRecommendation">
        {{ __('Send Request') }}
      </Button>
    </template>
  </Dialog>

  <!-- Start Culminating Project modal -->
  <Dialog v-model="showProjectDialog" :options="{ title: __('Start Culminating Project') }">
    <template #body-content>
      <p v-if="projectForReq" class="text-xs text-ink-gray-5 mb-3">
        {{ __('For') }}: <span class="font-medium">{{ requirementDisplayName(projectForReq) }}</span>
      </p>
      <FormControl v-model="projectForm.project_title" type="text"
        :label="__('Project Title')" required class="mb-3" />
      <FormControl v-model="projectForm.project_type" type="select"
        :label="__('Type')"
        :options="['Thesis', 'Capstone', 'Dissertation']" class="mb-3" />
      <FormControl v-model="projectForm.advisor" type="autocomplete"
        :label="__('Advisor')"
        :options="advisorOptions" required class="mb-3" />
      <FormControl v-model="projectForm.abstract" type="textarea"
        :label="__('Abstract (optional)')" class="mb-3" />
    </template>
    <template #actions>
      <Button @click="showProjectDialog = false">{{ __('Cancel') }}</Button>
      <Button variant="solid" :loading="projectSubmitting" @click="submitProject">
        {{ __('Create Project') }}
      </Button>
    </template>
  </Dialog>
</template>

<script setup>
import { Badge, Button, Dialog, FileUploader, FormControl, LoadingIndicator, call, createResource, toast } from 'frappe-ui'
import { computed, inject, reactive, ref, watch } from 'vue'

import ProgressBar from '@/components/ProgressBar.vue'
import MissingData from '@/components/MissingData.vue'
import { statusTheme } from '@/utils/statusTheme'

const user = inject('$user')
const isStudent = user.data?.is_student
const student = user.data?.student

const selectedPE = ref(null)

const enrollments = createResource({
  url: 'seminary.seminary.api.get_pgmenrollments',
  makeParams() {
    return { name: student }
  },
  onSuccess(data) {
    if (data && data.length) {
      selectedPE.value = data[0].name
    }
  },
  auto: !!student,
})

const audit = createResource({
  url: 'seminary.seminary.api.get_program_audit',
  makeParams() {
    return { program_enrollment: selectedPE.value }
  },
  auto: false,
})

watch(selectedPE, (val) => {
  if (val) audit.reload()
})

function loadAudit() {
  if (selectedPE.value) audit.reload()
}

const creditPercent = computed(() => {
  if (!audit.data) return 0
  const req = audit.data.effective_credits_required || 1
  return Math.round((audit.data.credits_earned / req) * 100)
})

const termPercent = computed(() => {
  if (!audit.data) return 0
  const req = audit.data.terms_required || 1
  return Math.round((audit.data.current_term / req) * 100)
})

function emphPercent(emph) {
  const req = emph.credits_required || 1
  return Math.round((emph.credits_capped / req) * 100)
}

const courseColumns = [
  { label: __('Course'), key: 'course_name', width: 2 },
  { label: __('Credits'), key: 'credits', width: 1 },
  { label: __('Status'), key: 'status', width: 1 },
  { label: __('Grade'), key: 'grade_code', width: 1 },
]

const programMandatoryCourses = computed(() => {
  if (!audit.data) return []
  return audit.data.mandatory_courses.map(mc => ({
    course: mc.course,
    course_name: mc.course_name || mc.course,
    credits: mc.credits,
    status: mc.status,
    grade_code: mc.grade_code || '',
  }))
})

function trackMandatoryCourses(emphasisTrack) {
  if (!audit.data) return []
  const emph = audit.data.emphases.find(e => e.emphasis_track === emphasisTrack)
  if (!emph || !emph.mandatory_courses) return []
  return emph.mandatory_courses.map(mc => ({
    course: mc.course,
    course_name: mc.course_name || mc.course,
    credits: mc.credits || '',
    status: mc.status,
    grade_code: mc.grade_code || '',
  }))
}

const hasGradRequirements = computed(
  () => audit.data && audit.data.graduation_requirements && audit.data.graduation_requirements.length > 0
)

const activeGradRequirements = computed(() => {
  if (!audit.data) return []
  return audit.data.graduation_requirements.filter(r => r.active)
})

const pendingGradRequirements = computed(() => {
  if (!audit.data) return []
  return audit.data.graduation_requirements.filter(r => !r.active)
})

function requirementDisplayName(req) {
  if ((req.slot_index || 1) > 1) {
    return `${req.requirement_name} (${req.slot_index})`
  }
  return req.requirement_name
}

function linkedDocUrl(req) {
  if (!req.link_doctype || !req.linked_doc) return '#'
  const dt = req.link_doctype.toLowerCase().replace(/ /g, '-')
  return `/app/${dt}/${encodeURIComponent(req.linked_doc)}`
}

function canStudentUpload(req) {
  if (req.requirement_type !== 'Manual Verification') return false
  if (req.status === 'Fulfilled' || req.status === 'Waived') return false
  return true
}

function canStartRecommendation(req) {
  return (
    req.requirement_type === 'Linked Document' &&
    req.link_doctype === 'Recommendation Letter' &&
    !req.linked_doc &&
    req.status !== 'Waived'
  )
}

async function onStudentEvidenceUploaded(req, file) {
  try {
    await call('seminary.seminary.graduation.submit_student_evidence', {
      program_enrollment: audit.data.program_enrollment,
      sgr_name: req.name,
      attachment_url: file.file_url,
    })
    toast.success(__('Evidence submitted'))
    audit.reload()
  } catch (e) {
    toast.error(e.message || __('Failed to submit evidence'))
  }
}

const showRecDialog = ref(false)
const recForReq = ref(null)
const recSubmitting = ref(false)
const recForm = reactive({ recommender_name: '', recommender_email: '', recommender_role: '' })

function openRecommendationDialog(req) {
  recForReq.value = req
  recForm.recommender_name = ''
  recForm.recommender_email = ''
  recForm.recommender_role = ''
  showRecDialog.value = true
}

async function submitRecommendation() {
  if (!recForm.recommender_name || !recForm.recommender_email) {
    toast.error(__('Recommender name and email are required'))
    return
  }
  recSubmitting.value = true
  try {
    await call('seminary.seminary.graduation.start_recommendation_letter', {
      program_enrollment: audit.data.program_enrollment,
      sgr_name: recForReq.value.name,
      recommender_name: recForm.recommender_name,
      recommender_email: recForm.recommender_email,
      recommender_role: recForm.recommender_role,
    })
    toast.success(__('Request sent to recommender'))
    showRecDialog.value = false
    audit.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Failed to send request'))
  } finally {
    recSubmitting.value = false
  }
}

function canStartProject(req) {
  return (
    req.requirement_type === 'Linked Document' &&
    req.link_doctype === 'Culminating Project' &&
    !req.linked_doc &&
    req.status !== 'Waived'
  )
}

const showProjectDialog = ref(false)
const projectForReq = ref(null)
const projectSubmitting = ref(false)
const projectForm = reactive({ project_title: '', project_type: 'Thesis', advisor: null, abstract: '' })
const advisorOptions = ref([])

const instructors = createResource({
  url: 'frappe.client.get_list',
  makeParams() {
    return { doctype: 'Instructor', fields: ['name', 'instructor_name'], limit_page_length: 0 }
  },
  onSuccess(data) {
    advisorOptions.value = (data || []).map(i => ({ label: i.instructor_name || i.name, value: i.name }))
  },
  auto: false,
})

function openProjectDialog(req) {
  projectForReq.value = req
  projectForm.project_title = ''
  projectForm.project_type = 'Thesis'
  projectForm.advisor = null
  projectForm.abstract = ''
  if (!instructors.data) instructors.fetch()
  showProjectDialog.value = true
}

async function submitProject() {
  if (!projectForm.project_title || !projectForm.advisor) {
    toast.error(__('Project title and advisor are required'))
    return
  }
  projectSubmitting.value = true
  try {
    const advisorValue = typeof projectForm.advisor === 'object'
      ? projectForm.advisor.value
      : projectForm.advisor
    await call('seminary.seminary.graduation.start_culminating_project', {
      program_enrollment: audit.data.program_enrollment,
      sgr_name: projectForReq.value.name,
      project_title: projectForm.project_title,
      project_type: projectForm.project_type,
      advisor: advisorValue,
      abstract: projectForm.abstract,
    })
    toast.success(__('Project created'))
    showProjectDialog.value = false
    audit.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Failed to create project'))
  } finally {
    projectSubmitting.value = false
  }
}
</script>
