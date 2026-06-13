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
              <tr v-for="cei in sortedEnrollments" :key="cei.name"
                :class="['Withdrawn', 'Unseated'].includes(cei.status) ? 'text-ink-gray-4 line-through' : ''">
                <td class="px-3 py-2">
                  <div>{{ cei.course_data }}</div>
                  <div v-if="cei.categories && cei.categories.length" class="flex flex-wrap gap-1 mt-1">
                    <Badge v-for="(cat, idx) in cei.categories" :key="idx" size="sm"
                      :theme="badgeTheme(cat.type)" :label="badgeLabel(cat)" />
                  </div>
                </td>
                <td class="px-3 py-2">{{ cei.credits || '-' }}</td>
                <td class="px-3 py-2">
                  <div class="flex flex-col gap-0.5">
                    <Badge :theme="statusTheme(cei.status)"
                      :label="cei.status === 'Draft' ? __('Pending') : __(cei.status)" />
                    <span v-if="cei.status === 'Awaiting Payment' && cei.paid_percent != null"
                      class="text-xs text-ink-gray-5">
                      {{ Math.round(cei.paid_percent) }}% {{ __('paid') }}
                    </span>
                    <span v-else-if="cei.status === 'Waitlisted' && cei.waitlist_position"
                      class="text-xs text-ink-gray-5">
                      {{ __('Position') }} #{{ cei.waitlist_position }}
                    </span>
                  </div>
                </td>
                <td class="px-3 py-2 text-right">
                  <Button v-if="cei.status === 'Draft'" size="sm" variant="ghost" theme="red"
                    @click="cancelEnrollment(cei.name)" :loading="cancelling === cei.name">
                    {{ __('Cancel') }}
                  </Button>
                  <div v-else-if="cei.status === 'Awaiting Payment'"
                    class="flex items-center justify-end gap-3">
                    <a v-if="cei.sales_invoice" :href="`/seminary/fees`"
                      class="text-ink-blue-3 hover:underline text-sm font-medium">
                      {{ __('Pay') }}
                    </a>
                    <Button size="sm" variant="ghost" theme="red"
                      @click="releaseUnpaid(cei)" :loading="cancelling === cei.name">
                      {{ __('Cancel') }}
                    </Button>
                  </div>
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
              <h3 class="font-semibold text-ink-gray-8 flex items-center gap-1">
                {{ course.course_name || course.course }}
                <Tooltip v-if="course.description" :hover-delay="0.2">
                  <HelpCircle class="w-4 h-4 text-ink-gray-5 cursor-help" />
                  <template #body>
                    <div
                      class="max-w-xs rounded bg-surface-gray-7 px-3 py-2 text-xs text-ink-white shadow-xl prose-sm"
                      v-html="course.description" />
                  </template>
                </Tooltip>
              </h3>
              <span class="text-sm text-ink-gray-5">{{ course.credits }} {{ __('credits') }}</span>
            </div>
            <Tooltip v-if="course.prerequisite_for && course.prerequisite_for.length" :hover-delay="0.2">
              <Badge theme="green" :label="__('Prerequisite')" />
              <template #body>
                <div class="max-w-xs rounded bg-surface-gray-7 px-3 py-2 text-xs text-ink-white shadow-xl">
                  <p class="font-medium mb-1">{{ __('Prerequisite for:') }}</p>
                  <ul class="space-y-0.5">
                    <li v-for="dep in course.prerequisite_for" :key="dep.course"
                      class="flex items-center justify-between gap-3">
                      <span>{{ dep.course_name }}</span>
                      <span class="opacity-70 whitespace-nowrap">
                        {{ dep.mandatory === 'Mandatory' ? __('Mandatory') : __('Recommended') }}
                      </span>
                    </li>
                  </ul>
                </div>
              </template>
            </Tooltip>
          </div>

          <!-- Category Badges -->
          <div class="flex flex-wrap gap-1 mb-3">
            <Badge v-for="(cat, idx) in course.categories" :key="idx" :theme="badgeTheme(cat.type)"
              :label="badgeLabel(cat)" />
          </div>

          <!-- Available Schedules -->
          <div v-if="course.course_schedules && course.course_schedules.length">
            <div v-for="cs in course.course_schedules" :key="cs.name"
              class="flex items-center justify-between py-2 border-t text-sm gap-3">
              <div class="flex-1 min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <span v-if="cs.section" class="font-semibold text-ink-gray-7">{{ cs.section }}</span>
                  <Badge v-if="cs.modality"
                    :theme="cs.modality === 'Virtual' ? 'blue' : cs.modality === 'Hybrid' ? 'orange' : 'gray'"
                    :label="cs.modality" />
                  <span v-if="cs.days" class="text-xs text-ink-gray-5 font-mono">{{ cs.days }}</span>
                  <span v-if="cs.time_range" class="text-xs text-ink-gray-5">{{ cs.time_range }}</span>
                  <Tooltip v-if="cs.schedule_conflict && cs.schedule_conflict.length"
                    :text="conflictSummary(cs.schedule_conflict)">
                    <Badge theme="orange" :label="__('Schedule overlap')" />
                  </Tooltip>
                </div>
                <div class="text-xs text-ink-gray-5 mt-0.5">
                  <span v-if="cs.instructors">{{ cs.instructors }}</span>
                  <span v-if="cs.instructors && cs.date_range"> · </span>
                  <span v-if="cs.date_range">{{ cs.date_range }}</span>
                </div>
              </div>
              <Button size="sm" variant="subtle" @click="enrollInCourse(cs)" :loading="enrolling === cs.name">
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

  <!-- ADR 050: double-booking is allowed on purpose — warn, don't block. -->
  <Dialog v-model="showConflictDialog" :options="{ title: __('Schedule overlap') }">
    <template #body-content>
      <p class="text-sm text-ink-gray-6 mb-3">
        {{ __('This section overlaps another of your enrollments:') }}
      </p>
      <ul class="text-sm text-ink-gray-7 list-disc pl-5 mb-3 space-y-1">
        <li v-for="(c, idx) in pendingConflicts" :key="idx">
          {{ conflictLine(c) }}
        </li>
      </ul>
      <p class="text-xs text-ink-gray-5 italic">
        {{ __('You can enroll anyway — for example to hold a seat while you wait for another section. The registrar may later cancel one of the two overlapping enrollments.') }}
      </p>
    </template>
    <template #actions>
      <Button @click="showConflictDialog = false">{{ __('Cancel') }}</Button>
      <Button variant="solid" @click="confirmConflictEnroll">{{ __('Enroll Anyway') }}</Button>
    </template>
  </Dialog>
