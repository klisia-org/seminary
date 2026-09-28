<template>

  <PageHeader>
  	<template #title>
  		<Breadcrumbs class="h-7" :items="breadcrumbs" />
  	</template>
  	<template #actions>
  		<div v-if="weightsApply && totalPoints !== 100" class="flex items-center mt-3 md:mt-0">
  		  <Tooltip :text="__('Save is only allowed when Total Points = 100')" placement="bottom">
  		    <Button variant="subtle" class="ml-2">
  		      <span>
  		        {{ __('Save only allowed when Total Points = 100') }}
  		      </span>
  		    </Button>
  		  </Tooltip>
  		</div>
  		<div v-else class="flex items-center mt-3 md:mt-0">
  		  <Button variant="solid" @click="submitCourseAssessment()" class="ml-2">
  		    <span>
  		      {{ __('Save') }}
  		    </span>
  		  </Button>
  		</div>
  	</template>
  </PageHeader>
  <div class="mt-5 mb-10 w-full px-5">
    <div class="container max-w-full mb-5 ">
      <div v-if="!course.data" class="text-lg font-semibold mb-4">
        {{ __('Assessment Criteria') }}
      </div>
      <div v-else class="text-lg font-semibold mb-4">
        {{ __('Assessment Criteria for ' + course.data.course) }}
      </div>
      <!-- A competency section has no weighted total: activity levels roll
           into a Competency Result, not a percentage (ADR 065 section 11a). -->
      <div v-if="weightsApply"
        :class="{ 'max-w-full flex justify-between mb-4 mt-5 text-xl': true, 'bg-surface-red-3 text-ink-red-3 rounded px-2': totalPoints !== 100 }">
        <div>
          <strong>{{ __('Total Points') }}:</strong> {{ totalPoints }}
        </div>
        <div>
          <strong>{{ __('Max Fudge Points') }}:</strong> {{ maxFudgePoints }}
        </div>
      </div>
      <div v-else class="max-w-full mb-4 mt-5 text-sm text-ink-gray-6">
        {{ __('Graded by competency: each assessment carries a competency and the weight of each dimension within it. Percentages do not apply.') }}
      </div>
    </div>
  </div>
  <!-- Late submissions (decisions/082 section 4): one policy per section,
       only where the scale is points. -->
  <div v-if="deadlines.data?.policy_available" class="mx-5 mb-6 rounded border border-outline-gray-2 p-4">
    <div class="flex items-center justify-between">
      <FormControl type="checkbox" v-model="policy.late_policy_enabled"
        :label="__('Deduct points for late work')" />
      <Button size="sm" :loading="savingPolicy" @click="savePolicy">{{ __('Save late policy') }}</Button>
    </div>
    <div v-if="policy.late_policy_enabled" class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <FormControl type="number" v-model="policy.late_deduction" :label="__('Deduction per interval (%)')" />
      <FormControl type="select" v-model="policy.late_interval" :label="__('Interval')"
        :options="[{ label: __('Day'), value: 'Day' }, { label: __('Hour'), value: 'Hour' }]" />
      <FormControl type="number" v-model="policy.late_grace_minutes" :label="__('Grace period (minutes)')" />
      <FormControl type="number" v-model="policy.late_floor" :label="__('Lowest possible score (%)')" />
      <FormControl type="number" v-model="policy.missing_reply_deduction"
        :label="__('Deduction per missing reply (%)')" />
    </div>
    <p v-if="policy.late_policy_enabled" class="mt-2 text-sm text-ink-gray-6">
      {{ __('Percentage points of the maximum score, for every started day or hour after the due date. Work within the grace period is not late.') }}
    </p>
  </div>
  <table class="min-w-full table-auto border-collapse overflow-auto">
    <thead>
      <tr>
        <th class="p-2 border">{{ __('Title') }}</th>
        <th class="p-2 border">{{ __('Assessment Type') }}</th>
        <th class="p-2 border">{{ __('Activity Selection') }}</th>
        <th v-if="isCbe" class="p-2 border">{{ __('Competency') }}</th>
        <th v-if="weightsApply" class="p-2 border">{{ __('Extra Credit?') }}</th>
        <th v-if="weightsApply" class="p-2 border">{{ __('Points') }}</th>
        <th class="p-2 border">{{ __('Due Date') }}</th>
        <th class="p-2 border">{{ __('Dates') }}</th>
        <th class="p-2 border">{{ __('In Lesson') }}</th>
        <th v-if="hasAretenic" class="p-2 border">{{ __('CLOs') }}</th>
        <th v-if="isCbe" class="p-2 border">{{ __('Weights') }}</th>
        <th class="p-2 border">{{ __('Delete') }}</th>
      </tr>
    </thead>
    <tbody>
      <template v-for="(criteria, index) in assessmentCriteria" :key="index">
      <tr>
        <td class="p-2 border">
          <FormControl v-model="criteria.title" class="mb-4 overflow-visible" :required="false" />
        </td>
        <td class="p-2 border">
          <Link v-model="criteria.assesscriteria_scac" class="mb-4" doctype="Assessment Criteria" :required="true"
            @update:modelValue="() => fetchType(criteria)" />
        </td>
        <td class="p-2 border">
          <template v-if="criteria.type === 'Quiz'">
            <Link v-model="criteria.quiz" doctype="Quiz" :label="__('Select a Quiz')" :required="true"
              :filters="{ course: course.data.course }" :onCreate="(value, close) => redirectToForm('quiz', close)" />
          </template>
          <template v-else-if="criteria.type === 'Exam'">
            <Link v-model="criteria.exam" doctype="Exam Activity" :label="__('Select an Exam')" :required="true"
              :filters="{ course: course.data.course }" :onCreate="(value, close) => redirectToForm('exam', close)" />
          </template>
          <template v-else-if="criteria.type === 'Assignment'">
            <Link v-model="criteria.assignment" doctype="Assignment Activity" :label="__('Select an Assignment')"
              :required="true" :filters="{ course: course.data.course }"
              :onCreate="(value, close) => redirectToForm('assignment', close)" />
          </template>
          <template v-else-if="criteria.type === 'Discussion'">
            <Link v-model="criteria.discussion" doctype="Discussion Activity"
              :label="__('Select a Discussion Activity')" :required="true" :filters="{ course: course.data.course }"
              :onCreate="(value, close) => redirectToForm('discussion', close)" />
          </template>
          <template v-else>
            <p>{{ __('Offline') }}</p>
          </template>
        </td>
        <td v-if="isCbe" class="p-2 border" style="width: 16%;">
          <FormControl type="select" v-model="criteria.course_competency"
            :options="competencyOptions" :disabled="!!chapterCompetency(criteria)" />
          <p v-if="chapterCompetency(criteria)" class="mt-1 text-xs text-ink-gray-5">
            {{ __('Set by its chapter.') }}
          </p>
        </td>
        <td v-if="weightsApply" class="p-2 border text-center">
          <FormControl v-model="criteria.extracredit_scac" type="checkbox" :required="false" class="mb-4 inline-block"
            :default="false" />
        </td>
        <td v-if="weightsApply" class="p-2 border" style="width: 10%;">
          <div v-if="criteria.extracredit_scac" class="mb-4 light-blue-bg p-2 rounded">
            <FormControl v-model="criteria.fudgepoints_scac" :label="__('Fudge Points')" type="float" class="max-w-14ch"
              :required="true" />
          </div>
          <div v-else class="mb-4">
            <FormControl v-model="criteria.weight_scac" :label="__('Weight')" type="float" class="max-w-14ch"
              :required="true" />
          </div>
        </td>
        <td class="p-2 border">
          <DateTimePicker v-model="criteria.due_date" variant="subtle" :required="false" class="date-column"
            :formatter="formatDate" />
        </td>
        <td class="p-2 border text-center align-middle">
          <Tooltip :text="criteria.name ? __('Cut-off, late deduction and student exceptions') : __('Save first')">
            <Button variant="ghost" size="sm" :disabled="!criteria.name" @click="toggleDates(criteria)">
              <Clock class="h-4 w-4 stroke-1.5"
                :class="criteria.cutoff_date || overridesFor(criteria).length ? 'text-ink-blue-3' : ''" />
            </Button>
          </Tooltip>
          <div v-if="overridesFor(criteria).length" class="text-xs text-ink-gray-5">
            {{ __('{0} exception(s)').format(overridesFor(criteria).length) }}
          </div>
        </td>
        <td class="p-2 border text-center">
          <span v-if="criteria.lesson" class="checkmark">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24"
              stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </span>
          <span v-else class="text-red-500">
            ✘
          </span>
        </td>
        <td v-if="hasAretenic" class="p-2 border text-center align-middle">
          <Tooltip v-if="!criteria.name" :text="__('Save the assessment before mapping outcomes')">
            <Button variant="ghost" size="sm" :disabled="true">
              <Target class="h-4 w-4 stroke-1.5" />
            </Button>
          </Tooltip>
          <Tooltip v-else :text="__('Map to Course Learning Outcomes')">
            <Button variant="ghost" size="sm" @click="openCloMapper(criteria)">
              <Target class="h-4 w-4 stroke-1.5" />
            </Button>
          </Tooltip>
        </td>
        <td v-if="isCbe" class="p-2 border text-center align-middle">
          <Button variant="ghost" size="sm"
            :disabled="!criteria.name"
            :title="criteria.name ? __('Dimensions and evaluators') : __('Save first')"
            @click="toggleDetail(criteria)">
            <SlidersHorizontal class="h-4 w-4 stroke-1.5" />
          </Button>
        </td>
        <td class="p-2 border text-center align-middle">
          <Button variant="ghost" size="sm" theme="red" @click="removeCriteria(index)">
            <Trash2 class="h-4 w-4 stroke-1.5" />
          </Button>
        </td>
      </tr>
      <!-- Dates for one assessment (decisions/082 sections 2, 3 and 5): its
           cut-off, the discussion replies date, the late opt-out, and the
           students who have their own dates. -->
      <tr v-if="openDates === criteria.name">
        <td :colspan="detailColspan" class="p-4 border bg-surface-gray-1">
          <div class="grid gap-4 lg:grid-cols-3">
            <div>
              <h4 class="font-semibold text-ink-gray-8 mb-1">{{ __('Cut-off') }}</h4>
              <p class="text-sm text-ink-gray-6 mb-2">
                {{ __('No submissions after this. Leave blank to accept late work at any time.') }}
              </p>
              <DateTimePicker v-model="criteria.cutoff_date" variant="subtle" :formatter="formatDate" />
            </div>
            <div v-if="twoDatesPossible(criteria)">
              <h4 class="font-semibold text-ink-gray-8 mb-1">{{ __('Replies due') }}</h4>
              <p class="text-sm text-ink-gray-6 mb-2">
                {{ __('With this set, the due date is for the initial post and each reply missing by this date loses the per-reply deduction.') }}
              </p>
              <DateTimePicker v-model="criteria.replies_due_date" variant="subtle" :formatter="formatDate" />
            </div>
            <div v-if="deadlines.data?.policy_available">
              <h4 class="font-semibold text-ink-gray-8 mb-1">{{ __('Late deduction') }}</h4>
              <FormControl type="checkbox" v-model="criteria.late_policy_exempt"
                :label="__('No late deduction for this assessment')" />
            </div>
          </div>
          <p class="mt-2 text-xs text-ink-gray-5">{{ __('These are saved with the Save button at the top of the page.') }}</p>

          <h4 class="mt-5 font-semibold text-ink-gray-8 mb-1">{{ __('Students with their own dates') }}</h4>
          <p class="text-sm text-ink-gray-6 mb-2">
            {{ __('Anything left blank follows the dates above.') }}
          </p>
          <table v-if="overridesFor(criteria).length" class="text-sm mb-3 w-full">
            <thead>
              <tr class="text-left text-ink-gray-6">
                <th class="p-1">{{ __('Student') }}</th>
                <th class="p-1">{{ __('Due') }}</th>
                <th class="p-1">{{ __('Cut-off') }}</th>
                <th v-if="twoDatesPossible(criteria)" class="p-1">{{ __('Replies due') }}</th>
                <th class="p-1">{{ __('Extra') }}</th>
                <th class="p-1">{{ __('Reason') }}</th>
                <th class="p-1"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ov in overridesFor(criteria)" :key="ov.name" class="border-t border-outline-gray-1">
                <td class="p-1">{{ ov.student_name }}</td>
                <td class="p-1">{{ formatDate(ov.due_date) || '—' }}</td>
                <td class="p-1">{{ formatDate(ov.cutoff_date) || '—' }}</td>
                <td v-if="twoDatesPossible(criteria)" class="p-1">{{ formatDate(ov.replies_due_date) || '—' }}</td>
                <td class="p-1">
                  <span v-if="ov.extra_minutes">{{ __('+{0} min').format(ov.extra_minutes) }} </span>
                  <span v-if="ov.extra_attempts">{{ __('+{0} attempt(s)').format(ov.extra_attempts) }}</span>
                </td>
                <td class="p-1">{{ ov.reason }}</td>
                <td class="p-1 whitespace-nowrap">
                  <Button variant="ghost" size="sm" @click="editOverride(ov)">{{ __('Edit') }}</Button>
                  <Button variant="ghost" size="sm" theme="red" @click="removeOverride(ov)">
                    <Trash2 class="h-4 w-4 stroke-1.5" />
                  </Button>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 rounded border border-outline-gray-2 bg-surface-white p-3">
            <FormControl type="select" v-model="ovForm.student" :label="__('Student')"
              :options="rosterOptions" :disabled="!!ovForm.name" />
            <div>
              <label class="text-xs text-ink-gray-5">{{ __('Due date') }}</label>
              <DateTimePicker v-model="ovForm.due_date" variant="subtle" :formatter="formatDate" />
            </div>
            <div>
              <label class="text-xs text-ink-gray-5">{{ __('Cut-off') }}</label>
              <DateTimePicker v-model="ovForm.cutoff_date" variant="subtle" :formatter="formatDate" />
            </div>
            <div v-if="twoDatesPossible(criteria)">
              <label class="text-xs text-ink-gray-5">{{ __('Replies due') }}</label>
              <DateTimePicker v-model="ovForm.replies_due_date" variant="subtle" :formatter="formatDate" />
            </div>
            <FormControl v-if="['Quiz', 'Exam'].includes(criteria.type)" type="number"
              v-model="ovForm.extra_minutes" :label="__('Extra minutes')" />
            <FormControl v-if="criteria.type === 'Quiz'" type="number"
              v-model="ovForm.extra_attempts" :label="__('Extra attempts')" />
            <FormControl class="sm:col-span-2" v-model="ovForm.reason" :label="__('Reason')" />
            <div class="flex items-end gap-2">
              <Button variant="solid" size="sm" :loading="savingOverride" @click="saveOverride(criteria)">
                {{ ovForm.name ? __('Save changes') : __('Add') }}
              </Button>
              <Button v-if="ovForm.name" size="sm" @click="resetOverrideForm()">{{ __('Cancel') }}</Button>
            </div>
          </div>
        </td>
      </tr>
      <!-- Dimension weights and the grading matrix (ADR 065 section 11b).
           Both are separate records keyed to a saved criteria row, which is
           why the opener waits for a name. -->
      <tr v-if="isCbe && openDetail === criteria.name">
        <td :colspan="detailColspan" class="p-4 border bg-surface-gray-1">
          <div class="grid gap-6 lg:grid-cols-2">
            <div>
              <h4 class="font-semibold text-ink-gray-8 mb-1">{{ __('Dimension weights') }}</h4>
              <p class="text-sm text-ink-gray-6 mb-2">
                {{ __('How much this assessment says about each dimension. Leave them equal if it says the same about all.') }}
              </p>
              <div v-for="d in dimensions" :key="d.dimension_code" class="mb-2">
                <FormControl type="number" :label="d.dimension"
                  v-model="detail.weights[d.dimension_code]" />
              </div>
            </div>
            <div>
              <h4 class="font-semibold text-ink-gray-8 mb-1">{{ __('Who grades what') }}</h4>
              <p class="text-sm text-ink-gray-6 mb-2">
                {{ __('Untick a box when that mentor does not judge that dimension here. That is not a zero — it drops out of the average entirely.') }}
              </p>
              <table class="text-sm">
                <thead>
                  <tr>
                    <th class="p-1 text-left">{{ __('Evaluator') }}</th>
                    <th v-for="d in dimensions" :key="d.dimension_code" class="p-1">
                      {{ d.dimension }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="g in gradingCategories" :key="g.instructor_category">
                    <td class="p-1 pr-3">{{ g.instructor_category }}</td>
                    <td v-for="d in dimensions" :key="d.dimension_code" class="p-1 text-center">
                      <input type="checkbox" :checked="cellGraded(g, d)"
                        @change="setCell(g, d, $event.target.checked)" />
                    </td>
                  </tr>
                </tbody>
              </table>
              <p v-if="!gradingCategories.length" class="text-sm text-ink-gray-5">
                {{ __('The framework names no evaluators who grade activities.') }}
              </p>
            </div>
          </div>
          <div class="mt-4 flex items-center gap-2">
            <Button variant="solid" size="sm" :loading="savingDetail" @click="saveDetail(criteria)">
              {{ __('Save these') }}
            </Button>
            <Button variant="subtle" size="sm" @click="openDetail = null">{{ __('Close') }}</Button>
          </div>
        </td>
      </tr>
      </template>
    </tbody>
  </table>

  <div class="mt-5 mb-10 max-w-full px-15">


    <br>
    <Button class="mb-4" size="sm" @click="openCourseAssessmentModal">
      {{ __('Add Evaluation') }}
    </Button>



    <CourseAssessmentModal v-model="showCourseAssessmentModal" v-model:modalcriteria="modalcriteria"
      :courseName="props.courseName" @assessment-saved="onAssessmentSaved" />

    <CLOAssessmentMapperModal v-if="hasAretenic" v-model="showCloMapper" :course="course.data?.course"
      :courseSchedule="props.courseName" :scheduledAssessCriteria="activeCriteria?.name"
      :assessmentType="activeCriteria?.type" :criteriaTitle="activeCriteria?.title"
      @saved="cloCoverageKey++" />
  </div>

  <!-- The reverse view, next to where the mapping is actually authored (decisions/034 section 4). -->
  <CLOCoveragePanel v-if="hasAretenic" :courseSchedule="props.courseName" :refreshKey="cloCoverageKey" />
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
import { call, createResource, Breadcrumbs, Button, FormControl, Tooltip, toast, DateTimePicker } from 'frappe-ui'
import { computed, reactive, onMounted, inject, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Trash2, Target, SlidersHorizontal, Clock } from 'lucide-vue-next'
import { updateDocumentTitle } from '@/utils'
import CourseAssessmentModal from '@/components/Modals/CourseAssessmentModal.vue'
import CLOAssessmentMapperModal from '@/components/Modals/CLOAssessmentMapperModal.vue'
import CLOCoveragePanel from '@/components/CLOCoveragePanel.vue'
import { useSettings } from '@/stores/settings'
import Link from '@/components/Controls/Link.vue'
import { getCsrfToken } from '../utils/csrf'



const route = useRoute()
const router = useRouter()
const user = inject('$user')
const settingsStore = useSettings()
const showCourseAssessmentModal = ref(false)
const show = defineModel()

// Optional CLO assessment mapper — only when the Aretenic app is installed (ADR 030).
const hasAretenic = computed(() => !!user?.data?.has_aretenic)
const showCloMapper = ref(false)
const activeCriteria = ref(null)
// Bumped when a mapping is saved, so the coverage panel below reflects it without a page reload.
const cloCoverageKey = ref(0)

function openCloMapper(criteria) {
  activeCriteria.value = criteria
  showCloMapper.value = true
}

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})

