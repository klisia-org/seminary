<template>
  <div v-if="isStudent">
    <header class="sticky top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
      <Breadcrumbs :items="breadcrumbs" />
    </header>

    <div v-if="status.loading" class="flex items-center justify-center py-20">
      <LoadingIndicator class="w-8 h-8" />
    </div>

    <div v-else-if="status.data" class="px-5 py-4 space-y-6">

      <!-- Withdrawal Status Banner -->
      <div v-if="status.data.withdrawal_request"
        class="rounded-lg border border-yellow-200 bg-yellow-50 p-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <AlertTriangle class="w-5 h-5 text-yellow-600" />
          <div>
            <p class="font-semibold text-yellow-800">{{ __('Withdrawal Request') }}</p>
            <p class="text-sm text-yellow-700">{{ __('Status') }}: {{ status.data.withdrawal_request.workflow_state }}</p>
          </div>
        </div>
      </div>

      <!-- Progress Section -->
      <div>
        <h3 class="text-lg font-semibold text-gray-800 mb-2">{{ __('Progress') }}</h3>
        <div class="flex items-center gap-4">
          <div class="flex-1 bg-gray-200 rounded-full h-4 overflow-hidden">
            <div class="bg-blue-500 h-4 rounded-full transition-all duration-300"
              :style="{ width: Math.min(status.data.progress || 0, 100) + '%' }">
            </div>
          </div>
          <span class="text-sm font-semibold text-gray-600 w-12 text-right">
            {{ Math.min(Math.ceil(status.data.progress || 0), 100) }}%
          </span>
        </div>
      </div>

      <!-- Assessments Table -->
      <div>
        <h3 class="text-lg font-semibold text-gray-800 mb-2">{{ __('Assessments') }}</h3>
        <div v-if="status.data.assessments && status.data.assessments.length > 0">
          <ListView :columns="assessmentColumns" :rows="assessmentRows" :options="{
            selectable: false,
            showTooltip: false,
            onRowClick: () => { },
          }" row-key="name">
            <ListHeader>
              <ListHeaderItem v-for="column in assessmentColumns" :key="column.key" :item="column" />
            </ListHeader>
            <ListRow v-for="row in assessmentRows" :key="row.name" :row="row" v-slot="{ column, item }">
              <ListRowItem :item="item" :align="column.align" />
            </ListRow>
          </ListView>
        </div>
        <div v-else class="text-gray-500 text-sm">{{ __('No assessments available yet.') }}</div>
      </div>

      <!-- Final Grade -->
      <div v-if="status.data.fgrade">
        <h3 class="text-lg font-semibold text-gray-800 mb-2">{{ __('Final Grade') }}</h3>
        <div class="flex gap-6 items-center">
          <div class="text-center">
            <p class="text-3xl font-bold text-gray-800">{{ status.data.fgrade }}</p>
            <p class="text-sm text-gray-500">{{ __('Grade') }}</p>
          </div>
          <div class="text-center">
            <p class="text-3xl font-bold text-gray-800">{{ status.data.fscore }}</p>
            <p class="text-sm text-gray-500">{{ __('Score') }}</p>
          </div>
          <div class="text-center">
            <Badge :variant="status.data.fgradepass === 'Pass' ? 'success' : 'warning'"
              :label="status.data.fgradepass" />
          </div>
        </div>
      </div>

      <!-- Withdrawal Button -->
      <div v-if="allowWithdrawal && !status.data.withdrawal_request" class="border-t pt-4">
        <Button variant="subtle" theme="red" @click="goToWithdrawal">
          {{ __('Request Withdrawal from this Course') }}
        </Button>
      </div>
    </div>

    <div v-else class="px-5 py-10">
      <p class="text-gray-500">{{ __('You are not enrolled in this course.') }}</p>
    </div>
  </div>
  <div v-else class="flex flex-col items-center justify-center py-20">
    <p class="text-lg font-bold text-gray-500">{{ __('This page is only available for students.') }}</p>
  </div>
</template>

<script setup>
import { Breadcrumbs, ListView, ListHeader, ListHeaderItem, ListRow, ListRowItem, Badge, Button, LoadingIndicator, createResource } from 'frappe-ui'
import { computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { AlertTriangle } from 'lucide-vue-next'

const props = defineProps({
  courseName: { type: String, required: true },
})

const user = inject('$user')
const router = useRouter()
const isStudent = user.data?.is_student

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: { course: props.courseName },
  auto: true,
})

const status = createResource({
  url: 'seminary.seminary.utils.get_student_course_status',
  params: { course: props.courseName },
  auto: true,
})

const seminarySettings = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Seminary Settings',
    fieldname: 'allow_portal_withdrawal',
  },
  auto: true,
})

const allowWithdrawal = computed(() => {
  return seminarySettings.data?.allow_portal_withdrawal === 1
})

const breadcrumbs = computed(() => {
  return [
    { label: __('Courses'), route: { name: 'Courses' } },
    { label: course.data?.title || props.courseName, route: { name: 'CourseDetail', params: { courseName: props.courseName } } },
    { label: __('My Status') },
  ]
})

const assessmentColumns = [
  { label: __('Assessment'), key: 'title', width: 2 },
  { label: __('Type'), key: 'type', width: 1 },
  { label: __('Status'), key: 'status', width: 1 },
  { label: __('Due Date'), key: 'due_date', width: 1 },
  { label: __('My Score'), key: 'score_display', width: 1, align: 'right' },
  { label: __('Weight'), key: 'weight_display', width: 1, align: 'right' },
  { label: __('Class Median'), key: 'median_display', width: 1, align: 'right' },
  { label: __('Percentile'), key: 'percentile', width: 1, align: 'right' },
]

const assessmentRows = computed(() => {
  if (!status.data?.assessments) return []
  const maxGrade = status.data.maxnumgrade || 100
  return status.data.assessments.map(a => ({
    name: a.grade_name || a.assessment_criteria,
    title: a.title || a.assessment_criteria,
    type: a.type || '-',
    status: a.status || '-',
    due_date: a.due_date || '-',
    score_display: a.rawscore_card != null && a.rawscore_card > 0 ? `${a.rawscore_card} / ${maxGrade}` : '-',
    weight_display: a.weight_scac ? `${a.weight_scac}%` : (a.extracredit_scac ? 'Extra' : '-'),
    median_display: a.class_median != null ? `${a.class_median} / ${maxGrade}` : '-',
    percentile: a.percentile != null ? `Top ${100 - a.percentile}%` : '-',
    rawPercentile: a.percentile,
  }))
})

function percentileClass(percentile) {
  if (percentile == null || percentile === '-') return 'text-gray-500'
  const raw = typeof percentile === 'string' ? parseInt(percentile) : percentile
  if (raw >= 50) return 'text-green-600 font-medium'
  return 'text-gray-600'
}

function goToWithdrawal() {
  router.push({
    name: 'CourseWithdrawalRequest',
    params: { courseName: props.courseName },
    query: {
      cei: status.data?.course_enrollment_individual,
      pe: status.data?.program_enrollment,
    },
  })
}
</script>