</template>

<script setup>
import { Badge, Button, Dialog, LoadingIndicator, Tooltip, createResource, toast } from 'frappe-ui'
import { HelpCircle } from 'lucide-vue-next'
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

// Group the table by status (active first, terminal/greyed last), then course,
// so it reads cleanly and the struck-through Withdrawn/Unseated rows sit together.
const STATUS_ORDER = {
  'Enrolled': 0,
  'Awaiting Payment': 1,
  'Waitlisted': 2,
  'Draft': 3,
  'Unseated': 4,
  'Withdrawn': 5,
}
const sortedEnrollments = computed(() =>
  [...(myEnrollments.data || [])].sort((a, b) => {
    const rank = (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99)
    return rank !== 0 ? rank : (a.course_data || '').localeCompare(b.course_data || '')
  })
)

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

// ADR 050: a section that overlaps another active enrollment shows an
// "Enroll Anyway / Cancel" confirm first; enrollment is never blocked.
const showConflictDialog = ref(false)
const pendingConflicts = ref([])
const pendingConflictCS = ref(null)

function conflictLine(c) {
  const when = [c.date, (c.from_time || c.to_time) ? `(${c.from_time}–${c.to_time})` : '']
    .filter(Boolean).join(' ')
  return when ? `${c.course} — ${when}` : c.course
}

function conflictSummary(conflicts) {
  return (conflicts || []).map(conflictLine).join('\n')
}

function enrollInCourse(cs) {
  const courseSchedule = typeof cs === 'string' ? cs : cs.name
  const conflicts = (typeof cs === 'object' && cs.schedule_conflict) || []
  if (conflicts.length) {
    pendingConflictCS.value = courseSchedule
    pendingConflicts.value = conflicts
    showConflictDialog.value = true
    return
  }
  doEnroll(courseSchedule)
}

function confirmConflictEnroll() {
  showConflictDialog.value = false
  if (pendingConflictCS.value) doEnroll(pendingConflictCS.value)
}

function doEnroll(courseSchedule) {
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

const releaseAction = createResource({
  url: 'seminary.seminary.api.cancel_unpaid_enrollment',
})

// Release an unpaid "Awaiting Payment" seat (cancels the invoice, frees the
// seat for the waitlist). Not a withdrawal — leaves no transcript record.
// Only possible while the section is still open for enrollment; once closed,
// the student must withdraw instead, so guide them there clearly.
function releaseUnpaid(cei) {
  if (!cei.enrollment_open) {
    toast.error(__('This course enrollment window is closed. You can withdraw from its My Status page or ask the registrar.'))
    return
  }
  cancelling.value = cei.name
  releaseAction.submit({ cei_name: cei.name }).then(() => {
    cancelling.value = null
    myEnrollments.reload()
    courses.reload()
  }).catch((err) => {
    cancelling.value = null
    toast.error(err?.messages?.[0] || __('Could not cancel this enrollment.'))
  })
}
</script>