// --- Competency mode (ADR 065 section 11b) ---------------------------------
// One derived mode drives every competency-specific column, validation and
// sub-editor on this page, so it cannot end up half in one world. Derived from
// the grading scale rather than stored, because the scale is already the
// authority on whether a section is competency-based.
//
// Declared after `props`, because `auto: true` runs `makeParams` during setup
// and `props` is only bound where `defineProps` is called.
const competencyContext = createResource({
  url: 'seminary.seminary.cbe_api.get_competency_context',
  makeParams: () => ({ course_schedule: props.courseName }),
  auto: true,
  onError: () => { },
})

const isCbe = computed(() => !!competencyContext.data?.is_cbe)
const weightsApply = computed(() => !isCbe.value)
const dimensions = computed(() => competencyContext.data?.dimensions || [])
const gradingCategories = computed(() => competencyContext.data?.grading_categories || [])

// frappe-ui's Select drops an option whose value is empty, so "no competency"
// needs a real value of its own; it is mapped back to blank on save.
const NO_COMPETENCY = '__none__'

const competencyOptions = computed(() => [
  { label: __('No competency'), value: NO_COMPETENCY },
  ...(competencyContext.data?.competencies || []).map((c) => ({
    label: c.competency_name,
    value: c.name,
  })),
])

