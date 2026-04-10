<template>
  <div v-if="isStudent">
    <h2
      class="text-xl font-bold text-ink-gray-8 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
      {{ __('Courses Open for Enrollment') }}
    </h2>

    <div class="px-5 py-4">
      <!-- PE Selector -->
      <div v-if="enrollments.data && enrollments.data.length > 1" class="mb-4">
        <label class="text-sm font-medium text-ink-gray-6 mb-1 block">{{ __('Program Enrollment') }}</label>
        <select v-model="selectedPE" @change="loadCourses"
          class="border border-outline-gray-2 bg-surface-white text-ink-gray-9 rounded-md px-3 py-2 text-sm w-full max-w-md">
          <option v-for="pe in activeEnrollments" :key="pe.name" :value="pe.name">
            {{ pe.program }}
          </option>
        </select>
      </div>
      <div v-else-if="selectedProgram" class="mb-4">
        <p class="text-sm font-medium text-ink-gray-6">
          {{ __('Program') }}: <span class="font-bold text-ink-gray-8">{{ selectedProgram }}</span>
        </p>
      </div>

      <!-- My Enrollments for this Term -->
      <div v-if="myEnrollments.data && myEnrollments.data.length" class="mb-6">
        <h3 class="text-lg font-semibold text-ink-gray-8 mb-2">{{ __('My Enrollments This Term') }}</h3>
        <div class="border rounded-lg overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-surface-gray-1 text-ink-gray-6">
              <tr>
                <th class="text-left px-3 py-2 font-medium">{{ __('Course') }}</th>
                <th class="text-left px-3 py-2 font-medium">{{ __('Credits') }}</th>
                <th class="text-left px-3 py-2 font-medium">{{ __('Status') }}</th>
                <th class="text-right px-3 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cei in myEnrollments.data" :key="cei.name"
                :class="cei.status === 'Withdrawn' ? 'text-ink-gray-4 line-through' : ''">
                <td class="px-3 py-2">{{ cei.course_data }}</td>
                <td class="px-3 py-2">{{ cei.credits || '-' }}</td>
                <td class="px-3 py-2">
                  <Badge
                    :theme="statusTheme(cei.status)"
                    :label="cei.status === 'Draft' ? __('Pending') : __(cei.status)" />
                </td>
                <td class="px-3 py-2 text-right">
                  <Button v-if="cei.status === 'Draft'" size="sm" variant="ghost" theme="red"
                    @click="cancelEnrollment(cei.name)" :loading="cancelling === cei.name">
                    {{ __('Cancel') }}
                  </Button>
                </td>
              </tr>
            </tbody>
            <tfoot v-if="totalCredits > 0" class="bg-surface-gray-1">
              <tr>
                <td class="px-3 py-2 font-medium text-ink-gray-7">{{ __('Total') }}</td>
                <td class="px-3 py-2 font-medium text-ink-gray-7">{{ totalCredits }}</td>
                <td colspan="2"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="courses.loading" class="flex justify-center py-12">
        <LoadingIndicator class="w-8 h-8" />
      </div>

      <!-- Course Cards -->
      <div v-else-if="courses.data && courses.data.length" class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div v-for="course in courses.data" :key="course.course" class="border rounded-lg p-4 bg-surface-white">
          <div class="flex items-start justify-between mb-2">
            <div>
              <h3 class="font-semibold text-ink-gray-8">{{ course.course_name || course.course }}</h3>
              <span class="text-sm text-ink-gray-5">{{ course.credits }} {{ __('credits') }}</span>
            </div>
          </div>

          <!-- Category Badges -->
          <div class="flex flex-wrap gap-1 mb-3">
            <Badge v-for="(cat, idx) in course.categories" :key="idx"
              :theme="badgeTheme(cat.type)"
              :label="badgeLabel(cat)" />
          </div>

          <!-- Available Schedules -->
          <div v-if="course.course_schedules && course.course_schedules.length">
            <div v-for="cs in course.course_schedules" :key="cs.name"
              class="flex items-center justify-between py-2 border-t text-sm gap-3">
              <div class="flex-1 min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <span v-if="cs.section" class="font-semibold text-ink-gray-7">{{ cs.section }}</span>
                  <Badge v-if="cs.modality" :theme="cs.modality === 'Virtual' ? 'blue' : cs.modality === 'Hybrid' ? 'orange' : 'gray'" :label="cs.modality" />
                  <span v-if="cs.days" class="text-xs text-ink-gray-5 font-mono">{{ cs.days }}</span>
                  <span v-if="cs.time_range" class="text-xs text-ink-gray-5">{{ cs.time_range }}</span>
                </div>
                <div class="text-xs text-ink-gray-5 mt-0.5">
                  <span v-if="cs.instructors">{{ cs.instructors }}</span>
                  <span v-if="cs.instructors && cs.date_range"> · </span>
                  <span v-if="cs.date_range">{{ cs.date_range }}</span>
                </div>
              </div>
              <Button size="sm" variant="subtle" @click="enrollInCourse(cs.name)"
                :loading="enrolling === cs.name">
                {{ __('Enroll') }}
              </Button>
            </div>
          </div>
          <div v-else class="text-xs text-ink-gray-4 mt-2">
            {{ __('No scheduled sections available') }}
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="!enrollments.loading">
        <MissingData :message="__('No courses available for enrollment')" />
      </div>
    </div>
  </div>
  <div v-else class="flex flex-col items-center justify-center py-20">
    <p class="text-lg font-bold text-ink-gray-5">{{ __('Course enrollment is only available for Students') }}</p>
  </div>
