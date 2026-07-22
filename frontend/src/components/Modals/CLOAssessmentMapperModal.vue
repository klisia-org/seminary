<template>
  <Dialog v-model="show" :options="dialogOptions">
    <template #body-content>
      <div class="space-y-4 text-base max-h-[60vh] overflow-y-auto">
        <p class="text-sm text-ink-gray-6">
          {{ __('Select the Course Learning Outcomes that this assessment measures.') }}
          <span v-if="criteriaTitle" class="font-medium text-ink-gray-8">— {{ criteriaTitle }}</span>
        </p>
        <div v-if="clos.loading" class="py-4 text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
        <div v-else-if="!cloList.length" class="py-4 text-sm text-ink-gray-5">
          {{ __('No Course Learning Outcomes are defined for this course yet.') }}
        </div>
        <ul v-else class="space-y-3">
          <li v-for="clo in cloList" :key="clo.name" class="border-b border-outline-gray-1 pb-3 last:border-0">
            <div class="flex items-start gap-2">
              <input
                :id="`clo-${clo.name}`"
                v-model="selected"
                type="checkbox"
                :value="clo.name"
                class="mt-1 h-4 w-4 rounded border-outline-gray-2 text-ink-blue-2 focus:ring-outline-blue-1 focus:ring-offset-1"
              />
              <label :for="`clo-${clo.name}`" class="cursor-pointer">
                <span class="text-sm font-medium text-ink-gray-8">
                  {{ clo.outcome_code }}<template v-if="clo.shorthand"> — {{ clo.shorthand }}</template>
                </span>
                <span class="clo-statement block text-sm text-ink-gray-6" v-html="clo.statement"></span>
              </label>
            </div>

            <!-- Per-CLO question scoping, only for Quiz/Exam components that have questions. -->
            <div v-if="isQuestionBased && selected.includes(clo.name)" class="ml-6 mt-2">
              <button
                type="button"
                class="text-xs font-medium text-ink-blue-2 hover:underline"
                @click="toggleExpand(clo.name)"
              >
                {{ expanded[clo.name] ? '▾' : '▸' }} {{ questionSummary(clo.name) }}
              </button>
              <div v-if="expanded[clo.name]" class="mt-2 rounded bg-surface-gray-1 p-3">
                <div v-if="questions.loading" class="text-xs text-ink-gray-5">{{ __('Loading questions…') }}</div>
                <template v-else-if="questionList.length">
                  <div class="mb-2 flex gap-3 text-xs">
                    <button type="button" class="text-ink-blue-2 hover:underline" @click="selectAll(clo.name)">
                      {{ __('Select all') }}
                    </button>
                    <button type="button" class="text-ink-gray-6 hover:underline" @click="clearQuestions(clo.name)">
                      {{ __('Whole assessment') }}
                    </button>
                  </div>
                  <ul class="space-y-1.5">
                    <li v-for="q in questionList" :key="q.id" class="flex items-start gap-2">
                      <input
                        :id="`q-${clo.name}-${q.id}`"
                        v-model="questionsByClo[clo.name]"
                        type="checkbox"
                        :value="q.id"
                        class="mt-0.5 h-3.5 w-3.5 rounded border-outline-gray-2 text-ink-blue-2"
                      />
                      <label :for="`q-${clo.name}-${q.id}`" class="cursor-pointer text-xs text-ink-gray-7">
                        {{ q.label }}
                        <span v-if="q.points" class="text-ink-gray-5">({{ q.points }} {{ __('pts') }})</span>
                      </label>
                    </li>
                  </ul>
                </template>
                <div v-else class="text-xs text-ink-gray-5">{{ __('This assessment has no listed questions.') }}</div>
              </div>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { createResource, Dialog, toast } from 'frappe-ui'
import { computed, reactive, ref, watch } from 'vue'

const show = defineModel()