// The chapter has already told the student which competency they are working
// on there, so an assessment inside it cannot choose a different one. The
// server resolves that chain and sends the answer, so the picker greys out
// exactly what would be refused rather than guessing.
const chapterCompetency = (criteria) => {
  const found = (competencyContext.data?.assessments || []).find(
    (a) => a.name === criteria.name
  )
  return found?.chapter_competency || null
}

const openDetail = ref(null)
const savingDetail = ref(false)
const detail = reactive({ weights: {}, matrix: [] })

// Title, type, activity, due date, in lesson, delete — then the conditional
// pairs: competency + weights, extra credit + points.
const detailColspan = computed(
  () => 7 + (isCbe.value ? 2 : 0) + (weightsApply.value ? 2 : 0) + (hasAretenic.value ? 1 : 0)
)

function toggleDetail(criteria) {
  if (openDetail.value === criteria.name) {
    openDetail.value = null
    return
  }
  const stored = (competencyContext.data?.assessments || []).find(
    (a) => a.name === criteria.name
  )
  detail.weights = {}
  for (const d of dimensions.value) {
    detail.weights[d.dimension_code] = stored?.weights?.[d.dimension_code] ?? 0
  }
  detail.matrix = (stored?.matrix || []).map((m) => ({ ...m }))
  openDetail.value = criteria.name
}

