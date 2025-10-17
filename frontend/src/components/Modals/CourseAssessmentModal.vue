<template>
  <Dialog
    v-model="show"
    :options="dialogOptions"
    :disableOutsideClickToClose="true"
  >
    <template #body-content>
      <div class="course-assessment-dialog space-y-4 text-base max-h-[70vh] overflow-y-auto">
        <FormControl
          v-model="criteria.title"
          :label="__('Title')"
          class="mb-4"
          :required="true"
        />
        <Link
          v-model="criteria.assesscriteria_scac"
          :label="__('Assessment Criteria')"
          class="mb-4"
          doctype="Assessment Criteria"
          :required="true"
        />
        <p> {{ criteria.type }}</p>
        <Link
          v-if="criteria.type === 'Quiz'"
          v-model="criteria.quiz"
          doctype="Quiz"
          :label="__('Select a Quiz')"
          :filters="{ course: course?.data?.course }"
          :onCreate="(value, close) => redirectToQuiz(value, close)"
        />
        <Link
          v-else-if="criteria.type === 'Exam'"
          v-model="criteria.exam"
          doctype="Exam Activity"
          :label="__('Select an Exam')"
          :filters="{ course: course?.data?.course }"
          :onCreate="(value, close) => redirectToExam(value, close)"
        />
        <Link
          v-else-if="criteria.type === 'Assignment'"
          v-model="criteria.assignment"
          doctype="Assignment Activity"
          :label="__('Select an Assignment')"
          :filters="{ course: course?.data?.course }"
          :onCreate="(value, close) => redirectToAssignment(value, close)"
        />
        <Link
          v-else-if="criteria.type === 'Discussion'"
          v-model="criteria.discussion"
          doctype="Discussion Activity"
          :label="__('Select a Discussion Activity')"
          :filters="{ course: course?.data?.course }"
          :onCreate="(value, close) => redirectToDiscussion(value, close)"
        />
        <template v-else>
          <p>Offline</p>
        </template>
        <FormControl
          v-model="criteria.weight_scac"
          :label="__('Weight')"
          class="mb-4"
          :required="true"
          maxlength="10"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { createResource, Dialog, FormControl, toast } from 'frappe-ui'
import { computed, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import Link from '@/components/Controls/Link.vue'
import { examStore } from '@/stores/exam'

const show = defineModel()
const modalcriteria = defineModel('modalcriteria')
const emit = defineEmits(['assessment-saved'])

const router = useRouter()

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})

const defaultCriteriaState = () => ({
  title: '',
  assesscriteria_scac: '',
  type: '',
  weight_scac: '',
  quiz: '',
  exam: '',
  assignment: '',
  discussion: '',
  extracredit_scac: '',
  fudgepoints_scac: '',
  parent: props.courseName,
  parenttype: 'Course Schedule',
  parentfield: 'courseassescrit_sc',
})

const criteria = reactive(defaultCriteriaState())

const resetCriteria = () => {
  Object.assign(criteria, defaultCriteriaState())
}

const syncCriteriaToParent = () => {
  if (modalcriteria?.value) {
    Object.assign(modalcriteria.value, criteria)
  }
}

watch(
  () => criteria,
  () => {
    syncCriteriaToParent()
  },
  { deep: true }
)

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
})

const fetchType = async () => {
  if (!criteria.assesscriteria_scac) {
    criteria.type = ''
    return
  }
  try {
    const response = await fetch(
      `/api/resource/Assessment Criteria/${criteria.assesscriteria_scac}`
    )
    const data = await response.json()
    const resolvedType = data?.data?.type || ''
    criteria.type = resolvedType
    if (resolvedType !== 'Quiz') {
      criteria.quiz = ''
    }
    if (resolvedType !== 'Exam') {
      criteria.exam = ''
    }
    if (resolvedType !== 'Assignment') {
      criteria.assignment = ''
    }
  } catch (error) {
    console.error('Error fetching type:', error)
  }
}

watch(
  () => criteria.assesscriteria_scac,
  (value) => {
    if (!value) {
      criteria.type = ''
      criteria.quiz = ''
      criteria.exam = ''
      criteria.assignment = ''
      criteria.discussion = ''
      return
    }
    fetchType()
  }
)

const redirectToExam = (value, close) => {
  examStore.setPrefillData({
    title: criteria.title,
    course: course?.data?.course,
  })
  router.push({
    name: 'ExamForm',
    params: { examID: 'new' },
  })
  close()
}

const redirectToQuiz = (value, close) => {
  examStore.setPrefillData({
    title: criteria.title,
    course: course?.data?.course,
  })
  router.push({
    name: 'QuizForm',
    params: { quizID: 'new' },
  })
  close()
}

const redirectToAssignment = (value, close) => {
  examStore.setPrefillData({
    title: criteria.title,
    course: course?.data?.course,
  })
  router.push({
    name: 'AssignmentForm',
    params: { assignmentID: 'new' },
  })
  close()
}

const redirectToDiscussion = (value, close) => {
  examStore.setPrefillData({
    title: criteria.title,
    course: course?.data?.course,
  })
  router.push({
    name: 'DiscussionActivityForm',
    params: { discussionID: 'new' },
  })
  close()
}

const insertCriteria = (close) => {
  fetch('/api/method/seminary.seminary.api.insert_cs_assessment', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ criteria }),
  })
    .then((response) => response.json())
    .then(() => {
      toast.success(__('Course Assessment added successfully'))
      emit('assessment-saved')
      show.value = false
      resetCriteria()
      close()
    })
    .catch((error) => {
      console.error('Error:', error)
      toast.error(error.messages?.[0] || error)
    })
}

const handleCancel = (close) => {
  show.value = false
  resetCriteria()
  syncCriteriaToParent()
  close?.()
}

watch(show, (value) => {
  if (value) {
    resetCriteria()
    syncCriteriaToParent()
  } else {
    resetCriteria()
    syncCriteriaToParent()
  }
})

const dialogOptions = computed(() => ({
  title: __('Add Course Assessment'),
  size: 'lg',
  actions: [
    {
      label: __('Create'),
      variant: 'solid',
      onClick: (close) => insertCriteria(close),
    },
    {
      label: __('Cancel'),
      variant: 'text',
      onClick: (close) => handleCancel(close),
    },
  ],
}))
</script>

<style>
.course-assessment-dialog input[type='number']::-webkit-inner-spin-button,
.course-assessment-dialog input[type='number']::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.course-assessment-dialog input[type='number'] {
  appearance: textfield;
  -moz-appearance: textfield;
}
</style>
