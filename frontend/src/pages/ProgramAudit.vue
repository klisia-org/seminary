<template>
  <div v-if="isStudent">
    <h2
      class="text-xl font-bold text-gray-800 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
      {{ __('Program Audit') }}
    </h2>

    <div class="px-5 py-4">
      <!-- PE Selector -->
      <div v-if="enrollments.data && enrollments.data.length > 1" class="mb-4">
        <label class="text-sm font-medium text-gray-600 mb-1 block">{{ __('Program Enrollment') }}</label>
        <select v-model="selectedPE" @change="loadAudit"
          class="border border-gray-300 rounded-md px-3 py-2 text-sm w-full max-w-md">
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
        <div v-if="audit.data.disclaimer" class="mb-3 text-xs text-gray-400 italic">
          {{ audit.data.disclaimer }}
        </div>

        <!-- Graduation Eligibility Banner -->
        <div class="mb-4 px-4 py-3 rounded-lg text-sm font-semibold"
          :class="audit.data.graduation_eligible ? 'bg-green-50 text-green-800' : 'bg-orange-50 text-orange-800'">
          {{ audit.data.graduation_eligible ? __('Eligible for Graduation') : __('Not Yet Eligible for Graduation') }}
        </div>

        <!-- Progress Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <!-- Credits Card -->
          <div v-if="audit.data.program_type === 'Credits-based'" class="border rounded-lg p-4 bg-white">
            <div class="text-sm text-gray-500 mb-1">{{ __('Program Credits') }}</div>
            <div class="text-lg font-bold text-gray-800 mb-2">
              {{ audit.data.credits_earned }} / {{ audit.data.effective_credits_required }}
            </div>
            <ProgressBar :progress="creditPercent" size="md" />
          </div>

          <!-- Terms Card (Time-based) -->
          <div v-if="audit.data.program_type === 'Time-based'" class="border rounded-lg p-4 bg-white">
            <div class="text-sm text-gray-500 mb-1">{{ __('Term Progress') }}</div>
            <div class="text-lg font-bold text-gray-800 mb-2">
              {{ __('Term') }} {{ audit.data.current_term }} {{ __('of') }} {{ audit.data.terms_required }}
            </div>
            <ProgressBar :progress="termPercent" size="md" />
          </div>

          <!-- Emphasis Cards -->
          <div v-for="emph in audit.data.emphases" :key="emph.emphasis_track"
            class="border rounded-lg p-4 bg-white">
            <div class="text-sm text-gray-500 mb-1">{{ emph.track_name }}</div>
            <div class="text-lg font-bold text-gray-800 mb-2">
              {{ emph.credits_capped }} / {{ emph.credits_required }}
              <span v-if="emph.max_credits > 0" class="text-xs text-gray-400 font-normal">
                ({{ __('cap') }}: {{ emph.max_credits }})
              </span>
            </div>
            <ProgressBar :progress="emphPercent(emph)" size="md" />
            <div v-if="emph.mandatory_remaining.length" class="mt-2 text-xs text-orange-600">
              {{ __('Remaining') }}: {{ emph.mandatory_remaining.join(', ') }}
            </div>
          </div>

          <!-- Elective Credits Card -->
          <div v-if="audit.data.program_type === 'Credits-based'" class="border rounded-lg p-4 bg-white">
            <div class="text-sm text-gray-500 mb-1">{{ __('Elective Credits') }}</div>
            <div class="text-lg font-bold text-gray-800 mb-2">
              {{ audit.data.elective_credits_earned }} / {{ audit.data.elective_credits_needed || '—' }}
            </div>
          </div>
        </div>

        <!-- Mandatory Courses Table: Program Requirements -->
        <div class="mb-6">
          <h3 class="text-md font-semibold text-gray-700 mb-3">{{ __('Program Requirements') }}</h3>
          <div v-if="programMandatoryCourses.length">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-gray-600">
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
                    <Badge
                      :theme="mc.status === 'Completed' ? 'green' : mc.status === 'In Progress' ? 'orange' : 'gray'"
                      :label="mc.status" />
                  </td>
                  <td class="py-2 px-3">{{ mc.grade_code }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="text-sm text-gray-400">{{ __('No mandatory courses defined') }}</div>
        </div>

        <!-- Mandatory Courses Table: Per-Emphasis Track Requirements -->
        <div v-for="emph in audit.data.emphases" :key="'track-' + emph.emphasis_track" class="mb-6">
          <h3 class="text-md font-semibold text-gray-700 mb-1">
            {{ __('Track Requirements') }}: {{ emph.track_name }}
          </h3>
          <p class="text-xs text-gray-400 mb-3 italic">
            {{ __('Courses mandatory for both the program and this emphasis are shown here only.') }}
          </p>
          <div v-if="trackMandatoryCourses(emph.emphasis_track).length">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-gray-600">
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
                    <Badge
                      :theme="mc.status === 'Completed' ? 'green' : mc.status === 'In Progress' ? 'orange' : 'gray'"
                      :label="mc.status" />
                  </td>
                  <td class="py-2 px-3">{{ mc.grade_code }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- No data -->
      <div v-else-if="!enrollments.loading">
        <MissingData :message="__('No program enrollment found')" />
      </div>
    </div>
  </div>
  <div v-else class="flex flex-col items-center justify-center py-20">
    <p class="text-lg font-bold text-gray-500">{{ __('Program Audit is only available for Students') }}</p>
  </div>
</template>

<script setup>
import { Badge, LoadingIndicator, createResource } from 'frappe-ui'
import { computed, inject, ref, watch } from 'vue'

import ProgressBar from '@/components/ProgressBar.vue'
import MissingData from '@/components/MissingData.vue'

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
</script>