const props = defineProps({
  // The Course the CLOs belong to.
  course: { type: String, default: '' },
  // The Course Schedule (offering) — the assessment component's parent.
  courseSchedule: { type: String, default: '' },
  // The Scheduled Course Assess Criteria row name being mapped.
  scheduledAssessCriteria: { type: String, default: '' },
  // The component's assessment type (Quiz/Exam/Assignment/Discussion/Offline).
  assessmentType: { type: String, default: '' },
  criteriaTitle: { type: String, default: '' },
})

const emit = defineEmits(['saved'])

const selected = ref([])
const questionsByClo = reactive({})
const expanded = reactive({})

const isQuestionBased = computed(() => ['Quiz', 'Exam'].includes(props.assessmentType))

const clos = createResource({
  url: 'aretenic.outcome_api.get_course_clos',
  makeParams: () => ({ course: props.course }),
})

const questions = createResource({
  url: 'aretenic.outcome_api.get_component_questions',
  makeParams: () => ({ scheduled_assess_criteria: props.scheduledAssessCriteria }),
})

const existingMaps = createResource({
  url: 'aretenic.outcome_api.get_clo_maps_for_component',
  makeParams: () => ({ scheduled_assess_criteria: props.scheduledAssessCriteria }),
})

const saver = createResource({
  url: 'aretenic.outcome_api.save_clo_maps',
  makeParams: () => ({
    course_schedule: props.courseSchedule,
    scheduled_assess_criteria: props.scheduledAssessCriteria,
    mappings: JSON.stringify(selected.value.map((clo) => ({ clo, questions: questionsByClo[clo] || [] }))),
  }),
  onSuccess() {
    toast.success(__('Outcome mapping saved'))
    emit('saved')
    show.value = false
  },
  onError(err) {
    toast.error(err?.messages?.[0] || err?.message || __('Failed to save mapping'))
  },
})

const cloList = computed(() => clos.data || [])
const questionList = computed(() => questions.data || [])

function ensureBucket(clo) {
  if (!Array.isArray(questionsByClo[clo])) questionsByClo[clo] = []
}
function toggleExpand(clo) {
  ensureBucket(clo)
  expanded[clo] = !expanded[clo]
}
function selectAll(clo) {
  questionsByClo[clo] = questionList.value.map((q) => q.id)
}
function clearQuestions(clo) {
  questionsByClo[clo] = []
}
function questionSummary(clo) {
  const n = (questionsByClo[clo] || []).length
  return n ? __('{0} of {1} questions', [n, questionList.value.length]) : __('Whole assessment')
}

// Keep a question bucket for every checked CLO so v-model bindings stay valid.
watch(
  selected,
  (val) => val.forEach(ensureBucket),
  { deep: true }
)

// Load CLOs, questions and the current mapping each time the dialog opens.
watch(show, (open) => {
  if (!open || !props.scheduledAssessCriteria) return
  selected.value = []
  Object.keys(questionsByClo).forEach((k) => delete questionsByClo[k])
  Object.keys(expanded).forEach((k) => delete expanded[k])
  clos.submit()
  if (isQuestionBased.value) questions.submit()
  existingMaps.submit().then(() => {
    const maps = existingMaps.data || []
    selected.value = maps.map((m) => m.clo)
    maps.forEach((m) => {
      let qs = []
      try {
        qs = m.mapped_questions ? JSON.parse(m.mapped_questions) : []
      } catch (e) {
        qs = []
      }
      questionsByClo[m.clo] = qs
      if (qs.length) expanded[m.clo] = true
    })
  })
})

const dialogOptions = computed(() => ({
  title: __('Map to Course Learning Outcomes'),
  size: 'lg',
  actions: [
    {
      label: __('Save Mapping'),
      variant: 'solid',
      loading: saver.loading,
      onClick: () => saver.submit(),
    },
  ],
}))
</script>

<style scoped>
.clo-statement :deep(p) {
  margin: 0;
}
</style>