// Absence means "follow the grading mode", which is why an untouched cell is
// ticked and storing nothing is the normal state.
const cellGraded = (g, d) => {
  const cell = detail.matrix.find(
    (m) => m.instructor_category === g.instructor_category
      && m.dimension_code === d.dimension_code
  )
  return cell ? !!cell.graded : true
}

function setCell(g, d, checked) {
  const i = detail.matrix.findIndex(
    (m) => m.instructor_category === g.instructor_category
      && m.dimension_code === d.dimension_code
  )
  if (checked) {
    // Back to the default rather than an explicit "on": the two are different
    // claims, and only the first follows a later change of grading mode.
    if (i >= 0) detail.matrix.splice(i, 1)
    return
  }
  if (i >= 0) detail.matrix[i].graded = 0
  else detail.matrix.push({
    instructor_category: g.instructor_category,
    dimension_code: d.dimension_code,
    graded: 0,
  })
}

async function saveDetail(criteria) {
  savingDetail.value = true
  try {
    await call('seminary.seminary.cbe_api.save_assessment_competency_config', {
      course_schedule: props.courseName,
      config: JSON.stringify([{
        assess_criteria: criteria.name,
        weights: detail.weights,
        matrix: detail.matrix,
      }]),
    })
    toast.success(__('Saved'))
    competencyContext.reload()
    openDetail.value = null
  } catch (e) {
    const msg = Array.isArray(e?.messages) && e.messages.length
      ? e.messages.join('\n')
      : (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()
    toast.error(msg || __('Could not save.'))
  } finally {
    savingDetail.value = false
  }
}

// --- Dates and late deductions (decisions/082) -----------------------------
const deadlines = createResource({
  url: 'seminary.seminary.deadlines.get_deadline_settings',
  makeParams: () => ({ course: props.courseName }),
  auto: true,
  onSuccess(data) {
    Object.assign(policy, data?.policy || {})
  },
  onError: () => { },
})

const policy = reactive({
  late_policy_enabled: 0,
  late_deduction: 0,
  late_interval: 'Day',
  late_grace_minutes: 0,
  late_floor: 0,
  missing_reply_deduction: 0,
})
const savingPolicy = ref(false)

function errorText(e, fallback) {
  const msg = Array.isArray(e?.messages) && e.messages.length
    ? e.messages.join('\n')
    : (e?.message || '').replace(/^[\w.]+Error:\s*/i, '').trim()
  return msg || fallback
}

async function savePolicy() {
  savingPolicy.value = true
  try {
    await call('seminary.seminary.deadlines.save_late_policy', {
      course: props.courseName,
      policy: JSON.stringify({ ...policy, late_policy_enabled: policy.late_policy_enabled ? 1 : 0 }),
    })
    toast.success(__('Late policy saved'))
    deadlines.reload()
  } catch (e) {
    toast.error(errorText(e, __('Could not save the late policy.')))
  } finally {
    savingPolicy.value = false
  }
}

const openDates = ref(null)

function toggleDates(criteria) {
  openDates.value = openDates.value === criteria.name ? null : criteria.name
  resetOverrideForm()
}

const overridesFor = (criteria) =>
  (deadlines.data?.overrides || []).filter((o) => o.course_assess === criteria.name)

const twoDatesPossible = (criteria) =>
  !!(deadlines.data?.rows || []).find((r) => r.name === criteria.name)?.two_dates_possible

const rosterOptions = computed(() => [
  { label: __('Choose a student'), value: '' },
  ...(deadlines.data?.roster || [])
    .filter((r) => r.active)
    .map((r) => ({ label: r.student_name, value: r.student })),
])

const emptyOverride = () => ({
  name: '', student: '', due_date: '', cutoff_date: '', replies_due_date: '',
  extra_minutes: '', extra_attempts: '', reason: '',
})
const ovForm = reactive(emptyOverride())
const savingOverride = ref(false)

function resetOverrideForm() {
  Object.assign(ovForm, emptyOverride())
}

function editOverride(ov) {
  Object.assign(ovForm, emptyOverride(), ov)
}

async function saveOverride(criteria) {
  savingOverride.value = true
  try {
    await call('seminary.seminary.deadlines.save_override', {
      data: JSON.stringify({ ...ovForm, course_assess: criteria.name }),
    })
    toast.success(__('Saved'))
    resetOverrideForm()
    deadlines.reload()
  } catch (e) {
    toast.error(errorText(e, __('Could not save.')))
  } finally {
    savingOverride.value = false
  }
}

async function removeOverride(ov) {
  if (!confirm(__('Remove the dates for {0}?').format(ov.student_name))) return
  try {
    await call('seminary.seminary.deadlines.delete_override', { name: ov.name })
    deadlines.reload()
  } catch (e) {
    toast.error(errorText(e, __('Could not remove.')))
  }
}

const modalcriteria = reactive({
  title: '',
  assesscriteria_scac: '',
  type: '',
  weight_scac: '',
  quiz: '',
  exam: '',
  assignment: '',
  discussion: '',
  extracredit_scac: 0,
  fudgepoints_scac: '',
  parent: props.courseName,
  parenttype: 'Course Schedule',
  parentfield: 'courseassescrit_sc'
})

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
})

