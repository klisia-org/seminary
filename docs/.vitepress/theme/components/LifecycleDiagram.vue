<template>
  <Suspense>
    <template #default>
      <Mermaid :id="diagramId" :graph="encodedGraph" />
    </template>
    <template #fallback>
      <div>Loading diagram…</div>
    </template>
  </Suspense>
</template>

<script setup>
import { computed } from 'vue'
import { useData } from 'vitepress'

const props = defineProps({
  type: { type: String, required: true },
})

const { lang } = useData()

const labelModules = import.meta.glob(
  '../../../en/**/diagram-labels.json',
  { eager: true, import: 'default' }
)

const enLabels =
  labelModules['../../../en/_i18n/diagram-labels.json'] || {}

function labelsForLang(code) {
  if (code === 'en') return enLabels
  return (
    labelModules[`../../../en/${code}/_i18n/diagram-labels.json`] || enLabels
  )
}

const diagrams = {
  enrollment: (t) => `
stateDiagram-v2
    direction LR
    state "${t('enrollment.draft')}" as draft
    state "${t('enrollment.awaitingPayment')}" as awaiting
    state "${t('enrollment.submitted')}" as submitted
    state "${t('enrollment.withdrawn')}" as withdrawn
    [*] --> draft
    draft --> awaiting
    awaiting --> submitted
    submitted --> withdrawn
    draft --> submitted
`,
  courseSchedule: (t) => `
stateDiagram-v2
    direction LR
    state "${t('courseSchedule.draft')}" as draft
    state "${t('courseSchedule.openForEnrollment')}" as open
    state "${t('courseSchedule.enrollmentClosed')}" as enrClosed
    state "${t('courseSchedule.grading')}" as grading
    state "${t('courseSchedule.closed')}" as final
    state "${t('courseSchedule.cancelled')}" as cancelled
    [*] --> draft
    draft --> open
    open --> enrClosed
    enrClosed --> grading
    grading --> final
    open --> cancelled
    enrClosed --> cancelled
`,
  graduationRequest: (t) => `
stateDiagram-v2
    direction LR
    state "${t('graduationRequest.draft')}" as draft
    state "${t('graduationRequest.awaitingPayment')}" as awaiting
    state "${t('graduationRequest.academicReview')}" as academic
    state "${t('graduationRequest.financialReview')}" as financial
    state "${t('graduationRequest.approved')}" as approved
    state "${t('graduationRequest.cancelled')}" as cancelled
    [*] --> draft
    draft --> awaiting
    awaiting --> academic
    academic --> financial
    financial --> approved
    draft --> academic : ${t('graduationRequest.freeSkips')}
    awaiting --> cancelled
    academic --> cancelled
    financial --> cancelled
`,
}

const graph = computed(() => {
  const dict = labelsForLang(lang.value)
  const t = (key) => dict[key] || enLabels[key] || key
  const builder = diagrams[props.type]
  if (!builder) {
    return `stateDiagram-v2\n    state "Unknown diagram: ${props.type}" as unknown`
  }
  return builder(t)
})

const encodedGraph = computed(() => encodeURIComponent(graph.value))
const diagramId = computed(() => `lifecycle-${props.type}-${lang.value}`)
</script>
