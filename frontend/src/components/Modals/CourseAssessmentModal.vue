<template>
  <Dialog
    v-model="show"
    :options="{
      title: 'Add Course Assessment',
      size: 'lg',
      actions: [
        {
          label: 'Create',
          variant: 'solid',
          onClick: (close) => insertCriteria(close),
        },
        {
          label: 'Cancel',
          variant: 'text',
          onClick: (close) => close(),
        },
      ],
    }"
  >
    <template #body-content>
      <div class="space-y-4 text-base">
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
          @update:modelValue="(val) => { console.log('update:modelValue triggered:', val); fetchType(criteria); }"
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
import {
  Button,
  createResource,
  Dialog,
  FormControl,
  toast
} from 'frappe-ui'
import { reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSettings } from '@/stores/settings'
import { createDialog } from '@/utils/dialogs'
import Link from '@/components/Controls/Link.vue'
import { examStore } from '@/stores/exam'

const $dialog = createDialog
const route = useRoute()
const router = useRouter()
const show = defineModel()
const CourseAssessment = defineModel('CourseAssessment')
const settingsStore = useSettings()
const emit = defineEmits(['assessment-saved'])

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})

const courseassess = reactive({
  title: '',
  assesscriteria_scac: '',
  type: '',
  weight_scac: '',
  quiz: '',
  exam: '',
  assignment: '',
  extracredit_scac: '',
  fudgepoints_scac: '',
  parent: props.courseName,
  parenttype: 'Course Schedule',
  parentfield: 'courseassescrit_sc'
})

const criteria = reactive({
  title: '',
  assesscriteria_scac: '',
  type: '',
  weight_scac: '',
  quiz: '',
  exam: '',
  assignment: '',
  extracredit_scac: '',
  fudgepoints_scac: '',
  parent: props.courseName,
  parenttype: 'Course Schedule',
  parentfield: 'courseassescrit_sc'
})

async function fetchType(criteria) {
  if (criteria.assesscriteria_scac) {
    try {
      const response = await fetch(`/api/resource/Assessment Criteria/${criteria.assesscriteria_scac}`);
      const data = await response.json();
      criteria.type = data.data.type;
    } catch (error) {
      console.error('Error fetching type:', error);
    }
  }
}
const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
})

function redirectToExam(value, close) {
  // Set the prefill data in store
  examStore.setPrefillData({
    title: criteria.title,
    course: course?.data?.course,
  })
  // Navigate to the exam creation page
  
  router.push({
    name: 'ExamForm',
    params: { examID: 'new' },
   
  });
  close();
  console.log('Navigating to Exam creation page with prefill data:', examStore.prefillData);
}


function redirectToQuiz(value, close) {
  // Set the prefill data in store
  examStore.setPrefillData({
    title: criteria.title,
    course: course?.data?.course,
  })
  // Navigate to the quiz creation page

  router.push({
    name: 'QuizForm',
    params: { quizID: 'new' },

  });
  close();
  console.log('Navigating to Quiz creation page with prefill data:', examStore.prefillData);
}

const redirectToAssignment = (value, close) => {
  // Set the prefill data in store
  examStore.setPrefillData({
    title: criteria.title,
    course: course?.data?.course,
  })
  // Navigate to the assignment creation page

  router.push({
    name: 'AssignmentForm',
    params: { assignmentID: 'new' },

  });
  close();
  console.log('Navigating to Assignment creation page with prefill data:', examStore.prefillData);
}

const insertCriteria = () => {
  console.log('Inserting Criteria:', criteria)
  if (criteria) {
    fetch('/api/method/seminary.seminary.api.insert_cs_assessment', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ criteria }) // Serialize criteria to JSON string
    })
    .then(response => response.json())
    .then(data => {
      toast.success(__('Course Assessment added successfully'))
      emit('assessment-saved');
      close();
    })
    .catch(error => {
      console.error('Error:', error)
      toast.error(err.messages?.[0] || err)
    })
  }
}
</script>