const assessments = createResource({
  url: 'seminary.seminary.utils.get_assessments',
  cache: ['assessments', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
})

const breadcrumbs = computed(() => {
  let items = [{ label: __('Courses'), route: { name: 'Courses' } }]
  items.push({
    label: course?.data?.course,
    route: { name: 'CourseDetail', params: { courseName: props.courseName } },
  })
  items.push({
    label: __('Assessment'),
    route: { name: 'CourseAssessment', params: { courseName: props.courseName } }
  })
  return items
})

const pageMeta = computed(() => {
  return {
    title: course?.data?.title,
    description: __("Assessment Configuration for the course"),
  }
})

updateDocumentTitle(pageMeta)

const assessmentCriteria = reactive([]);

// A row whose chapter names a competency takes that competency, whatever is
// stored: the server refuses any other, and showing a stale stored value in a
// locked picker leaves the instructor nothing they can correct.
watch(
  () => [competencyContext.data, assessmentCriteria.length],
  () => {
    for (const criteria of assessmentCriteria) {
      const fromChapter = chapterCompetency(criteria)
      if (fromChapter) criteria.course_competency = fromChapter
    }
  }
)


const totalPoints = computed(() => {
  return assessmentCriteria.reduce((sum, criteria) => {
    return criteria.extracredit_scac === 0 ? sum + parseFloat(criteria.weight_scac || 0) : sum;
  }, 0);
});

const maxFudgePoints = computed(() => {
  return assessmentCriteria.reduce((sum, criteria) => {
    return criteria.extracredit_scac ? sum + parseFloat(criteria.fudgepoints_scac || 0) : sum;
  }, 0);
});

onMounted(() => {
  watch(() => assessments.data, (newVal) => {
    if (newVal) {
      loadAssessmentCriteria();
    }
  });
  assessments.reload();
})

function toCriteria(item) {
  return {
    name: item.name || '',
    title: item.title || '',
    assesscriteria_scac: item.assesscriteria_scac || '',
    type: item.type || '',
    weight_scac: item.weight_scac || 0,
    quiz: item.quiz || '',
    exam: item.exam || '',
    assignment: item.assignment || '',
    discussion: item.discussion || '',
    creator: item.creator || '',
    extracredit_scac: item.extracredit_scac || 0,
    fudgepoints_scac: item.fudgepoints_scac || '',
    parent: item.parent || '',
    parenttype: item.parenttype || '',
    parentfield: item.parentfield || '',
    due_date: item.due_date || '',
    cutoff_date: item.cutoff_date || '',
    replies_due_date: item.replies_due_date || '',
    late_policy_exempt: item.late_policy_exempt ? 1 : 0,
    lesson: item.lesson || '',
    // Carried so a save writes back what is stored; leaving them out made the
    // competency picker read "Select option" after every reload.
    course_competency: item.course_competency || NO_COMPETENCY,
    grading_mode_override: item.grading_mode_override || '',
  }
}

function loadAssessmentCriteria() {
  assessmentCriteria.length = 0
  const data = assessments.data
  if (!data) return
  for (const item of Array.isArray(data) ? data : [data]) {
    assessmentCriteria.push(toCriteria(item))
  }
}

function addCriteria() {
  const newCriteria = reactive({
    name: '',
    title: '',
    assesscriteria_scac: '',
    type: '',
    weight_scac: 0,
    quiz: '',
    exam: '',
    assignment: '',
    discussion: '',
    extracredit_scac: 0,
    fudgepoints_scac: '',
    parent: props.courseName,
    parenttype: 'Course Schedule',
    parentfield: 'courseassescrit_sc',
    due_date: '',
    lesson: '',
    course_competency: NO_COMPETENCY,
  });

  // Add the new criteria to the reactive array.
  assessmentCriteria.push(newCriteria);

  // Attach a watcher to this new criteria.
  watch(
    () => newCriteria.assesscriteria_scac,
    (newVal) => {
      if (newVal) {
        fetchType(newCriteria)
      }
    }
  );
}

async function removeCriteria(index) {
  const criteria = assessmentCriteria[index];

  // Confirm deletion (optional)
  if (!confirm(__('Are you sure you want to delete this record?'))) {
    return;
  }

  // Check if the criteria has a `name` (only delete from backend if it exists)
  if (criteria.name) {
    try {
      // Call the deleteAssessmentResource to delete the record from the backend
      await deleteAssessmentResource.reload([criteria.name]);
      console.log(`Record with name ${criteria.name} deleted from backend.`);
      toast.success(__('Assessment criteria deleted successfully'));
    } catch (error) {
      console.error('Error deleting assessment criteria:', error);
      toast.error(__('Failed to delete assessment criteria'));
      return; // Stop further execution if backend deletion fails
    }
  }

  // Remove the record from the frontend array
  assessmentCriteria.splice(index, 1);
  console.log(`Record at index ${index} removed from frontend.`);
}

const deleteAssessmentResource = createResource({
  url: 'seminary.seminary.api.delete_documents',
  makeParams(values) {
    return {
      doctype: 'Scheduled Course Assess Criteria',
      documents: values, // Pass the array of document names
    };
  },
  onSuccess(data) {
    console.log('Delete successful:', data);
  },
  onError(err) {
    console.error('Error deleting documents:', err);
  },
});

function openCourseAssessmentModal() {
  showCourseAssessmentModal.value = true;
}

function validateCriteria() {
  for (const criteria of assessmentCriteria) {
    if (!criteria.assesscriteria_scac) {
      return false;
    }
    if (criteria.type === 'Quiz' && !criteria.quiz) {
      return false;
    }
    if (criteria.type === 'Exam' && !criteria.exam) {
      return false;
    }
    if (criteria.type === 'Assignment' && !criteria.assignment) {
      return false;
    }
    if (criteria.type === 'Discussion' && !criteria.discussion) {
      return false;
    }
    if (!criteria.extracredit_scac && !criteria.weight_scac) {
      return false;
    }
    if (criteria.extracredit_scac && !criteria.fudgepoints_scac) {
      return false;
    }
  }
  return true;
}




async function submitCourseAssessment() {
  if (!validateCriteria()) {
    toast.error(__('Please fill in all required fields'));
    return;
  }

  try {
    const response = await fetch('/api/method/seminary.seminary.api.save_course_assessment', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': getCsrfToken(),
      },
      body: JSON.stringify({
        course: props.courseName,
        assessment_data: assessmentCriteria.map((c) => ({
          ...c,
          course_competency: c.course_competency === NO_COMPETENCY ? '' : c.course_competency,
        })),
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = payload?._server_messages
        ? JSON.parse(payload._server_messages)
            .map((m) => {
              try { return JSON.parse(m).message; } catch { return m; }
            })
            .join('\n')
        : payload?.exception || payload?.message || `HTTP ${response.status}`;
      throw new Error(message);
    }
    toast.success(__('Course updated successfully'));
    deadlines.reload();
    // New rows only get a name on save, and the dimension editors key off it.
    if (isCbe.value) competencyContext.reload();
  } catch (error) {
    console.error('Error:', error);
    toast.error(error?.message || String(error));
  }
}

async function fetchType(criteria) {
  if (criteria.assesscriteria_scac) {
    try {
      const response = await fetch(`/api/resource/Assessment Criteria/${criteria.assesscriteria_scac}`);
      const data = await response.json();
      const resolvedType = data?.data?.type || '';
      criteria.type = resolvedType;
      if (resolvedType !== 'Quiz') {
        criteria.quiz = '';
      }
      if (resolvedType !== 'Exam') {
        criteria.exam = '';
      }
      if (resolvedType !== 'Assignment') {
        criteria.assignment = '';
      }
      if (resolvedType !== 'Discussion') {
        criteria.discussion = '';
      }
    } catch (error) {
      console.error('Error fetching type:', error);
    }
  } else {
    criteria.type = '';
    criteria.quiz = '';
    criteria.exam = '';
    criteria.assignment = '';
    criteria.discussion = '';
  }
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  const month = String(date.getMonth() + 1).padStart(2, '0'); // Month (MM)
  const day = String(date.getDate()).padStart(2, '0'); // Day (DD)
  const hours = String(date.getHours()).padStart(2, '0'); // Hours (HH)
  const minutes = String(date.getMinutes()).padStart(2, '0'); // Minutes (mm)
  return `${month}/${day} ${hours}:${minutes}`; // Format: MM/DD HH:mm
}

function onAssessmentSaved() {
  // Reload the parent's resource (e.g., assessments)
  assessments.reload()
  // Now, close the Modal
  showCourseAssessmentModal.value = false;
}

function redirectToForm(type, close) {
  const routeMap = {
    quiz: '/seminary/quizzes/new',
    exam: '/seminary/exams/new',
    assignment: '/seminary/assignments/new',
    discussion: '/seminary/discussion-activities/new',
  }
  const target = routeMap?.[String(type || '').toLowerCase()]
  if (typeof close === 'function') {
    close()
  }
  if (target) {
    window.open(target, '_blank')
  }
}
</script>

<style scoped>
.input {
  display: block;
  width: 100%;
  padding: 0.5rem;
  margin-bottom: 0.5rem;
}

.btn {
  margin-right: 0.5rem;
}

.light-blue-bg {
  background-color: #E6F4FF;
}

.date-column {
  max-width: 10ch;
  /* Adjust as needed */
}

.checkmark {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #46B37E !important;
  /* Tailwind's green-500 color */
}
</style>