</template>

<script setup>
import { Badge, Button, LoadingIndicator, createResource } from 'frappe-ui'
import { computed, inject, ref, watch } from 'vue'

import MissingData from '@/components/MissingData.vue'
import { statusTheme } from '@/utils/statusTheme'

const user = inject('$user')
const isStudent = user.data?.is_student
const student = user.data?.student

const selectedPE = ref(null)
const enrolling = ref(null)
const cancelling = ref(null)

const enrollments = createResource({
  url: 'seminary.seminary.api.get_pgmenrollments',
  makeParams() {
    return { name: student }
  },
  onSuccess(data) {
    if (data && data.length) {
      // Pick first active enrollment
      const active = data.find(pe => pe.pgmenrol_active) || data[0]
      selectedPE.value = active.name
    }
  },
  auto: !!student,
})

const activeEnrollments = computed(() => {
  return (enrollments.data || []).filter(pe => pe.pgmenrol_active)
})

const selectedProgram = computed(() => {
  if (!enrollments.data || !selectedPE.value) return ''
  const pe = enrollments.data.find(p => p.name === selectedPE.value)
  return pe ? pe.program : ''
})

const courses = createResource({
  url: 'seminary.seminary.api.get_available_courses_categorized',
  makeParams() {
    return { program_enrollment: selectedPE.value }
  },
  auto: false,
})

const myEnrollments = createResource({
  url: 'seminary.seminary.api.get_student_enrollments_for_term',
  makeParams() {
    return { program_enrollment: selectedPE.value }
  },
  auto: false,
})

const totalCredits = computed(() => {
  if (!myEnrollments.data) return 0
  return myEnrollments.data
    .filter(c => c.status !== 'Withdrawn')
    .reduce((sum, c) => sum + (c.credits || 0), 0)
})

watch(selectedPE, (val) => {
  if (val) {
    courses.reload()
    myEnrollments.reload()
  }
})

function loadCourses() {
  if (selectedPE.value) courses.reload()
}

function badgeTheme(type) {
  if (type === 'Program Mandatory') return 'red'
  if (type === 'Track Mandatory') return 'blue'
  if (type === 'Track Elective') return 'blue'
  return 'gray'
}

function badgeLabel(cat) {
  if (cat.type === 'Program Mandatory') return __('Required')
  if (cat.type === 'Track Mandatory') return cat.track_name || __('Track Required')
  if (cat.type === 'Track Elective') return cat.track_name || __('Track Elective')
  return __('Elective')
}

const enrollAction = createResource({
  url: 'seminary.seminary.api.course_enroll',
})

function enrollInCourse(courseSchedule) {
  enrolling.value = courseSchedule
  enrollAction.submit({
    pe_name: selectedPE.value,
    course: courseSchedule,
  }).then(() => {
    enrolling.value = null
    courses.reload()
    myEnrollments.reload()
  }).catch(() => {
    enrolling.value = null
  })
}

const cancelAction = createResource({
  url: 'seminary.seminary.api.cancel_draft_enrollment',
})

function cancelEnrollment(ceiName) {
  cancelling.value = ceiName
  cancelAction.submit({ cei_name: ceiName }).then(() => {
    cancelling.value = null
    myEnrollments.reload()
    courses.reload()
  }).catch(() => {
    cancelling.value = null
  })
}
</script>
