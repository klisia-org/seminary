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
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-semibold text-gray-800">{{ __('Assessments') }}</h3>
          <Button v-if="status.data.assessments?.length" :variant="simulating ? 'solid' : 'outline'"
            :theme="simulating ? 'orange' : 'gray'" size="sm" @click="toggleSimulation">
            {{ simulating ? __('Exit Simulation') : __('Simulate Grades') }}
          </Button>
        </div>
        <div v-if="status.data.assessments && status.data.assessments.length > 0">

          <!-- Normal table -->
          <ListView v-if="!simulating" :columns="assessmentColumns" :rows="assessmentRows" :options="{
            selectable: false,
            showTooltip: false,
            onRowClick: () => { },
          }" row-key="name">
            <ListHeader>
              <ListHeaderItem v-for="column in assessmentColumns" :key="column.key" :item="column" />
            </ListHeader>
            <ListRow v-for="row in assessmentRows" :key="row.name" :row="row"
              :class="row.isExtraCredit ? 'bg-blue-50' : ''"
              v-slot="{ column, item }">
              <ListRowItem :item="item" :align="column.align" />
            </ListRow>
          </ListView>

          <!-- Simulation table with editable scores -->
          <div v-else class="rounded-lg border border-orange-200 overflow-hidden">
            <table class="w-full text-sm">
              <thead class="bg-orange-50 text-gray-600">
                <tr>
                  <th class="text-left px-3 py-2 font-medium">{{ __('Assessment') }}</th>
                  <th class="text-left px-3 py-2 font-medium">{{ __('Weight') }}</th>
                  <th class="text-right px-3 py-2 font-medium">{{ __('Score') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="a in simAssessments" :key="a.key"
                  :class="a.isExtraCredit ? 'bg-orange-50/50' : ''">
                  <td class="px-3 py-2">{{ a.title }}</td>
                  <td class="px-3 py-2">{{ a.weight }}</td>
                  <td class="px-3 py-2 text-right">
                    <div class="inline-flex items-center gap-1">
                      <input type="number" :min="0" :max="a.maxGrade"
                        v-model.number="simScores[a.key]"
                        class="w-16 rounded border border-orange-300 px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-orange-400" />
                      <span class="text-gray-400">/ {{ a.maxGrade }}</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-else class="text-gray-500 text-sm">{{ __('No assessments available yet.') }}</div>
      </div>

      <!-- Grade Section -->
      <div v-if="currentGrade || projectedGrade">
        <h3 class="text-lg font-semibold text-gray-800 mb-2">{{ __('Your Grade') }}</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">

          <!-- Current / Simulated Grade -->
          <div class="rounded-lg border p-4" :class="simulating ? 'border-orange-200 bg-orange-50' : 'bg-gray-50'">
            <h4 class="text-sm font-semibold mb-1" :class="simulating ? 'text-orange-800' : 'text-gray-700'">
              {{ simulating ? __('Simulated Grade') : __('Current Grade') }}
            </h4>
            <p class="text-xs mb-3" :class="simulating ? 'text-orange-600' : 'text-gray-500'">
              {{ simulating
                ? __('Edit scores above and see the result here.')
                : __('Your final grade as of today, including zeros for unsubmitted work.') }}
            </p>
            <div class="flex gap-6 items-center">
              <div class="text-center">
                <p class="text-3xl font-bold" :class="simulating ? 'text-orange-800' : 'text-gray-800'">
                  {{ (simulating ? simulatedGrade : currentGrade)?.grade }}
                </p>
                <p class="text-xs" :class="simulating ? 'text-orange-500' : 'text-gray-500'">{{ __('Grade') }}</p>
              </div>
              <div class="text-center">
                <p class="text-3xl font-bold" :class="simulating ? 'text-orange-800' : 'text-gray-800'">
                  {{ (simulating ? simulatedGrade : currentGrade)?.score }} / {{ (simulating ? simulatedGrade : currentGrade)?.maxGrade }}
                </p>
                <p class="text-xs" :class="simulating ? 'text-orange-500' : 'text-gray-500'">{{ __('Score') }}</p>
              </div>
              <div class="text-center">
                <Badge :variant="(simulating ? simulatedGrade : currentGrade)?.gradePass === 'Pass' ? 'success' : 'warning'"
                  :label="(simulating ? simulatedGrade : currentGrade)?.gradePass" />
              </div>
            </div>
          </div>

          <!-- Projected Grade (hidden during simulation) -->
          <template v-if="!simulating">
            <div v-if="projectedGrade" class="rounded-lg border border-blue-200 p-4 bg-blue-50">
              <h4 class="text-sm font-semibold text-blue-800 mb-1">{{ __('Projected Grade') }}</h4>
              <p class="text-sm text-blue-700 mb-3">
                {{ __('You are on track for') }}
                <strong>{{ projectedGrade.grade }}</strong>
                {{ __('if you keep your efforts like this in future assessments.') }}
              </p>
              <div class="flex gap-6 items-center">
                <div class="text-center">
                  <p class="text-3xl font-bold text-blue-800">{{ projectedGrade.grade }}</p>
                  <p class="text-xs text-blue-500">{{ __('Projected') }}</p>
                </div>
                <div class="text-center">
                  <p class="text-3xl font-bold text-blue-800">{{ projectedGrade.score }} / {{ projectedGrade.maxGrade }}</p>
                  <p class="text-xs text-blue-500">{{ __('Based on due assessments') }}</p>
                </div>
              </div>
            </div>
            <div v-else class="rounded-lg border border-dashed p-4 bg-gray-50">
              <h4 class="text-sm font-semibold text-gray-700 mb-1">{{ __('Projected Grade') }}</h4>
              <p class="text-sm text-gray-500">
                {{ __('No assessments are due yet. Your projected grade will appear once the first assessment due date passes.') }}
              </p>
            </div>
          </template>

        </div>
      </div>
      <div v-else class="text-gray-500 text-sm">{{ __('No assessments available yet to calculate your grade.') }}</div>

      <!-- Withdrawal Rules & Button -->
      <div v-if="allowWithdrawal && !status.data.withdrawal_request && withdrawalRules.length > 0" class="border-t pt-4 space-y-3">
        <h3 class="text-lg font-semibold text-gray-800">{{ __('Key dates for withdrawal') }}</h3>
        <div class="inline-flex flex-col space-y-1">
          <div v-for="rule in withdrawalRules" :key="rule.withdrawal_rule"
            class="flex items-center gap-3 text-sm px-2 py-1 rounded"
            :class="rule.expired ? 'text-gray-400' : 'text-gray-700'">
            <span>{{ rule.withdrawal_rule }}</span>
            <span class="text-gray-400">—</span>
            <span>{{ formatDate(rule.applies_until) }}</span>
          </div>
        </div>
        <Button v-if="withdrawalStillOpen" variant="subtle" theme="red" @click="goToWithdrawal">
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
import { computed, inject, ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { AlertTriangle } from 'lucide-vue-next'
import { formatDate } from '@/utils'

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

const withdrawalRules = computed(() => {
  if (!status.data?.withdrawal_rules) return []
  const today = new Date().toISOString().slice(0, 10)
  return status.data.withdrawal_rules.map(r => ({
    ...r,
    expired: r.applies_until < today,
  }))
})

const withdrawalStillOpen = computed(() => {
  if (withdrawalRules.value.length === 0) return false
  return withdrawalRules.value.some(r => !r.expired)
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

  const sorted = [...status.data.assessments].sort((a, b) => {
    if (!a.due_date && b.due_date) return 1
    if (a.due_date && !b.due_date) return -1
    if (a.due_date && b.due_date) {
      const dateA = new Date(a.due_date)
      const dateB = new Date(b.due_date)
      if (dateA < dateB) return -1
      if (dateA > dateB) return 1
    }
    return (a.title || '').localeCompare(b.title || '')
  })

  return sorted.map(a => ({
    name: a.grade_name || a.assessment_criteria,
    title: a.title || a.assessment_criteria,
    type: a.type || '-',
    status: a.status || '-',
    due_date: a.due_date ? formatDate(a.due_date) : '-',
    isExtraCredit: !!a.extracredit_scac,
    score_display: a.extracredit_scac
      ? (a.actualextrapt_card != null && a.actualextrapt_card > 0 ? `+${a.actualextrapt_card} pts` : '-')
      : (a.rawscore_card != null && a.rawscore_card > 0 ? `${a.rawscore_card} / ${maxGrade}` : '-'),
    weight_display: a.weight_scac ? `${a.weight_scac}%` : (a.extracredit_scac ? `Extra ${a.fudgepoints_scac} pts` : '-'),
    median_display: a.class_median != null ? `${a.class_median} / ${maxGrade}` : '-',
    percentile: a.percentile != null ? `Top ${100 - a.percentile}%` : '-',
    rawPercentile: a.percentile,
  }))
})

const currentGrade = computed(() => {
  const assessments = status.data?.assessments
  const intervals = status.data?.grading_scale_intervals
  const maxGrade = status.data?.maxnumgrade || 100
  if (!assessments || !intervals || assessments.length === 0) return null

  const regular = assessments.filter(a => !a.extracredit_scac)
  const weightedSum = regular.reduce((sum, a) => {
    const raw = a.rawscore_card || 0
    return sum + raw * (a.weight_scac || 0)
  }, 0)

  const extraPoints = assessments
    .filter(a => a.extracredit_scac)
    .reduce((sum, a) => sum + (a.actualextrapt_card || 0), 0)

  const score = (weightedSum + extraPoints) / maxGrade

  const sorted = [...intervals].sort((a, b) => b.threshold - a.threshold)
  let grade = ''
  let gradePass = ''
  for (const interval of sorted) {
    if (score >= interval.threshold) {
      grade = interval.grade_code
      gradePass = interval.grade_pass
      break
    }
  }

  return { score: Math.round(score * 100) / 100, maxGrade, grade, gradePass }
})

const projectedGrade = computed(() => {
  const assessments = status.data?.assessments
  const intervals = status.data?.grading_scale_intervals
  const maxGrade = status.data?.maxnumgrade || 100
  if (!assessments || !intervals || assessments.length === 0) return null

  const regular = assessments.filter(a => !a.extracredit_scac)
  const graded = regular.filter(a => a.rawscore_card != null && a.rawscore_card > 0)
  if (graded.length === 0) return null

  // Unweighted average of graded assessments
  const avgRawScore = graded.reduce((sum, a) => sum + a.rawscore_card, 0) / graded.length

  // Actual score for graded, average for ungraded
  const weightedSum = regular.reduce((sum, a) => {
    const hasScore = a.rawscore_card != null && a.rawscore_card > 0
    const raw = hasScore ? a.rawscore_card : avgRawScore
    return sum + raw * (a.weight_scac || 0)
  }, 0)

  const extraPoints = assessments
    .filter(a => a.extracredit_scac)
    .reduce((sum, a) => sum + (a.actualextrapt_card || 0), 0)

  const score = (weightedSum + extraPoints) / maxGrade

  const sorted = [...intervals].sort((a, b) => b.threshold - a.threshold)
  let grade = ''
  let gradePass = ''
  for (const interval of sorted) {
    if (score >= interval.threshold) {
      grade = interval.grade_code
      gradePass = interval.grade_pass
      break
    }
  }

  return { score: Math.round(score * 100) / 100, maxGrade, grade, gradePass }
})

// ── Simulation ───────────────────────────────────────────────────────────────
const simAssessments = computed(() => {
  if (!status.data?.assessments) return []
  const maxGrade = status.data.maxnumgrade || 100
  return status.data.assessments.map(a => ({
    key: a.grade_name || a.assessment_criteria,
    title: a.title || a.assessment_criteria,
    isExtraCredit: !!a.extracredit_scac,
    weight: a.weight_scac ? `${a.weight_scac}%` : (a.extracredit_scac ? `Extra` : '-'),
    maxGrade,
  }))
})

const simulating = ref(false)
const simScores = reactive({})

watch(() => status.data?.assessments, (assessments) => {
  if (!assessments) return
  assessments.forEach(a => {
    const key = a.grade_name || a.assessment_criteria
    if (!(key in simScores)) {
      simScores[key] = a.rawscore_card || 0
    }
  })
}, { immediate: true })

function toggleSimulation() {
  if (simulating.value) {
    // Reset scores to actuals
    status.data?.assessments?.forEach(a => {
      const key = a.grade_name || a.assessment_criteria
      simScores[key] = a.rawscore_card || 0
    })
  }
  simulating.value = !simulating.value
}

const simulatedGrade = computed(() => {
  const assessments = status.data?.assessments
  const intervals = status.data?.grading_scale_intervals
  const maxGrade = status.data?.maxnumgrade || 100
  if (!assessments || !intervals || assessments.length === 0) return null

  const regular = assessments.filter(a => !a.extracredit_scac)
  const weightedSum = regular.reduce((sum, a) => {
    const key = a.grade_name || a.assessment_criteria
    const raw = Number(simScores[key]) || 0
    return sum + raw * (a.weight_scac || 0)
  }, 0)

  const extraPoints = assessments
    .filter(a => a.extracredit_scac)
    .reduce((sum, a) => {
      const key = a.grade_name || a.assessment_criteria
      return sum + (Number(simScores[key]) || 0)
    }, 0)

  const score = (weightedSum + extraPoints) / maxGrade

  const sorted = [...intervals].sort((a, b) => b.threshold - a.threshold)
  let grade = ''
  let gradePass = ''
  for (const interval of sorted) {
    if (score >= interval.threshold) {
      grade = interval.grade_code
      gradePass = interval.grade_pass
      break
    }
  }

  return { score: Math.round(score * 100) / 100, maxGrade, grade, gradePass }
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
